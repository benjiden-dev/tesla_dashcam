//  EventSidebar.swift
//  Source-list of events grouped by SentryClips / SavedClips / RecentClips.

import SwiftUI

struct EventSidebar: View {
    @Environment(AppModel.self) private var model
    @State private var filter: EventGroup? = nil

    private var filtered: [DashcamEvent] {
        filter == nil ? model.events : model.events.filter { $0.group == filter }
    }
    private var grouped: [(EventGroup, [DashcamEvent])] {
        EventGroup.allCases.compactMap { g in
            let items = filtered.filter { $0.group == g }
            return items.isEmpty ? nil : (g, items)
        }
    }

    var body: some View {
        @Bindable var model = model
        VStack(spacing: 0) {
            filterBar
            List(selection: $model.selectedEventID) {
                ForEach(grouped, id: \.0) { group, items in
                    Section(group.shortName.uppercased()) {
                        ForEach(items) { EventRow(event: $0) }
                    }
                }
            }
            .listStyle(.sidebar)
            .overlay {
                if model.isScanning { ProgressView().controlSize(.small) }
            }
        }
        .background(Theme.sidebar)
    }

    private var filterBar: some View {
        HStack(spacing: 4) {
            chip("All", nil)
            chip("Saved", .saved)
            chip("Sentry", .sentry)
            chip("Recent", .recent)
            Spacer()
        }
        .padding(.horizontal, 12).padding(.vertical, 8)
    }

    private func chip(_ label: String, _ group: EventGroup?) -> some View {
        Button {
            filter = group
        } label: {
            Text(label).font(.system(size: 11.5, weight: .medium))
                .padding(.horizontal, 9).padding(.vertical, 3)
        }
        .buttonStyle(.plain)
        .background(filter == group ? Theme.textPrimary : .clear)
        .foregroundStyle(filter == group ? Theme.window : Theme.textSecondary)
        .clipShape(Capsule())
        .overlay(Capsule().stroke(Theme.borderStrong, lineWidth: filter == group ? 0 : 1))
    }
}

private struct EventRow: View {
    let event: DashcamEvent

    var body: some View {
        HStack(spacing: 10) {
            RoundedRectangle(cornerRadius: 5)
                .fill(LinearGradient(colors: [Color(white: 0.28), Color(white: 0.16)],
                                     startPoint: .top, endPoint: .bottom))
                .frame(width: 52, height: 33)
                .overlay(Image(systemName: "video.fill")
                    .font(.system(size: 11)).foregroundStyle(.white.opacity(0.35)))
            VStack(alignment: .leading, spacing: 2) {
                Text(EventFormat.title(event.name))
                    .font(.system(size: 13, weight: .semibold)).lineLimit(1)
                Text(EventFormat.subtitle(event))
                    .font(.system(size: 11)).foregroundStyle(Theme.textSecondary).lineLimit(1)
                HStack(spacing: 4) {
                    if let reason = event.reasonLabel {
                        Badge(text: reason, tone: event.group == .sentry ? Theme.sentry : Theme.saved)
                    }
                    if event.metadata?.hasLocation == true { Badge(text: "GPS", tone: Theme.gps) }
                }
            }
            Spacer(minLength: 0)
        }
        .padding(.vertical, 3)
        .tag(event.id)
    }
}

enum EventFormat {
    static func title(_ name: String) -> String {
        // "2026-07-10_14-31-04" → "Jul 10, 2:31 PM"
        let parts = name.split(separator: "_")
        guard parts.count == 2 else { return name }
        let df = DateFormatter(); df.dateFormat = "yyyy-MM-dd_HH-mm-ss"
        guard let date = df.date(from: name) else { return name }
        let out = DateFormatter(); out.dateFormat = "MMM d, h:mm a"
        return out.string(from: date)
    }
    static func subtitle(_ event: DashcamEvent) -> String {
        var bits = ["\(event.minuteCount) min", ByteFormat.string(event.totalBytes)]
        if let city = event.metadata?.city { bits.append(city) }
        return bits.joined(separator: " · ")
    }
}

enum ByteFormat {
    static func string(_ bytes: Int64) -> String {
        ByteCountFormatter.string(fromByteCount: bytes, countStyle: .file)
    }
}
