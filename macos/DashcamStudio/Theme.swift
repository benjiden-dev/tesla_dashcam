//  Theme.swift
//  Comfort-Light / graphite-Dark design system. Every surface is a semantic,
//  appearance-adaptive token — no hardcoded pure white, dark = graphite not
//  black. Screens consume `Theme.*`, never raw hex.

import SwiftUI
import AppKit

/// User appearance preference (persisted).
enum AppAppearance: String, CaseIterable, Identifiable, Sendable {
    case system, light, dark
    var id: String { rawValue }
    var label: String { rawValue.capitalized }
    var colorScheme: ColorScheme? {
        switch self {
        case .system: return nil
        case .light: return .light
        case .dark: return .dark
        }
    }
}

/// Adaptive color built from light/dark hex values.
private func adaptive(_ lightHex: UInt32, _ darkHex: UInt32) -> Color {
    Color(nsColor: NSColor(name: nil) { appearance in
        let isDark = appearance.bestMatch(from: [.aqua, .darkAqua]) == .darkAqua
        return NSColor(hex: isDark ? darkHex : lightHex)
    })
}

enum Theme {
    // Surfaces — Comfort Light (warm neutrals) / graphite Dark
    static let window      = adaptive(0xEAE7E2, 0x1F2124)
    static let sidebar     = adaptive(0xE4E0D9, 0x26292D)
    static let card        = adaptive(0xF6F4F0, 0x2B2F33)
    static let cardHeader  = adaptive(0xEFECE7, 0x30343A)
    static let field       = adaptive(0xFCFBF9, 0x34383E)
    static let border      = adaptive(0xD6D1C8, 0x3A3F45)
    static let borderStrong = adaptive(0xC6C0B6, 0x474D55)

    // Text
    static let textPrimary   = adaptive(0x2C2A27, 0xECEAE6)
    static let textSecondary = adaptive(0x706C66, 0xA6A29B)
    static let textTertiary  = adaptive(0x9A958C, 0x7C7873)

    // Accent + semantic
    static let accent = adaptive(0x3F6FA8, 0x6F9FD8)
    static let sentry = adaptive(0xA8473F, 0xD98A82)
    static let saved  = adaptive(0x45638A, 0x8FB0D8)
    static let gps    = adaptive(0x4C7357, 0x86BE97)
    static let danger = adaptive(0xB23B3B, 0xE07A7A)
}

// MARK: - Hex helper
extension NSColor {
    convenience init(hex: UInt32) {
        self.init(
            srgbRed: Double((hex >> 16) & 0xFF) / 255,
            green: Double((hex >> 8) & 0xFF) / 255,
            blue: Double(hex & 0xFF) / 255,
            alpha: 1
        )
    }
}

// MARK: - Reusable styles
/// GroupBox-style titled card.
struct CardContainer<Content: View>: View {
    let title: String
    var hint: String? = nil
    @ViewBuilder let content: Content

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text(title.uppercased())
                    .font(.system(size: 11, weight: .bold))
                    .kerning(0.4)
                    .foregroundStyle(Theme.textSecondary)
                Spacer()
                if let hint {
                    Text(hint).font(.system(size: 11)).foregroundStyle(Theme.textTertiary)
                }
            }
            .padding(.horizontal, 14).padding(.vertical, 9)
            .background(Theme.cardHeader)
            Divider().overlay(Theme.border)
            VStack(alignment: .leading, spacing: 10) { content }
                .padding(14)
        }
        .background(Theme.card)
        .overlay(RoundedRectangle(cornerRadius: 9).stroke(Theme.border, lineWidth: 1))
        .clipShape(RoundedRectangle(cornerRadius: 9))
    }
}

struct PrimaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 13, weight: .semibold))
            .padding(.horizontal, 16).padding(.vertical, 8)
            .background(Theme.accent.opacity(configuration.isPressed ? 0.85 : 1))
            .foregroundStyle(.white)
            .clipShape(RoundedRectangle(cornerRadius: 7))
    }
}

struct Badge: View {
    let text: String
    var tone: Color = Theme.textSecondary
    var body: some View {
        Text(text)
            .font(.system(size: 10, weight: .semibold))
            .padding(.horizontal, 6).padding(.vertical, 1)
            .background(tone.opacity(0.16))
            .foregroundStyle(tone)
            .clipShape(RoundedRectangle(cornerRadius: 4))
    }
}
