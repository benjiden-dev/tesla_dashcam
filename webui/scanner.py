"""Scan the input directory for TeslaCam events, minutes and cameras.

An "event" is any folder containing files named like
``2026-07-10_14-32-15-front.mp4``. SavedClips/SentryClips event folders and
RecentClips-style loose folders are both supported. Each event exposes its
one-minute clips ("minutes") so the UI can select a subset for processing.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Optional

from . import config

_LOGGER = logging.getLogger(__name__)

CAMERAS: tuple[str, ...] = (
    "front",
    "back",
    "left_repeater",
    "right_repeater",
    "left_pillar",
    "right_pillar",
)

CLIP_RE = re.compile(
    r"^(?P<stamp>\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})-"
    r"(?P<camera>" + "|".join(CAMERAS) + r")\.mp4$"
)

KNOWN_GROUPS = {"SavedClips", "SentryClips", "RecentClips"}
MAX_DEPTH = 4


# ── Event ids ────────────────────────────────────────────────────────────
def encode_event_id(rel_path: str) -> str:
    return base64.urlsafe_b64encode(rel_path.encode()).decode().rstrip("=")


def decode_event_id(event_id: str) -> str:
    padded = event_id + "=" * (-len(event_id) % 4)
    return base64.urlsafe_b64decode(padded.encode()).decode()


def event_dir_from_id(event_id: str) -> Path:
    """Resolve an event id to a directory inside INPUT_DIR (traversal safe)."""
    rel = decode_event_id(event_id)
    root = config.INPUT_DIR.resolve()
    path = (root / rel).resolve()
    if path != root and root not in path.parents:
        raise ValueError(f"event path escapes input dir: {rel!r}")
    if not path.is_dir():
        raise FileNotFoundError(f"event folder not found: {rel!r}")
    return path


# ── event.json ───────────────────────────────────────────────────────────
def _coord(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_event_json(folder: Path) -> Optional[dict[str, Any]]:
    meta_file = folder / "event.json"
    if not meta_file.is_file():
        return None
    try:
        data = json.loads(meta_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _LOGGER.warning("Could not parse %s: %s", meta_file, exc)
        return None
    if not isinstance(data, dict):
        return None

    lat = _coord(data.get("est_lat"))
    lon = _coord(data.get("est_lon"))
    # 0,0 is in the ocean near Africa — treat as missing (matches the engine).
    if lat is not None and lon is not None:
        if round(lat, 5) == 0 and round(lon, 5) == 0:
            lat = lon = None
    return {
        "timestamp": data.get("timestamp"),
        "city": data.get("city"),
        "street": data.get("street"),
        "reason": data.get("reason"),
        "camera": data.get("camera"),
        "lat": lat,
        "lon": lon,
    }


# ── Scanning ─────────────────────────────────────────────────────────────
def _build_event(folder: Path, rel: Path, clip_names: list[str]) -> dict[str, Any]:
    minutes: dict[str, dict[str, Any]] = {}
    total_size = 0
    for name in sorted(clip_names):
        match = CLIP_RE.match(name)
        if match is None:  # pragma: no cover - filtered by caller
            continue
        stamp = match["stamp"]
        try:
            size = (folder / name).stat().st_size
        except OSError:
            size = 0
        total_size += size
        entry = minutes.setdefault(
            stamp,
            {
                "key": stamp,
                "time": stamp[11:].replace("-", ":"),
                "cameras": [],
                "size": 0,
            },
        )
        entry["cameras"].append(match["camera"])
        entry["size"] += size

    rel_str = "." if str(rel) == "." else rel.as_posix()
    group = rel.parts[0] if rel.parts else "root"
    if group not in KNOWN_GROUPS and rel.parts:
        group = "Other"

    minute_list = [minutes[key] for key in sorted(minutes)]
    return {
        "id": encode_event_id(rel_str),
        "path": rel_str,
        "name": folder.name,
        "group": group,
        "minutes": minute_list,
        "minute_count": len(minute_list),
        "clip_count": sum(len(m["cameras"]) for m in minute_list),
        "total_size": total_size,
        "has_thumb": (folder / "thumb.png").is_file(),
        "metadata": parse_event_json(folder),
    }


def scan_events() -> list[dict[str, Any]]:
    """Walk INPUT_DIR and return all events, newest first."""
    root = config.INPUT_DIR
    events: list[dict[str, Any]] = []
    if not root.is_dir():
        return events

    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        rel = current.relative_to(root)
        depth = 0 if str(rel) == "." else len(rel.parts)
        if depth >= MAX_DEPTH:
            dirnames[:] = []
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))

        clips = [f for f in filenames if CLIP_RE.match(f)]
        if not clips:
            continue
        events.append(_build_event(current, rel, clips))

    def sort_key(event: dict[str, Any]) -> str:
        # Latest minute stamp gives a chronological ordering that also works
        # for RecentClips-style folders whose names are not timestamps.
        if event["minutes"]:
            return event["minutes"][-1]["key"]
        return event["name"]

    events.sort(key=sort_key, reverse=True)
    return events


def get_event(event_id: str) -> dict[str, Any]:
    """Rescan a single event folder by id."""
    folder = event_dir_from_id(event_id)
    root = config.INPUT_DIR.resolve()
    rel = Path(".") if folder == root else folder.relative_to(root)
    clips = [f.name for f in folder.iterdir() if f.is_file() and CLIP_RE.match(f.name)]
    if not clips:
        raise FileNotFoundError(f"no clips found in event {event_id!r}")
    return _build_event(folder, rel, clips)


def minute_files(
    folder: Path,
    minute_keys: Optional[list[str]] = None,
    cameras: Optional[list[str]] = None,
) -> list[Path]:
    """Return clip files in an event folder filtered by minute and camera."""
    wanted_minutes = set(minute_keys) if minute_keys else None
    wanted_cameras = set(cameras) if cameras else None
    files: list[Path] = []
    for entry in sorted(folder.iterdir()):
        match = CLIP_RE.match(entry.name)
        if match is None or not entry.is_file():
            continue
        if wanted_minutes is not None and match["stamp"] not in wanted_minutes:
            continue
        if wanted_cameras is not None and match["camera"] not in wanted_cameras:
            continue
        files.append(entry)
    return files
