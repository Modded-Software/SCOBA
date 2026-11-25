"""Compare the built map's terrain files with NOTD refs saved as SC2_TMP/notd_<name>."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import workpaths

NAMES = [
    "MapInfo", "t3HeightMap", "t3SyncHeightMap", "t3CellFlags",
    "t3SyncCliffLevel", "t3SyncTextureInfo", "t3TextureMasks", "t3VertCol",
    "t3FluffDoodad", "t3HardTile", "t3Water", "t3Terrain.xml",
    "CellAttribute_Pnp", "CellAttribute_Pcl", "CellAttribute_Pgr",
    "CellAttribute_Pnb", "CellAttribute_Cpl",
]  # fmt: skip


def main() -> None:
    built = workpaths.path("SC2_BUILT_MAP")
    refs = workpaths.path("SC2_TMP")
    for name in NAMES:
        ours = built / name
        ref = refs / f"notd_{name}"
        print("=====", name)
        print("  ours:", "missing" if not ours.exists() else ours.stat().st_size)
        print("  ref :", "missing" if not ref.exists() else ref.stat().st_size)
        if ours.exists():
            print("  ours head:", ours.read_bytes()[:64].hex(" "))
        if ref.exists():
            print("  ref  head:", ref.read_bytes()[:64].hex(" "))


if __name__ == "__main__":
    main()
