"""Dashcam Studio — frozen macOS app entry point.

One binary, two personalities:

* default: start the web UI server and open the browser
* ``__engine__`` as the first argument: run the tesla_dashcam engine CLI
  (the web UI invokes its own binary this way, so the .app is fully
  self-contained — no system Python required)

Environment overrides work exactly like the dev setup: INPUT_DIR,
OUTPUT_DIR, CACHE_DIR, PORT.
"""

from __future__ import annotations

import os
import sys
import threading
import webbrowser
from pathlib import Path


def _run_engine() -> None:
    """Engine personality: behave exactly like `python -m tesla_dashcam`."""
    sys.argv = [sys.argv[0]] + sys.argv[2:]
    from tesla_dashcam.tesla_dashcam import main as engine_main

    sys.exit(engine_main())


if len(sys.argv) > 1 and sys.argv[1] == "__engine__":
    _run_engine()


# ── Server personality ───────────────────────────────────────────────────
BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
BIN_DIR = BUNDLE_DIR / "bin"

home = Path.home()
os.environ.setdefault("INPUT_DIR", str(home / "TeslaCam"))
os.environ.setdefault("OUTPUT_DIR", str(home / "Movies" / "TeslaDashcam"))
os.environ.setdefault(
    "CACHE_DIR", str(home / "Library" / "Caches" / "tesla-dashcam-webui")
)
os.environ.setdefault("PORT", "8088")

# Bundled ffmpeg/ffprobe for the backend, and on PATH for the engine.
os.environ["FFMPEG"] = str(BIN_DIR / "ffmpeg")
os.environ["FFPROBE"] = str(BIN_DIR / "ffprobe")
os.environ["PATH"] = f"{BIN_DIR}:{os.environ.get('PATH', '')}"

from webui import config  # noqa: E402  (env must be set before this import)

# The engine subprocess is this very binary in engine mode.
config.ENGINE_CMD = [sys.executable, "__engine__"]
config.ENGINE_CWD = None

config.ensure_dirs()
for directory in (config.INPUT_DIR, config.OUTPUT_DIR):
    directory.mkdir(parents=True, exist_ok=True)

import uvicorn  # noqa: E402

from webui.app import app  # noqa: E402


def _open_browser() -> None:
    webbrowser.open(f"http://localhost:{config.PORT}")


def main() -> None:
    threading.Timer(1.2, _open_browser).start()
    uvicorn.run(app, host="127.0.0.1", port=config.PORT, log_level="info")


if __name__ == "__main__":
    main()
