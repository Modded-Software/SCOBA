"""Fit trees and placed units around the resource lines (R-BASE-31).

A tree within its clearance (TREE_CLEAR + TREE_SCALE_CLEAR x scale) of a
line's keep-out moves to the nearest free spot on rings around it; a placed
unit within UNIT_CLEAR moves alone the same way. Fixed order (Objects
order, ring, angle): the same map gives the same result.
"""
from __future__ import annotations

import math
import re
from typing import NamedTuple

import numpy as np

from flora import terrain as terrain_mod
from flora.grid import distance_to

from . import config

TREE = re.compile(r'<ObjectDoodad\b[^>]*\bPosition="([^"]+)"[^>]*\bType="ZerusTree(?!ScobaBorder)[^"]*"[^>]*>')
UNIT = re.compile(r'<ObjectUnit\b[^>]*\bPosition="([^"]+)"[^>]*>')
ID = re.compile(r'\bId="(\d+)"')
SCALE = re.compile(r'\bScale="([^",]+)')
RESOURCE = re.compile(r'UnitType="(?:MineralField|VespeneGeyser)"')


class Moved(NamedTuple):
    kind: str           # "tree" or "unit"
    ident: str
    old: tuple[float, float]
    new: tuple[float, float]


def _xyz(pos: str) -> tuple[float, float, float]:
    v = [float(s) for s in pos.split(",")]
    return v[0], v[1], v[2] if len(v) > 2 else 0.0


def _ident(tag: str) -> str:
    m = ID.search(tag)
    return m.group(1) if m else "?"


def tree_clear(tag: str) -> float:
    m = SCALE.search(tag)
    return config.TREE_CLEAR + config.TREE_SCALE_CLEAR * (float(m.group(1)) if m else 1.0)


def spots(x: float, y: float):
    yield x, y
    for r in range(1, config.FIT_RINGS + 1):
        for a in range(config.FIT_ANGLES):
            t = 2 * math.pi * a / config.FIT_ANGLES
            yield x + r * math.cos(t), y + r * math.sin(t)


def _far(p: tuple[float, float], others: list[tuple[float, float]], gap: float) -> bool:
    return all(math.dist(p, o) >= gap for o in others)


def _free(dist: np.ndarray, good: np.ndarray, x: float, y: float, clear: float) -> bool:
    n = dist.shape[0]
    cx, cy = int(math.floor(x)), int(math.floor(y))
    return 0 <= cx < n and 0 <= cy < n and bool(good[cy, cx]) and dist[cy, cx] > clear


def _outside(dist: np.ndarray, x: float, y: float, clear: float) -> bool:
    """Off the map counts as outside: only the keep-out decides a move."""
    n = dist.shape[0]
    cx, cy = int(math.floor(x)), int(math.floor(y))
    return not (0 <= cx < n and 0 <= cy < n) or dist[cy, cx] > clear


def _move(items, i, dist, good, clear, others, gap):
    _m, (x, y, _z) = items[i]
    if _outside(dist, x, y, clear):
        return None
    for p in spots(x, y):
        if _free(dist, good, *p, clear) and _far(p, others, gap):
            return round(p[0], 2), round(p[1], 2)
    return False


def fit(objects: str, keep: np.ndarray, good: np.ndarray, terrain) -> tuple[str, list[Moved], list[str]]:
    """Objects with the trees and units moved out of the keep-out."""
    dist = distance_to(keep)
    trees = [(m, _xyz(m.group(1))) for m in TREE.finditer(objects)]
    units = [(m, _xyz(m.group(1))) for m in UNIT.finditer(objects) if not RESOURCE.search(m.group(0))]
    tree_at = [(t[0], t[1]) for _m, t in trees]
    unit_at = [(u[0], u[1]) for _m, u in units]
    edits, moved, problems = [], [], []
    for i, (m, (x, y, z)) in enumerate(trees):
        new = _move(trees, i, dist, good, tree_clear(m.group(0)), tree_at[:i] + tree_at[i + 1:], config.TREE_GAP)
        if new is None:
            continue
        if new is False:
            problems.append(f"tree {_ident(m.group(0))} at ({x:.1f},{y:.1f}): no free spot")
            continue
        nz = z + terrain_mod.ground_z(terrain, *new) - terrain_mod.ground_z(terrain, x, y)
        tree_at[i] = new
        edits.append((m.start(1), m.end(1), f"{new[0]:g},{new[1]:g},{nz:.4f}"))
        moved.append(Moved("tree", _ident(m.group(0)), (x, y), new))
    for i, (m, (x, y, z)) in enumerate(units):
        new = _move(units, i, dist, good, config.UNIT_CLEAR, unit_at[:i] + unit_at[i + 1:] + tree_at, config.UNIT_GAP)
        if new is None:
            continue
        if new is False:
            problems.append(f"unit {_ident(m.group(0))} at ({x:.1f},{y:.1f}): no free spot")
            continue
        unit_at[i] = new
        edits.append((m.start(1), m.end(1), f"{new[0]:g},{new[1]:g},{z:g}"))
        moved.append(Moved("unit", _ident(m.group(0)), (x, y), new))
    for start, end, text in sorted(edits, reverse=True):
        objects = objects[:start] + text + objects[end:]
    return objects, moved, problems


def inside(objects: str, keep: np.ndarray) -> list[str]:
    """Trees and units still within their clearance of the keep-out (validator)."""
    dist = distance_to(keep)
    out = []
    for kind, pattern in (("tree", TREE), ("unit", UNIT)):
        for m in pattern.finditer(objects):
            if RESOURCE.search(m.group(0)):
                continue
            clear = tree_clear(m.group(0)) if kind == "tree" else config.UNIT_CLEAR
            x, y, _z = _xyz(m.group(1))
            if not _outside(dist, x, y, clear):
                out.append(f"{kind} {_ident(m.group(0))} at ({x:.1f},{y:.1f}) in a line keep-out")
    return out
