"""Pool gardens: plants in a ring round every carved pool.

Operator 2026-11-20: "the pools need vegetation around". The pools are
the water features of mapgen/waterfeatures (terrain.pool). The general
rules place few plants there: their caps are spent on the whole map. So
the ring is planted first, with its own spacing (config.POOL_GARDEN), and
every later family keeps its distance from these plants.

The plants are of the flora families, so the flora checks, the crush data
and the non-blocking footprints cover them.
"""

from __future__ import annotations

import math
import random

import numpy as np

from . import config
from .grid import disk_cells, distance_to
from .rules import Context
from .scene import FINE, keep_radius


def unit_keepout(ctx: Context) -> np.ndarray:
    """Cells kept clear round every placed unit (scene.keep_radius).

    The scene's keep-out also holds the spawn and base regions. The pools by
    the psi decimator lie inside the Terran base region, and the operator
    asked for plants round them: the garden keeps clear of units only.
    """
    shape = ctx.terrain.height.shape
    out = np.zeros(shape, dtype=bool)
    for unit in ctx.scene.units:
        rows, cols = disk_cells(unit.x, unit.y, keep_radius(unit), shape)
        out[rows, cols] = True
    return out


def ring(ctx: Context) -> np.ndarray:
    """Cells [y, x] round the pools where the garden may grow."""
    pool = ctx.terrain.pool
    if pool is None or not pool.any():
        return np.zeros(ctx.terrain.height.shape, dtype=bool)
    near = distance_to(pool) <= config.POOL_GARDEN_BAND
    return near & ~pool & ~unit_keepout(ctx) & (ctx.terrain.slope < config.POOL_GARDEN_SLOPE)


def garden(ctx: Context, hazards: np.ndarray, seed: int) -> list:
    """Plants of the pool rings, in config.POOL_GARDEN order."""
    from .scatter import Plant

    ys, xs = np.nonzero(ring(ctx))
    cells = sorted(zip(xs.tolist(), ys.tolist()))
    taken: list = []
    for kind, spacing in config.POOL_GARDEN.items():
        family = config.FAMILIES[kind]
        rng = random.Random(f"{seed}:pool:{kind}")
        spots = [(round(x + rng.random(), 3), round(y + rng.random(), 3)) for x, y in cells]
        rng.shuffle(spots)
        for x, y in spots:
            if ctx.scene.tree_block[int(y * FINE), int(x * FINE)] or hazards[int(y), int(x)]:
                continue
            if not _clear(taken, kind, spacing, x, y):
                continue
            rotation = round(rng.uniform(0.0, 2 * math.pi), 4)
            taken.append(Plant(kind, x, y, rotation, round(rng.uniform(*family.scale), 4), rng.randrange(family.variations)))
    return taken


def _clear(taken: list, kind: str, spacing: float, x: float, y: float) -> bool:
    for p in taken:
        limit = spacing if p.kind == kind else config.MIX_SPACING * (spacing + config.POOL_GARDEN[p.kind]) / 2
        if math.hypot(p.x - x, p.y - y) < limit:
            return False
    return True
