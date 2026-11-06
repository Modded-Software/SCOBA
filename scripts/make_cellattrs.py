from pathlib import Path
import struct

MAP = Path(__file__).resolve().parent.parent / "out" / "SCOBA256.SC2Map"
SIZE = 256
bits = SIZE * SIZE * 8
for name in ["CellAttribute_Pcl", "CellAttribute_Pgr", "CellAttribute_Pnb"]:
    data = bytearray(4 + SIZE * SIZE)
    struct.pack_into("<I", data, 0, bits)
    (MAP / name).write_bytes(bytes(data))
    print("wrote", name, len(data))
