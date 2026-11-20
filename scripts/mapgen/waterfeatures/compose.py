"""The doodads of one water feature: falls from the pipes into the pool, rocks in it.

    pipe mouth -> fall -> pool <- rocks standing in it

A fall hangs from a pipe lip and ends over the water. Chance only varies
its size, turn and depth. There are no rock waterfalls: the operator
removed them (2026-11-20); the pool walls are painted with the dirt texture
instead (paint.py). Plain Zerus rocks stand in the pool (operator
2026-11-20: "some rocks inside"). The plants round it are flora's
(flora/pools.py).
"""

from __future__ import annotations

import math
import random
from typing import NamedTuple

from flora.terrain import bilinear

from . import config
from .models import Fall, Models, Point, footprint, rotation_facing, to_world, turned
from .sites import Mouth, Site


class Placement(NamedTuple):
    kind: str
    variation: int
    x: float
    y: float
    z: float
    rotation: float
    scale: float  # height (z)
    site: int
    mouth: int  # index into the site's mouths
    wide: float = 1.0  # x and y scale over the z scale: a fall as wide as its pipe wants

    @property
    def flat(self) -> float:
        """Scale on the ground plane (x and y). `scale` is the height (z)."""
        return self.scale * self.wide


def model_of(models: Models, p: Placement) -> Fall:
    return models.falls[p.kind][p.variation]


def outline(models: Models, p: Placement) -> list[Point]:
    return footprint(model_of(models, p), p.x, p.y, p.rotation, p.flat)


def top_z(models: Models, p: Placement) -> float:
    return p.z + model_of(models, p).hi[2] * p.scale


def surface_z(models: Models, p: Placement) -> float:
    """The water surface the placed model was made for."""
    return p.z + model_of(models, p).base_z * p.scale


def landing(models: Models, p: Placement) -> Point:
    """World point where the placed fall meets the pool."""
    return to_world(model_of(models, p).centre, p.x, p.y, p.rotation, p.flat)


def side_reach(models: Models, p: Placement, site: Site) -> float:
    """How far the fall reaches sideways from the middle of its pipe."""
    mouth = site.mouths[p.mouth]
    q = landing(models, p)
    off = (q[0] - mouth.x - site.shift[0]) * -mouth.dy + (q[1] - mouth.y - site.shift[1]) * mouth.dx
    return abs(off) + model_of(models, p).width * p.flat / 2


def common_facing(sites: list[Site]) -> Point | None:
    """Mean outward direction of every pipe mouth of every site, or None when they cancel."""
    x = sum(m.dx for site in sites for m in site.mouths)
    y = sum(m.dy for site in sites for m in site.mouths)
    size = math.hypot(x, y)
    return (x / size, y / size) if size > 1e-6 else None


def fall_facing(mouth: Mouth, common: Point | None) -> Point:
    """Where the falls of a mouth face: its pipe's direction, turned FALL_FACE_COMMON of the way to the common one."""
    if common is None:
        return mouth.out
    own = math.atan2(mouth.dy, mouth.dx)
    turn = (math.atan2(common[1], common[0]) - own + math.pi) % math.tau - math.pi
    angle = own + config.FALL_FACE_COMMON * turn
    return (math.cos(angle), math.sin(angle))


def pipe_falls(index: int, site: Site, level: float, models: Models, rng: random.Random, common: Point | None = None) -> list[Placement]:
    """Falls from every pipe mouth of a site: top just over the lip, base just over the water.

    Operator, 2026-11-20, in rounds:
    - height: on the lip was "way too low", 0.6 up the opening was "from
      the top": the top is FALL_TOP up the opening, near its bottom. Then
      the whole fall went up by FALL_RAISE;
    - width: the bigger pipe gets the bigger fall. Height follows the drop,
      so width is set apart from it: each fall is FALL_WIDTH of its opening;
    - no fall reaches past the side of its pipe;
    - "more variation in their scale": FALL_TOP_JITTER, FALL_WIDTH_JITTER;
    - facing: along the own pipe was "too much facing the east" at one
      group and "too much to the south" at the other; "need a southwest
      facing". The falls face the mean direction of all pipes (fall_facing).
      Where they stand does not change.
    """
    fall = models.falls[config.FALL_TYPE][0]
    out = []
    for m_index, mouth in enumerate(site.mouths):
        opening = 2 * mouth.radius
        width = config.FALL_WIDTH * opening
        # Centres stay inside the opening by half the widest fall.
        room = max(mouth.radius - width * (1 + config.FALL_WIDTH_JITTER) / 2, 0.0)
        count = config.FALL_COUNT
        side = (-mouth.dy, mouth.dx)
        for k in range(count):
            shift = (2 * k / (count - 1) - 1) * room if count > 1 else 0.0
            # Neighbours differ in size, turn and depth, so they do not read as copies.
            top = config.FALL_TOP + rng.uniform(-config.FALL_TOP_JITTER, config.FALL_TOP_JITTER)
            s = min(max(fall_scale(mouth, level, fall, top), config.FALL_SCALE[0]), config.FALL_SCALE[1])
            flat = width * (1 + rng.uniform(-config.FALL_WIDTH_JITTER, config.FALL_WIDTH_JITTER)) / fall.width
            rotation = (rotation_facing(fall_facing(mouth, common)) + rng.uniform(-config.FALL_TURN_JITTER, config.FALL_TURN_JITTER)) % math.tau
            reach = config.FALL_GAP + rng.uniform(-config.FALL_GAP_JITTER, config.FALL_GAP_JITTER) + fall.depth * flat / 2
            cx, cy = turned((fall.centre[0] * flat, fall.centre[1] * flat), rotation)
            # Water can only stand well inside the rectangle: a fall that would
            # land at its edge moves toward the middle of its pipe.
            x0, y0, x1, y1 = site.rect
            edge = config.RECT_INSET
            for pull in (1.0, 0.6, 0.3, 0.0):
                px = mouth.x + site.shift[0] + mouth.dx * reach + side[0] * shift * pull
                py = mouth.y + site.shift[1] + mouth.dy * reach + side[1] * shift * pull
                if x0 + edge <= px <= x1 - edge and y0 + edge <= py <= y1 - edge:
                    break
            else:
                continue
            out.append(Placement(config.FALL_TYPE, 0, px - cx, py - cy, level - fall.base_z * s + config.FALL_RAISE, rotation, s, index, m_index, flat / s))
    return out


class RockPlacement(NamedTuple):
    kind: str
    variation: int
    x: float
    y: float
    z: float  # the model origin: on the pool floor, so its underside is buried
    rotation: float
    scale: float
    site: int


def pool_rocks(index: int, vz, pool, level: float, landings: list[Point], models: Models, rng: random.Random) -> list[RockPlacement]:
    """Rocks standing in the pool (operator 2026-11-20: "some rocks inside").

    A spot is a pool vertex with every neighbour in the pool, in water at
    least ROCK_MIN_DEPTH deep, clear of where the falls land. Chance picks
    among the spots, the variation (none twice in a pool), the turn and the
    size.
    """
    shapes = models.rocks.get(config.ROCK_TYPE, {})
    if not shapes:
        return []
    h, w = pool.shape
    spots = []
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            if pool[y - 1 : y + 2, x - 1 : x + 2].all():
                spots.append((x, y))
    rng.shuffle(spots)
    variations = sorted(shapes)
    rng.shuffle(variations)
    out: list[RockPlacement] = []
    for x, y in spots:
        if len(out) >= min(config.ROCK_COUNT, len(variations)):
            break
        px = x + rng.uniform(-config.ROCK_JITTER, config.ROCK_JITTER)
        py = y + rng.uniform(-config.ROCK_JITTER, config.ROCK_JITTER)
        floor = bilinear(vz, px, py)
        if level - floor < config.ROCK_MIN_DEPTH:
            continue
        if any(math.hypot(px - q[0], py - q[1]) < config.ROCK_FALL_CLEAR for q in landings):
            continue
        if any(math.hypot(px - r.x, py - r.y) < config.ROCK_SPACING for r in out):
            continue
        fit = rock_fit(shapes[variations[len(out)]], floor, level, rng.uniform(*config.ROCK_ABOVE))
        if fit is None:
            continue
        out.append(RockPlacement(config.ROCK_TYPE, variations[len(out)], px, py, fit[0], rng.uniform(0.0, math.tau), fit[1], index))
    return out


def rock_fit(shape, floor: float, level: float, above: float) -> tuple[float, float] | None:
    """(origin z, scale) of a rock whose top stands `above` over the water, or None.

    The origin is on the pool floor and the scale follows the depth. Where
    the largest scale is too small, the origin goes up, at most ROCK_LIFT of
    the model's underside: the rock still stands in the floor.
    """
    low, high = config.ROCK_SCALE
    scale = min(max((level + above - floor) / shape.hi[2], low), high)
    z = max(floor, level + above - shape.hi[2] * scale)
    if z - floor > config.ROCK_LIFT * -shape.lo[2] * scale + 1e-9:
        return None
    # A shallow spot with the smallest scale: the top stands higher than asked.
    return z, scale


def fall_scale(mouth: Mouth, level: float, fall: Fall, top: float) -> float:
    """Height scale of a fall whose top is `top` of the way up the pipe opening (before FALL_RAISE)."""
    return (mouth.lip_z + top * 2 * mouth.radius - level) / fall.height
