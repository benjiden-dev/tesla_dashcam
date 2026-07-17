# Tesla Dashcam Web UI

A self-hosted web interface for `tesla_dashcam`: browse TeslaCam events,
pick exactly the minutes you want, preview the layout before rendering,
watch structured progress, play results in the browser — and optionally
burn a location map into the video and clean up the source footage.

![stack](https://img.shields.io/badge/stack-FastAPI%20%2B%20React%2019%20%2B%20Tailwind%204-blue)

## Features

- **Event browser** — SavedClips / SentryClips / RecentClips with thumbnails,
  Sentry reason, city and GPS badges straight from `event.json`.
- **Per-minute selection** — include only the minutes that matter
  (non-contiguous selections work). Selected minutes are staged as symlinks;
  the engine and your source footage are never modified.
- **True first-frame preview** — the selected minute is rendered through the
  actual engine (a few stream-copied seconds at low quality) so the preview
  is the exact composite you will get. Cached per event/minute/layout.
- **Structured progress** — the engine's output is parsed into phase, event
  and clip counters, percent and ETA, streamed over SSE, with the raw log one
  click away. Jobs are queued and cancellable.
- **Browser playback** — outputs gallery with poster frames, an in-browser
  player (HTTP range requests, so seeking works), download and delete.
- **Map burn-in** — an OpenStreetMap tile with the event location (from
  `event.json` `est_lat`/`est_lon`) composited onto the finished movie in an
  ffmpeg post-pass. Corner, size, opacity and zoom are configurable. Tiles
  are cached on disk and fetched with a proper User-Agent.
- **Delete input after processing** — opt-in per job, with confirmation.
  Source event folders are deleted only after the engine succeeded *and* the
  output file passes verification; freed space is reported.
- **Quality control** — Draft / Balanced / Archive presets plus the full
  advanced surface (CRF quality, preset, x264/x265, fps, scale) and — with
  GPU encoding — a real bitrate selector (`--bitrate`, added to the engine,
  since hardware encoders ignore CRF).
- **All the engine's layout power** — FULLSCREEN, WIDESCREEN, MOSAIC,
  PERSPECTIVE, CROSS, DIAMOND, HORIZONTAL layout picker with schematics,
  camera toggles (incl. pillars), mirror/rear view, swap, background color,
  timestamp styling, motion-only, speed up/slow down, merge, title-screen
  map, skip-existing.

## Quick start (Docker)

```bash
# from the repository root
RENDER_NODE=/dev/dri/renderD129 \
INPUT_DIR=/path/to/TeslaCam \
OUTPUT_DIR=/path/to/output \
docker compose -f docker-compose.webui.yml up -d --build
```

Open http://localhost:8088.

### VAAPI notes

The engine talks to `/dev/dri/renderD128` inside the container. The compose
file maps whatever host node you pick (`RENDER_NODE`) onto that path — handy
when the GPU you want is not the first render node (e.g. an eGPU next to an
iGPU is often `renderD129`). Find yours:

```bash
ls -l /dev/dri
vainfo --display drm --device /dev/dri/renderD129
```

With GPU encoding active the engine uses bitrate-based rate control
(hardware encoders ignore CRF); use the bitrate selector in the Quality
panel. Previews and the map post-pass always run on CPU — they are tiny
workloads.

## Development

```bash
# backend (needs Python 3.10+; the engine subprocess needs 3.13+)
pip install -r webui/requirements.txt -r requirements.txt
INPUT_DIR=./input OUTPUT_DIR=./output CACHE_DIR=./cache \
ENGINE_CMD="python3.13 -m tesla_dashcam" ENGINE_CWD=. \
python -m uvicorn webui.app:app --reload --port 8088

# frontend (Vite dev server proxies /api to :8088)
cd webui/frontend && npm install && npm run dev
```

Tests (hermetic, stdlib-only) and the end-to-end suite:

```bash
python3 tests/test_webui_scanner.py
python3 tests/test_webui_engine.py
python3 tests/test_webui_staging.py
python3 tests/e2e_webui.py   # needs ffmpeg + Python 3.13
```

## API sketch

| Endpoint | Purpose |
|---|---|
| `GET /api/config` | Dirs, GPU availability, defaults, choice lists |
| `GET /api/events` | Events with per-minute clips, cameras, metadata |
| `GET /api/events/{id}/thumb` | Event thumbnail (Tesla's `thumb.png` or extracted) |
| `GET /api/map/preview` | Cached OSM tile PNG for an event location |
| `POST /api/preview` | Engine-true first-frame JPEG for minute + settings |
| `POST /api/jobs` | Queue a render job (events, minutes, settings, map, delete) |
| `GET /api/jobs/{id}/stream` | SSE: structured progress + log lines |
| `POST /api/jobs/{id}/cancel` | Cancel a queued/running job |
| `GET /api/outputs` | Rendered movies |
| `GET /api/outputs/file/{path}` | Video file (range requests supported) |

## Architecture

```
webui/
  app.py        FastAPI routes + SPA serving
  config.py     env-driven configuration
  scanner.py    TeslaCam folder scanning (events → minutes → cameras)
  staging.py    symlink staging of selected minutes / preview trims
  engine.py     engine argv builder + stdout progress parser
  jobs.py       job queue, subprocess runner, map + delete post-steps
  preview.py    first-frame preview rendering (through the engine)
  maptile.py    OSM tile fetch/cache + ffmpeg overlay post-pass
  outputs.py    outputs listing, thumbnails, safe delete
  frontend/     React 19 + TypeScript + Tailwind v4 SPA (Vite)
```

The engine (`tesla_dashcam/tesla_dashcam.py`) is driven strictly as a
subprocess — the web UI never imports its internals, so upstream merges stay
trivial. The only engine changes in this fork are a `--bitrate` flag and a
one-line fix for `event.json` files without a `timestamp` key.
