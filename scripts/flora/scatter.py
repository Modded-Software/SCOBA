"""Pick plants from rule candidates: weighted order, spacing, caps, no overlap.

Families go in config.FAMILIES order. A candidate is taken when it is
outside every tree blocker (grown by TREE_MARGIN), clear of hazards, and far
enough from every plant already taken: SPACING of its own family, or
MIX_SPACING of the mean spacing for another family.
"""

from __future__ import annotations

import math
import random
from collections import defaultdict
from typing import NamedTuple

import numpy as np

from . import config
from .rules import RULES, Context
from .scene import FINE

BUCKET = 4.0


class Plant(NamedTuple):
    kind: str
    x: float
    y: float
    rotation: float
    scale: float
    variation: int


class Field:
    """Spatial hash of taken plants."""

    def __init__(self) -> None:
        self.buckets: dict[tuple[int, int], list[Plant]] = defaultdict(list)

    def clear(self, kind: str, x: float, y: float) -> bool:
        own = config.FAMILIES[kind].spacing
        reach = int(math.ceil(max(f.spacing for f in config.FAMILIES.values()) / BUCKET))
        bx, by = int(x // BUCKET), int(y // BUCKET)
        for gy in range(by - reach, by + reach + 1):
            for gx in range(bx - reach, bx + reach + 1):
                for p in self.buckets.get((gx, gy), ()):
                    if p.kind == kind:
                        limit = own
                    else:
                        limit = config.MIX_SPACING * (own + config.FAMILIES[p.kind].spacing) / 2
                    if math.hypot(p.x - x, p.y - y) < limit:
                        return False
        return True

    def add(self, plant: Plant) -> None:
        self.buckets[(int(plant.x // BUCKET), int(plant.y // BUCKET))].append(plant)


def ordered(candidates: list, rng: random.Random) -> list:
    """Weighted random order (Efraimidis-Spirakis keys)."""
    keyed = [(rng.random() ** (1.0 / max(c.weight, 1e-6)), i) for i, c in enumerate(candidates)]
    keyed.sort(reverse=True)
    return [candidates[i] for _, i in keyed]


def scatter(ctx: Context, hazards: np.ndarray, seed: int) -> list[Plant]:
    n = ctx.terrain.height.shape[0]
    field = Field()
    taken: list[Plant] = []
    for kind, family in config.FAMILIES.items():
        rng = random.Random(f"{seed}:{kind}")
        count = 0
        for cand in ordered(RULES[kind](ctx, rng), rng):
            if count >= family.cap:
                break
            # Positions are written with 3 decimals; spacing is checked on what is written.
            x, y = round(cand.x, 3), round(cand.y, 3)
            if not (0 <= x < n and 0 <= y < n):
                continue
            if ctx.scene.tree_block[int(y * FINE), int(x * FINE)]:
                continue
            if hazards[int(y), int(x)] or ctx.scene.keepout[int(y), int(x)]:
                continue
            if not field.clear(kind, x, y):
                continue
            rotation = cand.rotation if cand.rotation is not None else rng.uniform(0.0, 2 * math.pi)
            plant = Plant(
                kind,
                x,
                y,
                round(rotation % (2 * math.pi), 4),
                round(rng.uniform(*family.scale), 4),
                rng.randrange(family.variations),
            )
            field.add(plant)
            taken.append(plant)
            count += 1
    return taken
