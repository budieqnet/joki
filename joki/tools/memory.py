# ============================================================
# LONG-TERM MEMORY (per-session)
# ============================================================
def _memory_path(name=None):
    name = name or _CURRENT_SESSION or "default"
    return os.path.join(SESSION_DIR, "memories", f"{name}.json")

def _load_memory(name=None):
    path = _memory_path(name)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}

def _save_memory(data, name=None):
    path = _memory_path(name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

# ============================================================
# TODO LIST
# ============================================================
def _todo_path():
    return os.path.join(SESSION_DIR, "todos", f"{_CURRENT_SESSION or 'default'}.json")

def _load_todo():
    path = _todo_path()
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return []

def _save_todo(items):
    path = _todo_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(items, f, indent=2)

