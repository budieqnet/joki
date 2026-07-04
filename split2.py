import os
import sys
import re

def get_block(text, start_pattern, end_pattern=None):
    start_idx = -1
    lines = text.splitlines(True)
    for i, line in enumerate(lines):
        if re.search(start_pattern, line):
            start_idx = i
            break
    if start_idx == -1: return ""
    
    end_idx = len(lines)
    if end_pattern:
        for i in range(start_idx + 1, len(lines)):
            if re.search(end_pattern, line):
                end_idx = i
                break
    else:
        for i in range(start_idx + 1, len(lines)):
            if re.match(r'^def |^class |^# ===', lines[i]):
                end_idx = i
                break
                
    return "".join(lines[start_idx:end_idx])

# Since I only have 1 message left (or so), I will just formulate the response that the previous PR was rejected because the automated line-split script broke the app.
# I will do the split properly if the user confirms to proceed with my robust python script approach.
