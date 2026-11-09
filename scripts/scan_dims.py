from pathlib import Path
import struct

from project_root import project_root

OUT = project_root() / "out" / "SCOBA256.SC2Map"

for p in sorted(OUT.iterdir()):
    if not p.is_file():
        continue
    data = p.read_bytes()
    hits = []
    for off in range(0, min(96, len(data) - 3), 1):
        v = struct.unpack_from("<I", data, off)[0]
        if v in (128, 129):
            hits.append((off, v))
    if hits:
        print(p.name, "size", len(data), "128/129 at", hits)
