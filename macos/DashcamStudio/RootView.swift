//  RootView.swift
//  Top-level split view: event sidebar + detail, with a unified toolbar.

import SwiftUI

struct RootView: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        NavigationSplitView {
            EventSidebar()
                .navigationSplitViewColumnWidth(min: 260, ideal: 280, max: 340)
        } detail: {
            Group {
                if model.sourceFolder == nil {
                    EmptyStateView()
                } else if let event = model.selectedEvent {
                    EventDetailView(event: event)
                } else {
                    ContentUnavailableView("Select an event",
                                           systemImage: "film.stack",
                                           description: Text("Choose an event from the list to begin."))
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(Theme.window)
        }
        .toolbar {
            ToolbarItemGroup(placement: .principal) {
                Button {
                    Task { await model.rescan() }
                } label: { Image(systemName: "arrow.clockwise") }
                    .help("Rescan folder")
                    .disabled(model.sourceFolder == nil)
            }
        }
    }
}

struct EmptyStateView: View {
    @Environment(AppModel.self) private var model
    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "car.side.and.exclamationmark")
                .font(.system(size: 44)).foregroundStyle(Theme.textTertiary)
            Text("No folder chosen").font(.title2.weight(.semibold))
            Text("Choose your TeslaCam folder or USB drive. Footage is read in place — nothing is copied.")
                .font(.callout).foregroundStyle(Theme.textSecondary)
                .multilineTextAlignment(.center).frame(maxWidth: 360)
            Button("Choose Folder…") { model.chooseFolder() }
                .buttonStyle(PrimaryButtonStyle())
        }
        .padding(40)
    }
}
