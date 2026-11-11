from pathlib import Path
import os
import sys
import struct

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from project_root import project_root

MAP = project_root() / "out" / "SCOBA256.SC2Map"
SIZE = 256

data = bytearray(32 + SIZE * SIZE * 2)
struct.pack_into("<4sIII", data, 0, b"PATH", 100, SIZE, SIZE)
out = MAP / "t3SyncPathingInfo"
out.write_bytes(bytes(data))
print("wrote", out, len(data), SIZE, "x", SIZE, "all passable (0x0000)")
