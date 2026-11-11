from pathlib import Path
import struct
import sys

for p in sys.argv[1:]:
    data = Path(p).read_bytes()
    magic, ver, sx, sy = struct.unpack_from("<4sIII", data, 0)
    n = sx * sy
    off = 64 + n * 2
    sec = data[off:off + n]
    ter = data[off + n:off + 2 * n]
    def stats(name, g):
        if not g:
            print(" ", name, "missing")
            return
        c = {}
        for v in g:
            c[v] = c.get(v, 0) + 1
        top = sorted(c.items(), key=lambda kv: -kv[1])[:6]
        print(" ", name, "n", len(g), "distinct", len(c), "top", top)
    print(p, "sx,sy", sx, sy, "lens", len(sec), len(ter))
    stats("secondary", sec)
    stats("tertiary", ter)
