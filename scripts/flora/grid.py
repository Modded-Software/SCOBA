"""Grid helpers on the 1-unit cell grid: distance transform, shortest path, noise.

Grids are indexed [y, x]; cell (x, y) covers world [x, x + 1) x [y, y + 1).
"""

from __future__ import annotations

import heapq
import math
import random

import numpy as np

SQRT2 = math.sqrt(2.0)
STEPS = ((1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0), (1, 1, SQRT2), (1, -1, SQRT2), (-1, 1, SQRT2), (-1, -1, SQRT2))


def distance_to(mask: np.ndarray) -> np.ndarray:
    """Chamfer distance (1, sqrt 2) from every cell to the nearest True cell; inf without any."""
    h, w = mask.shape
    d = np.where(mask, 0.0, np.inf)
    for _ in range(2):
        for y in range(h):
            row = d[y]
            if y > 0:
                up = d[y - 1]
                row = np.minimum(row, up + 1.0)
                row[1:] = np.minimum(row[1:], up[:-1] + SQRT2)
                row[:-1] = np.minimum(row[:-1], up[1:] + SQRT2)
            for x in range(1, w):
                if row[x - 1] + 1.0 < row[x]:
                    row[x] = row[x - 1] + 1.0
            d[y] = row
        for y in range(h - 1, -1, -1):
            row = d[y]
            if y < h - 1:
                down = d[y + 1]
                row = np.minimum(row, down + 1.0)
                row[1:] = np.minimum(row[1:], down[:-1] + SQRT2)
                row[:-1] = np.minimum(row[:-1], down[1:] + SQRT2)
            for x in range(w - 2, -1, -1):
                if row[x + 1] + 1.0 < row[x]:
                    row[x] = row[x + 1] + 1.0
            d[y] = row
    return d


def shortest_path(cost: np.ndarray, start: tuple[int, int], goal: tuple[int, int]) -> list[tuple[int, int]]:
    """8-connected Dijkstra over per-cell cost (inf blocks). Cells as (x, y); empty when unreachable."""
    h, w = cost.shape
    dist = np.full((h, w), np.inf)
    prev = np.full((h, w, 2), -1, dtype=np.int32)
    sx, sy = start
    dist[sy, sx] = 0.0
    heap = [(0.0, sx, sy)]
    gx, gy = goal
    while heap:
        d, x, y = heapq.heappop(heap)
        if d > dist[y, x]:
            continue
        if (x, y) == (gx, gy):
            break
        for dx, dy, step in STEPS:
            nx, ny = x + dx, y + dy
            if not (0 <= nx < w and 0 <= ny < h):
                continue
            c = cost[ny, nx]
            if not math.isfinite(c):
                continue
            if dx and dy and not (math.isfinite(cost[y, nx]) and math.isfinite(cost[ny, x])):
                continue  # no corner cutting past blocked cells
            nd = d + step * c
            if nd < dist[ny, nx]:
                dist[ny, nx] = nd
                prev[ny, nx] = (x, y)
                heapq.heappush(heap, (nd, nx, ny))
    if not math.isfinite(dist[gy, gx]):
        return []
    path = [(gx, gy)]
    while path[-1] != (sx, sy):
        x, y = path[-1]
        px, py = prev[y, x]
        path.append((int(px), int(py)))
    return path[::-1]


def path_length(path: list[tuple[float, float]]) -> float:
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(path, path[1:]))


def value_noise(shape: tuple[int, int], period: int, rng: random.Random) -> np.ndarray:
    """Smooth noise in [0, 1): random lattice every `period` cells, bilinear between."""
    h, w = shape
    gh, gw = h // period + 2, w // period + 2
    lattice = np.array([[rng.random() for _ in range(gw)] for _ in range(gh)])
    ys = np.arange(h) / period
    xs = np.arange(w) / period
    y0 = ys.astype(int)
    x0 = xs.astype(int)
    fy = (ys - y0)[:, None]
    fx = (xs - x0)[None, :]
    fy = fy * fy * (3 - 2 * fy)
    fx = fx * fx * (3 - 2 * fx)
    a = lattice[np.ix_(y0, x0)]
    b = lattice[np.ix_(y0, x0 + 1)]
    c = lattice[np.ix_(y0 + 1, x0)]
    d = lattice[np.ix_(y0 + 1, x0 + 1)]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def disk_cells(x: float, y: float, r: float, shape: tuple[int, int]) -> tuple[np.ndarray, np.ndarray]:
    """Row and column indices of cells whose centre lies within r of (x, y)."""
    h, w = shape
    x0, x1 = max(0, int(math.floor(x - r))), min(w, int(math.ceil(x + r)) + 1)
    y0, y1 = max(0, int(math.floor(y - r))), min(h, int(math.ceil(y + r)) + 1)
    if x1 <= x0 or y1 <= y0:  # disk wholly off the map
        return np.zeros(0, dtype=int), np.zeros(0, dtype=int)
    ys, xs = np.mgrid[y0:y1, x0:x1]
    keep = np.hypot(xs + 0.5 - x, ys + 0.5 - y) <= r
    return ys[keep], xs[keep]
