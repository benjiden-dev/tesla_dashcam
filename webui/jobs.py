"""Job queue: stages input, runs the engine, tracks structured progress.

One worker thread processes jobs FIFO (a single ffmpeg/VAAPI pipeline at a
time). Each job:

1. stages the selected minutes as symlinks,
2. runs the engine subprocess, feeding stdout through ``EngineProgress``,
3. optionally burns the event map onto finished movies (post-pass),
4. optionally deletes source event folders — only after verified success.
"""

from __future__ import annotations

import json
import logging
import queue
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Optional

from . import config, engine, maptile, outputs, scanner, staging

_LOGGER = logging.getLogger(__name__)

TERMINAL_STATES = ("completed", "failed", "cancelled")
HISTORY_LIMIT = 100


class Job:
    def __init__(self, request: dict[str, Any]) -> None:
        self.id: str = uuid.uuid4().hex[:12]
        self.created_at: float = time.time()
        self.started_at: Optional[float] = None
        self.finished_at: Optional[float] = None
        self.status: str = "queued"
        self.request: dict[str, Any] = request
        self.progress: engine.EngineProgress = engine.EngineProgress()
        self.log: list[str] = []
        self.log_truncated: bool = False
        self.cli: Optional[str] = None
        self.outputs: list[str] = []
        self.deleted_inputs: list[str] = []
        self.delete_skipped: list[str] = []
        self.freed_bytes: int = 0
        self.error: Optional[str] = None
        self.version: int = 0
        self.cancel_requested: bool = False
        self._proc: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()

    def bump(self) -> None:
        self.version += 1

    def append_log(self, line: str) -> None:
        if len(self.log) >= config.LOG_TAIL_LIMIT:
            del self.log[: config.LOG_TAIL_LIMIT // 10]
            self.log_truncated = True
        self.log.append(line)

    def request_summary(self) -> dict[str, Any]:
        events = self.request.get("events", [])
        settings = self.request.get("settings") or {}
        return {
            "event_count": len(events),
            "event_names": [event.get("name") or event.get("id") for event in events][:8],
            "minute_count": sum(
                len(event.get("minutes") or []) or -1 for event in events
            ),
            "layout": settings.get("layout"),
            "map_overlay": bool((self.request.get("map_overlay") or {}).get("enabled")),
            "delete_input": bool(self.request.get("delete_input")),
        }

    def to_dict(self, log_since: Optional[int] = None) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "request": self.request_summary(),
            "progress": self.progress.to_dict(),
            "cli": self.cli,
            "outputs": self.outputs,
            "deleted_inputs": self.deleted_inputs,
            "delete_skipped": self.delete_skipped,
            "freed_bytes": self.freed_bytes,
            "error": self.error,
            "version": self.version,
            "log_length": len(self.log),
            "log_truncated": self.log_truncated,
        }
        if log_since is not None:
            data["log"] = self.log[log_since:]
        return data


class JobManager:
    def __init__(self) -> None:
        self.jobs: dict[str, Job] = {}
        self.order: list[str] = []
        self.history: list[dict[str, Any]] = []
        self._queue: "queue.Queue[str]" = queue.Queue()
        self._lock = threading.Lock()
        self._load_history()
        self._worker = threading.Thread(
            target=self._worker_loop, name="job-worker", daemon=True
        )
        self._worker.start()

    # ── public API ───────────────────────────────────────────────────────
    def submit(self, request: dict[str, Any]) -> Job:
        events = request.get("events") or []
        if not events:
            raise ValueError("select at least one event")

        for event in events:
            folder = scanner.event_dir_from_id(event["id"])
            event["name"] = folder.name
            minutes = event.get("minutes")
            if minutes is not None and len(minutes) == 0:
                raise ValueError(f"no minutes selected for event {folder.name!r}")
            if not scanner.minute_files(folder, minutes or None):
                raise ValueError(f"no clips found for selection in {folder.name!r}")

        map_overlay = maptile.normalized_overlay(request.get("map_overlay"))
        request["map_overlay"] = map_overlay
        settings = dict(request.get("settings") or {})
        if map_overlay["enabled"]:
            # Map burn-in is per event movie; merged movies span locations.
            settings["merge"] = False
        request["settings"] = settings
        request["delete_input"] = bool(request.get("delete_input"))

        job = Job(request)
        with self._lock:
            self.jobs[job.id] = job
            self.order.insert(0, job.id)
        self._queue.put(job.id)
        _LOGGER.info("Job %s queued (%d event(s))", job.id, len(events))
        return job

    def get(self, job_id: str) -> Optional[Job]:
        return self.jobs.get(job_id)

    def list_jobs(self) -> list[dict[str, Any]]:
        with self._lock:
            active = [self.jobs[job_id].to_dict() for job_id in self.order]
        return active + self.history

    def cancel(self, job_id: str) -> bool:
        job = self.jobs.get(job_id)
        if job is None or job.status in TERMINAL_STATES:
            return False
        job.cancel_requested = True
        if job.status == "queued":
            job.status = "cancelled"
            job.finished_at = time.time()
            job.bump()
            self._archive(job)
            return True
        proc = job._proc
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
            except OSError:  # pragma: no cover - race with process exit
                pass
        job.bump()
        return True

    def has_active(self) -> bool:
        return any(
            job.status in ("queued", "running") for job in self.jobs.values()
        )

    # ── worker ───────────────────────────────────────────────────────────
    def _worker_loop(self) -> None:
        while True:
            job_id = self._queue.get()
            job = self.jobs.get(job_id)
            if job is None or job.status != "queued":
                continue
            try:
                self._run(job)
            except Exception as exc:  # noqa: BLE001 - job isolation boundary
                _LOGGER.exception("Job %s crashed", job.id)
                job.status = "failed"
                job.error = str(exc)
                job.finished_at = time.time()
                job.bump()
            finally:
                self._archive(job)

    def _run(self, job: Job) -> None:
        job.status = "running"
        job.started_at = time.time()
        job.progress = engine.EngineProgress()
        job.bump()

        selections: list[dict[str, Any]] = []
        for event in job.request["events"]:
            selections.append(
                {
                    "dir": scanner.event_dir_from_id(event["id"]),
                    "minutes": event.get("minutes"),
                }
            )

        stage_root = staging.stage_job(job.id, selections)
        try:
            settings = job.request.get("settings") or {}
            args = engine.build_engine_args(
                stage_root,
                config.OUTPUT_DIR,
                settings,
                gpu_available=config.gpu_available(),
            )
            job.cli = engine.format_cli(args)
            job.bump()

            proc = subprocess.Popen(
                config.ENGINE_CMD + args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=config.ENGINE_CWD,
            )
            job._proc = proc

            assert proc.stdout is not None
            for raw_line in iter(proc.stdout.readline, ""):
                line = raw_line.rstrip("\n")
                job.append_log(line)
                changed = job.progress.feed(line)
                if changed or len(job.log) % 20 == 0:
                    job.bump()
                if job.cancel_requested and proc.poll() is None:
                    proc.terminate()

            return_code = proc.wait()
            job._proc = None

            if job.cancel_requested:
                job.status = "cancelled"
                job.progress.message = "Cancelled"
                return
            if return_code != 0:
                job.status = "failed"
                tail = "\n".join(job.log[-10:])
                job.error = f"engine exited with code {return_code}\n{tail}"
                return

            existing = [
                Path(path) for path in job.progress.outputs if Path(path).is_file()
            ]
            if not existing:
                job.status = "failed"
                detail = "; ".join(job.progress.errors[-3:])
                job.error = (
                    "engine finished without producing any output movies"
                    + (f": {detail}" if detail else "")
                )
                return

            map_overlay = job.request.get("map_overlay") or {}
            if map_overlay.get("enabled"):
                self._apply_map_overlays(job, selections, stage_root, map_overlay)

            job.outputs = [
                rel
                for rel in (outputs.rel_output(path) for path in existing)
                if rel is not None
            ]

            if job.request.get("delete_input"):
                self._delete_inputs(job, selections, stage_root)

            job.progress.phase = "done"
            job.progress.message = "Completed"
            job.status = "completed"
        finally:
            job.finished_at = time.time()
            staging.cleanup(stage_root)
            job._proc = None
            job.bump()

    # ── post steps ───────────────────────────────────────────────────────
    def _event_movie_for(
        self, job: Job, stage_root: Path, staged_name: str
    ) -> Optional[Path]:
        """Find the finished movie the engine reported for a staged folder."""
        for folder, movie in job.progress.event_outputs.items():
            if Path(folder).name == staged_name:
                movie_path = Path(movie)
                if movie_path.is_file():
                    return movie_path
        return None

    def _apply_map_overlays(
        self,
        job: Job,
        selections: list[dict[str, Any]],
        stage_root: Path,
        options: dict[str, Any],
    ) -> None:
        job.progress.phase = "map_overlay"
        crf = engine.QUALITY_CRF.get(
            (job.request.get("settings") or {}).get("quality", "LOWER"), 28
        )
        for selection in selections:
            metadata = scanner.parse_event_json(selection["dir"]) or {}
            lat, lon = metadata.get("lat"), metadata.get("lon")
            movie = self._event_movie_for(job, stage_root, selection["staged_name"])
            if movie is None:
                continue
            if lat is None or lon is None:
                job.progress.warnings.append(
                    f"No GPS in event.json for {selection['staged_name']}; "
                    "map overlay skipped."
                )
                job.bump()
                continue
            job.progress.message = f"Burning map into {movie.name}"
            job.bump()
            try:
                map_png = maptile.render_event_map(
                    lat, lon, zoom=int(options.get("zoom", 16))
                )
                maptile.overlay_map(
                    movie,
                    map_png,
                    corner=options.get("corner", "bottom_right"),
                    size_pct=float(options.get("size_pct", 0.22)),
                    opacity=float(options.get("opacity", 0.9)),
                    crf=crf,
                )
            except Exception as exc:  # noqa: BLE001 - keep job successful
                _LOGGER.exception("Map overlay failed for %s", movie)
                job.progress.warnings.append(
                    f"Map overlay failed for {movie.name}: {exc}"
                )
                job.bump()

    @staticmethod
    def _verify_movie(path: Optional[Path]) -> bool:
        """A movie counts as verified when it exists and ffprobe accepts it."""
        if path is None or not path.is_file() or path.stat().st_size < 10_000:
            return False
        try:
            maptile.probe_dimensions(path)
        except Exception:  # noqa: BLE001 - any probe failure means unverified
            return False
        return True

    def _delete_inputs(
        self, job: Job, selections: list[dict[str, Any]], stage_root: Path
    ) -> None:
        job.progress.phase = "cleanup"
        job.progress.message = "Deleting processed input"
        job.bump()

        merged_ok = any(
            self._verify_movie(Path(path))
            for path in job.progress.outputs
            if outputs.rel_output(path) in job.outputs
        )

        for selection in selections:
            staged_name = selection["staged_name"]
            source_dir: Path = selection["dir"]
            movie = self._event_movie_for(job, stage_root, staged_name)
            reported_ready = any(
                Path(folder).name == staged_name
                for folder in job.progress.event_outputs
            )
            verified = self._verify_movie(movie) or (reported_ready and merged_ok)
            if not verified:
                job.delete_skipped.append(source_dir.name)
                job.progress.warnings.append(
                    f"Skipped deleting {source_dir.name}: output not verified."
                )
                job.bump()
                continue
            try:
                freed = staging.directory_size(source_dir)
                shutil.rmtree(source_dir)
                job.freed_bytes += freed
                job.deleted_inputs.append(source_dir.name)
                _LOGGER.info(
                    "Deleted input folder %s (freed %d bytes)", source_dir, freed
                )
            except OSError as exc:
                job.delete_skipped.append(source_dir.name)
                job.progress.warnings.append(
                    f"Failed deleting {source_dir.name}: {exc}"
                )
            job.bump()

    # ── history ──────────────────────────────────────────────────────────
    def _archive(self, job: Job) -> None:
        if job.status not in TERMINAL_STATES:
            return
        entry = job.to_dict()
        entry.pop("log", None)
        with self._lock:
            if job.id in self.order:
                # Keep the most recent few full jobs in memory for the UI;
                # everything terminal also lands in persisted history.
                pass
            self.history = [h for h in self.history if h["id"] != job.id]
            self.history.insert(0, entry)
            self.history = self.history[:HISTORY_LIMIT]
            self._persist_history()
            # Drop finished jobs from the live map after a while: keep last 10.
            terminal_ids = [
                job_id
                for job_id in self.order
                if self.jobs[job_id].status in TERMINAL_STATES
            ]
            for old_id in terminal_ids[10:]:
                self.order.remove(old_id)
                self.jobs.pop(old_id, None)

    def _persist_history(self) -> None:
        try:
            config.JOBS_FILE.parent.mkdir(parents=True, exist_ok=True)
            config.JOBS_FILE.write_text(json.dumps(self.history, indent=1))
        except OSError as exc:  # pragma: no cover - disk issues
            _LOGGER.warning("Could not persist job history: %s", exc)

    def _load_history(self) -> None:
        try:
            if config.JOBS_FILE.is_file():
                self.history = json.loads(config.JOBS_FILE.read_text())[:HISTORY_LIMIT]
        except (OSError, json.JSONDecodeError) as exc:
            _LOGGER.warning("Could not load job history: %s", exc)
            self.history = []


MANAGER: Optional[JobManager] = None


def get_manager() -> JobManager:
    global MANAGER
    if MANAGER is None:
        MANAGER = JobManager()
    return MANAGER
