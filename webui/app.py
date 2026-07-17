"""Tesla Dashcam Web UI — FastAPI application.

Serves the built React SPA and a JSON API around the tesla_dashcam engine:
event scanning with per-minute selection, a job queue with structured SSE
progress, engine-true first-frame previews, output playback and map burn-in.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import subprocess
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from . import config, engine, jobs, maptile, outputs, preview, scanner

_LOGGER = logging.getLogger(__name__)

try:
    from tesla_dashcam import __version__ as _engine_version  # type: ignore
    ENGINE_VERSION = getattr(_engine_version, "VERSION_STR", None) or str(
        getattr(_engine_version, "VERSION", "")
    )
except Exception:  # noqa: BLE001 - engine not importable in dev is fine
    ENGINE_VERSION = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    config.ensure_dirs()
    jobs.get_manager()
    yield


app = FastAPI(title="Tesla Dashcam Web UI", lifespan=lifespan)


# ── Models ───────────────────────────────────────────────────────────────
class EventSelection(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    minutes: Optional[list[str]] = None  # None/omitted = all minutes


class JobRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    events: list[EventSelection] = Field(min_length=1)
    settings: dict[str, Any] = Field(default_factory=dict)
    map_overlay: Optional[dict[str, Any]] = None
    delete_input: bool = False


class PreviewRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    event_id: str
    minute: str
    settings: dict[str, Any] = Field(default_factory=dict)


class CliPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    settings: dict[str, Any] = Field(default_factory=dict)
    map_overlay: Optional[dict[str, Any]] = None


def _sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# ── Config / meta ────────────────────────────────────────────────────────
@app.get("/api/config")
def get_config() -> dict[str, Any]:
    return {
        "input_dir": str(config.INPUT_DIR),
        "output_dir": str(config.OUTPUT_DIR),
        "gpu_available": config.gpu_available(),
        "gpu_backend": config.gpu_backend(),
        "gpu_badge": config.gpu_badge(),
        "platform": "darwin" if config.IS_DARWIN else "linux",
        "render_node": config.RENDER_NODE,
        "default_gpu_type": config.DEFAULT_GPU_TYPE,
        "engine_version": ENGINE_VERSION,
        "defaults": engine.DEFAULT_SETTINGS,
        "map_overlay_defaults": maptile.DEFAULT_MAP_OVERLAY,
        "layouts": list(engine.LAYOUTS),
        "qualities": list(engine.QUALITIES),
        "compressions": list(engine.COMPRESSIONS),
        "encodings": list(engine.ENCODINGS),
        "gpu_types": list(engine.GPU_TYPES),
        "cameras": list(scanner.CAMERAS),
    }


# ── Events ───────────────────────────────────────────────────────────────
@app.get("/api/events")
def list_events() -> list[dict[str, Any]]:
    return scanner.scan_events()


@app.get("/api/events/{event_id}/thumb")
def event_thumb(
    event_id: str, minute: Optional[str] = None, camera: str = "front"
) -> FileResponse:
    try:
        folder = scanner.event_dir_from_id(event_id)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # Tesla writes a thumb.png alongside the clips — use it when present.
    thumb_png = folder / "thumb.png"
    if minute is None and thumb_png.is_file():
        return FileResponse(thumb_png, media_type="image/png")

    files = scanner.minute_files(folder, [minute] if minute else None, [camera])
    if not files:
        files = scanner.minute_files(folder, [minute] if minute else None)
    if not files:
        raise HTTPException(status_code=404, detail="no clips in event")
    source = files[0]

    stat = source.stat()
    key = hashlib.md5(
        f"{source}:{stat.st_mtime_ns}:{stat.st_size}".encode()
    ).hexdigest()[:16]
    cached = config.THUMB_DIR / f"ev_{key}.jpg"
    if not cached.exists():
        tmp = cached.with_suffix(".tmp.jpg")
        try:
            subprocess.run(
                [
                    config.FFMPEG,
                    "-y",
                    "-loglevel",
                    "error",
                    "-i",
                    str(source),
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
                timeout=60,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise HTTPException(
                status_code=500, detail="thumbnail extraction failed"
            ) from exc
        tmp.replace(cached)
    return FileResponse(cached, media_type="image/jpeg")


# ── Map ──────────────────────────────────────────────────────────────────
@app.get("/api/map/preview")
def map_preview(event_id: str, zoom: int = 16, size: int = 560):
    try:
        folder = scanner.event_dir_from_id(event_id)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    metadata = scanner.parse_event_json(folder) or {}
    lat, lon = metadata.get("lat"), metadata.get("lon")
    if lat is None or lon is None:
        raise HTTPException(status_code=404, detail="event has no GPS coordinates")
    size = max(128, min(int(size), 1024))
    zoom = max(3, min(int(zoom), 19))
    try:
        png = maptile.render_event_map(lat, lon, width=size, height=size, zoom=zoom)
    except Exception as exc:  # noqa: BLE001 - tile server/network issues
        _LOGGER.exception("Map render failed")
        raise HTTPException(status_code=502, detail=f"map render failed: {exc}") from exc
    return FileResponse(png, media_type="image/png")


# ── Previews ─────────────────────────────────────────────────────────────
@app.post("/api/preview")
def create_preview(request: PreviewRequest) -> dict[str, Any]:
    try:
        folder = scanner.event_dir_from_id(request.event_id)
        rel = scanner.decode_event_id(request.event_id)
        key, cached = preview.render_preview(
            folder, rel, request.minute, request.settings
        )
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (RuntimeError, subprocess.SubprocessError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"key": key, "url": f"/api/preview/{key}.jpg", "cached": cached}


@app.get("/api/preview/{key}.jpg")
def get_preview(key: str) -> FileResponse:
    path = preview.preview_path("".join(c for c in key if c.isalnum()))
    if not path.exists():
        raise HTTPException(status_code=404, detail="preview not found")
    return FileResponse(path, media_type="image/jpeg")


# ── Jobs ─────────────────────────────────────────────────────────────────
@app.post("/api/jobs", status_code=201)
def create_job(request: JobRequest) -> dict[str, Any]:
    manager = jobs.get_manager()
    try:
        job = manager.submit(request.model_dump())
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return job.to_dict()


@app.get("/api/jobs")
def list_jobs() -> list[dict[str, Any]]:
    return jobs.get_manager().list_jobs()


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str, log_since: Optional[int] = None) -> dict[str, Any]:
    job = jobs.get_manager().get(job_id)
    if job is None:
        for entry in jobs.get_manager().history:
            if entry["id"] == job_id:
                return entry
        raise HTTPException(status_code=404, detail="job not found")
    return job.to_dict(log_since=log_since)


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> dict[str, Any]:
    if not jobs.get_manager().cancel(job_id):
        raise HTTPException(status_code=409, detail="job not cancellable")
    return {"status": "cancelling"}


@app.get("/api/jobs/{job_id}/stream")
async def stream_job(job_id: str) -> StreamingResponse:
    manager = jobs.get_manager()
    if manager.get(job_id) is None:
        raise HTTPException(status_code=404, detail="job not found")

    async def generator():
        last_version = -1
        last_log = 0
        while True:
            job = manager.get(job_id)
            if job is None:
                yield _sse("done", "gone")
                return
            if job.version != last_version:
                last_version = job.version
                for line in job.log[last_log:]:
                    yield _sse("log", line)
                last_log = len(job.log)
                yield _sse("progress", job.to_dict())
            if job.status in jobs.TERMINAL_STATES:
                yield _sse("done", job.status)
                return
            await asyncio.sleep(0.4)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── CLI preview ──────────────────────────────────────────────────────────
@app.post("/api/cli_preview")
def cli_preview(request: CliPreviewRequest) -> dict[str, str]:
    settings = dict(request.settings)
    overlay = maptile.normalized_overlay(request.map_overlay)
    if overlay["enabled"]:
        settings["merge"] = False
    args = engine.build_engine_args(
        "<staged selection>",
        config.OUTPUT_DIR,
        settings,
        gpu_available=config.gpu_available(),
    )
    return {"cli": engine.format_cli(args)}


# ── Outputs ──────────────────────────────────────────────────────────────
@app.get("/api/outputs")
def get_outputs() -> list[dict[str, Any]]:
    return outputs.list_outputs()


@app.get("/api/outputs/file/{rel_path:path}")
def get_output_file(rel_path: str) -> FileResponse:
    try:
        path = outputs.resolve_output(rel_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not path.is_file():
        raise HTTPException(status_code=404, detail="output not found")
    return FileResponse(path, media_type="video/mp4", filename=path.name,
                        content_disposition_type="inline")


@app.delete("/api/outputs/file/{rel_path:path}")
def remove_output(rel_path: str) -> dict[str, Any]:
    try:
        outputs.delete_output(rel_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="output not found") from exc
    return {"deleted": rel_path}


@app.get("/api/outputs/thumb/{rel_path:path}")
def get_output_thumb(rel_path: str) -> FileResponse:
    try:
        thumb = outputs.output_thumb(rel_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="output not found") from exc
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise HTTPException(status_code=500, detail="thumbnail failed") from exc
    return FileResponse(thumb, media_type="image/jpeg")


# ── SPA ──────────────────────────────────────────────────────────────────
_DIST = Path(__file__).parent / "static" / "dist"
if _DIST.is_dir():
    app.mount("/", StaticFiles(directory=_DIST, html=True), name="spa")
else:  # pragma: no cover - developer convenience
    @app.get("/")
    def dev_index() -> JSONResponse:
        return JSONResponse(
            {
                "message": "Frontend build missing. Run: cd webui/frontend && "
                "npm install && npm run build",
                "api": "/docs",
            }
        )
