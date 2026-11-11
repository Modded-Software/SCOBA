from pathlib import Path
import os
import sys
import struct

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from project_root import project_root

MAP = project_root() / "out" / "SCOBA256.SC2Map"


def read(p):
    return p.read_bytes()


def write(p, b):
    p.write_bytes(b)


def flatten_heightmap():
    p = MAP / "t3HeightMap"
    data = bytearray(read(p))
    magic, ver, sx, sy = struct.unpack_from("<4sIII", data, 0)
    center = (sy // 2) * sx + sx // 2
    base, adj, unk = struct.unpack_from("<HHH", data, 32 + center * 6)
    for i in range(sx * sy):
        struct.pack_into("<HHH", data, 32 + i * 6, base, adj, unk)
    write(p, bytes(data))
    print("heightmap flat", sx, sy, base)
    return base, adj


def flatten_sync_heightmap():
    p = MAP / "t3SyncHeightMap"
    data = bytearray(read(p))
    magic, ver, sx, sy = struct.unpack_from("<4sIII", data, 0)
    n = sx * sy
    center = (sy // 2) * sx + sx // 2
    base = struct.unpack_from("<H", data, 64 + center * 2)[0]
    off = 64 + n * 2
    sec = struct.unpack_from("<h", data, off + center * 2)[0]
    for i in range(n):
        struct.pack_into("<H", data, 64 + i * 2, base)
        struct.pack_into("<h", data, off + i * 2, sec)
    write(p, bytes(data))
    print("sync heightmap flat", sx, sy, "primary", base, "secondary", sec)


def write_cell_flags(value=2):
    p = MAP / "t3CellFlags"
    data = bytearray(read(p))
    magic, ver = struct.unpack_from("<4sI", data, 0)
    w, h = struct.unpack_from("<II", data, 24)
    data[32:32 + w * h] = bytes([value]) * (w * h)
    write(p, bytes(data))
    print("cellflags all", value, w, h)


def write_cliff_level(value=64):
    p = MAP / "t3SyncCliffLevel"
    data = bytearray(read(p))
    w, h = struct.unpack_from("<II", data, 8)
    for i in range(w * h):
        struct.pack_into("<H", data, 32 + i * 2, value)
    write(p, bytes(data))
    print("cliff level all", value, w, h)


def clear_cell_attribute(name):
    p = MAP / name
    data = bytearray(read(p))
    bits = struct.unpack_from("<I", data, 0)[0]
    cells = bits // 8
    data[4:4 + cells] = bytes(cells)
    write(p, bytes(data))
    print(name, "cleared", cells)


base, adj = flatten_heightmap()
flatten_sync_heightmap()
write_cell_flags(2)
write_cliff_level(64)
clear_cell_attribute("CellAttribute_Cpl")
clear_cell_attribute("CellAttribute_Pnp")
print("done")
