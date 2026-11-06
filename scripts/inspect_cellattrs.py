from pathlib import Path
import struct
import sys


def load(path):
    data = Path(path).read_bytes()
    bits = struct.unpack_from("<I", data, 0)[0]
    cells = bits // 8
    n = int(cells ** 0.5)
    return n, data[4:4 + cells]


def summarize(name, n, grid):
    counts = {}
    for v in grid:
        counts[v] = counts.get(v, 0) + 1
    print(name, "n=", n, "counts=", dict(sorted(counts.items())))
    for (x0, x1, y0, y1, label) in [
        (0, n // 2, 0, n // 2, "LL"), (n // 2, n, n // 2, n, "UR"),
        (n // 2, n, 0, n // 2, "LR"), (0, n // 2, n // 2, n, "UL"),
    ]:
        vals = [grid[y * n + x] for y in range(y0, y1) for x in range(x0, x1)]
        c = {}
        for v in vals:
            c[v] = c.get(v, 0) + 1
        print("  ", label, dict(sorted(c.items())))


for path in sys.argv[1:]:
    n, grid = load(path)
    summarize(path, n, grid)
