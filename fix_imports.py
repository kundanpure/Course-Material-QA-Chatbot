import os
import re

# Directory to search
backend_dir = r"c:\Users\KIIT\Downloads\Major8th\backend"

# Pattern to find and replace
pattern = re.compile(r'from app\.([a-zA-Z0-9_.]+) import')
replacement = r'from \1 import'

# Counter
files_changed = 0
total_replacements = 0

# Walk through all Python files
for root, dirs, files in os.walk(backend_dir):
    # Skip frontend and venv directories
    if 'frontend' in root or 'venv' in root or 'node_modules' in root:
        continue
        
    for file in files:
        if file.endswith('.py'):
            filepath = os.path.join(root, file)
            
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Replace all occurrences
                new_content, count = pattern.subn(replacement, content)
                
                if count > 0:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    files_changed += 1
                    total_replacements += count
                    print(f"Fixed {count} imports in: {filepath}")
                    
            except Exception as e:
                print(f"Error processing {filepath}: {e}")

print(f"\n✅ Done! Fixed {total_replacements} imports in {files_changed} files")
