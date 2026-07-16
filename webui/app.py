"""
Tesla Dashcam Web UI
Flask application that provides a web interface for configuring and running
the tesla_dashcam Docker container.
"""
import json
import os
import signal
import subprocess
import threading
import time
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request

app = Flask(__name__)

# ── State ────────────────────────────────────────────────────────────────
_process: subprocess.Popen | None = None
_process_lock = threading.Lock()
_log_lines: list[str] = []
_is_running = False

CONTAINER_NAME = "tesla-dashcam-webui"
DOCKER_IMAGE = "tesla_dashcam:vaapi"

DEFAULT_SOURCE = "/home/ben/komodo/tesla_dashcam/input"
DEFAULT_OUTPUT = "/home/ben/komodo/tesla_dashcam/output"


# ── Routes ───────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/events")
def list_events():
    """List event folders in the source directory."""
    source = request.args.get("path", DEFAULT_SOURCE)
    source_path = Path(source)
    events = []
    if source_path.is_dir():
        for entry in sorted(source_path.iterdir()):
            if entry.is_dir() and not entry.name.startswith("."):
                files = list(entry.glob("*.mp4"))
                total_size = sum(f.stat().st_size for f in files)
                events.append(
                    {
                        "name": entry.name,
                        "file_count": len(files),
                        "total_size_mb": round(total_size / (1024 * 1024), 1),
                    }
                )
    return jsonify(events)


@app.route("/api/browse")
def browse():
    """List directories at a given path."""
    path = request.args.get("path", "/")
    target = Path(path)
    dirs = []
    if target.is_dir():
        try:
            for entry in sorted(target.iterdir()):
                if entry.is_dir() and not entry.name.startswith("."):
                    dirs.append(str(entry))
        except PermissionError:
            pass
    return jsonify({"path": str(target), "dirs": dirs})


@app.route("/api/generate", methods=["POST"])
def generate_command():
    """Generate the Docker run command from form data."""
    data = request.get_json()
    cmd = _build_command(data)
    return jsonify({"command": _format_command(cmd)})


@app.route("/api/run", methods=["POST"])
def run_process():
    """Execute the Docker command and stream output via SSE."""
    global _process, _is_running, _log_lines

    with _process_lock:
        if _is_running:
            return jsonify({"error": "A process is already running"}), 409

    data = request.get_json()
    cmd = _build_command(data)

    # First, stop any lingering container with the same name
    subprocess.run(
        ["docker", "rm", "-f", CONTAINER_NAME],
        capture_output=True,
    )

    def generate():
        global _process, _is_running, _log_lines
        _log_lines = []
        _is_running = True

        try:
            yield _sse("status", "starting")

            _process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            yield _sse("status", "running")

            for line in iter(_process.stdout.readline, ""):
                line = line.rstrip("\n")
                _log_lines.append(line)
                yield _sse("log", line)

            _process.wait()
            exit_code = _process.returncode
            yield _sse(
                "status", "completed" if exit_code == 0 else f"error (exit {exit_code})"
            )
            yield _sse("done", str(exit_code))
        except Exception as e:
            yield _sse("error", str(e))
            yield _sse("done", "1")
        finally:
            _is_running = False
            _process = None

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/api/stop", methods=["POST"])
def stop_process():
    """Stop the running container."""
    global _process, _is_running

    # Stop the Docker container by name
    result = subprocess.run(
        ["docker", "stop", CONTAINER_NAME],
        capture_output=True,
        text=True,
    )

    # Also try to kill the subprocess directly
    with _process_lock:
        if _process and _process.poll() is None:
            try:
                _process.terminate()
                _process.wait(timeout=5)
            except Exception:
                try:
                    _process.kill()
                except Exception:
                    pass

    _is_running = False
    return jsonify({"status": "stopped"})


@app.route("/api/status")
def get_status():
    """Check if a process is currently running."""
    return jsonify(
        {
            "running": _is_running,
            "log_lines": len(_log_lines),
        }
    )


# ── Helpers ──────────────────────────────────────────────────────────────
def _sse(event: str, data: str) -> str:
    """Format a Server-Sent Event."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _format_command(cmd: list[str]) -> str:
    """Format a command list into a readable shell command with line continuations."""
    # Group args: pair flags with their values
    parts = []
    i = 0
    while i < len(cmd):
        token = cmd[i]
        # If the next token doesn't start with '-', it's a value for this flag
        if token.startswith("-") and i + 1 < len(cmd) and not cmd[i + 1].startswith("-"):
            parts.append(f"{token} {cmd[i + 1]}")
            i += 2
        else:
            parts.append(token)
            i += 1

    # Split into docker flags and app args (after image name)
    try:
        img_idx = parts.index(DOCKER_IMAGE)
        docker_parts = parts[: img_idx + 1]
        app_parts = parts[img_idx + 1 :]
    except ValueError:
        docker_parts = parts
        app_parts = []

    lines = [" ".join(docker_parts[:1])]  # 'docker'
    for p in docker_parts[1:]:
        lines.append(f"  {p}")
    for p in app_parts:
        lines.append(f"  {p}")

    return " \\\n".join(lines)


def _build_command(data: dict) -> list[str]:
    """Build the complete docker run command from form data."""
    source = data.get("source", DEFAULT_SOURCE)
    output = data.get("output", DEFAULT_OUTPUT)
    gpu_enabled = data.get("gpu", True)

    # Docker part
    cmd = [
        "docker", "run", "--rm",
        "--name", CONTAINER_NAME,
    ]

    # GPU device passthrough
    if gpu_enabled:
        cmd += ["--device", "/dev/dri"]

    # Volume mounts
    cmd += [
        "-v", f"{source}:/data",
        "-v", f"{output}:/output",
    ]

    # Image
    cmd.append(DOCKER_IMAGE)

    # ── tesla_dashcam arguments ──
    cmd += ["/data", "--output", "/output"]

    # GPU
    if gpu_enabled:
        gpu_type = data.get("gpu_type", "vaapi")
        cmd += ["--gpu", "--gpu_type", gpu_type]

    # Layout
    layout = data.get("layout", "FULLSCREEN")
    cmd += ["--layout", layout]

    # Perspective
    if data.get("perspective"):
        cmd.append("--perspective")

    # Mirror / Rear
    view_mode = data.get("view_mode", "mirror")
    if view_mode == "mirror":
        cmd.append("--mirror")
    elif view_mode == "rear":
        cmd.append("--rear")

    # Swap
    if data.get("swap"):
        cmd.append("--swap")

    # Background
    bg = data.get("background", "#000000")
    if bg and bg != "#000000":
        # Convert hex to ffmpeg color format
        cmd += ["--background", bg.lstrip("#")]

    # Camera exclusions
    camera_map = {
        "front": "--no-front",
        "left": "--no-left",
        "right": "--no-right",
        "rear": "--no-rear",
        "left_pillar": "--no-left-pillar",
        "right_pillar": "--no-right-pillar",
    }
    excluded = data.get("excluded_cameras", [])
    for cam, flag in camera_map.items():
        if cam in excluded:
            cmd.append(flag)

    # Text overlay
    if data.get("no_timestamp"):
        cmd.append("--no-timestamp")
    else:
        halign = data.get("halign")
        if halign:
            cmd += ["--halign", halign]
        valign = data.get("valign")
        if valign:
            cmd += ["--valign", valign]
        fontsize = data.get("fontsize")
        if fontsize:
            cmd += ["--fontsize", str(fontsize)]
        fontcolor = data.get("fontcolor", "white")
        if fontcolor and fontcolor != "white":
            cmd += ["--fontcolor", fontcolor]
        overlay_fmt = data.get("text_overlay_fmt")
        if overlay_fmt:
            cmd += ["--text_overlay_fmt", overlay_fmt]

    # Video output
    if data.get("motion_only"):
        cmd.append("--motion_only")

    speedup = data.get("speedup")
    if speedup and float(speedup) > 0:
        cmd += ["--speedup", str(speedup)]

    slowdown = data.get("slowdown")
    if slowdown and float(slowdown) > 0:
        cmd += ["--slowdown", str(slowdown)]

    if data.get("merge", True):
        cmd.append("--merge")

    # Encoding
    quality = data.get("quality", "LOWER")
    cmd += ["--quality", quality]

    compression = data.get("compression", "medium")
    cmd += ["--compression", compression]

    encoding = data.get("encoding", "x264")
    cmd += ["--encoding", encoding]

    fps = data.get("fps", 24)
    if fps and int(fps) != 24:
        cmd += ["--fps", str(fps)]

    if data.get("no_faststart"):
        cmd.append("--no-faststart")

    # Advanced
    if data.get("skip_existing"):
        cmd.append("--skip_existing")

    if data.get("delete_source"):
        cmd.append("--delete_source")

    loglevel = data.get("loglevel", "INFO")
    if loglevel != "INFO":
        cmd += ["--loglevel", loglevel]

    return cmd


if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=5555, debug=debug)
