//  ProgressParser.swift  (WP-2)
//  Parse the engine's stdout into structured progress — port of the tested
//  webui EngineProgress parser. Pure Foundation, unit-testable.

import Foundation

final class EngineProgressParser {
    private(set) var totalEvents = 0
    private(set) var totalClips = 0
    private(set) var eventsDone = 0
    private(set) var currentEvent = 0
    private(set) var clipInEvent = 0
    private(set) var clipsInEvent = 0
    private var clipsBeforeEvent = 0
    private(set) var phase: RenderPhase = .staging
    private(set) var message = "Preparing clips"
    private(set) var outputs: [URL] = []
    private(set) var warnings: [String] = []
    private(set) var errors: [String] = []
    private var eventOutputs: [String: URL] = [:]   // staged folder name → movie
    private let started = Date()

    private var clipsDone: Int { clipsBeforeEvent + max(clipInEvent - 1, 0) }

    private func rx(_ p: String) -> NSRegularExpression { try! NSRegularExpression(pattern: p) }
    private lazy var reTotals = rx("^There are (\\d+) event folder\\(s\\) with (\\d+) clips")
    private lazy var reEventHeader = rx("^\\t*Processing (\\d+) clips in folder (.+?) \\((\\d+)/(\\d+)\\)")
    private lazy var reClip = rx("^\\t*Processing clip (\\d+)/(\\d+) from")
    private lazy var reCreating = rx("^(\\t*)\\s*Creating movie (.+?), please be patient")
    private lazy var reReady = rx("^\\t*Movie (.+?) for folder (.+?) with duration")
    private lazy var reDone = rx("Processing of movies has completed|All folders have been processed")
    private lazy var reError = rx("Error trying to create (movie|clip|title)|No valid clips to merge|No clips found")

    /// Feed one stdout line. Returns true if progress changed meaningfully.
    @discardableResult
    func feed(_ line: String) -> Bool {
        if line.trimmingCharacters(in: .whitespaces).isEmpty { return false }
        let full = NSRange(line.startIndex..., in: line)

        if let m = reTotals.firstMatch(in: line, range: full) {
            phase = .encoding
            totalEvents = intAt(line, m, 1); totalClips = intAt(line, m, 2)
            message = "\(totalEvents) event(s), \(totalClips) clip(s)"
            return true
        }
        if let m = reEventHeader.firstMatch(in: line, range: full) {
            phase = .encoding
            currentEvent = intAt(line, m, 3); clipsInEvent = intAt(line, m, 1); clipInEvent = 0
            message = "Event \(currentEvent)/\(max(totalEvents, 1))"
            return true
        }
        if let m = reClip.firstMatch(in: line, range: full) {
            phase = .encoding
            clipInEvent = intAt(line, m, 1); clipsInEvent = intAt(line, m, 2)
            if currentEvent == 0 { currentEvent = 1 }
            message = "Event \(currentEvent)/\(max(totalEvents, 1)) — clip \(clipInEvent)/\(clipsInEvent)"
            return true
        }
        if let m = reCreating.firstMatch(in: line, range: full) {
            let tabs = strAt(line, m, 1)
            let movie = strAt(line, m, 2)
            if tabs.filter({ $0 == "\t" }).count >= 2 {
                phase = .assembling; message = "Assembling \(URL(fileURLWithPath: movie).lastPathComponent)"
            } else {
                phase = .merging; message = "Merging \(URL(fileURLWithPath: movie).lastPathComponent)"
            }
            return true
        }
        if let m = reReady.firstMatch(in: line, range: full) {
            let movie = strAt(line, m, 1); let folder = strAt(line, m, 2)
            let url = URL(fileURLWithPath: movie)
            eventOutputs[URL(fileURLWithPath: folder).lastPathComponent] = url
            if !outputs.contains(url) { outputs.append(url) }
            eventsDone += 1; clipsBeforeEvent += clipsInEvent; clipInEvent = 0; clipsInEvent = 0
            message = "Event movie ready (\(eventsDone)/\(max(totalEvents, 1)))"
            return true
        }
        if reDone.firstMatch(in: line, range: full) != nil {
            phase = .done; message = "Completed"; return true
        }
        if reError.firstMatch(in: line, range: full) != nil {
            errors.append(line.trimmingCharacters(in: .whitespaces)); return true
        }
        return false
    }

    func snapshot(id: JobID) -> RenderProgress {
        var p = RenderProgress(id: id, phase: phase, message: message)
        p.totalEvents = totalEvents
        p.currentEvent = currentEvent
        p.clipInEvent = clipInEvent
        p.clipsInEvent = clipsInEvent
        p.outputs = outputs
        p.warnings = warnings
        p.errors = errors
        p.fractionCompleted = fraction
        p.etaSeconds = eta
        return p
    }

    var fraction: Double {
        switch phase {
        case .done: return 1
        case .mapOverlay: return 0.96
        case .cleanup: return 0.98
        default: break
        }
        guard totalClips > 0 else { return 0 }
        var f = min(Double(clipsDone) / Double(totalClips), 1) * 0.92
        if phase == .merging { f = max(f, 0.94) }
        return f
    }
    private var eta: Int? {
        guard clipsDone >= 1, totalClips > 0, phase != .done else { return nil }
        let elapsed = Date().timeIntervalSince(started)
        let remaining = max(totalClips - clipsDone, 0)
        return Int(elapsed / Double(clipsDone) * Double(remaining))
    }
    func movie(forStagedFolder name: String) -> URL? { eventOutputs[name] }

    private func intAt(_ s: String, _ m: NSTextCheckingResult, _ i: Int) -> Int {
        Int(strAt(s, m, i)) ?? 0
    }
    private func strAt(_ s: String, _ m: NSTextCheckingResult, _ i: Int) -> String {
        guard m.range(at: i).location != NSNotFound else { return "" }
        return (s as NSString).substring(with: m.range(at: i))
    }
}
