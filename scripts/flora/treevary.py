"""Tree variety: no two neighbouring trees look alike.

Neighbours: trunk distance < NEIGHBOUR_FACTOR * (canopy_a + canopy_b), with
canopy = CANOPY_PER_SCALE * scale. A neighbour pair is too similar when it has
the same variation AND scale within SCALE_DELTA (relative) AND rotation within
ROTATION_DELTA. One differing attribute is enough.

Repair, per conflicted tree, seeded and deterministic:
1. a new rotation at least ROTATION_DELTA from every same-variation neighbour;
2. else a variation no neighbour uses (12 variations, few neighbours);
3. else a scale outside SCALE_DELTA of every same-variation neighbour.
Neighbours come from a hash grid: linear in the tree count.
"""

from __future__ import annotations

import math
import random
import re
from collections import defaultdict
from typing import NamedTuple

TREE_TYPE = "ZerusTree"
VARIATIONS = 12  # map ModelData VariationCount
CANOPY_PER_SCALE = 0.5  # estimate: canopy radius per unit of model scale
NEIGHBOUR_FACTOR = 1.5
SCALE_DELTA = 0.35  # relative
ROTATION_DELTA = math.radians(45)
ROTATION_TRIES = 16
SEED = 20261115


class T(NamedTuple):
    x: float
    y: float
    scale: float
    rotation: float
    variation: int

    @property
    def canopy(self) -> float:
        return CANOPY_PER_SCALE * self.scale


def angle_gap(a: float, b: float) -> float:
    d = abs(a - b) % (2 * math.pi)
    return min(d, 2 * math.pi - d)


def too_similar(a: T, b: T) -> bool:
    return (
        a.variation % VARIATIONS == b.variation % VARIATIONS
        and abs(a.scale - b.scale) / max(a.scale, b.scale) < SCALE_DELTA
        and angle_gap(a.rotation, b.rotation) < ROTATION_DELTA
    )


def neighbours(trees: list[T]) -> list[list[int]]:
    cell = max((2 * NEIGHBOUR_FACTOR * t.canopy for t in trees), default=1.0)
    grid: dict[tuple[int, int], list[int]] = defaultdict(list)
    for i, t in enumerate(trees):
        grid[(int(t.x // cell), int(t.y // cell))].append(i)
    out: list[list[int]] = [[] for _ in trees]
    for i, a in enumerate(trees):
        gx, gy = int(a.x // cell), int(a.y // cell)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j in grid.get((gx + dx, gy + dy), ()):
                    b = trees[j]
                    if j != i and math.hypot(a.x - b.x, a.y - b.y) < NEIGHBOUR_FACTOR * (a.canopy + b.canopy):
                        out[i].append(j)
    return out


def conflicts(trees: list[T], near: list[list[int]] | None = None) -> list[tuple[int, int]]:
    near = near if near is not None else neighbours(trees)
    return [(i, j) for i, js in enumerate(near) for j in js if i < j and too_similar(trees[i], trees[j])]


def _ok(t: T, others: list[T]) -> bool:
    return not any(too_similar(t, o) for o in others)


def repair(trees: list[T], seed: int = SEED) -> tuple[list[T], int]:
    """Returns the repaired trees and the number changed. Positions never move."""
    trees = list(trees)
    near = neighbours(trees)
    rng = random.Random(seed)
    changed = 0
    for i in range(len(trees)):
        others = [trees[j] for j in near[i]]
        t = trees[i]
        if _ok(t, others):
            continue
        fixed = None
        for _ in range(ROTATION_TRIES):
            c = t._replace(rotation=round(rng.uniform(0.0, 2 * math.pi), 4))
            if _ok(c, others):
                fixed = c
                break
        if fixed is None:
            used = {o.variation % VARIATIONS for o in others}
            free = [v for v in range(VARIATIONS) if v not in used]
            if free:
                fixed = t._replace(variation=rng.choice(free))
        if fixed is None:
            for factor in (1.0 + SCALE_DELTA + 0.05, 1.0 / (1.0 + SCALE_DELTA + 0.05)):
                c = t._replace(scale=round(t.scale * factor, 4))
                if _ok(c, others):
                    fixed = c
                    break
        if fixed is None:
            raise ValueError(f"tree at ({t.x:.1f},{t.y:.1f}) has no distinct option")
        trees[i] = fixed
        changed += 1
    return trees, changed


_BLOCK = re.compile(r'<ObjectDoodad\b(?=[^>]*\bType="' + TREE_TYPE + r'")[^>]*>', re.S)


def _attr(tag: str, name: str) -> str | None:
    m = re.search(r'\b' + name + r'="([^"]+)"', tag)
    return m.group(1) if m else None


def parse(text: str) -> list[tuple[re.Match[str], T]]:
    out = []
    for m in _BLOCK.finditer(text):
        tag = m.group(0)
        x, y = (float(v) for v in (_attr(tag, "Position") or "0,0").split(",")[:2])
        scale = float((_attr(tag, "Scale") or "1").split(",")[0])
        out.append((m, T(x, y, scale, float(_attr(tag, "Rotation") or 0.0), int(_attr(tag, "Variation") or 0))))
    return out


def _set(tag: str, name: str, value: str) -> str:
    if re.search(r'\b' + name + r'="', tag):
        return re.sub(r'\b' + name + r'="[^"]*"', f'{name}="{value}"', tag, count=1)
    return tag.replace("<ObjectDoodad", f'<ObjectDoodad {name}="{value}"', 1)


def vary_objects(text: str, seed: int = SEED) -> tuple[str, int, int, int]:
    """Returns (text, conflicts before, changed trees, conflicts after)."""
    parsed = parse(text)
    trees = [t for _m, t in parsed]
    before = len(conflicts(trees))
    fixed, changed = repair(trees, seed)
    after = len(conflicts(fixed))
    pieces, last = [], 0
    for (m, old), new in zip(parsed, fixed):
        tag = m.group(0)
        if new.rotation != old.rotation:
            tag = _set(tag, "Rotation", f"{new.rotation:.4f}")
        if new.variation != old.variation:
            tag = _set(tag, "Variation", str(new.variation))
        if new.scale != old.scale:
            tag = _set(tag, "Scale", ",".join([f"{new.scale:.4f}"] * 3))
        pieces += [text[last : m.start()], tag]
        last = m.end()
    pieces.append(text[last:])
    return "".join(pieces), before, changed, after
