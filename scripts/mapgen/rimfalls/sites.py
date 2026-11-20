"""Where the rim waterfalls go: empty spots at the foot of the rim wall.

The map is a bowl: the ground rises to the map edge. A site is a vertex on
the lower part of that wall. Its direction is the wall's downhill normal on
the ground plane, from the ground averaged over NORMAL_RADIUS: the falls
face it, the raised terrain is behind them.

The rim is cut in SECTORS round the map centre and each sector gives at
most one site, its emptiest. Where the picks of two neighbouring sectors
are closer than MIN_SPACING, the emptier one stays. So a change in one
sector reaches the sectors next to it at most (through the spacing rule,
one sector further), never the far side of the rim.
"""

from __future__ import annotations

import math
import re
from typing import NamedTuple

import numpy as np

from flora.terrain import bilinear
from mapgen.waterfeatures.sites import rect_distance

from . import config

Point = tuple[float, float]
Rect = tuple[float, float, float, float]


class Site(NamedTuple):
    x: float
    y: float
    dir: Point  # downhill unit vector of the wall: the way the falls face
    slope: float
    clear: float  # distance to the nearest placed object, less its reach
    sector: int


def averaged(vz: np.ndarray, radius: int = config.NORMAL_RADIUS) -> np.ndarray:
    """The ground averaged over a square of (2 radius + 1) vertices, edges repeated."""
    padded = np.pad(vz, radius, mode="edge")
    h, w = vz.shape
    total = np.zeros_like(vz, dtype=float)
    for dy in range(2 * radius + 1):
        for dx in range(2 * radius + 1):
            total += padded[dy : dy + h, dx : dx + w]
    return total / (2 * radius + 1) ** 2


def normals(vz: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(slope, downhill x, downhill y) per vertex, from the averaged ground."""
    gy, gx = np.gradient(averaged(vz))
    slope = np.hypot(gx, gy)
    safe = np.where(slope > 1e-9, slope, 1.0)
    return slope, -gx / safe, -gy / safe


def placed_points(objects: str) -> np.ndarray:
    """(x, y, reach) of everything placed: doodads, units, points, cameras.

    A tree reaches TREE_REACH per unit of its scale (its canopy), a geyser
    GEYSER_REACH; anything else counts as a point.
    """
    rows = []
    for head in re.findall(r"<Object\w+\b[^>]*>", objects):
        at = re.search(r'\bPosition="([-\d.eE]+),([-\d.eE]+)', head)
        if at is None:
            continue
        kind = re.search(r'\bType="([^"]*)"', head)
        scale = re.search(r'\bScale="([-\d.eE]+)', head)
        unit = re.search(r'\bUnitType="([^"]*)"', head)
        reach = 0.0
        if kind is not None and kind.group(1).startswith(config.TREE_PREFIX):
            reach = config.TREE_REACH * float(scale.group(1) if scale else 1.0)
        elif unit is not None and unit.group(1) in config.GEYSER_UNITS:
            reach = config.GEYSER_REACH
        rows.append((float(at.group(1)), float(at.group(2)), reach))
    return np.array(rows, dtype=float).reshape(-1, 3)


def sector_of(x: float, y: float, centre: float) -> tuple[int, float]:
    """(sector, position in it 0..1) of a point, by its angle round the map centre."""
    turn = (math.atan2(y - centre, x - centre) % math.tau) / math.tau * config.SECTORS
    index = min(int(turn), config.SECTORS - 1)
    return index, turn - index


def candidates(vz: np.ndarray, placed: np.ndarray, rects: list[Rect]) -> list[Site]:
    """Every vertex that could take a group."""
    n = vz.shape[0] - 1
    centre = n / 2
    slope, dx, dy = normals(vz)
    out: list[Site] = []
    lo, hi = math.ceil(config.EDGE_MIN), math.floor(n - config.EDGE_MIN)
    for y in range(lo, hi + 1):
        for x in range(lo, hi + 1):
            edge = min(x, y, n - x, n - y)
            if edge > config.EDGE_MAX or slope[y, x] < config.WALL_SLOPE:
                continue
            d = (float(dx[y, x]), float(dy[y, x]))
            span = math.hypot(centre - x, centre - y)
            if span == 0 or (d[0] * (centre - x) + d[1] * (centre - y)) / span < config.INWARD:
                continue
            ux, uy = x - d[0] * config.WALL_REACH, y - d[1] * config.WALL_REACH
            fx, fy = x + d[0] * config.FOOT_REACH, y + d[1] * config.FOOT_REACH
            # Near the edge the uphill probe stops at the map edge.
            ux, uy = min(max(ux, 0.0), float(n)), min(max(uy, 0.0), float(n))
            if not (1 <= fx <= n - 1 and 1 <= fy <= n - 1):
                continue
            if bilinear(vz, ux, uy) - vz[y, x] < config.WALL_RISE:
                continue
            if bilinear(slope, fx, fy) > config.FOOT_SLOPE:
                continue
            sector, share = sector_of(x, y, centre)
            if abs(share - 0.5) > config.SECTOR_USE / 2:
                continue
            if any(rect_distance((x, y), r) < config.WATER_MARGIN for r in rects):
                continue
            clear = float((np.hypot(placed[:, 0] - x, placed[:, 1] - y) - placed[:, 2]).min()) if len(placed) else math.inf
            if clear < config.CLEAR:
                continue
            out.append(Site(float(x), float(y), d, float(slope[y, x]), clear, sector))
    return out


def find(vz: np.ndarray, placed: np.ndarray, rects: list[Rect]) -> list[Site]:
    """The emptiest candidate of every sector, in sector order."""
    best: dict[int, Site] = {}
    for site in candidates(vz, placed, rects):
        held = best.get(site.sector)
        # Emptiest first; the same clearance: the steeper wall, then the lower y and x.
        if held is None or (site.clear, site.slope, -site.y, -site.x) > (held.clear, held.slope, -held.y, -held.x):
            best[site.sector] = site
    # Two picks closer than MIN_SPACING (neighbouring sectors): the emptier one stays.
    kept: list[Site] = []
    for site in sorted(best.values(), key=lambda s: (-s.clear, -s.slope, s.y, s.x)):
        if all(math.hypot(site.x - k.x, site.y - k.y) >= config.MIN_SPACING for k in kept):
            kept.append(site)
    return sorted(kept, key=lambda s: s.sector)[: config.MAX_SITES]


def problems(sites: list[Site]) -> list[str]:
    out = []
    if not config.MIN_SITES <= len(sites) <= config.MAX_SITES:
        out.append(f"rim falls: {len(sites)} sites, wanted {config.MIN_SITES} to {config.MAX_SITES}")
    for i, a in enumerate(sites):
        for b in sites[i + 1 :]:
            gap = math.hypot(a.x - b.x, a.y - b.y)
            if gap < config.MIN_SPACING:
                out.append(f"rim falls: sites ({a.x:.0f},{a.y:.0f}) and ({b.x:.0f},{b.y:.0f}) are {gap:.1f} apart, under {config.MIN_SPACING}")
    return out
