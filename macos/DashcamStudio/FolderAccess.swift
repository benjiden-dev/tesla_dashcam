//  FolderAccess.swift
//  Native folder picking + persistent access via security-scoped bookmarks.
//  Reads footage IN PLACE — never copies/uploads. Forward-compatible with the
//  App Sandbox (the bookmark uses .withSecurityScope regardless).

import AppKit
import Foundation

enum FolderAccess {
    private static let bookmarkKey = "sourceFolderBookmark"

    /// Present a native directory picker. Returns the chosen folder, or nil if
    /// cancelled. Persists a bookmark so access survives relaunches.
    @MainActor
    static func chooseFolder() -> URL? {
        let panel = NSOpenPanel()
        panel.title = "Choose TeslaCam Folder"
        panel.message = "Select your TeslaCam folder, USB drive, or any folder of events."
        panel.prompt = "Choose"
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = false
        panel.canCreateDirectories = false
        guard panel.runModal() == .OK, let url = panel.url else { return nil }
        saveBookmark(for: url)
        return url
    }

    /// Resolve the previously chosen folder and begin accessing it.
    static func restoreFolder() -> URL? {
        guard let data = UserDefaults.standard.data(forKey: bookmarkKey) else { return nil }
        var stale = false
        guard let url = try? URL(
            resolvingBookmarkData: data,
            options: [.withSecurityScope],
            relativeTo: nil,
            bookmarkDataIsStale: &stale
        ) else { return nil }
        if stale { saveBookmark(for: url) }
        _ = url.startAccessingSecurityScopedResource()
        return url
    }

    private static func saveBookmark(for url: URL) {
        guard let data = try? url.bookmarkData(
            options: [.withSecurityScope],
            includingResourceValuesForKeys: nil,
            relativeTo: nil
        ) else { return }
        UserDefaults.standard.set(data, forKey: bookmarkKey)
    }
}
