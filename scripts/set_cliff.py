from pathlib import Path
import struct
import sys

from project_root import project_root

MAP = project_root() / "out" / "SCOBA256.SC2Map"
value = int(sys.argv[1]) if len(sys.argv) > 1 else 0

p = MAP / "t3SyncCliffLevel"
data = bytearray(p.read_bytes())
w, h = struct.unpack_from("<II", data, 8)
for i in range(w * h):
    struct.pack_into("<H", data, 32 + i * 2, value)
p.write_bytes(bytes(data))
print("cliff set", value, w, h)
