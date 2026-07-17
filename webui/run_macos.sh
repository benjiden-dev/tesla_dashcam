#!/usr/bin/env bash
# Native macOS runner for the tesla_dashcam web UI.
#
# Runs the FastAPI backend + engine directly on macOS so hardware encoding
# uses Apple VideoToolbox (Docker on a Mac cannot reach the media engine).
#
# Usage:
#   bash webui/run_macos.sh [INPUT_DIR] [OUTPUT_DIR] [PORT]
# or with environment variables:
#   INPUT_DIR=~/TeslaCam OUTPUT_DIR=~/Movies/TeslaDashcam bash webui/run_macos.sh
#
# First run creates a virtualenv (.venv-webui) and builds the frontend once
# (requires node/npm). Re-build the UI later with FORCE_FRONTEND=1.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INPUT_DIR="${1:-${INPUT_DIR:-$HOME/TeslaCam}}"
OUTPUT_DIR="${2:-${OUTPUT_DIR:-$HOME/Movies/TeslaDashcam}}"
PORT="${3:-${PORT:-8088}}"
CACHE_DIR="${CACHE_DIR:-$HOME/Library/Caches/tesla-dashcam-webui}"

# ── Prerequisites ────────────────────────────────────────────────────────
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "error: ffmpeg not found — install it with: brew install ffmpeg" >&2
  exit 1
fi

PYTHON=""
for candidate in python3.14 python3.13 python3; do
  if command -v "$candidate" >/dev/null 2>&1 \
    && "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 13) else 1)' 2>/dev/null; then
    PYTHON="$candidate"
    break
  fi
done
if [ -z "$PYTHON" ]; then
  echo "error: Python 3.13+ not found (the engine requires it)." >&2
  echo "       install it with: brew install python@3.13" >&2
  exit 1
fi

# ── Virtualenv with engine + web UI dependencies ─────────────────────────
VENV="$REPO_ROOT/.venv-webui"
if [ ! -x "$VENV/bin/python" ]; then
  echo "Creating virtualenv with $PYTHON ..."
  "$PYTHON" -m venv "$VENV"
  "$VENV/bin/pip" install --quiet --upgrade pip
  "$VENV/bin/pip" install --quiet \
    -r "$REPO_ROOT/requirements.txt" \
    -r "$REPO_ROOT/webui/requirements.txt"
fi

# ── Frontend build (once) ────────────────────────────────────────────────
if [ ! -f "$REPO_ROOT/webui/static/dist/index.html" ] || [ "${FORCE_FRONTEND:-0}" = "1" ]; then
  if ! command -v npm >/dev/null 2>&1; then
    echo "error: npm not found — needed once to build the UI (brew install node)" >&2
    exit 1
  fi
  echo "Building frontend ..."
  (cd "$REPO_ROOT/webui/frontend" && npm install --no-audit --no-fund && npm run build)
fi

mkdir -p "$INPUT_DIR" "$OUTPUT_DIR" "$CACHE_DIR"

echo ""
echo "  Input:   $INPUT_DIR"
echo "  Output:  $OUTPUT_DIR"
echo "  Cache:   $CACHE_DIR"
echo "  Encode:  Apple VideoToolbox (hardware)"
echo "  UI:      http://localhost:$PORT"
echo ""

exec env \
  INPUT_DIR="$INPUT_DIR" \
  OUTPUT_DIR="$OUTPUT_DIR" \
  CACHE_DIR="$CACHE_DIR" \
  PORT="$PORT" \
  ENGINE_CMD="$VENV/bin/python -m tesla_dashcam" \
  ENGINE_CWD="$REPO_ROOT" \
  "$VENV/bin/python" -m uvicorn webui.app:app --host 0.0.0.0 --port "$PORT"
