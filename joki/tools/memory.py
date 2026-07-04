import os, sys, json, subprocess, sqlite3, re, time, random, base64, socket, urllib, csv, platform
from pathlib import Path
from difflib import unified_diff
from datetime import datetime
import httpx
from duckduckgo_search import DDGS
from joki.shared import _console, _current_model_config, _get_data_dir, _print_markdown, _numbered, _HAS_TTY, TOOLS, _joki_cancel, JokiError, ToolError, LLMError, ConfigError, _shell_execute

def handle_memory_store(args):
        mem = _load_memory()
        mem[args["key"]] = args["value"]
        _save_memory(mem)
        return f"Memory saved: {args['key']}"


def handle_memory_recall(args):
        mem = _load_memory()
        key = args.get("key", "")
        if key:
            if key in mem:
                return f"{key}: {mem[key]}"
            return f"Memory '{key}' not found"
        if not mem:
            return "(no memories stored)"
        lines = [f"  {k}: {v[:100]}{'...' if len(v) > 100 else ''}" for k, v in mem.items()]
        return f"Memori tersimpan ({len(mem)}):\n" + "\n".join(lines)


def handle_memory_forget(args):
        mem = _load_memory()
        if args["key"] in mem:
            del mem[args["key"]]
            _save_memory(mem)
            return f"Memory forgotten: {args['key']}"
        return f"Memory '{args['key']}' not found"


