//  RenderProgress.swift
//  Job request + structured progress (Phase 0 contract). Mirrors the web
//  backend's JobProgress so the stdout parser ports directly in WP-2.

import Foundation

typealias JobID = UUID

/// One event's selected minutes for a render.
struct EventSelection: Hashable, Sendable {
    let eventID: String
    /// nil = all minutes; otherwise the chosen minute keys.
    var minutes: [String]?
}

/// A complete render request.
struct RenderRequest: Sendable {
    var selections: [EventSelection]
    var settings: RenderSettings
    var deleteInputAfter: Bool = false
}

enum RenderPhase: String, Sendable {
    case queued, staging, scanning, encoding, assembling, merging
    case mapOverlay = "map_overlay"
    case cleanup, done, failed, cancelled

    var label: String {
        switch self {
        case .queued: return "Queued"
        case .staging: return "Preparing clips"
        case .scanning: return "Scanning"
        case .encoding: return "Encoding clips"
        case .assembling: return "Assembling movie"
        case .merging: return "Merging"
        case .mapOverlay: return "Burning in map"
        case .cleanup: return "Cleaning up"
        case .done: return "Done"
        case .failed: return "Failed"
        case .cancelled: return "Cancelled"
        }
    }
    var isTerminal: Bool { self == .done || self == .failed || self == .cancelled }
}

/// Structured snapshot streamed from a running job.
struct RenderProgress: Identifiable, Sendable {
    let id: JobID
    var phase: RenderPhase = .queued
    var message: String = ""
    var fractionCompleted: Double = 0        // 0...1
    var currentEvent: Int = 0
    var totalEvents: Int = 0
    var clipInEvent: Int = 0
    var clipsInEvent: Int = 0
    var etaSeconds: Int?
    var outputs: [URL] = []
    var warnings: [String] = []
    var errors: [String] = []
    var errorMessage: String?

    var percentText: String { "\(Int((fractionCompleted * 100).rounded()))%" }
}
