import re

with open('lib/main.dart', 'r', encoding='utf-8') as f:
    lines = f.readlines()

current_class = None
classes = {}

for i, line in enumerate(lines, 1):
    m_class = re.match(r'^class\s+([A-Za-z0-9_]+)', line)
    if m_class:
        current_class = m_class.group(1)
        classes[current_class] = {'line': i, 'methods': []}
        continue
    
    if current_class:
        # Match methods
        m_method = re.match(r'^\s{2,4}([A-Za-z0-9_<>]+(?:\s+[A-Za-z0-9_<>]+)?)\s+([A-Za-z0-9_]+)\s*\((.*?)\)', line)
        if m_method:
            ret_type, name, args = m_method.groups()
            if name not in ['if', 'for', 'while', 'switch', 'catch']:
                classes[current_class]['methods'].append((i, name, args, line.strip()))

with open('scratch/main_structure.txt', 'w', encoding='utf-8') as f:
    for cls, info in classes.items():
        f.write(f"Class: {cls} (Line {info['line']})\n")
        for m in info['methods']:
            f.write(f"   Line {m[0]}: {m[1]} ({m[2]})\n")
        f.write("\n")

print(f"Analyzed {len(classes)} classes")
