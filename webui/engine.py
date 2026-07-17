"""Build tesla_dashcam engine arguments and parse its progress output.

The engine is a battle-tested CLI; the web UI drives it as a subprocess and
never imports its internals. This module owns the two contact surfaces:

* ``build_engine_args`` — translate a UI settings dict into engine argv.
* ``EngineProgress`` — a line-by-line parser of the engine's stdout that
  produces structured progress (phase, percentages, ETA, output files).
"""

from __future__ import annotations

import re
import shlex
import time
from pathlib import Path
from typing import Any, Optional

from . import config
from .scanner import CAMERAS

QUALITIES = ("LOWEST", "LOWER", "LOW", "MEDIUM", "HIGH")
COMPRESSIONS = (
    "ultrafast",
    "superfast",
    "veryfast",
    "faster",
    "fast",
    "medium",
    "slow",
    "slower",
    "veryslow",
)
ENCODINGS = ("x264", "x265")
LAYOUTS = (
    "FULLSCREEN",
    "WIDESCREEN",
    "MOSAIC",
    "PERSPECTIVE",
    "CROSS",
    "DIAMOND",
    "HORIZONTAL",
)
GPU_TYPES = ("vaapi", "intel", "qsv", "nvidia", "rpi")
VIEW_MODES = ("default", "mirror", "rear")

# CRF values the engine maps quality names to (software encoders only).
QUALITY_CRF = {"HIGH": 18, "MEDIUM": 20, "LOW": 23, "LOWER": 28, "LOWEST": 33}

# Map scanner camera names to the engine's exclusion flags.
CAMERA_FLAGS = {
    "front": "--no-front",
    "back": "--no-rear",
    "left_repeater": "--no-left",
    "right_repeater": "--no-right",
    "left_pillar": "--no-left-pillar",
    "right_pillar": "--no-right-pillar",
}

DEFAULT_SETTINGS: dict[str, Any] = {
    "layout": "FULLSCREEN",
    "perspective": False,
    "view_mode": "mirror",
    "swap": False,
    "background": "#000000",
    "cameras": {camera: True for camera in CAMERAS},
    "show_timestamp": True,
    "halign": None,
    "valign": None,
    "fontsize": None,
    "fontcolor": None,
    "font": None,
    "text_overlay_fmt": None,
    "motion_only": False,
    "speedup": None,
    "slowdown": None,
    "merge": True,
    "quality": "LOWER",
    "compression": "medium",
    "encoding": "x264",
    "fps": 24,
    "bitrate": None,  # GPU encoders only, e.g. "8M"
    "scale": None,
    "faststart": True,
    "skip_existing": False,
    "gpu": True,
    "gpu_type": "vaapi",
    "title_screen_map": False,
    "loglevel": "INFO",
}


def merged_settings(overrides: Optional[dict[str, Any]]) -> dict[str, Any]:
    """Overlay user settings on the defaults (cameras merged per key)."""
    settings = dict(DEFAULT_SETTINGS)
    settings["cameras"] = dict(DEFAULT_SETTINGS["cameras"])
    for key, value in (overrides or {}).items():
        if key == "cameras" and isinstance(value, dict):
            for camera, enabled in value.items():
                if camera in settings["cameras"]:
                    settings["cameras"][camera] = bool(enabled)
        elif key in settings:
            settings[key] = value
    return settings


def _choice(value: Any, allowed: tuple[str, ...], default: str) -> str:
    return value if value in allowed else default


def build_engine_args(
    source: Path | str,
    output: Path | str,
    settings: Optional[dict[str, Any]] = None,
    gpu_available: bool = True,
) -> list[str]:
    """Translate a settings dict into the engine's argv (excluding the cmd)."""
    s = merged_settings(settings)
    args: list[str] = [str(source), "--output", str(output)]

    args += ["--layout", _choice(s["layout"], LAYOUTS, "FULLSCREEN")]
    if s["perspective"]:
        args.append("--perspective")

    view_mode = _choice(s["view_mode"], VIEW_MODES, "mirror")
    if view_mode == "mirror":
        args.append("--mirror")
    elif view_mode == "rear":
        args.append("--rear")

    if s["swap"]:
        args.append("--swap")

    background = str(s.get("background") or "").lstrip("#").lower()
    if background and background != "000000":
        args += ["--background", background]

    for camera, flag in CAMERA_FLAGS.items():
        if not s["cameras"].get(camera, True):
            args.append(flag)

    if not s["show_timestamp"]:
        args.append("--no-timestamp")
    else:
        for key, flag in (
            ("halign", "--halign"),
            ("valign", "--valign"),
            ("fontsize", "--fontsize"),
            ("fontcolor", "--fontcolor"),
            ("font", "--font"),
            ("text_overlay_fmt", "--text_overlay_fmt"),
        ):
            if s.get(key) not in (None, ""):
                args += [flag, str(s[key])]

    if s["motion_only"]:
        args.append("--motion_only")
    if s.get("speedup"):
        args += ["--speedup", str(s["speedup"])]
    if s.get("slowdown"):
        args += ["--slowdown", str(s["slowdown"])]
    if s["merge"]:
        args.append("--merge")

    args += ["--quality", _choice(s["quality"], QUALITIES, "LOWER")]
    args += ["--compression", _choice(s["compression"], COMPRESSIONS, "medium")]
    args += ["--encoding", _choice(s["encoding"], ENCODINGS, "x264")]
    if s.get("fps") and int(s["fps"]) != 24:
        args += ["--fps", str(int(s["fps"]))]
    if s.get("scale"):
        args += ["--scale", str(s["scale"])]
    if not s["faststart"]:
        args.append("--no-faststart")
    if s["skip_existing"]:
        args.append("--skip_existing")

    if s["gpu"] and gpu_available:
        args += ["--gpu", "--gpu_type", _choice(s.get("gpu_type"), GPU_TYPES, "vaapi")]
        if s.get("bitrate"):
            args += ["--bitrate", str(s["bitrate"])]
    else:
        args.append("--no-gpu")

    if s["title_screen_map"]:
        args.append("--title_screen_map")
    if s.get("loglevel") and s["loglevel"] != "INFO":
        args += ["--loglevel", str(s["loglevel"])]

    # Always: no update checks or desktop notifications from a container, and
    # keep intermediate files out of the (staged) source folders.
    args += ["--no-check_for_update", "--no-notification"]
    args += ["--temp_dir", str(config.TMP_DIR)]
    return args


def format_cli(args: list[str]) -> str:
    """Human-readable engine invocation for the UI's command preview."""
    display = " ".join(config.ENGINE_CMD) if config.ENGINE_CMD else "tesla_dashcam"
    return f"{display} {shlex.join(args)}"


# ── Progress parsing ─────────────────────────────────────────────────────
# The engine prints (no timestamp prefix unless --display_ts is passed):
#   Scanning 1 folder(s)
#   Scanned 1/1.
#   There are 2 event folder(s) with 13 clips to process.
#   \t\tProcessing clip 1/10 from 07/10/26 14:32:15 and 59 seconds long.
#   \t\tCreating movie /out/2026-07-10_14-30-11.mp4, please be patient.
#   \tMovie /out/... for folder /staged/... with duration 0:09:58 is ready.
#   \tCreating movie /out/merged.mp4, please be patient.        (merge phase)
#    Movie /out/merged.mp4 with duration ... has been created.
#   Following movies have been created:  (+ \t/out/x.mp4 with duration ...)
#   Processing of movies has completed.

RE_SCANNING = re.compile(r"^Scanning (\d+) folder")
RE_SCANNED = re.compile(r"^Scanned (\d+)/(\d+)")
RE_TOTALS = re.compile(
    r"^There are (\d+) event folder\(s\) with (\d+) clips to process"
)
RE_EVENT_HEADER = re.compile(
    r"^\t*Processing (\d+) clips in folder (.+?) \((\d+)/(\d+)\)"
)
RE_CLIP = re.compile(
    r"^\t*Processing clip (\d+)/(\d+) from (.+?) and (\d+) seconds long"
)
RE_CREATING = re.compile(r"^(\t*)\s*Creating movie (.+?), please be patient")
RE_EVENT_READY = re.compile(
    r"^\t*Movie (.+?) for folder (.+?) with duration (.+?) is ready"
)
RE_FINAL_SINGLE = re.compile(r"^\s*Movie (.+?) with duration .* has been created")
RE_FINAL_MULTI_HEADER = re.compile(r"Following movies have been created")
RE_FINAL_MULTI_ITEM = re.compile(r"^\t(.+?) with duration ")
RE_COMPLETED = re.compile(
    r"Processing of movies has completed|All folders have been processed"
)
RE_MOVIE_ERROR = re.compile(
    r"Error trying to create (movie|clip|title)|No valid clips to merge found"
    r"|No clips found"
)
RE_GPU_DISABLED = re.compile(r"GPU acceleration not available")

TERMINAL_PHASES = ("done",)


class EngineProgress:
    """Incremental parser turning engine stdout into structured progress."""

    def __init__(self) -> None:
        self.phase: str = "starting"
        self.message: str = "Starting engine"
        self.total_events: int = 0
        self.total_clips: int = 0
        self.events_done: int = 0
        self.current_event: int = 0
        self.clip_in_event: int = 0
        self.clips_in_event: int = 0
        self._clips_before_event: int = 0
        self.outputs: list[str] = []
        self.event_outputs: dict[str, str] = {}  # staged folder -> movie file
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.started_at: float = time.monotonic()
        self._in_multi_list: bool = False

    # -- derived ---------------------------------------------------------
    @property
    def clips_done(self) -> int:
        return self._clips_before_event + max(self.clip_in_event - 1, 0)

    @property
    def percent(self) -> float:
        if self.phase == "done":
            return 100.0
        if self.phase == "map_overlay":
            return 96.0
        if self.phase == "cleanup":
            return 98.0
        if self.total_clips <= 0:
            return 0.0
        encode = min(self.clips_done / self.total_clips, 1.0) * 92.0
        if self.phase == "merging":
            encode = max(encode, 94.0)
        return round(encode, 1)

    @property
    def eta_seconds(self) -> Optional[int]:
        done = self.clips_done
        if done < 1 or self.total_clips <= 0 or self.phase == "done":
            return None
        elapsed = time.monotonic() - self.started_at
        remaining = max(self.total_clips - done, 0)
        return int(elapsed / done * remaining)

    # -- feeding ---------------------------------------------------------
    def feed(self, line: str) -> bool:
        """Consume one stdout line; return True when progress changed."""
        if not line.strip():
            return False

        if match := RE_SCANNING.match(line):
            self.phase = "scanning"
            self.message = f"Scanning {match[1]} folder(s)"
            return True

        if RE_SCANNED.match(line):
            return False

        if match := RE_TOTALS.match(line):
            self.phase = "processing"
            self.total_events = int(match[1])
            self.total_clips = int(match[2])
            self.message = (
                f"{self.total_events} event(s), {self.total_clips} clip(s) to process"
            )
            return True

        if match := RE_EVENT_HEADER.match(line):
            self.phase = "processing"
            self.current_event = int(match[3])
            self.clips_in_event = int(match[1])
            self.clip_in_event = 0
            self.message = (
                f"Event {self.current_event}/{max(self.total_events, 1)} — "
                f"{Path(match[2]).name}"
            )
            return True

        if match := RE_CLIP.match(line):
            clip_number = int(match[1])
            self.phase = "processing"
            if clip_number == 1 or self.current_event == 0:
                self.current_event = self.events_done + 1
            self.clip_in_event = clip_number
            self.clips_in_event = int(match[2])
            self.message = (
                f"Event {self.current_event}/{max(self.total_events, 1)} — "
                f"clip {clip_number}/{match[2]}"
            )
            return True

        if match := RE_CREATING.match(line):
            tabs = match[1]
            if tabs.count("\t") >= 2:
                self.phase = "assembling"
                self.message = f"Assembling event movie {Path(match[2]).name}"
            else:
                self.phase = "merging"
                self.message = f"Merging into {Path(match[2]).name}"
            return True

        if match := RE_EVENT_READY.match(line):
            movie, folder = match[1].strip(), match[2].strip()
            self.event_outputs[folder] = movie
            if movie not in self.outputs:
                self.outputs.append(movie)
            self.events_done += 1
            self._clips_before_event += self.clips_in_event or 0
            self.clip_in_event = 0
            self.clips_in_event = 0
            self.message = f"Event movie ready ({self.events_done}/{max(self.total_events, 1)})"
            return True

        if RE_FINAL_MULTI_HEADER.search(line):
            self._in_multi_list = True
            return False

        if self._in_multi_list and (match := RE_FINAL_MULTI_ITEM.match(line)):
            movie = match[1].strip()
            if movie not in self.outputs:
                self.outputs.append(movie)
            return True

        if match := RE_FINAL_SINGLE.match(line):
            movie = match[1].strip()
            if movie not in self.outputs:
                self.outputs.append(movie)
            return True

        if RE_COMPLETED.search(line):
            self.phase = "done"
            self.message = "Engine finished"
            return True

        if RE_MOVIE_ERROR.search(line):
            self.errors.append(line.strip())
            self.message = "Engine reported an error"
            return True

        if RE_GPU_DISABLED.search(line):
            self.warnings.append(line.strip())
            return True

        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase": self.phase,
            "message": self.message,
            "percent": self.percent,
            "eta_seconds": self.eta_seconds,
            "total_events": self.total_events,
            "total_clips": self.total_clips,
            "clips_done": self.clips_done,
            "events_done": self.events_done,
            "current_event": self.current_event,
            "clip_in_event": self.clip_in_event,
            "clips_in_event": self.clips_in_event,
            "outputs": list(self.outputs),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }
