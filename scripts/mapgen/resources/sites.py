"""Resource lines of the built map: six mains and twelve expansion sites.

R-BASE-26: every field and geyser is a placed map object (A11). R-BASE-3:
the Zerg jungle anchors come from the Lurkers; no site coordinate is
written by hand. R-BASE-31: lines are planned on bare terrain, before trees
and units are fitted. R-BASE-32: the pile shape is organic, seeded per line.
"""
from __future__ import annotations

import math
import random
import re
from pathlib import Path
from typing import NamedTuple

import numpy as np

from flora import terrain as terrain_mod
from flora.grid import disk_cells
from flora.scene import regions_of
from mapgen.melee_map import region_centres, start_points

from . import config

HALL_GAP = 3   # pile cells keep this far from the hall square (stock NearResources ring)


class Line(NamedTuple):
    name: str
    hall: tuple[int, int]
    fields: tuple[tuple[float, float], ...]
    geysers: tuple[tuple[float, float], ...]


class Ground(NamedTuple):
    good: np.ndarray        # pathable and dry
    site: np.ndarray        # good and off the spawn discs
    wet_site: np.ndarray    # pathable and off the spawn discs (config.WET_SITES)


def ground(map_dir: Path) -> Ground:
    terrain = terrain_mod.load(map_dir)
    spawn = np.zeros_like(terrain.pathable)
    regions = regions_of((map_dir / "Regions").read_text(encoding="utf-8"))
    for name in config.SPAWNS:
        r = regions[name]
        rows, cols = disk_cells(r.x, r.y, r.radius + config.SPAWN_CLEAR, spawn.shape)
        spawn[rows, cols] = True
    good = terrain.pathable & ~terrain.wet
    return Ground(good, good & ~spawn, terrain.pathable & ~spawn)


def away_deg(at: tuple[float, float]) -> float:
    return math.degrees(math.atan2(at[1] - config.CENTRE[1], at[0] - config.CENTRE[0]))


def polar(at: tuple[float, float], r: float, deg: float) -> tuple[float, float]:
    return at[0] + r * math.cos(math.radians(deg)), at[1] + r * math.sin(math.radians(deg))


def cells(x: float, y: float, size: tuple[int, int]) -> list[tuple[int, int]]:
    """Cells under a footprint centred at (x, y)."""
    x0, y0 = int(round(x - size[0] / 2)), int(round(y - size[1] / 2))
    return [(cx, cy) for cx in range(x0, x0 + size[0]) for cy in range(y0, y0 + size[1])]


def hall_cells(hall: tuple[int, int], grow: int = 0) -> list[tuple[int, int]]:
    h = config.HALL_HALF + grow
    return [(x, y) for x in range(hall[0] - h, hall[0] + h) for y in range(hall[1] - h, hall[1] + h)]


def shape(name: str, hall: tuple[int, int]) -> list[tuple[str, float, float]]:
    """Raw pile spots (kind, angle, radius): 8 fields on a jittered arc, 2 geysers past its ends."""
    rng = random.Random(f"{config.SEED}:{name}")
    mid = away_deg(hall) + rng.uniform(-config.ARC_TURN, config.ARC_TURN)
    span = rng.uniform(*config.ARC_SPAN)
    out = []
    for i in range(config.FIELDS):
        a = mid - span / 2 + span * i / (config.FIELDS - 1) + rng.uniform(-config.FIELD_JITTER, config.FIELD_JITTER)
        r = rng.uniform(*config.FIELD_R) + (rng.uniform(0.0, config.FIELD_BACK) if i % 2 else 0.0)
        out.append(("field", a, r))
    out.append(("geyser", mid - span / 2 - rng.uniform(*config.GEYSER_GAP), rng.uniform(*config.GEYSER_R)))
    out.append(("geyser", mid + span / 2 + rng.uniform(*config.GEYSER_GAP), rng.uniform(*config.GEYSER_R)))
    return out


def _snap(kind: str, x: float, y: float) -> tuple[float, float]:
    if kind == "field":  # 2x1: whole x, half y
        return float(round(x)), math.floor(y) + 0.5
    return math.floor(x) + 0.5, math.floor(y) + 0.5  # 3x3 geyser


def _ok(mask: np.ndarray, cs: list[tuple[int, int]], taken: set) -> bool:
    n = mask.shape[0]
    return all(0 <= x < n and 0 <= y < n and (x, y) not in taken and mask[y, x] for x, y in cs)


def _pile(mask: np.ndarray, hall: tuple[int, int], kind: str, a: float, r: float, taken: set) -> tuple[float, float] | None:
    size = config.FIELD_SIZE if kind == "field" else config.GEYSER_SIZE
    near = set(hall_cells(hall, HALL_GAP))
    for push in range(13):  # out along the ray until the hall gap holds
        sx, sy = _snap(kind, *polar(hall, r + 0.5 * push, a))
        for dx, dy in config.SNAP_TRIES:
            cs = cells(sx + dx, sy + dy, size)
            if not near.intersection(cs) and _ok(mask, cs, taken):
                taken.update(cs)
                return sx + dx, sy + dy
    return None


def line_at(mask: np.ndarray, name: str, hall: tuple[int, int], taken: set, check_hall: bool = True) -> Line | None:
    """The line at a hall spot, or None. taken is updated only on success."""
    mine = set(taken)
    hc = hall_cells(hall)
    if check_hall and not _ok(mask, hc, mine):
        return None
    mine.update(hc)
    fields, geysers = [], []
    for kind, a, r in shape(name, hall):
        p = _pile(mask, hall, kind, a, r, mine)
        if p is None:
            return None
        (fields if kind == "field" else geysers).append(p)
    taken.update(mine)
    return Line(name, hall, tuple(fields), tuple(geysers))


def search(mask: np.ndarray, name: str, anchor: tuple[float, float], taken: set) -> Line | None:
    """First good spot: the anchor, then rings by ring and angle (fixed order, R-BASE-8)."""
    spots = [anchor]
    for r in range(1, config.RINGS + 1):
        for a in range(config.ANGLES):
            spots.append(polar(anchor, config.RING * r, 360.0 * a / config.ANGLES))
    for x, y in spots:
        line = line_at(mask, name, (int(round(x)), int(round(y))), taken)
        if line is not None:
            return line
    return None


def units_of(objects: str, kind: str, player: str | None = None) -> list[tuple[float, float]]:
    out = []
    for m in re.finditer(r"<ObjectUnit\b[^>]*>", objects):
        block = m.group(0)
        if f'UnitType="{kind}"' not in block or (player is not None and f'Player="{player}"' not in block):
            continue
        x, y = re.search(r'Position="([^"]+)"', block).group(1).split(",")[:2]
        out.append((float(x), float(y)))
    return out


def lurker_anchors(objects: str) -> list[tuple[float, float]]:
    """Two-means of the Lurkers, seeded by the two farthest apart (R-BASE-3)."""
    pts = units_of(objects, config.LURKER, config.LURKER_PLAYER)
    if len(pts) < 2:
        raise ValueError(f"resources: {len(pts)} {config.LURKER} of player {config.LURKER_PLAYER}, want at least 2")
    best, seeds = -1.0, (pts[0], pts[1])
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            if math.dist(pts[i], pts[j]) > best:
                best, seeds = math.dist(pts[i], pts[j]), (pts[i], pts[j])
    groups: list[list[tuple[float, float]]] = [[], []]
    for p in pts:
        groups[1 if math.dist(p, seeds[1]) < math.dist(p, seeds[0]) else 0].append(p)
    return [(sum(p[0] for p in g) / len(g), sum(p[1] for p in g) / len(g)) for g in groups]


def anchors(objects: str, regions_xml: str) -> list[tuple[str, tuple[float, float]]]:
    """(site name, anchor): jungles as double sites, then each camp front and back."""
    centres = region_centres(regions_xml)
    jungles = [(name, centres[rid]) for name, rid in config.TERRAN_JUNGLES]
    jungles += [(f"ZergJungle{i + 1}", a) for i, a in enumerate(lurker_anchors(objects))]
    out = []
    for name, a in jungles:
        out.append((name + "A", polar(a, config.DOUBLE_OFFSET, away_deg(a) + 90.0)))
        out.append((name + "B", polar(a, config.DOUBLE_OFFSET, away_deg(a) - 90.0)))
    for name, kind in config.GUARDS:
        camps = units_of(objects, kind)
        if len(camps) != 1:
            raise ValueError(f"resources: {len(camps)} {kind}, want 1")
        out.append((name + "Front", polar(camps[0], config.GUARD_OFFSET, away_deg(camps[0]) + 180.0)))
        out.append((name + "Back", polar(camps[0], config.GUARD_OFFSET, away_deg(camps[0]))))
    return out


class Plan(NamedTuple):
    mains: dict[int, Line]          # owner -> line
    sites: list[Line]
    problems: list[str]

    def lines(self) -> list[Line]:
        return [self.mains[o] for o in sorted(self.mains)] + self.sites


def plan(map_dir: Path) -> Plan:
    """Lines on bare terrain. Reads the scaled Objects before any unit moves."""
    map_dir = Path(map_dir)
    g = ground(map_dir)
    objects = (map_dir / "Objects").read_text(encoding="utf-8")
    regions = (map_dir / "Regions").read_text(encoding="utf-8")
    taken: set[tuple[int, int]] = set()
    problems, mains, sites = [], {}, []
    for owner, at in sorted(start_points(regions).items()):
        line = line_at(g.good, f"main{owner}", at, taken, check_hall=False)
        if line is None:
            problems.append(f"main of {owner} at {at}: no room for its piles")
        else:
            mains[owner] = line
    for name, anchor in anchors(objects, regions):
        line = search(g.wet_site if name in config.WET_SITES else g.site, name, anchor, taken)
        if line is None:
            problems.append(f"site {name} near ({anchor[0]:.1f},{anchor[1]:.1f}): no spot")
        else:
            sites.append(line)
    if len(sites) != config.SITE_COUNT:
        problems.append(f"{len(sites)} sites, want {config.SITE_COUNT}")
    return Plan(mains, sites, problems)


def keepout(lines: list[Line], n: int) -> np.ndarray:
    """Hall and pile cells of every line, grown by KEEP_GROW."""
    mask = np.zeros((n, n), dtype=bool)
    k = config.KEEP_GROW
    for line in lines:
        for x, y in hall_cells(line.hall):
            mask[max(0, y - k):y + k + 1, max(0, x - k):x + k + 1] = True
        for size, piles in ((config.FIELD_SIZE, line.fields), (config.GEYSER_SIZE, line.geysers)):
            for px, py in piles:
                for x, y in cells(px, py, size):
                    mask[max(0, y - k):y + k + 1, max(0, x - k):x + k + 1] = True
    return mask
