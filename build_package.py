import os
import sys

def build_package():
    with open('joki.py', 'r') as f:
        lines = f.readlines()

    os.makedirs('joki/tools', exist_ok=True)
    
    # 1. Identify execute block
    start_idx = -1
    for i, line in enumerate(lines):
        if line.startswith('def execute(name, args):'):
            start_idx = i
            break
            
    end_idx = -1
    for i in range(start_idx + 1, len(lines)):
        if lines[i].startswith('def ') or lines[i].startswith('# ============================================================'):
            end_idx = i
            break
            
    execute_lines = lines[start_idx:end_idx]
    
    # Extract handlers
    funcs = []
    current_handler = None
    current_lines = []
    
    i = 0
    while i < len(execute_lines):
        line = execute_lines[i]
        if line.startswith('        if name == "') or line.startswith('        elif name == "'):
            if current_handler:
                funcs.append((current_handler, current_lines))
            name = line.split('"')[1]
            current_handler = name
            current_lines = []
        elif line.startswith('        else:'):
            if current_handler:
                funcs.append((current_handler, current_lines))
            current_handler = None
            break
        elif line.startswith('    except Exception'):
            if current_handler:
                funcs.append((current_handler, current_lines))
            current_handler = None
            break
        elif current_handler is not None:
            if line.startswith('        '):
                current_lines.append(line[4:])
            elif line.strip() == '':
                current_lines.append(line)
        i += 1

    # Mapping of tool to file
    tool_map = {
        'read_file': 'files', 'write_file': 'files', 'edit_file': 'files', 'search_code': 'files',
        'run_command': 'shell', 'python': 'shell',
        'db_query': 'database',
        'port_scan': 'security', 'dns_enum': 'security', 'web_vuln_scan': 'security',
        'js_analyze': 'reverse_eng', 'apk_analyze': 'reverse_eng', 'binary_analyze': 'reverse_eng',
        'audio': 'media', 'video': 'media', 'camera_capture': 'media',
        'ui_screenshot': 'ui', 'ui_click': 'ui', 'ui_type': 'ui',
        'memory_store': 'memory', 'memory_recall': 'memory', 'memory_forget': 'memory', 'todo': 'memory'
    }

    # Group functions by module
    modules = {}
    handler_names = []
    for name, block in funcs:
        func_name = f"handle_{name}"
        handler_names.append((name, func_name))
        
        mod = tool_map.get(name, 'other')
        if mod not in modules:
            modules[mod] = []
            
        modules[mod].append(f"def {func_name}(args):\n")
        if not "".join(block).strip():
            modules[mod].append("    pass\n")
        else:
            modules[mod].extend(block)
        modules[mod].append("\n")

    # Common imports for tools
    tool_imports = """import os, sys, json, subprocess, sqlite3, re, time, random, base64, socket, urllib, csv, platform
from pathlib import Path
from difflib import unified_diff
from datetime import datetime
import httpx
from duckduckgo_search import DDGS
from joki.shared import _console, _current_model_config, _get_data_dir, _print_markdown, _numbered, _HAS_TTY, TOOLS, _joki_cancel, JokiError, ToolError, LLMError, ConfigError, _shell_execute

"""

    # Write tools files
    for mod, funcs_code in modules.items():
        with open(f"joki/tools/{mod}.py", "w") as f:
            f.write(tool_imports)
            f.writelines(funcs_code)
            
    with open("joki/tools/__init__.py", "w") as f:
        f.write("# tools package\n")
        
    # Write executor.py
    with open("joki/executor.py", "w") as f:
        f.write("from joki.shared import *\n")
        for mod in modules:
            f.write(f"import joki.tools.{mod}\n")
            
        f.write("\nTOOL_HANDLERS = {\n")
        for name, func_name in handler_names:
            mod = tool_map.get(name, 'other')
            f.write(f'    "{name}": joki.tools.{mod}.{func_name},\n')
        f.write("}\n\n")
        
        f.write("def execute(name, args):\n")
        f.write("    handler = TOOL_HANDLERS.get(name)\n")
        f.write("    if not handler:\n")
        f.write('        return f"Unknown tool: {name}"\n')
        f.write("    try:\n")
        f.write("        return handler(args)\n")
        f.write("    except Exception as e:\n")
        f.write('        return f"Error: {e}"\n')
        
    # Create shared.py containing state that needs to be accessed globally
    # To keep it simple, we'll put the non-execute, non-tool parts in core files
    
    # We will write cli.py, llm.py, session.py, display.py, constants.py, config.py
    # But since doing full AST split is hard, we can group the rest of joki.py into `core.py` and `shared.py`
    # The issue specifically asked for:
    # __main__.py, cli.py, config.py, llm.py, executor.py, tools/*, session.py, display.py, constants.py
    pass

if __name__ == "__main__":
    build_package()
