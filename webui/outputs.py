"""List, thumbnail, serve and delete rendered movies in the output folder."""

from __future__ import annotations

import hashlib
import logging
import os
import subprocess
from pathlib import Path
from typing import Any

from . import config

_LOGGER = logging.getLogger(__name__)

VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv"}


def resolve_output(rel_path: str) -> Path:
    """Resolve a relative output path safely inside OUTPUT_DIR."""
    root = config.OUTPUT_DIR.resolve()
    path = (root / rel_path).resolve()
    if path != root and root not in path.parents:
        raise ValueError(f"path escapes output dir: {rel_path!r}")
    return path


def rel_output(path: Path | str) -> str | None:
    """Relative form of an absolute output path (None when outside)."""
    try:
        return Path(path).resolve().relative_to(config.OUTPUT_DIR.resolve()).as_posix()
    except ValueError:
        return None


def list_outputs() -> list[dict[str, Any]]:
    root = config.OUTPUT_DIR
    entries: list[dict[str, Any]] = []
    if not root.is_dir():
        return entries
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for name in filenames:
            path = Path(dirpath) / name
            if path.suffix.lower() not in VIDEO_SUFFIXES:
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            entries.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "name": path.name,
                    "size": stat.st_size,
                    "mtime": int(stat.st_mtime),
                    "playable": path.suffix.lower() == ".mp4",
                }
            )
    entries.sort(key=lambda entry: entry["mtime"], reverse=True)
    return entries


def output_thumb(rel_path: str) -> Path:
    """Extract (and cache) a poster frame for an output video."""
    video = resolve_output(rel_path)
    if not video.is_file():
        raise FileNotFoundError(rel_path)
    stat = video.stat()
    key = hashlib.md5(f"{rel_path}:{stat.st_mtime_ns}:{stat.st_size}".encode())
    thumb = config.THUMB_DIR / f"out_{key.hexdigest()[:16]}.jpg"
    if thumb.exists():
        return thumb

    tmp = thumb.with_suffix(".tmp.jpg")
    subprocess.run(
        [
            config.FFMPEG,
            "-y",
            "-loglevel",
            "error",
            "-ss",
            "0.5",
            "-i",
            str(video),
            "-frames:v",
            "1",
            "-vf",
            "scale=480:-2",
            "-q:v",
            "5",
            str(tmp),
        ],
        check=True,
        capture_output=True,
        timeout=120,
    )
    tmp.replace(thumb)
    return thumb


def delete_output(rel_path: str) -> None:
    path = resolve_output(rel_path)
    if not path.is_file():
        raise FileNotFoundError(rel_path)
    path.unlink()
    _LOGGER.info("Deleted output %s", rel_path)
