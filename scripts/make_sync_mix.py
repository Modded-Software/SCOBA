from pathlib import Path
import shutil
import struct
import sys

from project_root import project_root

ROOT = project_root()
BASE = ROOT / "out" / "SCOBA256.SC2Map"
DST = ROOT / "out" / "SCOBA256_mix.SC2Map"
OURS = BASE / "t3SyncHeightMap"
REF = Path("/tmp/notd_t3SyncHeightMap")

mode = sys.argv[1] if len(sys.argv) > 1 else "primary"

ours = bytearray(OURS.read_bytes())
ref = REF.read_bytes()
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

if DST.exists():
    shutil.rmtree(DST)
shutil.copytree(BASE, DST)
(DST / "t3SyncHeightMap").write_bytes(bytes(ours))
print("built", DST, "mode", mode)
