from pathlib import Path
import os
import sys
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from project_root import project_root

ROOT = project_root()
SRC = ROOT / "out" / "SCOBA256.SC2Map"
DST = ROOT / "out" / "SCOBA256_notd.SC2Map"

SWAP = [
    "t3HeightMap", "t3SyncHeightMap", "t3CellFlags", "t3SyncCliffLevel",
    "t3SyncTextureInfo", "t3TextureMasks", "t3VertCol", "t3FluffDoodad",
    "t3HardTile", "t3Water", "t3Terrain.xml", "CellAttribute_Pnp",
]

if DST.exists():
    shutil.rmtree(DST)
shutil.copytree(SRC, DST)
for name in SWAP:
    ref = Path("/tmp") / f"notd_{name}"
    if ref.exists() and ref.stat().st_size > 100:
        shutil.copyfile(ref, DST / name)
        print("swapped", name, ref.stat().st_size)
    else:
        print("kept", name, "(no ref)")
print("built", DST)
