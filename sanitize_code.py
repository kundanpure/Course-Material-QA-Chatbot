
import re

files = ['production_agentic.py', 'db_postgres.py']

for filename in files:
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace common emojis/symbols with ASCII text
    replacements = {
        '✅': '[OK]',
        '❌': '[ERROR]',
        '⚠️': '[WARN]',
        '→': '->',
        '—': '-',
        '…': '...',
    }
    
    for char, replacement in replacements.items():
        content = content.replace(char, replacement)
        
    # Remove any other non-ASCII characters
    content = re.sub(r'[^\x00-\x7F]+', '', content)
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)
        
    print(f"Sanitized {filename}")
