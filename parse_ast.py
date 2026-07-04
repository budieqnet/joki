import ast
import os

with open('joki.py', 'r') as f:
    source = f.read()

tree = ast.parse(source)

# We want to extract functions and classes to files
mapping = {
    'cli': ['agent_loop', 'main', '_check_update'],
    'config': ['_load_models', '_auto_create_config', '_get_config_path', '_get_data_dir'],
    'llm': ['call_llm', '_trim_messages', 'estimate_tokens'],
    'session': ['save_session', '_load_session_data', 'list_sessions', 'view_session_history', '_session_path'],
    'display': ['_numbered', 'stream_print', '_clean_latex', '_is_markdown'],
    'constants': ['__version__', 'BACKUP_DIR', 'TOOLS']
}
