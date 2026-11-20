"""The doodads of one rim group: rock waterfalls, normal waterfalls, basin rocks.

    wall | rock waterfall(s) | normal waterfall(s) in front | basin with rocks

Every piece faces the wall's downhill normal (site.dir), with a small turn
of chance. Chance also picks the counts, variations, sizes and offsets. A
group draws from its own sequence, keyed on the seed and the site's
position: a change at one site never changes another group.
"""

from __future__ import annotations

import math
import random
from typing import NamedTuple

import numpy as np

from flora.terrain import bilinear
from mapgen.waterfeatures.compose import Placement, RockPlacement
from mapgen.waterfeatures.models import Models, Point, rotation_facing, to_world

from . import carve, config
from .sites import Site


class Group(NamedTuple):
    site: Site
    basin: Point
    edge: float  # level of the basin edge
    surface: float  # the water surface the fall models stand on
    falls: tuple[Placement, ...]  # rock waterfalls first, then the normal ones
    rocks: tuple[RockPlacement, ...]


def group_rng(site: Site) -> random.Random:
    return random.Random(f"{config.SEED}:{site.x:.0f}:{site.y:.0f}")


def facing(site: Site, rng: random.Random) -> float:
    return (rotation_facing(site.dir) + rng.uniform(-config.TURN_JITTER, config.TURN_JITTER)) % math.tau


def landings(models: Models, p: Placement) -> list[Point]:
    """World points where the streams of a placed fall land."""
    return [to_world(s, p.x, p.y, p.rotation, p.flat) for s in models.falls[p.kind][p.variation].splashes]


def embed_back(ground: np.ndarray, start: Point, d: Point, level: float) -> float:
    """How far uphill of `start` a rock waterfall stands to be embedded in the wall.

    Operator, 2026-11-20: "these need to be embedded in the terrain, they
    are floating in front of it". The first point uphill where the cut
    ground reaches `level`; EMBED_REACH at most, and inside the map.
    """
    n = ground.shape[0] - 1
    back = config.ROCK_FALL_BACK * config.BASIN_RADIUS
    while back < config.EMBED_REACH:
        x, y = start[0] - d[0] * back, start[1] - d[1] * back
        nx, ny = x - d[0] * config.EMBED_STEP, y - d[1] * config.EMBED_STEP
        if bilinear(ground, x, y) >= level or not (1.0 <= nx <= n - 1.0 and 1.0 <= ny <= n - 1.0):
            break
        back += config.EMBED_STEP
    return back


def embedded(ground: np.ndarray, models: Models, p: Placement, surface: float) -> float:
    """Share of a placed rock waterfall's height over the water that the ground at its origin covers."""
    shape = models.falls[p.kind][p.variation]
    return (bilinear(ground, p.x, p.y) - surface) / ((shape.hi[2] - shape.base_z) * p.scale)


def make(index: int, site: Site, ground: np.ndarray, edge: float, models: Models) -> Group:
    """The group of one site, on the cut ground."""
    rng = group_rng(site)
    d = site.dir
    side = (-d[1], d[0])
    bx, by = carve.basin_centre(site)
    surface = edge - config.BASIN_DEPTH * config.SURFACE
    falls: list[Placement] = []

    # Rock waterfalls: the first in the notch behind the basin, a second beside it.
    variations = sorted(models.falls[config.ROCK_FALL])
    rng.shuffle(variations)
    count = rng.randint(*config.ROCK_FALLS)
    first_side = rng.choice((-1.0, 1.0))
    for k in range(count):
        shape = models.falls[config.ROCK_FALL][variations[k]]
        flat = rng.uniform(*config.ROCK_FALL_SCALE) * (1.0 if k == 0 else 0.75)
        tall = flat * rng.uniform(*config.ROCK_FALL_TALL)
        across = 0.0 if k == 0 else first_side * rng.uniform(*config.ROCK_FALL_SIDE)
        share = rng.uniform(*config.EMBED)
        back = embed_back(ground, (bx + side[0] * across, by + side[1] * across), d, surface + share * (shape.hi[2] - shape.base_z) * tall)
        x, y = bx - d[0] * back + side[0] * across, by - d[1] * back + side[1] * across
        falls.append(Placement(config.ROCK_FALL, variations[k], x, y, surface - shape.base_z * tall, facing(site, rng), tall, index, 0, flat / tall))

    # Normal waterfalls, layered in front of the first rock waterfall.
    back = falls[0]
    rise = (models.falls[config.ROCK_FALL][back.variation].hi[2] - models.falls[config.ROCK_FALL][back.variation].base_z) * back.scale
    shape = models.falls[config.FALL][0]
    for _ in range(rng.randint(*config.FALLS)):
        tall = rng.uniform(*config.FALL_REACH) * rise / shape.height
        flat = rng.uniform(*config.FALL_WIDE)
        across = rng.uniform(-config.FALL_SIDE, config.FALL_SIDE)
        along = rng.uniform(*config.FALL_AHEAD)
        x, y = back.x + d[0] * along + side[0] * across, back.y + d[1] * along + side[1] * across
        falls.append(Placement(config.FALL, 0, x, y, surface - shape.base_z * tall, facing(site, rng), tall, index, 0, flat / tall))

    # Rocks on the basin floor, clear of where the rock waterfalls' streams land.
    wet = [q for p in falls if p.kind == config.ROCK_FALL for q in landings(models, p)]
    shapes = models.rocks[config.ROCK_SOURCE]
    kinds = sorted(shapes)
    rng.shuffle(kinds)
    rocks: list[RockPlacement] = []
    want = min(rng.randint(*config.ROCKS), len(kinds))
    for _ in range(config.ROCK_TRIES):
        if len(rocks) >= want:
            break
        r = config.ROCK_SPREAD * config.BASIN_RADIUS * math.sqrt(rng.random())
        a = rng.uniform(0.0, math.tau)
        x, y = bx + r * math.cos(a), by + r * math.sin(a)
        scale = rng.uniform(*config.ROCK_SCALE)
        turn = rng.uniform(0.0, math.tau)
        if any(math.hypot(x - q[0], y - q[1]) < config.ROCK_FALL_CLEAR for q in wet):
            continue
        if any(math.hypot(x - o.x, y - o.y) < config.ROCK_SPACING for o in rocks):
            continue
        rocks.append(RockPlacement(config.ROCK, kinds[len(rocks)], x, y, bilinear(ground, x, y) - config.ROCK_SINK, turn, scale, index))
    return Group(site, (bx, by), edge, surface, tuple(falls), tuple(rocks))
