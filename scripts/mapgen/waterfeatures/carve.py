"""Shape the ground of a water feature. Pure functions on the vertex grid.

The grid is [y, x]; vertex (x, y) is the world point (x, y). The water of a
rectangle is drawn wherever its ground is below the water height, so the
ground decides the pool:

- basin: a bowl under every point where water lands;
- mouth: the ground under a pipe mouth stays clear of it;
- pool: the wet ground connected to the landing points, strictly inside
  the rectangle and within POOL_RADIUS of a landing point;
- rim: every other vertex of the rectangle, and low ground close outside
  it, is raised above the water. The water sheet then ends on a shore, not
  on the straight edge of its rectangle;
- feather: every change fades into the old ground.
"""

from __future__ import annotations

from collections import deque

import numpy as np

from . import config
from .models import Point
from .sites import Mouth, Rect


def _axes(shape: tuple[int, int]) -> tuple[np.ndarray, np.ndarray]:
    ys, xs = np.mgrid[0 : shape[0], 0 : shape[1]]
    return xs.astype(float), ys.astype(float)


def inside(shape: tuple[int, int], rect: Rect, grow: float = 0.0) -> np.ndarray:
    """Vertices of a rectangle, bounds included, grown by `grow` (negative shrinks)."""
    xs, ys = _axes(shape)
    x0, y0, x1, y1 = rect
    return (xs >= x0 - grow) & (xs <= x1 + grow) & (ys >= y0 - grow) & (ys <= y1 + grow)


def basin(vz: np.ndarray, rect: Rect, points: list[Point], level: float, depth: float = config.BASIN_DEPTH, radius: float = config.BASIN_RADIUS) -> np.ndarray:
    """Lower the ground to a bowl under each point. Only strictly inside the rectangle."""
    xs, ys = _axes(vz.shape)
    out = vz.copy()
    allowed = inside(vz.shape, rect, -1.0)
    for px, py in points:
        r = np.hypot(xs - px, ys - py)
        bowl = level - depth * (1.0 - (r / radius) ** 2)
        out = np.where(allowed & (r < radius), np.minimum(out, bowl), out)
    return out


def mouth_mask(shape: tuple[int, int], mouth: Mouth) -> np.ndarray:
    """Vertices under the mouth end of a pipe."""
    xs, ys = _axes(shape)
    ax, ay = mouth.x - mouth.dx * config.MOUTH_BACK, mouth.y - mouth.dy * config.MOUTH_BACK
    bx, by = mouth.x + mouth.dx * config.MOUTH_FRONT, mouth.y + mouth.dy * config.MOUTH_FRONT
    span = (bx - ax) ** 2 + (by - ay) ** 2
    t = np.clip(((xs - ax) * (bx - ax) + (ys - ay) * (by - ay)) / span, 0.0, 1.0)
    return np.hypot(xs - (ax + t * (bx - ax)), ys - (ay + t * (by - ay))) <= mouth.radius + config.PIPE_CLEAR


def free_mouths(vz: np.ndarray, mouths: tuple[Mouth, ...]) -> np.ndarray:
    """Keep the ground PIPE_CLEAR below every pipe lip, around the mouth."""
    out = vz.copy()
    for mouth in mouths:
        mask = mouth_mask(vz.shape, mouth)
        out = np.where(mask, np.minimum(out, mouth.lip_z - config.PIPE_CLEAR), out)
    return out


def pool(vz: np.ndarray, rect: Rect, seeds: list[Point], level: float) -> np.ndarray:
    """Wet vertices connected to the seeds: below the level, strictly inside the rectangle, near a seed."""
    xs, ys = _axes(vz.shape)
    near = np.zeros(vz.shape, dtype=bool)
    for px, py in seeds:
        near |= np.hypot(xs - px, ys - py) <= config.POOL_RADIUS
    allowed = inside(vz.shape, rect, -1.0) & near & (vz < level)
    out = np.zeros(vz.shape, dtype=bool)
    queue: deque[tuple[int, int]] = deque()
    for px, py in seeds:
        y, x = int(round(py)), int(round(px))
        if 0 <= y < vz.shape[0] and 0 <= x < vz.shape[1] and allowed[y, x] and not out[y, x]:
            out[y, x] = True
            queue.append((y, x))
    while queue:
        y, x = queue.popleft()
        for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
            if 0 <= ny < vz.shape[0] and 0 <= nx < vz.shape[1] and allowed[ny, nx] and not out[ny, nx]:
                out[ny, nx] = True
                queue.append((ny, nx))
    return out


def rim(vz: np.ndarray, rect: Rect, wet: np.ndarray, level: float) -> np.ndarray:
    """Raise every dry-to-be vertex of the rectangle and its shore margin above the water."""
    zone = inside(vz.shape, rect, config.SHORE_MARGIN) & ~wet
    return np.where(zone, np.maximum(vz, level + config.RIM), vz)


def feather(old: np.ndarray, new: np.ndarray, keep: np.ndarray) -> np.ndarray:
    """Fade every change into the unchanged ground around it. `keep` vertices are not touched."""
    delta = new - old
    fixed = (delta != 0.0) | keep
    for _ in range(config.BLEND_PASSES):
        padded = np.pad(delta, 1, mode="edge")
        n = delta.shape[0]
        around = np.stack([padded[1 + dy : 1 + dy + n, 1 + dx : 1 + dx + n] for dy in (-1, 0, 1) for dx in (-1, 0, 1) if (dy, dx) != (0, 0)])
        up = around.max(axis=0) * config.BLEND_KEEP
        down = around.min(axis=0) * config.BLEND_KEEP_CUT
        spread = np.where(up > -down, np.maximum(up, 0.0), np.minimum(down, 0.0))
        delta = np.where(fixed, delta, spread)
    return old + delta
