#!/usr/bin/env python3
"""End-to-end test for the web UI backend against the real engine.

Generates tiny synthetic TeslaCam footage with ffmpeg, then exercises the
whole pipeline: scanning, minute-selective staging, a real engine run via the
job manager, first-frame preview rendering, map overlay compositing and
verified input deletion.

Requires ffmpeg and a Python >= 3.13 interpreter for the engine (the web UI
backend itself runs on 3.10+). Skips politely when prerequisites are missing.

Run: python3 tests/e2e_webui.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


def find_engine_python() -> str | None:
    candidates = [os.environ.get("E2E_ENGINE_PY"), "python3.13", "python3"]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            result = subprocess.run(
                [candidate, "-c", "import sys; sys.exit(0 if sys.version_info >= (3, 13) else 1)"],
                capture_output=True,
                timeout=15,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode == 0:
            return candidate
    return None


if shutil.which("ffmpeg") is None:
    print("e2e_webui: SKIP (ffmpeg not found)")
    sys.exit(0)

ENGINE_PY = find_engine_python()
if ENGINE_PY is None:
    print("e2e_webui: SKIP (no Python >= 3.13 for the engine)")
    sys.exit(0)

TMP = Path(tempfile.mkdtemp(prefix="webui-e2e-"))
os.environ["INPUT_DIR"] = str(TMP / "input")
os.environ["OUTPUT_DIR"] = str(TMP / "output")
os.environ["CACHE_DIR"] = str(TMP / "cache")
os.environ["ENGINE_CMD"] = f"{ENGINE_PY} -m tesla_dashcam"
os.environ["ENGINE_CWD"] = str(REPO_ROOT)

from webui import config, jobs, maptile, preview, scanner  # noqa: E402

CLIP_SECONDS = 8


def gen_clip(path: Path, seed: int) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"testsrc2=duration={CLIP_SECONDS}:size=448x320:rate=24",
            "-vf",
            f"hue=h={seed * 40}",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "30",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        check=True,
        capture_output=True,
        timeout=120,
    )


def make_event(folder: Path, minutes: list[str], cameras: list[str], meta: dict | None) -> None:
    folder.mkdir(parents=True)
    for index, minute in enumerate(minutes):
        for camera in cameras:
            gen_clip(folder / f"{minute}-{camera}.mp4", seed=index + len(camera))
    if meta is not None:
        (folder / "event.json").write_text(json.dumps(meta))


def probe_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    return float(json.loads(result.stdout)["format"]["duration"])


def base_settings() -> dict:
    # show_timestamp off: static ffmpeg builds without drawtext (as found in
    # some CI sandboxes) would fail every clip otherwise. The container's
    # Debian ffmpeg has drawtext, and hermetic arg tests cover the flags.
    settings = {
        "quality": "LOWEST",
        "compression": "ultrafast",
        "merge": False,
        "gpu": True,  # no render node in CI -> auto CPU fallback
        "layout": "FULLSCREEN",
        "show_timestamp": False,
    }
    return settings


def wait_for(job, timeout: int = 600) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if job.status in jobs.TERMINAL_STATES:
            return
        time.sleep(1)
    raise AssertionError(f"job {job.id} timed out (status={job.status})")


def main() -> None:
    config.ensure_dirs()
    root = config.INPUT_DIR

    print(f"e2e_webui: generating synthetic footage (engine: {ENGINE_PY})")
    minutes_a = ["2026-07-10_14-28-01", "2026-07-10_14-29-01", "2026-07-10_14-30-01"]
    make_event(
        root / "SavedClips" / "2026-07-10_14-30-11",
        minutes_a,
        ["front", "back", "left_repeater"],
        {
            "timestamp": "2026-07-10T14:30:11",
            "city": "Denver",
            "est_lat": "39.7392",
            "est_lon": "-104.9903",
            "reason": "user_interaction_honk",
        },
    )
    make_event(
        root / "SentryClips" / "2026-07-11_09-15-22",
        ["2026-07-11_09-14-22"],
        ["front", "back"],
        {"timestamp": "2026-07-11T09:15:22", "est_lat": 39.75, "est_lon": -104.99},
    )

    events = scanner.scan_events()
    assert len(events) == 2, f"expected 2 events, got {len(events)}"
    saved = next(e for e in events if e["group"] == "SavedClips")
    sentry = next(e for e in events if e["group"] == "SentryClips")

    # ── Job 1: minute-selective processing (skip the middle minute) ──────
    manager = jobs.get_manager()
    job = manager.submit(
        {
            "events": [
                {"id": saved["id"], "minutes": [minutes_a[0], minutes_a[2]]},
                {"id": sentry["id"], "minutes": None},
            ],
            "settings": base_settings(),
            "map_overlay": {"enabled": False},
            "delete_input": False,
        }
    )
    print(f"e2e_webui: job {job.id} running…")
    wait_for(job)
    assert job.status == "completed", f"job failed: {job.error}\n" + "\n".join(job.log[-20:])
    assert job.progress.total_events == 2, job.progress.to_dict()
    assert job.progress.total_clips == 3, job.progress.to_dict()
    assert job.progress.percent == 100.0
    assert len(job.outputs) == 2, job.outputs

    for rel in job.outputs:
        out_path = config.OUTPUT_DIR / rel
        assert out_path.is_file() and out_path.stat().st_size > 10_000, rel

    # The engine names movies by time range; map back via the folder mapping.
    saved_out = next(
        Path(movie)
        for folder, movie in job.progress.event_outputs.items()
        if Path(folder).name == "2026-07-10_14-30-11"
    )
    assert saved_out.is_file()
    duration = probe_duration(saved_out)
    # Two selected minutes of ~8s each; the skipped middle minute must be absent.
    assert 10 <= duration <= 22, f"unexpected duration {duration}s (minute selection broken?)"
    print(f"e2e_webui: job outputs OK (selected-minutes duration {duration:.1f}s)")

    # ── First-frame preview through the real engine ──────────────────────
    key, cached = preview.render_preview(
        scanner.event_dir_from_id(saved["id"]),
        saved["path"],
        minutes_a[0],
        base_settings(),
    )
    preview_file = preview.preview_path(key)
    assert preview_file.is_file() and preview_file.stat().st_size > 1_000
    assert cached is False
    _, cached2 = preview.render_preview(
        scanner.event_dir_from_id(saved["id"]), saved["path"], minutes_a[0], base_settings()
    )
    assert cached2 is True
    print(f"e2e_webui: preview OK ({preview_file.stat().st_size} bytes, cache hit verified)")

    # ── Map overlay post-pass (local PNG, no network) ────────────────────
    from PIL import Image, ImageDraw

    map_png = config.MAP_DIR / "fake_map.png"
    image = Image.new("RGB", (280, 280), (240, 240, 235))
    draw = ImageDraw.Draw(image)
    draw.ellipse((120, 120, 160, 160), fill=(232, 33, 39))
    image.save(map_png)

    size_before = saved_out.stat().st_size
    maptile.overlay_map(saved_out, map_png, corner="bottom_right", size_pct=0.25, opacity=0.9)
    assert saved_out.is_file() and saved_out.stat().st_size > 10_000
    assert abs(probe_duration(saved_out) - duration) < 2.0
    print(f"e2e_webui: map overlay OK ({size_before} -> {saved_out.stat().st_size} bytes)")

    # Real tile fetch is network-dependent; try briefly and tolerate failure.
    import socket

    socket.setdefaulttimeout(10)
    try:
        tile = maptile.render_event_map(39.7392, -104.9903, width=280, height=280, zoom=13)
        print(f"e2e_webui: live OSM tile fetch OK ({tile.name})")
    except Exception as exc:  # noqa: BLE001
        print(f"e2e_webui: live OSM tile fetch skipped ({type(exc).__name__})")
    finally:
        socket.setdefaulttimeout(None)

    # ── Job 2: delete input after verified success ───────────────────────
    delete_dir = root / "SavedClips" / "2026-07-12_10-00-00"
    make_event(delete_dir, ["2026-07-12_09-59-00"], ["front"], {"city": "Denver"})
    events = scanner.scan_events()
    target = next(e for e in events if e["name"] == "2026-07-12_10-00-00")

    job2 = manager.submit(
        {
            "events": [{"id": target["id"], "minutes": None}],
            "settings": base_settings(),
            "map_overlay": {"enabled": False},
            "delete_input": True,
        }
    )
    wait_for(job2)
    assert job2.status == "completed", f"job2 failed: {job2.error}\n" + "\n".join(job2.log[-20:])
    assert not delete_dir.exists(), "input folder was not deleted"
    assert job2.freed_bytes > 0
    assert job2.deleted_inputs == ["2026-07-12_10-00-00"]
    print(f"e2e_webui: verified delete OK (freed {job2.freed_bytes} bytes)")

    # A failed/unverified job must never delete input — simulate by asking to
    # delete with an impossible selection guard: cancelled before start is
    # covered by unit paths; here we just confirm skip list stays empty.
    assert job2.delete_skipped == []

    # ── Job 3: delete_input on a root-level event must NOT delete the root ──
    # Loose clips directly in INPUT_DIR scan as an event whose folder IS the
    # input dir; deletion must be skipped with a warning (regression guard for
    # the Gemini-flagged critical bug).
    gen_clip(root / "2026-07-13_08-00-00-front.mp4", seed=5)
    events = scanner.scan_events()
    root_event = next(e for e in events if e["path"] == ".")
    job3 = manager.submit(
        {
            "events": [{"id": root_event["id"], "minutes": None}],
            "settings": base_settings(),
            "map_overlay": {"enabled": False},
            "delete_input": True,
        }
    )
    wait_for(job3)
    assert job3.status == "completed", f"job3 failed: {job3.error}\n" + "\n".join(job3.log[-20:])
    assert root.is_dir(), "INPUT ROOT WAS DELETED"
    assert (root / "2026-07-13_08-00-00-front.mp4").is_file(), "root clip removed"
    assert (root / "SavedClips").is_dir(), "sibling event folders removed"
    assert job3.deleted_inputs == [], job3.deleted_inputs
    assert job3.delete_skipped == [root.name], job3.delete_skipped
    assert any("root input directory" in warning for warning in job3.progress.warnings)
    print("e2e_webui: root-delete guard OK (input dir preserved)")

    print("e2e_webui: ALL OK")


if __name__ == "__main__":
    try:
        main()
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
