//  EventDetailView.swift
//  Event header, first-frame preview, minute selector, settings cards, and a
//  persistent footer action bar with live progress.

import SwiftUI

struct EventDetailView: View {
    @Environment(AppModel.self) private var model
    let event: DashcamEvent

    var body: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    header
                    PreviewCard(event: event)
                    MinutesCard(event: event)
                    SettingsGrid()
                }
                .padding(18)
            }
            FooterBar()
        }
    }

    private var header: some View {
        HStack(alignment: .top, spacing: 16) {
            VStack(alignment: .leading, spacing: 4) {
                Text(EventFormat.title(event.name))
                    .font(.system(size: 19, weight: .bold))
                HStack(spacing: 8) {
                    Badge(text: event.group.shortName,
                          tone: event.group == .sentry ? Theme.sentry : Theme.saved)
                    if let reason = event.reasonLabel { Badge(text: reason) }
                    Text(headerDetail).font(.system(size: 12.5)).foregroundStyle(Theme.textSecondary)
                }
            }
            Spacer()
            if event.metadata?.hasLocation == true {
                RoundedRectangle(cornerRadius: 8)
                    .fill(LinearGradient(colors: [Theme.gps.opacity(0.25), Theme.accent.opacity(0.2)],
                                         startPoint: .topLeading, endPoint: .bottomTrailing))
                    .frame(width: 92, height: 66)
                    .overlay(Image(systemName: "mappin.circle.fill")
                        .font(.system(size: 20)).foregroundStyle(Theme.sentry))
                    .overlay(RoundedRectangle(cornerRadius: 8).stroke(Theme.borderStrong, lineWidth: 1))
            }
        }
    }

    private var headerDetail: String {
        var bits: [String] = []
        if let street = event.metadata?.street { bits.append(street) }
        bits.append("\(event.minuteCount) min")
        bits.append(ByteFormat.string(event.totalBytes))
        return "· " + bits.joined(separator: " · ")
    }
}

// MARK: - Preview
private struct PreviewCard: View {
    @Environment(AppModel.self) private var model
    let event: DashcamEvent

    var body: some View {
        CardContainer(title: "Preview", hint: "First frame · \(model.settings.layout.displayName)") {
            ZStack {
                RoundedRectangle(cornerRadius: 4).fill(Color(white: 0.11))
                    .aspectRatio(16.0/9.0, contentMode: .fit)
                VStack(spacing: 6) {
                    Image(systemName: "photo.on.rectangle.angled")
                        .font(.system(size: 28)).foregroundStyle(.white.opacity(0.4))
                    Text("Live preview appears here once the engine is wired (WP-2/WP-3).")
                        .font(.system(size: 11.5)).foregroundStyle(.white.opacity(0.5))
                }
            }
        }
    }
}

// MARK: - Minutes
private struct MinutesCard: View {
    @Environment(AppModel.self) private var model
    let event: DashcamEvent

    var body: some View {
        let included = model.includedMinutes(for: event)
        CardContainer(title: "Minutes to include",
                      hint: "\(included.count) of \(event.minuteCount) selected") {
            FlexWrap(spacing: 7) {
                ForEach(event.minutes) { minute in
                    MinuteChip(time: minute.shortTime, on: included.contains(minute.key)) {
                        model.toggleMinute(event, minute.key)
                    }
                }
            }
            HStack(spacing: 8) {
                Button("Select all") { model.selectAllMinutes(event) }
                Button("Last minute only") { model.selectLastMinute(event) }
                Text("Skipped minutes are excluded from the video.")
                    .font(.system(size: 11.5)).foregroundStyle(Theme.textTertiary)
            }
            .controlSize(.small)
        }
    }
}

private struct MinuteChip: View {
    let time: String
    let on: Bool
    let action: () -> Void
    var body: some View {
        Button(action: action) {
            HStack(spacing: 6) {
                Image(systemName: on ? "checkmark.square.fill" : "square")
                    .foregroundStyle(on ? Theme.accent : Theme.textTertiary)
                Text(time).strikethrough(!on)
            }
            .font(.system(size: 12))
            .foregroundStyle(on ? Theme.textPrimary : Theme.textTertiary)
            .padding(.horizontal, 10).padding(.vertical, 5)
            .background(on ? Theme.field : .clear)
            .overlay(RoundedRectangle(cornerRadius: 7).stroke(Theme.borderStrong, lineWidth: 1))
            .clipShape(RoundedRectangle(cornerRadius: 7))
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Footer
private struct FooterBar: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        VStack(spacing: 0) {
            Divider().overlay(Theme.border)
            if let p = model.activeProgress, model.isRendering {
                ProgressStrip(progress: p)
            }
            HStack(spacing: 14) {
                Text(statusLine).font(.system(size: 12.5)).foregroundStyle(Theme.textSecondary)
                Spacer()
                if model.isRendering {
                    Button("Cancel") { model.cancelRender() }
                } else {
                    Button("Create Video") { confirmAndStart() }
                        .buttonStyle(PrimaryButtonStyle())
                        .disabled(model.selectedMinuteCount == 0)
                }
            }
            .padding(.horizontal, 18).padding(.vertical, 12)
        }
        .background(Theme.cardHeader)
    }

    private var statusLine: String {
        let mins = model.selectedMinuteCount
        var bits = ["\(mins) minute\(mins == 1 ? "" : "s")"]
        bits.append(model.settings.codec.rawValue)
        if model.settings.map.enabled { bits.append("map burn-in") }
        if model.deleteInputAfter { bits.append("deletes input") }
        return bits.joined(separator: " · ")
    }

    private func confirmAndStart() {
        if model.deleteInputAfter {
            let alert = NSAlert()
            alert.messageText = "Delete source footage after processing?"
            alert.informativeText = "The source folder for this event is permanently removed after a verified successful render."
            alert.addButton(withTitle: "Process & Delete")
            alert.addButton(withTitle: "Cancel")
            guard alert.runModal() == .alertFirstButtonReturn else { return }
        }
        model.startRender()
    }
}

private struct ProgressStrip: View {
    let progress: RenderProgress
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(progress.phase.label).font(.system(size: 12, weight: .semibold))
                Text(progress.message).font(.system(size: 11.5)).foregroundStyle(Theme.textSecondary)
                Spacer()
                Text(progress.percentText).font(.system(size: 12, weight: .semibold)).monospacedDigit()
            }
            ProgressView(value: progress.fractionCompleted).tint(Theme.accent)
        }
        .padding(.horizontal, 18).padding(.top, 10)
    }
}
