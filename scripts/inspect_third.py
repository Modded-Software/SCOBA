from pathlib import Path
import struct
import sys

for p in sys.argv[1:]:
    data = Path(p).read_bytes()
    magic, ver, sx, sy = struct.unpack_from("<4sIII", data, 0)
    n = sx * sy
    third = [struct.unpack_from("<H", data, 32 + i * 6 + 4)[0] for i in range(n)]
    c = {}
    for v in third:
        c[v] = c.get(v, 0) + 1
    print(p, "sx,sy", sx, sy, "distinct", len(c), "top", sorted(c.items(), key=lambda kv: -kv[1])[:8])
