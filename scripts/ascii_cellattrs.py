from pathlib import Path
import struct
import sys


def load(path):
    data = Path(path).read_bytes()
    bits = struct.unpack_from("<I", data, 0)[0]
    cells = bits // 8
    n = int(round(cells ** 0.5))
    return n, data[4:4 + cells]


def ascii_map(grid, n, step):
    for y in range(0, n, step):
        row = []
        for x in range(0, n, step):
            v = grid[y * n + x]
            row.append("#" if v else ".")
        print("".join(row))


for path in sys.argv[1:]:
    n, grid = load(path)
    print(path, "n=", n)
    ascii_map(grid, n, max(1, n // 64))
    print()
