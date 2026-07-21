//  SettingsCards.swift
//  The six GroupBox setting cards + a lightweight flow-layout helper.

import SwiftUI

struct SettingsGrid: View {
    var body: some View {
        LazyVGrid(columns: [GridItem(.flexible(), spacing: 14),
                            GridItem(.flexible(), spacing: 14)],
                  spacing: 14) {
            LayoutCard()
            CamerasCard()
            QualityCard()
            MapCard()
            TimestampCard()
            OptionsCard()
        }
    }
}

private struct LayoutCard: View {
    @Environment(AppModel.self) private var model
    var body: some View {
        @Bindable var model = model
        CardContainer(title: "Layout") {
            LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 8), count: 4), spacing: 8) {
                ForEach(MovieLayout.allCases) { layout in
                    Button { model.settings.layout = layout } label: {
                        VStack(spacing: 3) {
                            Image(systemName: "rectangle.3.group")
                                .font(.system(size: 15))
                            Text(layout.rawValue).font(.system(size: 9, weight: .semibold))
                                .lineLimit(1).minimumScaleFactor(0.7)
                        }
                        .frame(maxWidth: .infinity).padding(.vertical, 7)
                        .foregroundStyle(model.settings.layout == layout ? Theme.accent : Theme.textSecondary)
                        .background(model.settings.layout == layout ? Theme.accent.opacity(0.12) : Theme.field)
                        .overlay(RoundedRectangle(cornerRadius: 7)
                            .stroke(model.settings.layout == layout ? Theme.accent : Theme.borderStrong, lineWidth: 1))
                        .clipShape(RoundedRectangle(cornerRadius: 7))
                    }
                    .buttonStyle(.plain)
                }
            }
            Picker("Rear view", selection: $model.settings.viewMode) {
                ForEach(ViewMode.allCases) { Text($0.displayName).tag($0) }
            }
            .pickerStyle(.segmented)
        }
    }
}

private struct CamerasCard: View {
    @Environment(AppModel.self) private var model
    var body: some View {
        CardContainer(title: "Cameras") {
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())],
                      alignment: .leading, spacing: 9) {
                ForEach(CameraID.allCases) { cam in
                    Toggle(isOn: Binding(
                        get: { model.settings.cameras.contains(cam) },
                        set: { on in
                            if on { model.settings.cameras.insert(cam) }
                            else { model.settings.cameras.remove(cam) }
                        }
                    )) { Text(cam.displayName).font(.system(size: 13)) }
                    .toggleStyle(.checkbox)
                }
            }
        }
    }
}

private struct QualityCard: View {
    @Environment(AppModel.self) private var model
    var body: some View {
        @Bindable var model = model
        CardContainer(title: "Quality", hint: "VideoToolbox") {
            Picker("Preset", selection: $model.settings.quality) {
                ForEach(Quality.allCases) { Text($0.rawValue).tag($0) }
            }
            Picker("Codec", selection: $model.settings.codec) {
                ForEach(Codec.allCases) { Text($0.rawValue).tag($0) }
            }
            Picker("Bitrate", selection: Binding(
                get: { model.settings.bitrate ?? "auto" },
                set: { model.settings.bitrate = $0 == "auto" ? nil : $0 }
            )) {
                Text("Auto").tag("auto")
                Text("4 Mbps — small").tag("4M")
                Text("8 Mbps — good").tag("8M")
                Text("14 Mbps — high").tag("14M")
            }
            if model.settings.codec == .hevc {
                Text("HEVC may not play in every viewer.")
                    .font(.system(size: 11.5)).foregroundStyle(Theme.danger)
            }
        }
    }
}

private struct MapCard: View {
    @Environment(AppModel.self) private var model
    var body: some View {
        @Bindable var model = model
        CardContainer(title: "Map overlay") {
            Toggle(isOn: $model.settings.map.enabled) {
                Text("Burn location map into video").font(.system(size: 13))
            }
            .toggleStyle(.checkbox)
            if model.settings.map.enabled {
                Picker("Corner", selection: $model.settings.map.corner) {
                    ForEach(MapCorner.allCases) { Text($0.displayName).tag($0) }
                }
                HStack { Text("Size").font(.system(size: 13)); Slider(value: $model.settings.map.sizePercent, in: 0.1...0.4) }
                HStack { Text("Opacity").font(.system(size: 13)); Slider(value: $model.settings.map.opacity, in: 0.3...1.0) }
                Text("Uses the event's GPS via Apple Maps.")
                    .font(.system(size: 11.5)).foregroundStyle(Theme.textTertiary)
            }
        }
    }
}

private struct TimestampCard: View {
    @Environment(AppModel.self) private var model
    var body: some View {
        @Bindable var model = model
        CardContainer(title: "Timestamp") {
            Toggle(isOn: $model.settings.showTimestamp) {
                Text("Show timestamp on video").font(.system(size: 13))
            }
            .toggleStyle(.checkbox)
            if model.settings.showTimestamp {
                Picker("Horizontal", selection: $model.settings.timestampHAlign) {
                    ForEach([TextAlign.left, .center, .right], id: \.self) { Text($0.label).tag($0) }
                }.pickerStyle(.segmented)
                Picker("Vertical", selection: $model.settings.timestampVAlign) {
                    ForEach([TextAlign.top, .middle, .bottom], id: \.self) { Text($0.label).tag($0) }
                }.pickerStyle(.segmented)
            }
        }
    }
}

private struct OptionsCard: View {
    @Environment(AppModel.self) private var model
    var body: some View {
        @Bindable var model = model
        CardContainer(title: "Options") {
            Toggle(isOn: $model.settings.merge) {
                Text("Merge events into one movie").font(.system(size: 13))
            }.toggleStyle(.checkbox).disabled(model.settings.map.enabled)
            Toggle(isOn: $model.settings.motionOnly) {
                Text("Motion only (skip idle Sentry)").font(.system(size: 13))
            }.toggleStyle(.checkbox)
            Toggle(isOn: $model.deleteInputAfter) {
                Text("Delete source after processing")
                    .font(.system(size: 13, weight: .semibold)).foregroundStyle(Theme.danger)
            }.toggleStyle(.checkbox)
            Text("Source folders are removed only after the output is verified.")
                .font(.system(size: 11.5)).foregroundStyle(Theme.textTertiary)
        }
    }
}

// MARK: - Simple flow-wrap layout for the minute chips
struct FlexWrap: Layout {
    var spacing: CGFloat = 7

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let maxWidth = proposal.width ?? .infinity
        var x: CGFloat = 0, y: CGFloat = 0, rowHeight: CGFloat = 0
        for view in subviews {
            let size = view.sizeThatFits(.unspecified)
            if x + size.width > maxWidth { x = 0; y += rowHeight + spacing; rowHeight = 0 }
            x += size.width + spacing
            rowHeight = max(rowHeight, size.height)
        }
        return CGSize(width: maxWidth == .infinity ? x : maxWidth, height: y + rowHeight)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        var x = bounds.minX, y = bounds.minY, rowHeight: CGFloat = 0
        for view in subviews {
            let size = view.sizeThatFits(.unspecified)
            if x + size.width > bounds.maxX { x = bounds.minX; y += rowHeight + spacing; rowHeight = 0 }
            view.place(at: CGPoint(x: x, y: y), proposal: ProposedViewSize(size))
            x += size.width + spacing
            rowHeight = max(rowHeight, size.height)
        }
    }
}
