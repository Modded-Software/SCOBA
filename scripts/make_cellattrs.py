from pathlib import Path
import struct

from project_root import project_root

MAP = project_root() / "out" / "SCOBA256.SC2Map"
SIZE = 256
bits = SIZE * SIZE * 8
for name in ["CellAttribute_Pcl", "CellAttribute_Pgr", "CellAttribute_Pnb"]:
    data = bytearray(4 + SIZE * SIZE)
    struct.pack_into("<I", data, 0, bits)
    (MAP / name).write_bytes(bytes(data))
    print("wrote", name, len(data))
