from pathlib import Path
import struct
import sys


def load_hm(path):
    data = Path(path).read_bytes()
    magic, ver, sx, sy = struct.unpack_from("<4sIII", data, 0)
    vals = []
    for i in range(sx * sy):
        base, adj, unk = struct.unpack_from("<HHH", data, 32 + i * 6)
        vals.append(base)
    return sx, sy, vals


for path in sys.argv[1:]:
    sx, sy, vals = load_hm(path)
    lo, hi = min(vals), max(vals)
    print(path, "sx", sx, "sy", sy, "min", lo, "max", hi, "span", hi - lo)
    counts = {}
    for v in vals:
        k = v // 256
        counts[k] = counts.get(k, 0) + 1
    print("  hist/256", dict(sorted(counts.items())[:8]), "..." if len(counts) > 8 else "")
    step = max(1, sx // 64)
    chars = " .:-=+*#%@"
    for y in range(0, sy, step):
        row = []
        for x in range(0, sx, step):
            v = vals[y * sx + x]
            idx = 0 if hi == lo else int((v - lo) * (len(chars) - 1) / (hi - lo))
            row.append(chars[idx])
        print("".join(row))
    print()
