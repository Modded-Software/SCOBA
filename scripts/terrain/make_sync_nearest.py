from pathlib import Path
import os
import sys
import struct

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from project_root import project_root

ROOT = project_root()
SRC = ROOT / "src" / "SCOBA.SC2Map" / "t3SyncHeightMap"
DST = ROOT / "out" / "SCOBA256.SC2Map" / "t3SyncHeightMap"
NEW = 257

data = SRC.read_bytes()
magic, ver, sx, sy = struct.unpack_from("<4sIII", data, 0)
n = sx * sy
primary = list(struct.unpack_from("<" + "H" * n, data, 64))
off = 64 + n * 2
sec = data[off:off + n]
ter = data[off + n:off + 2 * n]

out = bytearray(64 + NEW * NEW * 4)
out[:64] = data[:64]
struct.pack_into("<4sIII", out, 0, magic, ver, NEW, NEW)
for y in range(NEW):
    oy = min(y // 2, sy - 1)
    for x in range(NEW):
        ox = min(x // 2, sx - 1)
        struct.pack_into("<H", out, 64 + (y * NEW + x) * 2, primary[oy * sx + ox])
noff = 64 + NEW * NEW * 2
for y in range(NEW):
    oy = min(y // 2, sy - 1)
    for x in range(NEW):
        ox = min(x // 2, sx - 1)
        out[noff + y * NEW + x] = sec[oy * sx + ox]
        out[noff + NEW * NEW + y * NEW + x] = ter[oy * sx + ox]
DST.write_bytes(bytes(out))
print("wrote nearest sync", len(out))
