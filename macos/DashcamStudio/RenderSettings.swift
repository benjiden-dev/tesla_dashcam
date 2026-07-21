//  RenderSettings.swift
//  User-configurable render options (Phase 0 contract).

import Foundation

enum Quality: String, CaseIterable, Codable, Identifiable, Sendable {
    case draft = "Draft"
    case balanced = "Balanced"
    case archive = "Archive"
    var id: String { rawValue }
}

enum Codec: String, CaseIterable, Codable, Identifiable, Sendable {
    case h264 = "H.264"
    case hevc = "HEVC"
    var id: String { rawValue }
    var subtitle: String { self == .h264 ? "compatible" : "smaller, less compatible" }
}

enum MapCorner: String, CaseIterable, Codable, Identifiable, Sendable {
    case topLeft = "top_left"
    case topRight = "top_right"
    case bottomLeft = "bottom_left"
    case bottomRight = "bottom_right"
    var id: String { rawValue }
    var displayName: String {
        switch self {
        case .topLeft: return "Top-left"
        case .topRight: return "Top-right"
        case .bottomLeft: return "Bottom-left"
        case .bottomRight: return "Bottom-right"
        }
    }
}

enum TextAlign: String, CaseIterable, Codable, Sendable {
    case left = "LEFT", center = "CENTER", right = "RIGHT"
    case top = "TOP", middle = "MIDDLE", bottom = "BOTTOM"
    var label: String { rawValue.capitalized }
}

struct MapOverlaySettings: Codable, Hashable, Sendable {
    var enabled: Bool = false
    var corner: MapCorner = .bottomRight
    var sizePercent: Double = 0.22
    var opacity: Double = 0.90
    var zoom: Int = 16
}

struct RenderSettings: Codable, Hashable, Sendable {
    var layout: MovieLayout = .fullscreen
    var perspective: Bool = false
    var viewMode: ViewMode = .mirror
    var swap: Bool = false
    var cameras: Set<CameraID> = Set(CameraID.allCases)

    var showTimestamp: Bool = true
    var timestampHAlign: TextAlign = .center
    var timestampVAlign: TextAlign = .bottom

    var quality: Quality = .balanced
    var codec: Codec = .h264
    var bitrate: String? = "8M"          // nil = engine default
    var fps: Int = 24

    var merge: Bool = true
    var motionOnly: Bool = false

    var map: MapOverlaySettings = .init()

    /// Cameras excluded relative to the full set (engine takes exclusions).
    var excludedCameras: [CameraID] {
        CameraID.allCases.filter { !cameras.contains($0) }
    }
}
