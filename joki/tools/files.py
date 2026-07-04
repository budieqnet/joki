import os, sys, json, subprocess, sqlite3, re, time, random, base64, socket, urllib, csv, platform
from pathlib import Path
from difflib import unified_diff
from datetime import datetime
import httpx
from duckduckgo_search import DDGS
from joki.shared import _console, _current_model_config, _get_data_dir, _print_markdown, _numbered, _HAS_TTY, TOOLS, _joki_cancel, JokiError, ToolError, LLMError, ConfigError, _shell_execute

def handle_read_file(args):
        with open(args["path"]) as f:
            return _numbered(f.read())


def handle_write_file(args):
        path = args["path"]
        new = args["content"]
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        diff_str = ""
        if os.path.exists(path):
            with open(path) as f:
                old = f.read()
            if old != new:
                diff = unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True), fromfile=path, tofile=path)
                diff_str = "".join(diff)
        with open(path, "w") as f:
            f.write(new)
        msg = f"Written: {path} ({len(new)} bytes)"
        if diff_str:
            msg += f"\n--- DIFF ---\n{diff_str}--- END DIFF ---"
        return msg


def handle_edit_file(args):
        with open(args["path"]) as f:
            old = f.read()
        ot = args["old_text"]
        if not ot:
            new = args["new_text"] + old
        else:
            if ot not in old:
                return f"Error: 'old_text' not found in {args['path']}"
            new = old.replace(ot, args["new_text"])
        diff = unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True), fromfile=args["path"], tofile=args["path"])
        with open(args["path"], "w") as f:
            f.write(new)
        msg = f"Edited: {args['path']}"
        diff_str = "".join(diff)
        if diff_str:
            msg += f"\n--- DIFF ---\n{diff_str}--- END DIFF ---"
        return msg


def handle_search_code(args):
        cmd = ["grep", "-rn", "--include=*.py", "--include=*.js", "--include=*.ts",
               "--include=*.html", "--include=*.css", "--include=*.json",
               "--include=*.yaml", "--include=*.yml", "--include=*.md",
               "--include=*.conf", "--include=*.cfg", "--include=*.ini",
               args["pattern"], args.get("path", ".")]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.stdout or "(not found)"


