"""Copy the built map to SCOBA256_notd and swap in NOTD refs from SC2_TMP/notd_<name>."""

import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import workpaths

SWAP = [
    "t3HeightMap", "t3SyncHeightMap", "t3CellFlags", "t3SyncCliffLevel",
    "t3SyncTextureInfo", "t3TextureMasks", "t3VertCol", "t3FluffDoodad",
    "t3HardTile", "t3Water", "t3Terrain.xml", "CellAttribute_Pnp",
]  # fmt: skip


def main() -> None:
    dst = workpaths.path("SC2_OUT") / "SCOBA256_notd.SC2Map"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(workpaths.path("SC2_BUILT_MAP"), dst)
    for name in SWAP:
        ref = workpaths.path("SC2_TMP") / f"notd_{name}"
        if ref.exists() and ref.stat().st_size > 100:
            shutil.copyfile(ref, dst / name)
            print("swapped", name, ref.stat().st_size)
        else:
            print("kept", name, "(no ref)")
    print("built", dst)


if __name__ == "__main__":
    main()
