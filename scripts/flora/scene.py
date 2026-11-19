"""Placed objects of a built map: trees with their blockers, units, keep-out areas.

Runs after footprints.build, so each tree's actor names its generated Shape.
The Shape is placed the way the fprot probe found: turned by the quarter
turns the engine applies, at the position rounded to 0.5.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import NamedTuple

import numpy as np

from mapgen.footprints.catalog import attr, catalog_bodies, shape_of
from mapgen.footprints.slices import engine_quarter_turns

from . import config
from .grid import disk_cells

FINE = 2  # tree blocker grid: cells per unit


class Tree(NamedTuple):
    ident: str
    x: float
    y: float
    scale: float
    polygon: tuple[tuple[float, float], ...]  # world space

    @property
    def radius(self) -> float:
        return max(math.hypot(px - self.x, py - self.y) for px, py in self.polygon)


class Unit(NamedTuple):
    ident: str
    kind: str
    player: str
    x: float
    y: float


class Region(NamedTuple):
    name: str
    x: float
    y: float
    radius: float


class Scene(NamedTuple):
    trees: list[Tree]
    units: list[Unit]
    keepout: np.ndarray  # bool cells: no flora, no hazards
    tree_block: np.ndarray  # bool, FINE cells per unit: tree Shapes grown by TREE_MARGIN
    next_id: int
    regions: dict[str, Region]


def regions_of(text: str) -> dict[str, Region]:
    """Circle regions of a Regions file, by name."""
    out = {}
    for match in re.finditer(r"<region\b[^>]*>(.*?)</region>", text, re.S):
        body = match.group(1)
        name = re.search(r'<name value="([^"]*)"/>', body)
        centre = re.search(r'<center value="([^"]+)"/>', body)
        radius = re.search(r'<radius value="([^"]+)"/>', body)
        if name and centre and radius:
            x, y = (float(v) for v in centre.group(1).split(","))
            out[name.group(1)] = Region(name.group(1), x, y, float(radius.group(1)))
    return out


def _position(block: str) -> tuple[float, float]:
    value = attr(block, "Position")
    if value is None:
        raise ValueError(f"placed object has no Position: {block[:120]}")
    x, y = (float(v) for v in value.split(",")[:2])
    return x, y


def place_shape(shape: tuple[tuple[float, float], ...], x: float, y: float, rotation: float) -> tuple[tuple[float, float], ...]:
    turns = engine_quarter_turns(rotation)
    px, py = math.floor(x * 2 + 0.5) / 2, math.floor(y * 2 + 0.5) / 2
    out = []
    for vx, vy in shape:
        for _ in range(turns):
            vx, vy = -vy, vx
        out.append((px + vx, py + vy))
    return tuple(out)


def _inside(poly: tuple[tuple[float, float], ...], xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    hit = np.zeros(xs.shape, dtype=bool)
    for i in range(len(poly)):
        x1, y1 = poly[i - 1]
        x2, y2 = poly[i]
        if y1 == y2:
            continue
        straddle = (y1 > ys) != (y2 > ys)
        cross = x1 + (ys - y1) * (x2 - x1) / (y2 - y1)
        hit ^= straddle & (xs < cross)
    return hit


def trees_of(map_dir: Path, objects: str) -> list[Tree]:
    data = map_dir / "Base.SC2Data" / "GameData"
    footprints = catalog_bodies(data / "FootprintData.xml", "CFootprint")
    actors = catalog_bodies(data / "ActorData.xml", "CActorDoodad")
    trees = []
    for match in re.finditer(r'<ObjectDoodad\b[^>]*\bType="(ZerusTree[^"]*)"[^>]*>', objects):
        block = match.group(0)
        if match.group(1) == "ZerusTreeScobaBorder":
            continue  # border trees (flora/border.py): off the playable area, no footprint
        body = actors.get(match.group(1), "")
        fp = re.search(r'<Footprint value="([^"]+)"/>', body)
        if fp is None or fp.group(1) not in footprints:
            raise ValueError(f"tree {attr(block, 'Id')} has no generated footprint; run footprints.build first")
        x, y = _position(block)
        scale = float((attr(block, "Scale") or "1").split(",")[0])
        polygon = place_shape(shape_of(footprints[fp.group(1)]), x, y, float(attr(block, "Rotation") or 0.0))
        trees.append(Tree(attr(block, "Id") or "", x, y, scale, polygon))
    return trees


def units_of(objects: str) -> list[Unit]:
    units = []
    for match in re.finditer(r"<ObjectUnit\b[^>]*>", objects):
        block = match.group(0)
        x, y = _position(block)
        units.append(Unit(attr(block, "Id") or "", attr(block, "UnitType") or "", attr(block, "Player") or "", x, y))
    return units


def keep_radius(unit: Unit) -> float:
    if unit.player == "1" or unit.kind in config.HERO_UNITS:
        return config.KEEP_HERO
    if unit.kind in config.STRUCTURE_UNITS:
        return config.KEEP_STRUCTURE
    return config.KEEP_UNIT


def tree_grid(trees: list[Tree], n: int) -> np.ndarray:
    grid = np.zeros((n * FINE, n * FINE), dtype=bool)
    m = config.TREE_MARGIN
    for tree in trees:
        xs = [p[0] for p in tree.polygon]
        ys = [p[1] for p in tree.polygon]
        x0, x1 = max(0, int((min(xs) - m) * FINE)), min(n * FINE, int(math.ceil((max(xs) + m) * FINE)))
        y0, y1 = max(0, int((min(ys) - m) * FINE)), min(n * FINE, int(math.ceil((max(ys) + m) * FINE)))
        if x0 >= x1 or y0 >= y1:
            continue
        gy, gx = np.mgrid[y0:y1, x0:x1]
        cx, cy = (gx + 0.5) / FINE, (gy + 0.5) / FINE
        hit = _inside(tree.polygon, cx, cy)
        # Grow by the margin: any sub-cell centre within m of a vertex-sampled edge.
        for i in range(len(tree.polygon)):
            ax, ay = tree.polygon[i - 1]
            bx, by = tree.polygon[i]
            dx, dy = bx - ax, by - ay
            t = np.clip(((cx - ax) * dx + (cy - ay) * dy) / max(dx * dx + dy * dy, 1e-9), 0.0, 1.0)
            hit |= np.hypot(cx - (ax + t * dx), cy - (ay + t * dy)) < m
        grid[y0:y1, x0:x1] |= hit
    return grid


def site_halls(map_dir: Path) -> list[tuple[float, float]]:
    """Hall points of the resource lines (scripts/mapgen/resources report), if any."""
    path = Path(map_dir) / config.SITE_REPORT
    if not path.exists():
        return []
    out = []
    for row in path.read_text(encoding="utf-8").splitlines():
        if row.startswith("line "):
            x, y = row.split()[-1].split(",")
            out.append((float(x), float(y)))
    return out


def load(map_dir: Path, n: int = config.MAP_CELLS) -> Scene:
    map_dir = Path(map_dir)
    objects = (map_dir / "Objects").read_text(encoding="utf-8")
    trees = trees_of(map_dir, objects)
    units = units_of(objects)
    regions = regions_of((map_dir / "Regions").read_text(encoding="utf-8"))
    keepout = np.zeros((n, n), dtype=bool)
    for unit in units:
        rows, cols = disk_cells(unit.x, unit.y, keep_radius(unit), keepout.shape)
        keepout[rows, cols] = True
    for name in config.SPAWN_REGIONS:
        if name not in regions:
            raise ValueError(f"{map_dir / 'Regions'} has no region {name!r}")
        r = regions[name]
        rows, cols = disk_cells(r.x, r.y, r.radius + config.KEEP_SPAWN, keepout.shape)
        keepout[rows, cols] = True
    for x, y in site_halls(map_dir):
        rows, cols = disk_cells(x, y, config.KEEP_HALL, keepout.shape)
        keepout[rows, cols] = True
    ids = [int(v) for v in re.findall(r'\bId="(\d+)"', objects)]
    return Scene(trees, units, keepout, tree_grid(trees, n), max(ids, default=0) + 1, regions)
