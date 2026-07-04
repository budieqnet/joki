import os, sys, json, subprocess, sqlite3, re, time, random, base64, socket, urllib, csv, platform
from pathlib import Path
from difflib import unified_diff
from datetime import datetime
import httpx
from duckduckgo_search import DDGS
from joki.shared import _console, _current_model_config, _get_data_dir, _print_markdown, _numbered, _HAS_TTY, TOOLS, _joki_cancel, JokiError, ToolError, LLMError, ConfigError, _shell_execute

def handle_db_query(args):
        scheme, user, password, host, port, database = _parse_connection(args["connection"])
        if not _confirm_dangerous(args["query"]):
            return "Dibatalkan oleh user."
        with _Spinner("Query database"):
            return _run_db_query(scheme, args["query"], user, password, host, port, database)


