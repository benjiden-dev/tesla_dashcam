//  Staging.swift  (WP-2)
//  Stage selected minutes as a temp folder of symlinks so the engine only
//  sees the chosen clips — non-contiguous selection works with zero engine
//  changes. Port of the tested webui staging.py. Reads in place (symlinks).

import Foundation

struct Staging: Sendable {
    let scanner = TeslaCamScanner()
    private var fm: FileManager { .default }

    struct StagedEvent {
        let stagedName: String
        let stagedDir: URL
        let sourceDir: URL
    }

    /// Create a fresh staging root with one symlinked folder per event.
    /// `selections` maps a source event folder → chosen minute keys (nil = all).
    func stage(jobID: JobID,
               cacheRoot: URL,
               selections: [(source: URL, minutes: Set<String>?)]) throws -> (root: URL, events: [StagedEvent]) {
        let root = cacheRoot.appending(path: "staging/\(jobID.uuidString)")
        try? fm.removeItem(at: root)
        try fm.createDirectory(at: root, withIntermediateDirectories: true)

        var used = Set<String>()
        var staged: [StagedEvent] = []
        for sel in selections {
            var name = sel.source.lastPathComponent
            if used.contains(name) {
                var i = 2
                while used.contains("\(name)_\(i)") { i += 1 }
                name = "\(name)_\(i)"
            }
            used.insert(name)

            let dir = root.appending(path: name)
            try fm.createDirectory(at: dir, withIntermediateDirectories: true)

            let files = scanner.clipURLs(in: sel.source, minutes: sel.minutes)
            guard !files.isEmpty else { throw EngineError.noClips }
            for f in files {
                try fm.createSymbolicLink(at: dir.appending(path: f.lastPathComponent),
                                          withDestinationURL: f.resolvingSymlinksInPath())
            }
            let eventJSON = sel.source.appending(path: "event.json")
            if fm.fileExists(atPath: eventJSON.path) {
                try? fm.copyItem(at: eventJSON, to: dir.appending(path: "event.json"))
            }
            staged.append(StagedEvent(stagedName: name, stagedDir: dir, sourceDir: sel.source))
        }
        return (root, staged)
    }

    func cleanup(_ root: URL?) {
        guard let root else { return }
        try? fm.removeItem(at: root)
    }

    /// Total size of real files under a folder (symlink targets excluded).
    func directorySize(_ url: URL) -> Int64 {
        guard let en = fm.enumerator(at: url, includingPropertiesForKeys: [.isSymbolicLinkKey, .fileSizeKey]) else { return 0 }
        var total: Int64 = 0
        for case let f as URL in en {
            let v = try? f.resourceValues(forKeys: [.isSymbolicLinkKey, .fileSizeKey])
            if v?.isSymbolicLink == true { continue }
            total += Int64(v?.fileSize ?? 0)
        }
        return total
    }
}
