from pathlib import Path
import struct
import sys

for p in sys.argv[1:]:
    data = Path(p).read_bytes()
    magic, ver, sx, sy = struct.unpack_from("<4sIII", data, 0)
    n = sx * sy
    prim = struct.unpack_from("<" + "H" * n, data, 64)
    lo, hi = min(prim), max(prim)
    chars = " .:-=+*#%@"
    step = max(1, sx // 64)
    print("=====", p, "min", lo, "max", hi)
    for y in range(0, sy, step):
        row = []
        for x in range(0, sx, step):
            v = prim[y * sx + x]
            idx = 0 if hi == lo else int((v - lo) * (len(chars) - 1) / (hi - lo))
            row.append(chars[idx])
        print("".join(row))
    print()
