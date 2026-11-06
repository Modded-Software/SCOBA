from pathlib import Path
import struct

MAP = Path(__file__).resolve().parent.parent / "out" / "SCOBA256.SC2Map"
SIZE = 256

data = bytearray(32 + SIZE * SIZE * 2)
struct.pack_into("<4sIII", data, 0, b"PATH", 100, SIZE, SIZE)
out = MAP / "t3SyncPathingInfo"
out.write_bytes(bytes(data))
print("wrote", out, len(data), SIZE, "x", SIZE, "all passable (0x0000)")
