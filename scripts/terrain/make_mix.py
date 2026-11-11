from pathlib import Path
import shutil
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from project_root import project_root

ROOT = project_root()
BASE = ROOT / "out" / "SCOBA256.SC2Map"
DST = ROOT / "out" / "SCOBA256_mix.SC2Map"

names = sys.argv[1:]
if DST.exists():
    shutil.rmtree(DST)
shutil.copytree(BASE, DST)
for name in names:
    ref = Path("/tmp") / f"notd_{name}"
    if not ref.exists() or ref.stat().st_size < 100:
        raise SystemExit(f"no notd ref for {name}")
    shutil.copyfile(ref, DST / name)
    print("swapped in NOTD", name)
print("built", DST)
