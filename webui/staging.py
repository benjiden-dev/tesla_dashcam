"""Stage selected event minutes for the engine.

Jobs get a staging folder of symlinks so the engine only sees the selected
one-minute clips — non-contiguous selections work without any engine changes.
Previews get short stream-copied trims instead so the engine encodes only a
couple of seconds.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional

from . import config
from .scanner import CLIP_RE, minute_files

_LOGGER = logging.getLogger(__name__)


def _fresh_dir(path: Path) -> Path:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    return path


def stage_job(job_id: str, selections: list[dict[str, Any]]) -> Path:
    """Create a staging root with one folder per selected event.

    Each ``selection`` is ``{"dir": Path, "minutes": [keys] | None}`` and gets
    a ``staged_name`` key set on it (unique folder name inside the staging
    root, which also becomes the output movie name).
    """
    root = _fresh_dir(config.STAGING_DIR / job_id)
    used_names: set[str] = set()

    for selection in selections:
        source_dir: Path = selection["dir"]
        name = source_dir.name
        if name in used_names:
            suffix = 2
            while f"{name}_{suffix}" in used_names:
                suffix += 1
            name = f"{name}_{suffix}"
        used_names.add(name)
        selection["staged_name"] = name

        staged_dir = root / name
        staged_dir.mkdir()

        files = minute_files(source_dir, selection.get("minutes") or None)
        if not files:
            raise ValueError(f"no clips selected in event folder {source_dir.name!r}")
        for file in files:
            (staged_dir / file.name).symlink_to(file.resolve())

        event_json = source_dir / "event.json"
        if event_json.is_file():
            shutil.copy2(event_json, staged_dir / "event.json")

    return root


def stage_preview(
    preview_id: str,
    event_dir: Path,
    minute_key: str,
    cameras: Optional[list[str]] = None,
    seconds: int = 3,
) -> Path:
    """Stage one minute as short stream-copied trims for a fast preview."""
    root = _fresh_dir(config.STAGING_DIR / f"preview-{preview_id}")

    files = minute_files(event_dir, [minute_key], cameras)
    if not files:
        raise ValueError(f"no clips found for minute {minute_key!r}")

    for file in files:
        subprocess.run(
            [
                config.FFMPEG,
                "-y",
                "-loglevel",
                "error",
                "-i",
                str(file),
                "-t",
                str(seconds),
                "-c",
                "copy",
                str(root / file.name),
            ],
            check=True,
            capture_output=True,
            timeout=60,
        )

    event_json = event_dir / "event.json"
    if event_json.is_file():
        shutil.copy2(event_json, root / "event.json")
    return root


def cleanup(path: Path) -> None:
    """Remove a staging folder, ignoring errors."""
    if path and path.exists():
        shutil.rmtree(path, ignore_errors=True)


def directory_size(path: Path) -> int:
    """Total size in bytes of all real files under path (symlinks excluded)."""
    total = 0
    for entry in path.rglob("*"):
        try:
            if entry.is_file() and not entry.is_symlink():
                total += entry.stat().st_size
        except OSError:
            continue
    return total
