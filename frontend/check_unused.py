import os
import re

src_dir = r"d:\Trading\quadrium\frontend\src"
ui_dir = os.path.join(src_dir, "components", "ui")

if not os.path.exists(ui_dir):
    print("UI directory not found")
    exit(0)

ui_components = [f[:-4] for f in os.listdir(ui_dir) if f.endswith('.tsx')]
used_components = set()

for root, dirs, files in os.walk(src_dir):
    for file in files:
        if not file.endswith(('.tsx', '.ts')): continue
        filepath = os.path.join(root, file)
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            for comp in ui_components:
                # If we're looking at the component's own file, skip self-check
                if filepath == os.path.join(ui_dir, comp + '.tsx'):
                    continue
                    
                # Match various import styles:
                # @/components/ui/button
                # ../ui/button
                # ./button (if imported from another ui component)
                pattern = r"['\"](?:[^'\"]*?/ui/|(?:\./|\.\./)+)" + re.escape(comp) + r"['\"]"
                if re.search(pattern, content):
                    used_components.add(comp)

unused = set(ui_components) - used_components
for u in unused:
    print(u)
