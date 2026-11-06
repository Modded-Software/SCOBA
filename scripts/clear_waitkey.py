from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parent.parent
path = ROOT / "out" / "SCOBA256.SC2Map" / "MapInfo"
data = bytearray(path.read_bytes())
version = struct.unpack_from("<I", data, 4)[0]
pos = 8
hash_off = pos
pos += 8
width, height = struct.unpack_from("<II", data, pos)
pos += 8
locale_mode = struct.unpack_from("<I", data, pos)[0]
pos += 4
if locale_mode == 2:
    pos = data.index(0, pos) + 1
if version >= 22:
    preview_type = struct.unpack_from("<I", data, pos)[0]
    pos += 4
    if preview_type == 2:
        pos = data.index(0, pos) + 1
if version >= 28:
    pos = data.index(0, pos) + 1
if version >= 37:
    pos = data.index(0, pos) + 1
if version >= 29:
    pos += 4
if version >= 11:
    pos += 4
if version >= 3:
    pos = data.index(0, pos) + 1
desc_start = pos
desc_end = data.index(0, pos)
desc_len = desc_end - desc_start
pos = desc_end + 1
bounds_off = pos
left, bottom, right, top = struct.unpack_from("<4i", data, bounds_off)
pos += 16
if version >= 19:
    pos += 4
if version >= 14:
    pos += 4
    pos = data.index(0, pos) + 1
if version >= 23:
    bar_len = struct.unpack_from("<H", data, pos)[0]
    pos += 2 + bar_len
if version >= 20:
    pos += 24
if version >= 35:
    pos = data.index(0, pos) + 1
    locale_len = struct.unpack_from("<H", data, pos)[0]
    pos += 2 + locale_len
if version >= 39:
    str_len = struct.unpack_from("<H", data, pos)[0]
    pos += 2 + str_len
flags_off = pos
flags = struct.unpack_from("<I", data, flags_off)[0]
print("version", version, "w,h", width, height, "bounds", (left, bottom, right, top))
print("flags_off", flags_off, "flags", hex(flags), "wait_for_key", bool(flags & 0x02))

if len(sys.argv) > 1 and sys.argv[1] == "clear":
    newflags = flags & ~0x02
    struct.pack_into("<I", data, flags_off, newflags)
    popcount = bin(newflags).count("1")
    dx, dy = right - left, top - bottom
    hash_value = desc_len + 7 * height + 2 * (dx * dx + dy * dy) + 3 * width - popcount - 17
    struct.pack_into("<Q", data, hash_off, hash_value)
    path.write_bytes(bytes(data))
    print("cleared; new flags", hex(newflags), "hash", hash_value)
