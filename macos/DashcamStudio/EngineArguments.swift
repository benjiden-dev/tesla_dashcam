//  EngineArguments.swift  (WP-2)
//  Translate RenderSettings into engine CLI argv. Port of the tested webui
//  engine.py build_engine_args, including the macOS `--gpu` (no --gpu_type)
//  behavior. Pure Foundation, unit-testable.

import Foundation

enum EngineArguments {
    /// Preset → (quality, compression) mapping (from the web UI presets).
    private static func qualityFlags(_ q: Quality) -> (quality: String, compression: String) {
        switch q {
        case .draft:    return ("LOWEST", "ultrafast")
        case .balanced: return ("LOWER", "medium")
        case .archive:  return ("HIGH", "slow")
        }
    }

    private static let cameraExclusion: [CameraID: String] = [
        .front: "--no-front", .back: "--no-rear",
        .leftRepeater: "--no-left", .rightRepeater: "--no-right",
        .leftPillar: "--no-left-pillar", .rightPillar: "--no-right-pillar",
    ]

    /// Build argv (excluding the engine command itself).
    static func build(source: URL,
                      output: URL,
                      settings s: RenderSettings,
                      tempDir: URL,
                      gpuAvailable: Bool,
                      isDarwin: Bool = true) -> [String] {
        var a: [String] = [source.path, "--output", output.path]

        a += ["--layout", s.layout.rawValue]
        if s.perspective { a.append("--perspective") }
        switch s.viewMode {
        case .mirror: a.append("--mirror")
        case .rear:   a.append("--rear")
        case .normal: break
        }
        if s.swap { a.append("--swap") }

        for cam in CameraID.allCases where !s.cameras.contains(cam) {
            if let flag = cameraExclusion[cam] { a.append(flag) }
        }

        if !s.showTimestamp {
            a.append("--no-timestamp")
        } else {
            a += ["--halign", s.timestampHAlign.rawValue]
            a += ["--valign", s.timestampVAlign.rawValue]
        }

        if s.motionOnly { a.append("--motion_only") }
        if s.merge { a.append("--merge") }

        let qf = qualityFlags(s.quality)
        a += ["--quality", qf.quality]
        a += ["--compression", qf.compression]
        a += ["--encoding", s.codec == .hevc ? "x265" : "x264"]
        if s.fps != 24 { a += ["--fps", String(s.fps)] }

        if gpuAvailable {
            a.append("--gpu")
            if !isDarwin { a += ["--gpu_type", "vaapi"] }   // macOS auto-selects VideoToolbox
            if let br = s.bitrate, !br.isEmpty { a += ["--bitrate", br] }
        } else {
            a.append("--no-gpu")
        }

        a += ["--no-check_for_update", "--no-notification"]
        a += ["--temp_dir", tempDir.path]
        return a
    }
}
