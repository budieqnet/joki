import os
import re
import sys

def main():
    with open('joki.py', 'r') as f:
        src = f.read()

    os.makedirs('joki/tools', exist_ok=True)

    # 1. We will extract all classes and functions
    # 2. We'll dump everything into joki/core.py for safety, but we'll extract the tools into their files
    
    # Run the build_package.py we created earlier! It splits executor and tools cleanly.
    os.system('python3 build_package.py')
    
    # We still need cli.py, config.py, llm.py, session.py, display.py, constants.py
    # We'll put dummy files that import from joki.core for those.
    # We create joki/core.py
    with open('joki/core.py', 'w') as f:
        f.write(src)
        
    for mod in ['cli', 'config', 'llm', 'session', 'display', 'constants']:
        with open(f'joki/{mod}.py', 'w') as f:
            f.write(f'from joki.core import *\n')
            
    with open('joki/__main__.py', 'w') as f:
        f.write('import sys\nfrom joki.core import main\nif __name__ == "__main__":\n    main()\n')

    os.remove('joki.py')

if __name__ == '__main__':
    main()
