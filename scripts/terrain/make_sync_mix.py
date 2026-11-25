"""Copy the built map to SCOBA256_mix with t3SyncHeightMap layers from SC2_TMP/notd_t3SyncHeightMap."""

import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import workpaths


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "primary"
    base = workpaths.path("SC2_BUILT_MAP")
    dst = workpaths.path("SC2_OUT") / "SCOBA256_mix.SC2Map"
    ours = bytearray((base / "t3SyncHeightMap").read_bytes())
    ref = (workpaths.path("SC2_TMP") / "notd_t3SyncHeightMap").read_bytes()
    n = 257 * 257
    poff = 64
    soff = 64 + n * 2

    if mode == "primary":
        ours[poff:soff] = ref[poff:soff]
    elif mode == "secondary":
        ours[soff:] = ref[soff:]
    elif mode == "both":
        ours = bytearray(ref)
    else:
        raise SystemExit("mode: primary|secondary|both")

    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(base, dst)
    (dst / "t3SyncHeightMap").write_bytes(bytes(ours))
    print("built", dst, "mode", mode)


if __name__ == "__main__":
    main()
