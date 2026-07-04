import os, sys, json, subprocess, sqlite3, re, time, random, base64, socket, urllib, csv, platform
from pathlib import Path
from difflib import unified_diff
from datetime import datetime
import httpx
from duckduckgo_search import DDGS
from joki.shared import _console, _current_model_config, _get_data_dir, _print_markdown, _numbered, _HAS_TTY, TOOLS, _joki_cancel, JokiError, ToolError, LLMError, ConfigError, _shell_execute

def handle_run_command(args):
        cmd = args["cmd"].strip()
        if not _confirm_dangerous(cmd):
            return "Dibatalkan oleh user."
        sudo_password = None
        actual_cmd = cmd
        use_sudo = False

        if cmd.startswith("sudo ") or (os.name == 'nt' and cmd.startswith("runas ")):
            use_sudo = True
            sudo_password = _prompt_sudo()
            if sudo_password:
                prefix = "sudo " if cmd.startswith("sudo ") else "runas "
                actual_cmd = cmd[len(prefix):].lstrip()

        if use_sudo and sudo_password:
            with _Spinner("Menjalankan perintah"):
                result = _run_elevated(actual_cmd, sudo_password)
            output = result.stdout + result.stderr
            return output or "(no output)"
        else:
            with _Spinner("Menjalankan perintah"):
                output = _shell_execute(cmd)
                return output or "(no output)"


