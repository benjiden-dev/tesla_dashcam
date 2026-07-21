//  Models.swift
//  Shared domain models (Phase 0 contract). Pure value types, no UI.

import Foundation

/// The six Tesla cameras, in canonical order.
enum CameraID: String, CaseIterable, Codable, Identifiable, Sendable {
    case front
    case back
    case leftRepeater = "left_repeater"
    case rightRepeater = "right_repeater"
    case leftPillar = "left_pillar"
    case rightPillar = "right_pillar"

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .front: return "Front"
        case .back: return "Rear"
        case .leftRepeater: return "Left repeater"
        case .rightRepeater: return "Right repeater"
        case .leftPillar: return "Left pillar"
        case .rightPillar: return "Right pillar"
        }
    }
}

/// Composite layouts supported by the engine.
enum MovieLayout: String, CaseIterable, Codable, Identifiable, Sendable {
    case fullscreen = "FULLSCREEN"
    case widescreen = "WIDESCREEN"
    case mosaic = "MOSAIC"
    case perspective = "PERSPECTIVE"
    case cross = "CROSS"
    case diamond = "DIAMOND"
    case horizontal = "HORIZONTAL"

    var id: String { rawValue }
    var displayName: String { rawValue.capitalized }
}

enum ViewMode: String, CaseIterable, Codable, Identifiable, Sendable {
    case normal, mirror, rear
    var id: String { rawValue }
    var displayName: String {
        switch self {
        case .normal: return "Normal"
        case .mirror: return "Mirrored"
        case .rear: return "Rear-first"
        }
    }
}

/// TeslaCam folder groupings.
enum EventGroup: String, Codable, CaseIterable, Sendable {
    case sentry = "SentryClips"
    case saved = "SavedClips"
    case recent = "RecentClips"
    case other = "Other"

    var shortName: String {
        switch self {
        case .sentry: return "Sentry"
        case .saved: return "Saved"
        case .recent: return "Recent"
        case .other: return "Other"
        }
    }
}

/// A single camera clip file (one minute, one camera).
struct Clip: Identifiable, Hashable, Sendable {
    let url: URL
    let camera: CameraID
    let start: Date
    var id: URL { url }
}

/// One minute of an event across its available cameras.
struct Minute: Identifiable, Hashable, Sendable {
    let key: String          // e.g. "2026-07-10_14-31-00"
    let time: String         // "14:31:00"
    let cameras: [CameraID]
    let sizeBytes: Int64
    var id: String { key }

    var shortTime: String { String(time.prefix(5)) }  // "14:31"
}

/// Parsed event.json metadata.
struct EventMetadata: Hashable, Sendable {
    var timestamp: Date?
    var city: String?
    var street: String?
    var reason: String?
    var latitude: Double?
    var longitude: Double?

    var hasLocation: Bool { latitude != nil && longitude != nil }
}

/// A dashcam event (a folder of minute clips + optional metadata).
struct DashcamEvent: Identifiable, Hashable, Sendable {
    let id: String           // stable id derived from relative path
    let url: URL
    let name: String
    let group: EventGroup
    let minutes: [Minute]
    let metadata: EventMetadata?
    let hasThumbnail: Bool

    var minuteCount: Int { minutes.count }
    var totalBytes: Int64 { minutes.reduce(0) { $0 + $1.sizeBytes } }

    /// Human-friendly reason label ("Honk", "Sentry · Object", …).
    var reasonLabel: String? {
        guard let reason = metadata?.reason else { return nil }
        switch reason {
        case let r where r.contains("honk"): return "Honk"
        case let r where r.contains("object_detection"): return "Sentry · Object"
        case let r where r.contains("accel"): return "Sentry · Motion"
        case let r where r.contains("dashcam"): return "Manual save"
        default: return reason.replacingOccurrences(of: "_", with: " ").capitalized
        }
    }
}
