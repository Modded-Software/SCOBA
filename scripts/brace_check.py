from pathlib import Path
import sys

path = Path(sys.argv[1])
limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10**9
depth = 0
for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
    if number > limit:
        break
    depth += line.count("{") - line.count("}")
    if depth < 0:
        print("negative depth at", number, line)
        break
print("depth", depth, "at line", min(number, limit))
