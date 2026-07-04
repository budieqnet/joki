import os, sys, json, subprocess, sqlite3, re, time, random, base64, socket, urllib, csv, platform
from pathlib import Path
from difflib import unified_diff
from datetime import datetime
import httpx
from duckduckgo_search import DDGS
from joki.shared import _console, _current_model_config, _get_data_dir, _print_markdown, _numbered, _HAS_TTY, TOOLS, _joki_cancel, JokiError, ToolError, LLMError, ConfigError, _shell_execute

def handle_camera_capture(args):
        device = args.get("device", "/dev/video0")
        path = args.get("path", "/tmp/joki_cam.jpg")
        resolution = args.get("resolution", "640x480")
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        # Try fswebcam first, then ffmpeg
        r = subprocess.run(["fswebcam", "-d", device, "-r", resolution, path],
                           capture_output=True, text=True, timeout=15)
        if os.path.exists(path) and os.path.getsize(path) > 0:
            return f"Camera capture saved: {path} ({os.path.getsize(path)} bytes)"
        r2 = subprocess.run(
            ["ffmpeg", "-f", "v4l2", "-i", device, "-vframes", "1", "-s", resolution, "-y", path],
            capture_output=True, text=True, timeout=15
        )
        if os.path.exists(path) and os.path.getsize(path) > 0:
            return f"Camera capture saved: {path} ({os.path.getsize(path)} bytes)"
        return "Gagal capture kamera. Install fswebcam: sudo apt install fswebcam"


