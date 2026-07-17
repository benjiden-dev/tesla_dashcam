"""Configuration for the tesla_dashcam web UI backend.

Everything is driven by environment variables so the same code runs in the
container (where /data, /output and /cache are fixed mounts) and in local
development.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Native macOS runs use Apple's VideoToolbox instead of VAAPI render nodes.
IS_DARWIN: bool = sys.platform == "darwin"


def _path_env(name: str, default: str) -> Path:
    return Path(os.environ.get(name, default)).expanduser()


# Directories (fixed container mounts by default, overridable for development).
INPUT_DIR: Path = _path_env("INPUT_DIR", "/data")
OUTPUT_DIR: Path = _path_env("OUTPUT_DIR", "/output")
CACHE_DIR: Path = _path_env("CACHE_DIR", "/cache")

STAGING_DIR: Path = CACHE_DIR / "staging"
PREVIEW_DIR: Path = CACHE_DIR / "previews"
THUMB_DIR: Path = CACHE_DIR / "thumbs"
MAP_DIR: Path = CACHE_DIR / "maps"
TMP_DIR: Path = CACHE_DIR / "tmp"
JOBS_FILE: Path = CACHE_DIR / "jobs.json"

# Engine invocation. The console script is installed with the package inside
# the container; for development point ENGINE_CMD at e.g.
# "python3.11 -m tesla_dashcam" and ENGINE_CWD at the repository root.
ENGINE_CMD: list[str] = os.environ.get("ENGINE_CMD", "tesla_dashcam").split()
ENGINE_CWD: str | None = os.environ.get("ENGINE_CWD") or None

FFMPEG: str = os.environ.get("FFMPEG", "ffmpeg")
FFPROBE: str = os.environ.get("FFPROBE", "ffprobe")

# Hardware acceleration. The engine hardcodes /dev/dri/renderD128; compose
# maps the desired host render node onto that container path.
RENDER_NODE: str = os.environ.get("RENDER_NODE", "/dev/dri/renderD128")
DEFAULT_GPU_TYPE: str = os.environ.get("GPU_TYPE", "vaapi")

# Map tiles (OpenStreetMap standard tiles by default). Tiles are cached on
# disk and fetched with an identifying User-Agent per the OSM tile policy.
TILE_URL: str = os.environ.get(
    "MAP_TILE_URL", "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png"
)
MAP_USER_AGENT: str = os.environ.get(
    "MAP_USER_AGENT",
    "tesla-dashcam-webui/1.0 (self-hosted; "
    "+https://github.com/benjiden-dev/tesla_dashcam)",
)

PORT: int = int(os.environ.get("PORT", "8088"))

# Maximum number of engine log lines kept in memory per job.
LOG_TAIL_LIMIT: int = int(os.environ.get("LOG_TAIL_LIMIT", "4000"))


def ensure_dirs() -> None:
    """Create all cache directories."""
    for directory in (STAGING_DIR, PREVIEW_DIR, THUMB_DIR, MAP_DIR, TMP_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def gpu_available() -> bool:
    """True when hardware encoding is available.

    macOS: VideoToolbox ships with the OS (always available natively).
    Linux: requires the VAAPI render node inside the container.
    """
    if IS_DARWIN:
        return True
    return os.path.exists(RENDER_NODE)


def gpu_backend() -> str:
    """Human-readable name of the hardware encode backend."""
    if IS_DARWIN:
        return "VideoToolbox"
    return DEFAULT_GPU_TYPE.upper()


def gpu_badge() -> str | None:
    """Short status label for the UI header (None = CPU only)."""
    if not gpu_available():
        return None
    if IS_DARWIN:
        return "VideoToolbox"
    return f"{gpu_backend()} · {RENDER_NODE.rsplit('/', 1)[-1]}"
