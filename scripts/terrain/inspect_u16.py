from pathlib import Path
import struct
import sys

for p in sys.argv[1:]:
    data = Path(p).read_bytes()
    w, h = struct.unpack_from("<II", data, 8)
    vals = struct.unpack_from("<" + "H" * (w * h), data, 32)
    c = {}
    for v in vals:
        c[v] = c.get(v, 0) + 1
    print(p, "w,h", w, h, "distinct", sorted(c.items())[:12], "n", len(c))
