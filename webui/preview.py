"""First-frame composite previews rendered through the real engine.

To show exactly what a layout + camera selection will look like, the preview
stages a few stream-copied seconds of the selected minute, runs the actual
engine on it (CPU, lowest quality, reduced scale) and extracts frame one as a
JPEG. Results are cached by everything that affects composition.
"""

from __future__ import annotations

import hashlib
import json
import logging
import subprocess
import threading
from pathlib import Path
from typing import Any, Optional

from . import config, engine, staging

_LOGGER = logging.getLogger(__name__)

_LOCK = threading.Lock()

# Settings that change the composed frame (and therefore the cache key).
_VISUAL_KEYS = (
    "layout",
    "perspective",
    "view_mode",
    "swap",
    "background",
    "cameras",
    "show_timestamp",
    "halign",
    "valign",
    "fontsize",
    "fontcolor",
    "font",
    "text_overlay_fmt",
    "scale",
)

PREVIEW_SECONDS = 3
PREVIEW_TIMEOUT = 240


def preview_key(event_path: str, minute_key: str, settings: dict[str, Any]) -> str:
    merged = engine.merged_settings(settings)
    relevant = {key: merged.get(key) for key in _VISUAL_KEYS}
    payload = json.dumps([event_path, minute_key, relevant], sort_keys=True)
    return hashlib.md5(payload.encode()).hexdigest()[:20]


def preview_path(key: str) -> Path:
    return config.PREVIEW_DIR / f"{key}.jpg"


def render_preview(
    event_dir: Path,
    event_path: str,
    minute_key: str,
    settings: Optional[dict[str, Any]] = None,
) -> tuple[str, bool]:
    """Render (or reuse) a first-frame preview; returns (key, was_cached)."""
    merged = engine.merged_settings(settings)
    key = preview_key(event_path, minute_key, merged)
    out = preview_path(key)
    if out.exists():
        return key, True

    with _LOCK:
        if out.exists():
            return key, True

        # Speed-focused overrides that do not change the composed frame.
        pv_settings = dict(merged)
        pv_settings.update(
            {
                "quality": "LOWEST",
                "compression": "ultrafast",
                "encoding": "x264",
                "gpu": False,
                "merge": False,
                "motion_only": False,
                "speedup": None,
                "slowdown": None,
                "faststart": False,
                "skip_existing": False,
                "title_screen_map": False,
                "fps": 24,
                "bitrate": None,
            }
        )
        if not pv_settings.get("scale"):
            pv_settings["scale"] = 0.5

        enabled_cameras = [
            camera
            for camera, enabled in pv_settings["cameras"].items()
            if enabled
        ]
        if not enabled_cameras:
            raise ValueError("at least one camera must be enabled for a preview")

        stage_root = staging.stage_preview(
            key, event_dir, minute_key, enabled_cameras, seconds=PREVIEW_SECONDS
        )
        try:
            out_dir = stage_root / "out"
            out_dir.mkdir()
            args = engine.build_engine_args(
                stage_root,
                out_dir / "preview.mp4",
                pv_settings,
                gpu_available=False,
            )
            result = subprocess.run(
                config.ENGINE_CMD + args,
                capture_output=True,
                text=True,
                timeout=PREVIEW_TIMEOUT,
                cwd=config.ENGINE_CWD,
            )
            movies = sorted(out_dir.glob("*.mp4"))
            if result.returncode != 0 or not movies:
                error_msg = result.stderr or result.stdout or ""
                tail = "\n".join(error_msg.splitlines()[-12:])
                raise RuntimeError(
                    f"engine preview render failed (rc={result.returncode}):\n{tail}"
                )

            tmp_jpg = out.with_suffix(".tmp.jpg")
            subprocess.run(
                [
                    config.FFMPEG,
                    "-y",
                    "-loglevel",
                    "error",
                    "-i",
                    str(movies[0]),
                    "-frames:v",
                    "1",
                    "-q:v",
                    "4",
                    str(tmp_jpg),
                ],
                check=True,
                capture_output=True,
                timeout=60,
            )
            tmp_jpg.replace(out)
        finally:
            staging.cleanup(stage_root)

    return key, False
