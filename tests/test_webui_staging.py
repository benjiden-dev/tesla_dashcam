#!/usr/bin/env python3
"""Hermetic test for webui.staging — symlink staging of selected minutes.

Run: python3 tests/test_webui_staging.py
"""

import json
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

TMP = tempfile.mkdtemp(prefix="webui-staging-")
os.environ["INPUT_DIR"] = str(Path(TMP) / "input")
os.environ["OUTPUT_DIR"] = str(Path(TMP) / "output")
os.environ["CACHE_DIR"] = str(Path(TMP) / "cache")

from webui import config, staging  # noqa: E402


def make_event(folder: Path, minutes: list[str], cameras: list[str]) -> None:
    folder.mkdir(parents=True)
    for minute in minutes:
        for camera in cameras:
            (folder / f"{minute}-{camera}.mp4").write_bytes(b"v" * 100)
    (folder / "event.json").write_text(json.dumps({"city": "Denver"}))


def main() -> None:
    config.ensure_dirs()
    root = Path(os.environ["INPUT_DIR"])

    event_a = root / "SavedClips" / "2026-07-10_14-30-11"
    make_event(
        event_a,
        ["2026-07-10_14-28-01", "2026-07-10_14-29-01", "2026-07-10_14-30-01"],
        ["front", "back"],
    )
    # Same folder name under a different group — must not collide when staged.
    event_b = root / "SentryClips" / "2026-07-10_14-30-11"
    make_event(event_b, ["2026-07-10_14-28-01"], ["front"])

    selections = [
        {
            "dir": event_a,
            # Non-contiguous selection: first and last minute only.
            "minutes": ["2026-07-10_14-28-01", "2026-07-10_14-30-01"],
        },
        {"dir": event_b, "minutes": None},
    ]
    stage_root = staging.stage_job("job1", selections)

    assert selections[0]["staged_name"] == "2026-07-10_14-30-11"
    assert selections[1]["staged_name"] == "2026-07-10_14-30-11_2"

    staged_a = stage_root / selections[0]["staged_name"]
    files_a = sorted(f.name for f in staged_a.iterdir())
    assert files_a == [
        "2026-07-10_14-28-01-back.mp4",
        "2026-07-10_14-28-01-front.mp4",
        "2026-07-10_14-30-01-back.mp4",
        "2026-07-10_14-30-01-front.mp4",
        "event.json",
    ], files_a

    # Skipped middle minute must not be present; links must resolve to bytes.
    for name in files_a:
        path = staged_a / name
        if name.endswith(".mp4"):
            assert path.is_symlink(), f"{name} should be a symlink"
            assert path.read_bytes() == b"v" * 100
        else:
            assert not path.is_symlink(), "event.json must be a real copy"

    staged_b = stage_root / selections[1]["staged_name"]
    assert (staged_b / "2026-07-10_14-28-01-front.mp4").is_symlink()

    # Empty selection must raise.
    try:
        staging.stage_job("job2", [{"dir": event_a, "minutes": ["1999-01-01_00-00-00"]}])
    except ValueError:
        pass
    else:
        raise AssertionError("empty selection did not raise")

    # directory_size counts real bytes only (not symlink targets).
    assert staging.directory_size(event_a) == 6 * 100 + len(
        (event_a / "event.json").read_bytes()
    )
    assert staging.directory_size(staged_a) == len(
        (staged_a / "event.json").read_bytes()
    )

    staging.cleanup(stage_root)
    assert not stage_root.exists()

    print("test_webui_staging: OK")


if __name__ == "__main__":
    main()
