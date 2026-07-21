//  SidecarEngineService.swift  (WP-2)
//  Real EngineService: native scan (WP-1) + drive the bundled engine binary
//  as a subprocess, parsing stdout into structured progress. Rendering needs
//  the engine sidecar (bundled in WP-6); scanning works today.

import Foundation

@MainActor
final class SidecarEngineService: EngineService {
    private let scanner = TeslaCamScanner()
    private let staging = Staging()
    private let cacheRoot: URL
    private let outputRoot: URL

    /// eventID → source folder, populated on scan so render() can resolve.
    private var index: [String: URL] = [:]
    private var processes: [JobID: Process] = [:]

    init(cacheRoot: URL, outputRoot: URL) {
        self.cacheRoot = cacheRoot
        self.outputRoot = outputRoot
    }

    /// Locate the bundled engine helper (WP-6 places it in Resources); an
    /// ENGINE_CMD env var overrides for development.
    private var engineCommand: [String]? {
        if let override = ProcessInfo.processInfo.environment["ENGINE_CMD"], !override.isEmpty {
            return override.split(separator: " ").map(String.init)
        }
        if let helper = Bundle.main.url(forResource: "dashcam-engine", withExtension: nil),
           FileManager.default.isExecutableFile(atPath: helper.path) {
            return [helper.path]
        }
        return nil
    }

    // MARK: - Scan (WP-1, works now)
    func scanEvents(in folder: URL) async throws -> [DashcamEvent] {
        let scanner = self.scanner
        let events = await Task.detached { scanner.scan(root: folder) }.value
        index = Dictionary(events.map { ($0.id, $0.url) }, uniquingKeysWith: { first, _ in first })
        return events
    }

    // MARK: - Preview (stub until WP-3 wires MKMapSnapshotter + frame extract)
    func renderPreview(event: DashcamEvent, minute: String, settings: RenderSettings) async throws -> URL {
        throw EngineError.previewUnavailable
    }

    // MARK: - Render
    func render(_ request: RenderRequest) -> (id: JobID, progress: AsyncStream<RenderProgress>) {
        let id = JobID()
        let stream = AsyncStream<RenderProgress> { continuation in
            let task = Task { await self.run(id: id, request: request) { continuation.yield($0) } }
            continuation.onTermination = { _ in task.cancel() }
        }
        return (id, stream)
    }

    func cancel(_ id: JobID) {
        processes[id]?.terminate()
    }

    private func run(id: JobID,
                     request: RenderRequest,
                     yield: @escaping (RenderProgress) -> Void) async {
        let parser = EngineProgressParser()
        yield(parser.snapshot(id: id))

        guard let engineCmd = engineCommand else {
            var p = parser.snapshot(id: id)
            p.phase = .failed
            p.errorMessage = "The render engine isn't bundled yet (WP-6). Native scanning works; rendering will once the sidecar ships."
            yield(p); return
        }

        // Resolve selections → source folders.
        let selections: [(URL, Set<String>?)] = request.selections.compactMap {
            guard let url = index[$0.eventID] else { return nil }
            return (url, $0.minutes.map(Set.init))
        }
        guard !selections.isEmpty else {
            var p = parser.snapshot(id: id); p.phase = .failed
            p.errorMessage = "No matching events for this render."; yield(p); return
        }

        let tempDir = cacheRoot.appending(path: "tmp")
        try? FileManager.default.createDirectory(at: outputRoot, withIntermediateDirectories: true)
        try? FileManager.default.createDirectory(at: tempDir, withIntermediateDirectories: true)

        var stagingRoot: URL?
        do {
            let staged = try staging.stage(jobID: id, cacheRoot: cacheRoot,
                                           selections: selections.map { (source: $0.0, minutes: $0.1) })
            stagingRoot = staged.root

            var settings = request.settings
            if settings.map.enabled { settings.merge = false }
            let args = EngineArguments.build(source: staged.root, output: outputRoot,
                                             settings: settings, tempDir: tempDir,
                                             gpuAvailable: true, isDarwin: true)

            let proc = Process()
            proc.executableURL = URL(fileURLWithPath: engineCmd[0])
            proc.arguments = Array(engineCmd.dropFirst()) + args
            let pipe = Pipe()
            proc.standardOutput = pipe
            proc.standardError = pipe
            processes[id] = proc

            try proc.run()

            // Stream stdout line-by-line off the main actor.
            let handle = pipe.fileHandleForReading
            var buffer = Data()
            for await chunk in handle.bytesChunks() {
                buffer.append(chunk)
                while let nl = buffer.firstIndex(of: 0x0A) {
                    let lineData = buffer[..<nl]
                    buffer.removeSubrange(...nl)
                    let line = String(decoding: lineData, as: UTF8.self)
                    if parser.feed(line) { yield(parser.snapshot(id: id)) }
                }
            }
            proc.waitUntilExit()
            processes[id] = nil

            var final = parser.snapshot(id: id)
            if Task.isCancelled {
                final.phase = .cancelled; final.message = "Cancelled"
            } else if proc.terminationStatus != 0 && parser.phase != .done {
                final.phase = .failed
                final.errorMessage = "Engine exited with code \(proc.terminationStatus)."
            } else {
                final.phase = .done; final.message = "Completed"; final.fractionCompleted = 1
            }
            yield(final)
        } catch {
            var p = parser.snapshot(id: id); p.phase = .failed
            p.errorMessage = error.localizedDescription; yield(p)
        }
        staging.cleanup(stagingRoot)
    }
}

// MARK: - Async byte chunks from a FileHandle
private extension FileHandle {
    func bytesChunks() -> AsyncStream<Data> {
        AsyncStream { continuation in
            readabilityHandler = { handle in
                let data = handle.availableData
                if data.isEmpty {
                    handle.readabilityHandler = nil
                    continuation.finish()
                } else {
                    continuation.yield(data)
                }
            }
        }
    }
}
