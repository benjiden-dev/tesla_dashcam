//  AppModel.swift
//  Observable app state. Owns the source folder, scanned events, selection,
//  render settings and the active job. Talks only to an EngineService.

import SwiftUI
import Observation

@MainActor
@Observable
final class AppModel {
    // Source / events
    var sourceFolder: URL?
    var events: [DashcamEvent] = []
    var isScanning = false
    var scanError: String?

    // Selection
    var selectedEventID: String?
    /// Per-event chosen minute keys (absent = all minutes).
    var minuteSelection: [String: Set<String>] = [:]

    // Settings
    var settings = RenderSettings()
    var deleteInputAfter = false

    // Appearance (persisted to UserDefaults; @AppStorage is view-only so we
    // write through here instead).
    var appearance: AppAppearance {
        didSet { UserDefaults.standard.set(appearance.rawValue, forKey: Self.appearanceKey) }
    }
    private static let appearanceKey = "appearance"

    // Active job
    var activeProgress: RenderProgress?
    private var activeJobID: JobID?

    let engine: EngineService

    init(engine: EngineService = MockEngineService()) {
        self.engine = engine
        let stored = UserDefaults.standard.string(forKey: Self.appearanceKey)
        self.appearance = stored.flatMap(AppAppearance.init(rawValue:)) ?? .system
    }

    var selectedEvent: DashcamEvent? {
        guard let id = selectedEventID else { return nil }
        return events.first { $0.id == id }
    }

    // MARK: - Folder + scan
    func chooseFolder() {
        guard let url = FolderAccess.chooseFolder() else { return }
        sourceFolder = url
        Task { await rescan() }
    }

    func restoreLastFolder() {
        if let url = FolderAccess.restoreFolder() {
            sourceFolder = url
            Task { await rescan() }
        }
    }

    func rescan() async {
        guard let folder = sourceFolder else { return }
        isScanning = true; scanError = nil
        defer { isScanning = false }
        do {
            events = try await engine.scanEvents(in: folder)
            if selectedEventID == nil { selectedEventID = events.first?.id }
        } catch {
            scanError = error.localizedDescription
            events = []
        }
    }

    // MARK: - Minute selection
    func includedMinutes(for event: DashcamEvent) -> Set<String> {
        minuteSelection[event.id] ?? Set(event.minutes.map(\.key))
    }

    func isMinuteIncluded(_ event: DashcamEvent, _ key: String) -> Bool {
        includedMinutes(for: event).contains(key)
    }

    func toggleMinute(_ event: DashcamEvent, _ key: String) {
        var set = includedMinutes(for: event)
        if set.contains(key) { set.remove(key) } else { set.insert(key) }
        if set.count == event.minutes.count {
            minuteSelection[event.id] = nil          // "all"
        } else {
            minuteSelection[event.id] = set
        }
    }

    func selectAllMinutes(_ event: DashcamEvent) { minuteSelection[event.id] = nil }

    func selectLastMinute(_ event: DashcamEvent) {
        if let last = event.minutes.last?.key { minuteSelection[event.id] = [last] }
    }

    var selectedMinuteCount: Int {
        guard let event = selectedEvent else { return 0 }
        return includedMinutes(for: event).count
    }

    // MARK: - Render
    var isRendering: Bool {
        guard let phase = activeProgress?.phase else { return false }
        return !phase.isTerminal
    }

    func startRender() {
        guard let event = selectedEvent else { return }
        if settings.map.enabled { settings.merge = false }  // map is per-event
        let selection = EventSelection(
            eventID: event.id,
            minutes: minuteSelection[event.id].map(Array.init)
        )
        let request = RenderRequest(selections: [selection],
                                    settings: settings,
                                    deleteInputAfter: deleteInputAfter)
        let (id, stream) = engine.render(request)
        activeJobID = id
        Task {
            for await progress in stream { activeProgress = progress }
        }
    }

    func cancelRender() {
        if let id = activeJobID { engine.cancel(id) }
    }
}
