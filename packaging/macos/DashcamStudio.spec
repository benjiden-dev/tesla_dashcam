# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Dashcam Studio macOS app.

Build (from the repo root, after building webui/frontend and placing
ffmpeg + ffprobe in packaging/macos/bin/):

    pyinstaller --noconfirm packaging/macos/DashcamStudio.spec
"""

from pathlib import Path

ROOT = Path(SPECPATH).resolve().parents[1]  # noqa: F821 - SPECPATH is injected

a = Analysis(  # noqa: F821
    [str(ROOT / "packaging" / "macos" / "launcher.py")],
    pathex=[str(ROOT)],
    binaries=[
        (str(ROOT / "packaging" / "macos" / "bin" / "ffmpeg"), "bin"),
        (str(ROOT / "packaging" / "macos" / "bin" / "ffprobe"), "bin"),
    ],
    datas=[
        (str(ROOT / "webui" / "static" / "dist"), "webui/static/dist"),
        (str(ROOT / "ffmpeg_LICENSE.txt"), "."),
        (str(ROOT / "LICENSE"), "."),
    ],
    hiddenimports=[
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter"],
    # Keep our packages as plain source files on disk so Path(__file__)
    # based data lookups (webui/static/dist) work unchanged.
    module_collection_mode={
        "webui": "py",
        "tesla_dashcam": "py",
    },
    noarchive=False,
)

pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DashcamStudio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="DashcamStudio",
)

app = BUNDLE(  # noqa: F821
    coll,
    name="Dashcam Studio.app",
    icon=str(ROOT / "bundles" / "MacOS" / "tesla_dashcam.icns"),
    bundle_identifier="dev.benjiden.dashcam-studio",
    info_plist={
        "CFBundleName": "Dashcam Studio",
        "CFBundleDisplayName": "Dashcam Studio",
        "CFBundleShortVersionString": "1.0.0",
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
        "LSApplicationCategoryType": "public.app-category.video",
    },
)
