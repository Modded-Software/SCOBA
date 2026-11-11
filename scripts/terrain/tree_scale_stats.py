from pathlib import Path
import re
import sys

for path in sys.argv[1:]:
    text = Path(path).read_text(encoding="utf-8")
    blocks = re.findall(r'<ObjectDoodad\b(?=[^>]*\bType="ZerusTree")[^>]*>', text)
    scales = []
    for block in blocks:
        m = re.search(r'\bScale="([^"]+)"', block)
        if m:
            scales.append(float(m.group(1).split(",")[0]))
    print(path, "trees", len(blocks), "min", min(scales), "max", max(scales))
