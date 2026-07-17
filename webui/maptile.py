"""Render cached map tiles for events and burn them onto finished videos.

Tile rendering reuses the ``staticmap`` package the engine already depends on
(for its title-screen map). Tiles are cached on disk and fetched with an
identifying User-Agent, keeping usage well within the OSM tile policy. The
burn-in itself is an ffmpeg overlay post-pass on the finished movie so the
engine's filter graph stays untouched.
"""

from __future__ import annotations

import hashlib
import json
import logging
import subprocess
from pathlib import Path
from typing import Any, Optional

import requests as _requests
import staticmap

from . import config

_LOGGER = logging.getLogger(__name__)

CORNERS = ("top_left", "top_right", "bottom_left", "bottom_right")

DEFAULT_MAP_OVERLAY: dict[str, Any] = {
    "enabled": False,
    "corner": "bottom_right",
    "size_pct": 0.22,
    "opacity": 0.9,
    "zoom": 16,
}


class _RequestsShim:
    """Inject our User-Agent into staticmap's tile fetches."""

    @staticmethod
    def get(url: str, **kwargs: Any):  # noqa: ANN401 - passthrough shim
        headers = kwargs.pop("headers", None) or {}
        headers.setdefault("User-Agent", config.MAP_USER_AGENT)
        kwargs.setdefault("timeout", 10)
        return _requests.get(url, headers=headers, **kwargs)


def _patch_staticmap() -> None:
    module = getattr(staticmap, "staticmap", None)
    if module is not None and getattr(module, "requests", None) is not _RequestsShim:
        module.requests = _RequestsShim


def render_event_map(
    lat: float,
    lon: float,
    width: int = 560,
    height: int = 560,
    zoom: int = 16,
) -> Path:
    """Render (or reuse) a cached map PNG with a marker at the event location."""
    key_src = f"{lat:.5f},{lon:.5f},{zoom},{width}x{height},{config.TILE_URL}"
    key = hashlib.md5(key_src.encode()).hexdigest()[:16]
    out = config.MAP_DIR / f"map_{key}.png"
    if out.exists():
        return out

    _patch_staticmap()
    tile_map = staticmap.StaticMap(width, height, url_template=config.TILE_URL)
    coordinate = (lon, lat)
    tile_map.add_marker(staticmap.CircleMarker(coordinate, "white", 18))
    tile_map.add_marker(staticmap.CircleMarker(coordinate, "#e82127", 12))
    image = tile_map.render(zoom=zoom)

    tmp = out.with_suffix(".tmp.png")
    image.save(tmp)
    tmp.replace(out)
    _LOGGER.info("Rendered map tile for %.5f,%.5f -> %s", lat, lon, out.name)
    return out


def probe_dimensions(video: Path) -> tuple[int, int]:
    """Return (width, height) of the first video stream."""
    result = subprocess.run(
        [
            config.FFPROBE,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "json",
            str(video),
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    stream = json.loads(result.stdout)["streams"][0]
    return int(stream["width"]), int(stream["height"])


def overlay_map(
    video: Path,
    map_png: Path,
    corner: str = "bottom_right",
    size_pct: float = 0.22,
    opacity: float = 0.9,
    crf: int = 20,
    margin: int = 24,
) -> None:
    """Composite the map onto the video (in place, atomic replace)."""
    width, _height = probe_dimensions(video)
    map_width = max(96, int(width * max(0.05, min(size_pct, 0.5))))
    opacity = max(0.2, min(float(opacity), 1.0))

    positions = {
        "top_left": f"{margin}:{margin}",
        "top_right": f"W-w-{margin}:{margin}",
        "bottom_left": f"{margin}:H-h-{margin}",
        "bottom_right": f"W-w-{margin}:H-h-{margin}",
    }
    position = positions.get(corner, positions["bottom_right"])

    filter_complex = (
        f"[1:v]scale={map_width}:-1,format=rgba,"
        f"colorchannelmixer=aa={opacity}[map];"
        f"[0:v][map]overlay={position}:format=auto"
    )

    tmp_out = video.with_name(video.stem + ".map-tmp.mp4")
    try:
        subprocess.run(
            [
                config.FFMPEG,
                "-y",
                "-loglevel",
                "error",
                "-i",
                str(video),
                "-i",
                str(map_png),
                "-filter_complex",
                filter_complex,
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                str(crf),
                "-movflags",
                "+faststart",
                "-an",
                str(tmp_out),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=6 * 3600,
        )
        tmp_out.replace(video)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"ffmpeg failed: {exc.stderr}") from exc
    finally:
        if tmp_out.exists():
            tmp_out.unlink(missing_ok=True)


def normalized_overlay(options: Optional[dict[str, Any]]) -> dict[str, Any]:
    """Merge user overlay options with defaults and clamp values."""
    merged = dict(DEFAULT_MAP_OVERLAY)
    for key, value in (options or {}).items():
        if key in merged:
            merged[key] = value
    if merged["corner"] not in CORNERS:
        merged["corner"] = "bottom_right"
    try:
        merged["size_pct"] = max(0.05, min(float(merged["size_pct"]), 0.5))
    except (TypeError, ValueError):
        merged["size_pct"] = 0.22
    try:
        merged["opacity"] = max(0.2, min(float(merged["opacity"]), 1.0))
    except (TypeError, ValueError):
        merged["opacity"] = 0.9
    try:
        merged["zoom"] = max(3, min(int(merged["zoom"]), 19))
    except (TypeError, ValueError):
        merged["zoom"] = 16
    merged["enabled"] = bool(merged["enabled"])
    return merged
