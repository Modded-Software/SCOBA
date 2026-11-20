"""Where a water feature goes: a pool of a site water type with pipe mouths over it."""

from __future__ import annotations

import math
import re
from typing import Callable, NamedTuple

from . import config
from .models import Models, Point, turned

Rect = tuple[float, float, float, float]
UNIT_RE = re.compile(r"<ObjectUnit\b[^>]*>")


class Mouth(NamedTuple):
    """The outer end of one pipe, in the world."""

    x: float
    y: float
    lip_z: float  # the water leaves here
    top_z: float
    dx: float  # outward, unit length
    dy: float
    radius: float
    length: float

    @property
    def at(self) -> Point:
        return (self.x, self.y)

    @property
    def out(self) -> Point:
        return (self.dx, self.dy)


class Site(NamedTuple):
    rect: Rect
    water: str
    mouths: tuple[Mouth, ...]
    shift: Point = (0.0, 0.0)  # where the water leaves, against the measured mouths


def toward_big(mouths: tuple[Mouth, ...]) -> Point:
    """SITE_SHIFT along the row of mouths, from the smallest pipe toward the biggest.

    Operator, 2026-11-20, from the game: both features stood 2 to 3 cells
    off their pipes, each on the side of its smaller pipe.
    """
    small = min(mouths, key=lambda m: m.radius)
    big = max(mouths, key=lambda m: m.radius)
    span = math.hypot(big.x - small.x, big.y - small.y)
    if span == 0.0:
        return (0.0, 0.0)
    return ((big.x - small.x) / span * config.SITE_SHIFT, (big.y - small.y) / span * config.SITE_SHIFT)


def _attr(head: str, name: str) -> str | None:
    m = re.search(rf'\b{name}="([^"]*)"', head)
    return m.group(1) if m else None


def pipe_mouths(objects: str, models: Models, ground_at: Callable[[float, float], float], unit_scale: dict[str, float] | None = None) -> list[Mouth]:
    """Every pipe mouth of the placed pipe units.

    unit_scale: factor per unit type a later build step still applies to the
    placed Scale (mapgen.spore_scale).
    """
    out = []
    for match in UNIT_RE.finditer(objects):
        head = match.group(0)
        pipe = models.pipes.get(config.PIPE_UNITS.get(_attr(head, "UnitType") or "", ""))
        if pipe is None:
            continue
        x, y, _z = (float(v) for v in _attr(head, "Position").split(","))
        rotation = float(_attr(head, "Rotation") or 0.0)
        placed = float((_attr(head, "Scale") or "1").split(",")[0])
        scale = pipe.model_scale * placed * (unit_scale or {}).get(_attr(head, "UnitType"), 1.0)
        base = ground_at(x, y)
        for tube in pipe.tubes:
            mx, my = turned((tube.mouth[0] * scale, tube.mouth[1] * scale), rotation)
            dx, dy = turned(tube.dir, rotation)
            out.append(Mouth(x + mx, y + my, base + tube.lip_z * scale, base + tube.top_z * scale, dx, dy, tube.radius * scale, tube.length * scale))
    return out


def rect_distance(p: Point, rect: Rect) -> float:
    x0, y0, x1, y1 = rect
    return math.hypot(max(x0 - p[0], 0.0, p[0] - x1), max(y0 - p[1], 0.0, p[1] - y1))


def find(rects: list[tuple[str, Rect]], mouths: list[Mouth]) -> list[Site]:
    """One site per rectangle of a site water type that a pipe mouth reaches."""
    sites = []
    for water, rect in rects:
        if water not in config.SITE_WATER:
            continue
        near = tuple(m for m in mouths if rect_distance(m.at, rect) <= config.MOUTH_REACH)
        if near:
            sites.append(Site(rect, water, near, toward_big(near)))
    return sites


def levels(sites: list[Site]) -> dict[str, float]:
    """Water height per site water type: DROP below its lowest pipe lip."""
    out: dict[str, float] = {}
    for site in sites:
        low = min(m.lip_z for m in site.mouths) - config.DROP
        out[site.water] = min(out.get(site.water, low), low)
    return out
