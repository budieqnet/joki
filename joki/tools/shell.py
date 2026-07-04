# ============================================================
# PERSISTENT SHELL SESSION
# ============================================================
def _get_shell():
    """Start or return the persistent shell process (bash)."""
    global _PERSISTENT_SHELL
    if _PERSISTENT_SHELL is not None:
        poll = _PERSISTENT_SHELL.poll()
        if poll is None:
            return _PERSISTENT_SHELL
        _PERSISTENT_SHELL = None
    try:
        _PERSISTENT_SHELL = subprocess.Popen(
            ["bash", "--norc", "--noprofile"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=0
        )
    except FileNotFoundError:
        try:
            _PERSISTENT_SHELL = subprocess.Popen(
                ["sh"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=0
            )
        except Exception:
            return None
    return _PERSISTENT_SHELL

def _close_shell():
    """Kill the persistent shell process if running."""
    global _PERSISTENT_SHELL
    if _PERSISTENT_SHELL is not None:
        try:
            _PERSISTENT_SHELL.terminate()
            _PERSISTENT_SHELL.wait(timeout=3)
        except Exception:
            try:
                _PERSISTENT_SHELL.kill()
            except Exception:
                pass
        _PERSISTENT_SHELL = None

def _shell_execute(cmd, timeout=60):
    """Execute command in the persistent shell.
    Returns (stdout+stderr) string.
    """
    shell = _get_shell()
    if shell is None:
        return "[ERROR] Tidak bisa memulai persistent shell."

    end_marker = f"__SHELL_END_{os.getpid()}_{time.time_ns()}__"

    full_cmd = f" ( {cmd} ) 2>&1; echo '{end_marker}'"

    with _SHELL_LOCK:
        try:
            shell.stdin.write(full_cmd + "\n")
            shell.stdin.flush()
        except Exception as e:
            _close_shell()
            return f"[ERROR] Gagal menulis ke shell: {e}"

        output = []
        start = time.time()
        while True:
            if _joki_cancel.is_set():
                return "[CANCELLED]"
            elapsed = time.time() - start
            if elapsed > timeout:
                _close_shell()
                return f"[ERROR] Command timeout ({timeout}s). Shell di-restart."
            try:
                line = shell.stdout.readline()
                if not line:
                    _close_shell()
                    return "[ERROR] Shell process mati."
                if line.strip() == end_marker:
                    break
                output.append(line)
            except (Exception, KeyboardInterrupt):
                _close_shell()
                return "[ERROR] Gagal membaca output shell."

    return "".join(output).rstrip("\n")

