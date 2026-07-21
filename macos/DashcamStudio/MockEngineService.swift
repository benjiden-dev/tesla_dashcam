//  MockEngineService.swift
//  In-memory engine stand-in so the UI runs (and previews) before the real
//  sidecar exists. Emits scripted progress and canned sample events.

import Foundation

@MainActor
final class MockEngineService: EngineService {
    private var cancelled = Set<JobID>()

    func scanEvents(in folder: URL) async throws -> [DashcamEvent] {
        try? await Task.sleep(for: .milliseconds(250))
        return Self.sampleEvents(root: folder)
    }

    func renderPreview(
        event: DashcamEvent,
        minute: String,
        settings: RenderSettings
    ) async throws -> URL {
        try? await Task.sleep(for: .milliseconds(400))
        throw EngineError.previewUnavailable   // UI shows a placeholder in mock mode
    }

    func render(_ request: RenderRequest) -> (id: JobID, progress: AsyncStream<RenderProgress>) {
        let id = JobID()
        let totalEvents = max(request.selections.count, 1)
        let stream = AsyncStream<RenderProgress> { continuation in
            let task = Task { @MainActor in
                var p = RenderProgress(id: id, phase: .staging,
                                       message: "Preparing clips", totalEvents: totalEvents)
                continuation.yield(p)
                let steps = 24
                for step in 1...steps {
                    if cancelled.contains(id) {
                        p.phase = .cancelled; p.message = "Cancelled"
                        continuation.yield(p); continuation.finish(); return
                    }
                    try? await Task.sleep(for: .milliseconds(120))
                    p.phase = .encoding
                    p.currentEvent = min(totalEvents, 1 + step / max(steps / totalEvents, 1))
                    p.clipsInEvent = 3
                    p.clipInEvent = 1 + (step % 3)
                    p.fractionCompleted = Double(step) / Double(steps) * 0.92
                    p.etaSeconds = (steps - step) / 4
                    p.message = "Event \(p.currentEvent)/\(totalEvents) — clip \(p.clipInEvent)/3"
                    continuation.yield(p)
                }
                p.phase = .done
                p.fractionCompleted = 1
                p.message = "Completed"
                p.etaSeconds = nil
                p.outputs = [request.selections.first.map {
                    URL(fileURLWithPath: "/tmp/\($0.eventID).mp4")
                } ?? URL(fileURLWithPath: "/tmp/output.mp4")]
                continuation.yield(p)
                continuation.finish()
            }
            continuation.onTermination = { _ in task.cancel() }
        }
        return (id, stream)
    }

    func cancel(_ id: JobID) { cancelled.insert(id) }

    // MARK: - Sample data
    static func sampleEvents(root: URL) -> [DashcamEvent] {
        func minutes(_ base: String, _ count: Int, cams: [CameraID]) -> [Minute] {
            (0..<count).map { i in
                let mm = String(format: "%02d", 28 + i)
                return Minute(key: "\(base)_14-\(mm)-00",
                              time: "14:\(mm):00",
                              cameras: cams,
                              sizeBytes: Int64(120_000_000))
            }
        }
        let allCams = CameraID.allCases
        return [
            DashcamEvent(
                id: "SentryClips/2026-07-18_09-15-22",
                url: root.appending(path: "SentryClips/2026-07-18_09-15-22"),
                name: "2026-07-18_09-15-22", group: .sentry,
                minutes: minutes("2026-07-18", 2, cams: allCams),
                metadata: EventMetadata(timestamp: .now, city: "Denver", street: "16th St",
                                        reason: "sentry_aware_object_detection",
                                        latitude: 39.7508, longitude: -104.9964),
                hasThumbnail: false),
            DashcamEvent(
                id: "SavedClips/2026-07-10_14-31-04",
                url: root.appending(path: "SavedClips/2026-07-10_14-31-04"),
                name: "2026-07-10_14-31-04", group: .saved,
                minutes: minutes("2026-07-10", 10, cams: allCams),
                metadata: EventMetadata(timestamp: .now, city: "Denver", street: "1400 Larimer St",
                                        reason: "user_interaction_honk",
                                        latitude: 39.7473, longitude: -104.9992),
                hasThumbnail: true),
            DashcamEvent(
                id: "RecentClips/2026-07-12_08-00-00",
                url: root.appending(path: "RecentClips/2026-07-12_08-00-00"),
                name: "2026-07-12_08-00-00", group: .recent,
                minutes: minutes("2026-07-12", 2, cams: [.front, .back]),
                metadata: nil, hasThumbnail: false),
        ]
    }
}
