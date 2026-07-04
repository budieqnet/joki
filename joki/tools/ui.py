import os, sys, json, subprocess, sqlite3, re, time, random, base64, socket, urllib, csv, platform
from pathlib import Path
from difflib import unified_diff
from datetime import datetime
import httpx
from duckduckgo_search import DDGS
from joki.shared import _console, _current_model_config, _get_data_dir, _print_markdown, _numbered, _HAS_TTY, TOOLS, _joki_cancel, JokiError, ToolError, LLMError, ConfigError, _shell_execute

def handle_ui_screenshot(args):
        path = args.get("path", "/tmp/joki_ui_screen.png")
        region = args.get("region", "full")
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        if region == "full":
            r = subprocess.run(["import", "-window", "root", path], capture_output=True, text=True, timeout=15)
        else:
            r = subprocess.run(["import", "-crop", region, path], capture_output=True, text=True, timeout=15)
        if os.path.exists(path) and os.path.getsize(path) > 0:
            return f"Screenshot saved: {path} ({os.path.getsize(path)} bytes)"
        return f"Error screenshot: {r.stderr or 'unknown'}. Install imagemagick: sudo apt install imagemagick"


def handle_ui_click(args):
        x, y = args["x"], args["y"]
        btn = args.get("button", "left")
        btn_map = {"left": 1, "middle": 2, "right": 3}
        count = args.get("click_count", 1)
        click_arg = "".join([str(btn_map.get(btn, 1))] * count)
        r = subprocess.run(["xdotool", "mousemove", str(x), str(y), "click", click_arg],
                           capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            return f"Clicked {btn} at ({x},{y})"
        return f"Click error: {r.stderr}. Install xdotool: sudo apt install xdotool"


def handle_ui_type(args):
        text = args["text"]
        safe = text.replace('"', '\\"')
        r = subprocess.run(["xdotool", "type", safe], capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            return f"Typed: {text[:100]}{'...' if len(text) > 100 else ''}"
        return f"Type error: {r.stderr}"


