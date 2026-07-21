//  Scanner.swift  (WP-1)
//  Native TeslaCam folder scanner — a direct port of the tested webui
//  scanner.py. Pure Foundation, no UI, so it is unit-testable and safe to run
//  off the main actor. Reads in place; never mutates the source.

import Foundation

struct TeslaCamScanner: Sendable {
    static let cameraRaw = ["front", "back", "left_repeater",
                            "right_repeater", "left_pillar", "right_pillar"]

    // ^2026-07-10_14-31-00-front.mp4$
    private static let clipRegex = try! NSRegularExpression(
        pattern: "^(\\d{4}-\\d{2}-\\d{2}_\\d{2}-\\d{2}-\\d{2})-(" +
                 cameraRaw.joined(separator: "|") + ")\\.mp4$")

    private static let knownGroups: Set<String> = ["SavedClips", "SentryClips", "RecentClips"]
    private static let maxDepth = 4

    private var fm: FileManager { .default }

    // MARK: - Public API
    func scan(root: URL) -> [DashcamEvent] {
        guard let en = fm.enumerator(at: root,
                                     includingPropertiesForKeys: [.isDirectoryKey],
                                     options: [.skipsHiddenFiles]) else { return [] }
        var eventsByDir: [URL: [String]] = [:]     // dir → clip filenames
        // Group all clip files by their containing directory.
        for case let url as URL in en {
            if en.level > Self.maxDepth { en.skipDescendants() }
            let name = url.lastPathComponent
            guard Self.clipRegex.firstMatch(in: name, range: nsRange(name)) != nil else { continue }
            let dir = url.deletingLastPathComponent()
            eventsByDir[dir, default: []].append(name)
        }

        var events = eventsByDir.compactMap { dir, clips in
            buildEvent(dir: dir, root: root, clipNames: clips)
        }
        // Newest first, by latest minute key.
        events.sort { ($0.minutes.last?.key ?? $0.name) > ($1.minutes.last?.key ?? $1.name) }
        return events
    }

    /// Clip file URLs in an event folder filtered by minute keys (nil = all).
    func clipURLs(in folder: URL, minutes: Set<String>?) -> [URL] {
        guard let items = try? fm.contentsOfDirectory(at: folder,
                                                       includingPropertiesForKeys: nil) else { return [] }
        return items.filter { url in
            let name = url.lastPathComponent
            guard let m = Self.clipRegex.firstMatch(in: name, range: nsRange(name)) else { return false }
            guard let minutes else { return true }
            let stamp = (name as NSString).substring(with: m.range(at: 1))
            return minutes.contains(stamp)
        }.sorted { $0.lastPathComponent < $1.lastPathComponent }
    }

    // MARK: - Building one event
    private func buildEvent(dir: URL, root: URL, clipNames: [String]) -> DashcamEvent? {
        var minutesByStamp: [String: (cameras: [CameraID], size: Int64)] = [:]
        for name in clipNames.sorted() {
            guard let m = Self.clipRegex.firstMatch(in: name, range: nsRange(name)) else { continue }
            let stamp = (name as NSString).substring(with: m.range(at: 1))
            let camRaw = (name as NSString).substring(with: m.range(at: 2))
            guard let cam = CameraID(rawValue: camRaw) else { continue }
            let size = fileSize(dir.appending(path: name))
            var entry = minutesByStamp[stamp] ?? ([], 0)
            entry.cameras.append(cam)
            entry.size += size
            minutesByStamp[stamp] = entry
        }
        guard !minutesByStamp.isEmpty else { return nil }

        let minutes = minutesByStamp.keys.sorted().map { stamp -> Minute in
            let e = minutesByStamp[stamp]!
            return Minute(key: stamp,
                          time: timeComponent(stamp),
                          cameras: e.cameras,
                          sizeBytes: e.size)
        }

        let rel = relativePath(of: dir, under: root)
        let group = groupFor(rel: rel)
        return DashcamEvent(
            id: rel.isEmpty ? dir.lastPathComponent : rel,
            url: dir,
            name: dir.lastPathComponent,
            group: group,
            minutes: minutes,
            metadata: parseEventJSON(dir.appending(path: "event.json")),
            hasThumbnail: fm.fileExists(atPath: dir.appending(path: "thumb.png").path))
    }

    // MARK: - event.json
    func parseEventJSON(_ url: URL) -> EventMetadata? {
        guard let data = try? Data(contentsOf: url),
              let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        else { return nil }

        func double(_ key: String) -> Double? {
            if let d = obj[key] as? Double { return d }
            if let s = obj[key] as? String { return Double(s) }
            return nil
        }
        var lat = double("est_lat"), lon = double("est_lon")
        // 0,0 is in the ocean off Africa — treat as missing (matches engine).
        if let la = lat, let lo = lon, la.rounded(toPlaces: 5) == 0, lo.rounded(toPlaces: 5) == 0 {
            lat = nil; lon = nil
        }
        var ts: Date?
        if let s = obj["timestamp"] as? String {
            let f = DateFormatter(); f.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
            ts = f.date(from: s)
        }
        return EventMetadata(timestamp: ts,
                             city: obj["city"] as? String,
                             street: obj["street"] as? String,
                             reason: obj["reason"] as? String,
                             latitude: lat, longitude: lon)
    }

    // MARK: - helpers
    private func groupFor(rel: String) -> EventGroup {
        let first = rel.split(separator: "/").first.map(String.init) ?? ""
        return EventGroup(rawValue: first) ?? .other
    }
    private func relativePath(of url: URL, under root: URL) -> String {
        let r = root.standardizedFileURL.path
        let u = url.standardizedFileURL.path
        guard u.hasPrefix(r) else { return url.lastPathComponent }
        return String(u.dropFirst(r.count)).trimmingCharacters(in: CharacterSet(charactersIn: "/"))
    }
    private func timeComponent(_ stamp: String) -> String {
        // "2026-07-10_14-31-00" → "14:31:00"
        guard let t = stamp.split(separator: "_").last else { return stamp }
        return t.replacingOccurrences(of: "-", with: ":")
    }
    private func fileSize(_ url: URL) -> Int64 {
        (try? url.resourceValues(forKeys: [.fileSizeKey]).fileSize).flatMap { Int64($0) } ?? 0
    }
    private func nsRange(_ s: String) -> NSRange { NSRange(s.startIndex..., in: s) }
}

private extension Double {
    func rounded(toPlaces places: Int) -> Double {
        let f = pow(10.0, Double(places))
        return (self * f).rounded() / f
    }
}
