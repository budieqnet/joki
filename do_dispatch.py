import sys

def refactor():
    with open('joki.py', 'r') as f:
        lines = f.readlines()
        
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
        
    out = []
    handler_names = []
    for name, block in funcs:
        func_name = f"handle_{name}"
        handler_names.append((name, func_name))
        out.append(f"def {func_name}(args):\n")
        if not "".join(block).strip():
            out.append("    pass\n")
        else:
            out.extend(block)
        out.append("\n")
        
    out.append("TOOL_HANDLERS = {\n")
    for name, func_name in handler_names:
        out.append(f'    "{name}": {func_name},\n')
    out.append("}\n\n")
    
    out.append("def execute(name, args):\n")
    out.append("    handler = TOOL_HANDLERS.get(name)\n")
    out.append("    if not handler:\n")
    out.append('        return f"Unknown tool: {name}"\n')
    out.append("    try:\n")
    out.append("        return handler(args)\n")
    out.append("    except Exception as e:\n")
    out.append('        return f"Error: {e}"\n')
    out.append("\n")
    
    final_lines = lines[:start_idx] + out + lines[end_idx:]
    with open('joki.py', 'w') as f:
        f.writelines(final_lines)

if __name__ == "__main__":
    refactor()
