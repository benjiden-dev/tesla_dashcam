# Dashcam Studio — native macOS app (Tier 2, Phase 0)

A conventional, native SwiftUI front end for `tesla_dashcam`. It drives the
existing engine as a bundled sidecar (added in a later work package) — **no web
server, no embedded webpage, no browser**. Footage is read **in place** from a
folder you pick; nothing is copied.

> **Status: Phase 0 + WP-1 (scanner) + WP-2 (engine bridge).** The app now
> **scans real folders natively** (point it at a TeslaCam folder and see actual
> events). Rendering stages the selected minutes, runs the engine as a
> subprocess and parses its stdout into structured progress — it activates once
> the engine sidecar is bundled (WP-6); until then the UI reports that clearly.
> `MockEngineService` remains for SwiftUI previews. WP-3 (map + first-frame
> preview) is next.
>
> ⚠️ Authored on Linux (no Apple toolchain), so this has **not been compiled
> yet**. The pure logic (scanner, argument builder, stdout parser) is a direct
> port of the tested Python engine/webui, but treat the first Xcode build as the
> smoke test and expect a few small fixes.

## Build & run

```bash
brew install xcodegen          # one-time
cd macos
xcodegen generate              # produces DashcamStudio.xcodeproj from project.yml
open DashcamStudio.xcodeproj    # ⌘R in Xcode 26/27
```

The generated `.xcodeproj` is intentionally **not committed** — `project.yml`
plus the Swift sources are the source of truth.

- **Deployment target:** macOS 15.0 (Sequoia) — current − 2 (Golden Gate 27,
  Tahoe 26, Sequoia 15).
- **Architecture:** arm64 only. Universal/Intel is deferred (it would mean fat
  ffmpeg + fat Python sidecars); see the Tier 2 build-plan doc.

## Layout

```
macos/
  project.yml                 # XcodeGen manifest (deterministic project)
  DashcamStudio/
    Models.swift              # CameraID, MovieLayout, DashcamEvent, Minute…
    RenderSettings.swift      # RenderSettings, MapOverlaySettings, enums
    RenderProgress.swift      # RenderRequest, RenderProgress, phases
    EngineService.swift       # the backend contract (protocol)
    MockEngineService.swift   # in-memory stand-in + sample events (previews)
    Scanner.swift             # WP-1: native TeslaCam folder scanner
    EngineArguments.swift     # WP-2: RenderSettings → engine argv
    ProgressParser.swift      # WP-2: engine stdout → RenderProgress
    Staging.swift             # WP-2: symlink selected minutes
    SidecarEngineService.swift# WP-2: real service (native scan + subprocess render)
    FolderAccess.swift        # NSOpenPanel + security-scoped bookmarks
    Theme.swift               # Comfort-Light / graphite tokens + card/button styles
    AppModel.swift            # @Observable app state
    DashcamStudioApp.swift    # @main, menu-bar commands, Preferences
    RootView.swift            # NavigationSplitView + empty state
    EventSidebar.swift        # source-list of events
    EventDetailView.swift     # header, preview, minutes, footer + progress
    SettingsCards.swift       # the six GroupBox setting cards
    Resources/                # Info.plist, entitlements
```

## Design intent (must hold)

- **Conventional macOS**: real File/View/Help menu bar, GroupBox cards,
  standard controls, explicit Cancel / Create Video. No command palette, no
  floating panels, no monospaced badges.
- **Comfort Light**: warm neutral surfaces, never pure white; Dark is graphite,
  not black. All colors are appearance-adaptive semantic tokens in `Theme`;
  Appearance (System/Light/Dark) lives in Preferences (⌘,).

## Next work packages

✅ WP-1 native scanner · ✅ WP-2 engine bridge + stdout progress parser ·
WP-3 map (`MKMapSnapshotter`) + first-frame preview · WP-5 outputs gallery
(AVKit playback) · WP-6 bundle the engine/ffmpeg sidecar + wire into the DMG
workflow. See the Tier 2 build-plan document.
