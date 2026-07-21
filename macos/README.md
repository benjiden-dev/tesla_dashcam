# Dashcam Studio — native macOS app (Tier 2, Phase 0)

A conventional, native SwiftUI front end for `tesla_dashcam`. It drives the
existing engine as a bundled sidecar (added in a later work package) — **no web
server, no embedded webpage, no browser**. Footage is read **in place** from a
folder you pick; nothing is copied.

> **Status: Phase 0 scaffold.** This establishes the shared models, the
> `EngineService` contract + a mock, the Comfort-Light/graphite theme, folder
> access, and the app shell. It runs today against `MockEngineService` (canned
> sample events + scripted progress). The real scanner/engine bridge/preview
> land in WP-1…WP-3.
>
> ⚠️ This scaffold was authored on Linux (no Apple toolchain), so it has **not
> been compiled yet**. Treat the first `xcodegen generate` + build in Xcode as
> the smoke test and expect to fix a few small things.

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
    MockEngineService.swift   # in-memory stand-in + sample events
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

WP-1 native scanner · WP-2 engine bridge + stdout progress parser · WP-3 map
(`MKMapSnapshotter`) + first-frame preview · WP-6 bundle the engine/ffmpeg
sidecar + wire into the DMG workflow. See the Tier 2 build-plan document.
