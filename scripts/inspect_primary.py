from pathlib import Path
import struct
import sys

for p in sys.argv[1:]:
    data = Path(p).read_bytes()
    magic, ver, sx, sy = struct.unpack_from("<4sIII", data, 0)
    n = sx * sy
    prim = list(struct.unpack_from("<" + "H" * n, data, 64))
    print(p, "sx,sy", sx, sy, "min", min(prim), "max", max(prim))
    for label, y0, y1 in [("low", 0, sy // 2), ("high", sy // 2, sy)]:
        vals = [prim[y * sx + x] for y in range(y0, y1) for x in range(sx)]
        print("  ", label, "min", min(vals), "max", max(vals), "mean", sum(vals) / len(vals))
