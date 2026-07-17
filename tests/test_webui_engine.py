#!/usr/bin/env python3
"""Hermetic test for webui.engine — arg builder + stdout progress parser.

Run: python3 tests/test_webui_engine.py
"""

import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

TMP = tempfile.mkdtemp(prefix="webui-engine-")
os.environ["INPUT_DIR"] = str(Path(TMP) / "input")
os.environ["OUTPUT_DIR"] = str(Path(TMP) / "output")
os.environ["CACHE_DIR"] = str(Path(TMP) / "cache")

from webui import engine  # noqa: E402


def test_args_defaults() -> None:
    args = engine.build_engine_args("/stage", "/output", {}, gpu_available=True)
    joined = " ".join(args)
    assert args[0] == "/stage"
    assert "--output /output" in joined
    assert "--layout FULLSCREEN" in joined
    assert "--mirror" in joined
    assert "--merge" in joined
    assert "--quality LOWER" in joined
    assert "--compression medium" in joined
    assert "--encoding x264" in joined
    assert "--gpu --gpu_type vaapi" in joined
    assert "--no-check_for_update" in joined
    assert "--no-notification" in joined
    assert "--temp_dir" in joined
    assert "--fps" not in joined  # 24 is the engine default
    assert "--background" not in joined  # black is the default


def test_args_custom() -> None:
    settings = {
        "layout": "CROSS",
        "perspective": True,
        "view_mode": "rear",
        "swap": True,
        "background": "#112233",
        "cameras": {"left_pillar": False, "right_pillar": False, "back": False},
        "show_timestamp": False,
        "motion_only": True,
        "speedup": 2,
        "merge": False,
        "quality": "HIGH",
        "compression": "slow",
        "encoding": "x265",
        "fps": 30,
        "scale": 0.5,
        "faststart": False,
        "skip_existing": True,
        "gpu": True,
        "gpu_type": "vaapi",
        "bitrate": "8M",
        "title_screen_map": True,
        "loglevel": "DEBUG",
    }
    args = engine.build_engine_args("/s", "/o", settings, gpu_available=True)
    joined = " ".join(args)
    assert "--layout CROSS" in joined
    assert "--perspective" in joined
    assert "--rear" in joined and "--mirror" not in joined
    assert "--swap" in joined
    assert "--background 112233" in joined
    assert "--no-rear" in joined
    assert "--no-left-pillar" in joined and "--no-right-pillar" in joined
    assert "--no-front" not in joined
    assert "--no-timestamp" in joined
    assert "--motion_only" in joined
    assert "--speedup 2" in joined
    assert "--merge" not in joined
    assert "--quality HIGH" in joined
    assert "--encoding x265" in joined
    assert "--fps 30" in joined
    assert "--scale 0.5" in joined
    assert "--no-faststart" in joined
    assert "--skip_existing" in joined
    assert "--bitrate 8M" in joined
    assert "--title_screen_map" in joined
    assert "--loglevel DEBUG" in joined


def test_args_darwin_gpu() -> None:
    # On macOS the engine has no --gpu_type; VideoToolbox is selected
    # automatically. The builder must emit --gpu alone (bitrate still valid).
    from webui import config

    original = config.IS_DARWIN
    config.IS_DARWIN = True
    try:
        args = engine.build_engine_args(
            "/s", "/o", {"gpu": True, "bitrate": "8M"}, gpu_available=True
        )
        joined = " ".join(args)
        assert "--gpu" in args
        assert "--gpu_type" not in joined
        assert "--bitrate 8M" in joined

        args = engine.build_engine_args("/s", "/o", {"gpu": False}, gpu_available=True)
        assert "--no-gpu" in args
    finally:
        config.IS_DARWIN = original

    # Back on Linux, --gpu_type must be emitted again.
    args = engine.build_engine_args("/s", "/o", {"gpu": True}, gpu_available=True)
    assert "--gpu_type vaapi" in " ".join(args)


def test_args_gpu_fallback() -> None:
    # GPU requested but no render node — engine must run on CPU.
    args = engine.build_engine_args(
        "/s", "/o", {"gpu": True, "bitrate": "8M"}, gpu_available=False
    )
    joined = " ".join(args)
    assert "--no-gpu" in joined
    assert "--gpu " not in f"{joined} "
    assert "--bitrate" not in joined

    # Invalid choices fall back to safe defaults.
    args = engine.build_engine_args(
        "/s", "/o", {"layout": "BOGUS", "quality": "ULTRA"}, gpu_available=True
    )
    joined = " ".join(args)
    assert "--layout FULLSCREEN" in joined
    assert "--quality LOWER" in joined


# Mirrors real engine output (v0.1.21 dev) including the per-event header
# lines and the non-merge completion line.
TRANSCRIPT = """Scanning 1 folder(s)
Scanned 1/1.
There are 2 event folder(s) with 5 clips to process.
\tProcessing 3 clips in folder /cache/staging/j1/2026-07-10_14-30-11 (1/2)
\t\tProcessing clip 1/3 from 07/10/26 14:28:01 and 59 seconds long.
\t\tProcessing clip 2/3 from 07/10/26 14:29:01 and 59 seconds long.
\t\tProcessing clip 3/3 from 07/10/26 14:30:01 and 58 seconds long.
\t\tCreating movie /output/2026-07-10T14-28-01_2026-07-10T14-30-59.mp4, please be patient.
\tMovie /output/2026-07-10T14-28-01_2026-07-10T14-30-59.mp4 for folder /cache/staging/j1/2026-07-10_14-30-11 with duration 0:02:56 is ready.
\tProcessing 2 clips in folder /cache/staging/j1/2026-07-11_09-15-22 (2/2)
\t\tProcessing clip 1/2 from 07/11/26 09:13:22 and 59 seconds long.
\t\tProcessing clip 2/2 from 07/11/26 09:14:22 and 59 seconds long.
\t\tCreating movie /output/2026-07-11T09-13-22_2026-07-11T09-15-20.mp4, please be patient.
\tMovie /output/2026-07-11T09-13-22_2026-07-11T09-15-20.mp4 for folder /cache/staging/j1/2026-07-11_09-15-22 with duration 0:01:58 is ready.
\tCreating movie /output/merged_movie.mp4, please be patient.
 Movie /output/merged_movie.mp4 with duration 0:04:54 has been created.
All folders have been processed, resulting movie files are located in /output"""


def test_parser() -> None:
    progress = engine.EngineProgress()
    lines = TRANSCRIPT.split("\n")

    for line in lines[:3]:
        progress.feed(line)
    assert progress.phase == "processing"
    assert progress.total_events == 2
    assert progress.total_clips == 5

    progress.feed(lines[3])  # event header 1/2
    assert progress.current_event == 1
    assert progress.clips_in_event == 3

    progress.feed(lines[4])  # clip 1/3
    assert progress.clip_in_event == 1
    assert progress.clips_done == 0

    progress.feed(lines[5])  # clip 2/3
    assert progress.clips_done == 1
    assert 0 < progress.percent < 40

    progress.feed(lines[6])  # clip 3/3
    progress.feed(lines[7])  # creating event movie (2 tabs)
    assert progress.phase == "assembling"

    progress.feed(lines[8])  # event ready
    assert progress.events_done == 1
    assert progress.clips_done == 3
    folder = "/cache/staging/j1/2026-07-10_14-30-11"
    assert progress.event_outputs[folder].endswith("2026-07-10T14-30-59.mp4")

    progress.feed(lines[9])  # event header 2/2
    assert progress.current_event == 2
    assert progress.clips_done == 3

    progress.feed(lines[10])
    progress.feed(lines[11])
    progress.feed(lines[12])
    progress.feed(lines[13])  # event 2 ready
    assert progress.events_done == 2
    assert progress.clips_done == 5

    progress.feed(lines[14])  # merging (1 tab)
    assert progress.phase == "merging"
    assert progress.percent >= 94

    progress.feed(lines[15])  # merged movie created
    assert "/output/merged_movie.mp4" in progress.outputs

    progress.feed(lines[16])  # completed (non-monitor completion line)
    assert progress.phase == "done"
    assert progress.percent == 100.0
    assert len(progress.outputs) == 3

    # The monitor-mode completion line must also close things out.
    other = engine.EngineProgress()
    other.feed("Processing of movies has completed.")
    assert other.phase == "done"


def test_parser_error_and_multi() -> None:
    progress = engine.EngineProgress()
    progress.feed("There are 1 event folder(s) with 1 clips to process.")
    progress.feed(
        "\t\t\tError trying to create movie /output/x.mp4. RC: 1"
    )
    assert progress.errors, "error line not captured"
    progress.feed(
        "\t\t\tError trying to create clip for /in/2026-07-10T14-28-01.mp4.RC: 8"
    )
    progress.feed("\t\tError: No valid clips to merge found.")
    assert len(progress.errors) == 3

    progress.feed("Following movies have been created:")
    progress.feed("\t/output/a.mp4 with duration 0:01:00")
    progress.feed("\t/output/b.mp4 with duration 0:02:00")
    assert "/output/a.mp4" in progress.outputs
    assert "/output/b.mp4" in progress.outputs


def main() -> None:
    test_args_defaults()
    test_args_custom()
    test_args_darwin_gpu()
    test_args_gpu_fallback()
    test_parser()
    test_parser_error_and_multi()
    print("test_webui_engine: OK")


if __name__ == "__main__":
    main()
