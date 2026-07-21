//  DashcamStudioApp.swift
//  App entry point: window, native menu-bar commands, Preferences scene.

import SwiftUI

@main
struct DashcamStudioApp: App {
    @State private var model = AppModel()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(model)
                .frame(minWidth: 960, minHeight: 640)
                .preferredColorScheme(model.appearance.colorScheme)
                .onAppear { model.restoreLastFolder() }
        }
        .windowToolbarStyle(.unified)
        .commands {
            // File ▸ Open Folder / Rescan
            CommandGroup(replacing: .newItem) {
                Button("Open Folder…") { model.chooseFolder() }
                    .keyboardShortcut("o")
                Button("Rescan") { Task { await model.rescan() } }
                    .keyboardShortcut("r")
                    .disabled(model.sourceFolder == nil)
            }
            // View ▸ Appearance
            CommandGroup(after: .toolbar) {
                Picker("Appearance", selection: Binding(
                    get: { model.appearance },
                    set: { model.appearance = $0 }
                )) {
                    ForEach(AppAppearance.allCases) { Text($0.label).tag($0) }
                }
            }
            CommandGroup(replacing: .help) {
                Link("Dashcam Studio Help",
                     destination: URL(string: "https://github.com/benjiden-dev/tesla_dashcam")!)
            }
        }

        Settings {
            PreferencesView().environment(model)
        }
    }
}

/// Preferences (⌘,) — conventional home for Appearance.
struct PreferencesView: View {
    @Environment(AppModel.self) private var model
    var body: some View {
        @Bindable var model = model
        Form {
            Section("Appearance") {
                Picker("Theme", selection: $model.appearance) {
                    ForEach(AppAppearance.allCases) { Text($0.label).tag($0) }
                }
                .pickerStyle(.segmented)
                Text("Light uses warm neutral surfaces; Dark is graphite, not black.")
                    .font(.footnote).foregroundStyle(Theme.textTertiary)
            }
            Section("Source") {
                LabeledContent("Folder", value: model.sourceFolder?.path ?? "None chosen")
                Button("Choose Folder…") { model.chooseFolder() }
            }
        }
        .formStyle(.grouped)
        .frame(width: 460, height: 260)
    }
}
