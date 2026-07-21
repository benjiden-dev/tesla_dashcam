//  EngineService.swift
//  The seam between the app and the render backend (Phase 0 contract).
//
//  Phase 0 ships MockEngineService. WP-1/WP-2 implement the real
//  `SidecarEngineService` behind this same protocol (scan natively, stage
//  minutes, run the bundled engine binary, parse stdout → RenderProgress).
//  UI code depends only on this protocol, never on an implementation.

import Foundation

@MainActor
protocol EngineService: AnyObject {
    /// Scan a chosen folder for events (reads in place — no copying).
    func scanEvents(in folder: URL) async throws -> [DashcamEvent]

    /// Render a first-frame preview for a selection; returns an image file URL.
    func renderPreview(
        event: DashcamEvent,
        minute: String,
        settings: RenderSettings
    ) async throws -> URL

    /// Start a render. Progress is delivered as an async stream; the final
    /// element has a terminal phase.
    func render(_ request: RenderRequest) -> (id: JobID, progress: AsyncStream<RenderProgress>)

    /// Request cancellation of a running job.
    func cancel(_ id: JobID)
}

enum EngineError: LocalizedError {
    case noClips
    case engineFailed(String)
    case previewUnavailable

    var errorDescription: String? {
        switch self {
        case .noClips: return "No clips found for the current selection."
        case .engineFailed(let detail): return detail
        case .previewUnavailable: return "Preview could not be rendered."
        }
    }
}
