import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import workpaths


def main() -> None:
    built = workpaths.path("SC2_BUILT_MAP")
    xml = (built / "t3Terrain.xml").read_text(encoding="utf-8", errors="replace")
    m = re.search(
        r'<vertData[^>]*quantizeBias="([^"]+)"[^>]*quantizeScale="([^"]+)"[^>]*standardHeight="([^"]+)"',
        xml,
    )
    q_bias = float(m.group(1))
    q_scale = float(m.group(2))
    std = float(m.group(3))

    hm = (built / "t3HeightMap").read_bytes()
    sx, sy = struct.unpack_from("<II", hm, 8)
    records = [struct.unpack_from("<HHH", hm, 32 + i * 6) for i in range(sx * sy)]

    shp = built / "t3SyncHeightMap"
    sh = bytearray(shp.read_bytes())
    _magic, _version, ssx, ssy = struct.unpack_from("<4sIII", sh, 0)
    assert (sx, sy) == (ssx, ssy)

    for i in range(sx * sy):
        adj, base, _mask = records[i]
        level = (adj + base) * q_scale - q_bias - std - 1.0
        value = round((level + 1.0) * 256.0)
        value = max(0, min(65535, value))
        struct.pack_into("<H", sh, 64 + i * 2, value)
    shp.write_bytes(bytes(sh))
    print("rebaked sync primary from render; sx,sy", sx, sy)


if __name__ == "__main__":
    main()
