from pathlib import Path
import os
import sys
import re
import struct

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from project_root import project_root

ROOT = project_root()
SRCDIR = ROOT / "src" / "SCOBA.SC2Map"

xml = (SRCDIR / "t3Terrain.xml").read_text(encoding="utf-8", errors="replace")
m = re.search(r'<vertData[^>]*quantizeBias="([^"]+)"[^>]*quantizeScale="([^"]+)"[^>]*standardHeight="([^"]+)"', xml)
q_bias = float(m.group(1)); q_scale = float(m.group(2)); std = float(m.group(3))
print("quantizeBias", q_bias, "quantizeScale", q_scale, "standardHeight", std)

hm = (SRCDIR / "t3HeightMap").read_bytes()
sx, sy = struct.unpack_from("<II", hm, 8)
recs = [struct.unpack_from("<HHH", hm, 32 + i * 6) for i in range(sx * sy)]

sh = (SRCDIR / "t3SyncHeightMap").read_bytes()
ssx, ssy = struct.unpack_from("<II", sh, 8)
prim = struct.unpack_from("<" + "H" * (ssx * ssy), sh, 64)

for idx in [0, 100, 5000, 8000, 16000, 9000, 12000]:
    adj, base, mask = recs[idx]
    sync = prim[idx]
    level = (adj + base) * q_scale - q_bias - std - 1
    print(f"i={idx} adj={adj} base={base} sum={adj+base} mask={mask} sync={sync} sync/256={sync/256:.3f} sync/4={sync/4:.3f} level={level:.3f} level*256={(level+1)*256:.1f}")
