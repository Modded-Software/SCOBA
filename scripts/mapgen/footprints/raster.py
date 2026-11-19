"""Outline sampling, erosion and tracing on the 0.5 pathing grid.

Masks are indexed [row = y, col = x]. Fine sample masks hold
config.SAMPLES_PER_SUB samples per sub-cell side.
"""

from __future__ import annotations

import math

import numpy as np

from . import config

Polygon = tuple[tuple[float, float], ...]


def inside(points: np.ndarray, seg: np.ndarray) -> np.ndarray:
    """Even-odd test of points (N, 2) against the closed outline of segments (M, 4)."""
    if len(seg) == 0:
        return np.zeros(len(points), dtype=bool)
    px = points[:, 0:1]
    py = points[:, 1:2]
    x1, y1, x2, y2 = (seg[:, i][None, :] for i in range(4))
    straddle = (y1 > py) != (y2 > py)
    with np.errstate(divide="ignore", invalid="ignore"):
        cross_x = x1 + (py - y1) * (x2 - x1) / (y2 - y1)
    hits = straddle & (px < cross_x)
    return (hits.sum(axis=1) % 2) == 1


def mesh_samples(outlines: list[np.ndarray], clip: bool = False) -> tuple[np.ndarray, float, float, int, int]:
    """Fine samples of the union of outlines on a grid aligned to the sub-cells.

    clip: a sample counts for an outline only inside that outline's box, so
    an open contour cannot fill along its row beyond its own part (halls).
    Returns (inside mask of samples, x0, y0 of the grid, sub rows, sub cols).
    """
    sub = config.SUB
    per = config.SAMPLES_PER_SUB
    every = np.concatenate([o for o in outlines if len(o)] or [np.zeros((0, 4))])
    if len(every) == 0:
        return np.zeros((0, 0), dtype=bool), 0.0, 0.0, 0, 0
    xs = np.concatenate([every[:, 0], every[:, 2]])
    ys = np.concatenate([every[:, 1], every[:, 3]])
    x0 = math.floor(xs.min() / sub) * sub - sub
    y0 = math.floor(ys.min() / sub) * sub - sub
    cols = int(math.ceil((xs.max() - x0) / sub)) + 1
    rows = int(math.ceil((ys.max() - y0) / sub)) + 1
    fine = sub / per
    gx = x0 + (np.arange(cols * per) + 0.5) * fine
    gy = y0 + (np.arange(rows * per) + 0.5) * fine
    mx, my = np.meshgrid(gx, gy)
    points = np.stack([mx.ravel(), my.ravel()], axis=1)
    mask = np.zeros(len(points), dtype=bool)
    for outline in outlines:
        hit = inside(points, outline)
        if clip and len(outline):
            lo_x = min(outline[:, 0].min(), outline[:, 2].min())
            hi_x = max(outline[:, 0].max(), outline[:, 2].max())
            lo_y = min(outline[:, 1].min(), outline[:, 3].min())
            hi_y = max(outline[:, 1].max(), outline[:, 3].max())
            hit &= (points[:, 0] >= lo_x) & (points[:, 0] <= hi_x) & (points[:, 1] >= lo_y) & (points[:, 1] <= hi_y)
        mask |= hit
    return mask.reshape(len(gy), len(gx)), x0, y0, rows, cols


def erode(samples: np.ndarray, radius: float) -> np.ndarray:
    """Keep the samples whose whole disk of `radius` is mesh."""
    reach = int(round(radius / (config.SUB / config.SAMPLES_PER_SUB)))
    if reach <= 0 or samples.size == 0:
        return samples
    padded = np.pad(samples, reach, constant_values=False)
    out = samples.copy()
    rows, cols = samples.shape
    for dy in range(-reach, reach + 1):
        for dx in range(-reach, reach + 1):
            if dx * dx + dy * dy <= reach * reach:
                out &= padded[reach + dy : reach + dy + rows, reach + dx : reach + dx + cols]
    return out


def fill_subcells(samples: np.ndarray, rows: int, cols: int) -> np.ndarray:
    """Share of mesh per sub-cell."""
    per = config.SAMPLES_PER_SUB
    return samples.reshape(rows, per, cols, per).mean(axis=(1, 3))


def largest_component(mask: np.ndarray) -> np.ndarray:
    """Largest 4-connected component of mask, holes filled, pinches closed."""
    rows, cols = mask.shape
    seen = np.zeros_like(mask)
    best: list[tuple[int, int]] = []
    for r in range(rows):
        for c in range(cols):
            if not mask[r, c] or seen[r, c]:
                continue
            stack = [(r, c)]
            seen[r, c] = True
            cells = []
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < rows and 0 <= nx < cols and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
            if len(cells) > len(best):
                best = cells
    out = np.zeros_like(mask)
    for y, x in best:
        out[y, x] = True
    # Fill holes: open cells not reachable from the border.
    outside = np.zeros_like(mask)
    stack = [(y, x) for y in range(rows) for x in (0, cols - 1)] + [(y, x) for x in range(cols) for y in (0, rows - 1)]
    while stack:
        y, x = stack.pop()
        if not (0 <= y < rows and 0 <= x < cols) or outside[y, x] or out[y, x]:
            continue
        outside[y, x] = True
        stack.extend(((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)))
    return close_pinches(~outside)


def close_pinches(mask: np.ndarray) -> np.ndarray:
    """Fill one cell of every 2x2 block whose cells touch only at a corner.

    A corner pinch would make the outline visit one grid point twice.
    """
    mask = mask.copy()
    changed = True
    while changed:
        changed = False
        for r in range(mask.shape[0] - 1):
            for c in range(mask.shape[1] - 1):
                a, b = mask[r, c], mask[r, c + 1]
                d, e = mask[r + 1, c], mask[r + 1, c + 1]
                if a and e and not b and not d:
                    mask[r, c + 1] = True
                    changed = True
                elif b and d and not a and not e:
                    mask[r, c] = True
                    changed = True
    return mask


def trace(mask: np.ndarray, x0: float, y0: float) -> Polygon:
    """Clockwise outline of one simply connected region of sub-cells, collinear points removed."""
    rows, cols = mask.shape
    edges: dict[tuple[int, int], tuple[int, int]] = {}
    # Directed boundary edges with the region on the right (clockwise outline),
    # in grid corner coordinates (x = column, y = row).
    for r in range(rows):
        for c in range(cols):
            if not mask[r, c]:
                continue
            if r == 0 or not mask[r - 1, c]:
                edges[(c + 1, r)] = (c, r)  # bottom edge, right to left
            if r == rows - 1 or not mask[r + 1, c]:
                edges[(c, r + 1)] = (c + 1, r + 1)  # top edge, left to right
            if c == 0 or not mask[r, c - 1]:
                edges[(c, r)] = (c, r + 1)  # left edge, upward
            if c == cols - 1 or not mask[r, c + 1]:
                edges[(c + 1, r + 1)] = (c + 1, r)  # right edge, downward
    if not edges:
        return ()
    start = min(edges)
    loop = [start]
    point = edges[start]
    while point != start:
        loop.append(point)
        point = edges[point]
    corners = []
    count = len(loop)
    for i in range(count):
        a, b, c = loop[i - 1], loop[i], loop[(i + 1) % count]
        if (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]) != 0:
            corners.append((round(x0 + b[0] * config.SUB, 4), round(y0 + b[1] * config.SUB, 4)))
    return tuple(corners)
