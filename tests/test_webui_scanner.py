#!/usr/bin/env python3
"""Hermetic test for webui.scanner — synthetic TeslaCam tree, no deps.

Run: python3 tests/test_webui_scanner.py
"""

import json
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

TMP = tempfile.mkdtemp(prefix="webui-scanner-")
os.environ["INPUT_DIR"] = str(Path(TMP) / "input")
os.environ["OUTPUT_DIR"] = str(Path(TMP) / "output")
os.environ["CACHE_DIR"] = str(Path(TMP) / "cache")

from webui import scanner  # noqa: E402


def make_tree(root: Path) -> None:
    saved = root / "SavedClips" / "2026-07-10_14-30-11"
    saved.mkdir(parents=True)
    for minute in ("2026-07-10_14-28-01", "2026-07-10_14-29-01", "2026-07-10_14-30-01"):
        for camera in ("front", "back", "left_repeater", "right_repeater"):
            (saved / f"{minute}-{camera}.mp4").write_bytes(b"x" * 10)
    (saved / "event.json").write_text(
        json.dumps(
            {
                "timestamp": "2026-07-10T14:30:11",
                "city": "Denver",
                "est_lat": "39.7392",
                "est_lon": "-104.9903",
                "reason": "user_interaction_honk",
                "camera": "0",
            }
        )
    )
    (saved / "thumb.png").write_bytes(b"png")

    sentry = root / "SentryClips" / "2026-07-11_09-15-22"
    sentry.mkdir(parents=True)
    for minute in ("2026-07-11_09-13-22", "2026-07-11_09-14-22"):
        for camera in scanner.CAMERAS:
            (sentry / f"{minute}-{camera}.mp4").write_bytes(b"x" * 20)
    (sentry / "event.json").write_text(
        json.dumps({"timestamp": "2026-07-11T09:15:22", "est_lat": 0, "est_lon": 0})
    )

    recent = root / "RecentClips"
    recent.mkdir(parents=True)
    for minute in ("2026-07-12_08-00-00", "2026-07-12_08-01-00"):
        for camera in ("front", "back"):
            (recent / f"{minute}-{camera}.mp4").write_bytes(b"x" * 5)

    # Noise that must be ignored.
    (root / "SavedClips" / ".hidden").mkdir()
    (root / "SavedClips" / "empty_folder").mkdir()
    (saved / "notes.txt").write_text("ignore me")


def main() -> None:
    root = Path(os.environ["INPUT_DIR"])
    make_tree(root)

    events = scanner.scan_events()
    assert len(events) == 3, f"expected 3 events, got {len(events)}"

    by_group = {event["group"]: event for event in events}
    assert set(by_group) == {"SavedClips", "SentryClips", "RecentClips"}

    # Newest first (RecentClips has the latest stamps).
    assert events[0]["group"] == "RecentClips"

    saved = by_group["SavedClips"]
    assert saved["name"] == "2026-07-10_14-30-11"
    assert saved["minute_count"] == 3
    assert saved["clip_count"] == 12
    assert saved["has_thumb"] is True
    assert saved["metadata"]["city"] == "Denver"
    assert abs(saved["metadata"]["lat"] - 39.7392) < 1e-6
    assert abs(saved["metadata"]["lon"] - -104.9903) < 1e-6
    assert saved["minutes"][0]["key"] == "2026-07-10_14-28-01"
    assert saved["minutes"][0]["time"] == "14:28:01"
    assert saved["minutes"][0]["cameras"] == [
        "back",
        "front",
        "left_repeater",
        "right_repeater",
    ]

    sentry = by_group["SentryClips"]
    assert sentry["minute_count"] == 2
    assert sentry["clip_count"] == 12
    # 0,0 coordinates are invalid and must be dropped.
    assert sentry["metadata"]["lat"] is None
    assert sentry["metadata"]["lon"] is None

    recent = by_group["RecentClips"]
    assert recent["minute_count"] == 2
    assert recent["metadata"] is None

    # Id round-trip + single event rescan.
    event = scanner.get_event(saved["id"])
    assert event["name"] == saved["name"]
    folder = scanner.event_dir_from_id(saved["id"])
    assert folder.name == "2026-07-10_14-30-11"

    # Path traversal must be rejected.
    evil = scanner.encode_event_id("../../etc")
    try:
        scanner.event_dir_from_id(evil)
    except (ValueError, FileNotFoundError):
        pass
    else:
        raise AssertionError("traversal id was not rejected")

    # Minute/camera filtering.
    files = scanner.minute_files(folder, ["2026-07-10_14-29-01"])
    assert len(files) == 4
    files = scanner.minute_files(folder, ["2026-07-10_14-29-01"], ["front"])
    assert len(files) == 1 and files[0].name.endswith("front.mp4")
    files = scanner.minute_files(folder, None, ["front"])
    assert len(files) == 3

    print("test_webui_scanner: OK")


if __name__ == "__main__":
    main()
