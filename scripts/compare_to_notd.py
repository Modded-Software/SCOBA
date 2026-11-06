from pathlib import Path
import struct

OURS = Path(__file__).resolve().parent.parent / "out" / "SCOBA256.SC2Map"
REF_DIR = Path("/tmp")

names = [
    "MapInfo", "t3HeightMap", "t3SyncHeightMap", "t3CellFlags",
    "t3SyncCliffLevel", "t3SyncTextureInfo", "t3TextureMasks", "t3VertCol",
    "t3FluffDoodad", "t3HardTile", "t3Water", "t3Terrain.xml",
    "CellAttribute_Pnp", "CellAttribute_Pcl", "CellAttribute_Pgr",
    "CellAttribute_Pnb", "CellAttribute_Cpl",
]

for name in names:
    ours = OURS / name
    ref = REF_DIR / f"notd_{name}"
    print("=====", name)
    print("  ours:", "missing" if not ours.exists() else ours.stat().st_size)
    print("  ref :", "missing" if not ref.exists() else ref.stat().st_size)
    if ours.exists():
        b = ours.read_bytes()[:64]
        print("  ours head:", b.hex(" "))
    if ref.exists():
        b = ref.read_bytes()[:64]
        print("  ref  head:", b.hex(" "))
