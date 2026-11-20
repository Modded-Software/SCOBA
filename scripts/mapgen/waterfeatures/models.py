"""The measured models (scripts/data/water_models.json) and placement geometry.

Axes (hitvolumes/ray.py, footprints/slices.py; checked in game there): a
placed object is drawn as Rz(Rotation) x scale x model. A model's front is
its -y. A unit without a Rotation is drawn as authored.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import NamedTuple

from project_root import project_root

DATA = project_root() / "scripts" / "data" / "water_models.json"

Point = tuple[float, float]


class Fall(NamedTuple):
    """One water doodad model, model space."""

    kind: str
    variation: int
    lo: tuple[float, float, float]
    hi: tuple[float, float, float]
    base_z: float  # the water surface the model was made for
    splashes: tuple[Point, ...]  # where its streams land

    @property
    def height(self) -> float:
        """Water surface to the top of the model."""
        return self.hi[2] - self.base_z

    @property
    def width(self) -> float:
        return self.hi[0] - self.lo[0]

    @property
    def depth(self) -> float:
        return self.hi[1] - self.lo[1]

    @property
    def centre(self) -> Point:
        return ((self.lo[0] + self.hi[0]) / 2, (self.lo[1] + self.hi[1]) / 2)


class Tube(NamedTuple):
    """One pipe of a unit model, model space."""

    mouth: Point
    lip_z: float
    top_z: float
    dir: Point
    radius: float
    length: float


class Pipe(NamedTuple):
    model_scale: float
    tubes: tuple[Tube, ...]


class Rock(NamedTuple):
    """One rock doodad model, model space."""

    kind: str
    variation: int
    lo: tuple[float, float, float]
    hi: tuple[float, float, float]

    @property
    def radius(self) -> float:
        """Farthest reach from the origin on the ground plane."""
        return max(abs(self.lo[0]), abs(self.lo[1]), abs(self.hi[0]), abs(self.hi[1]))


class Models(NamedTuple):
    falls: dict[str, dict[int, Fall]]
    pipes: dict[str, Pipe]
    rocks: dict[str, dict[int, Rock]] = {}


def load(path: Path = DATA) -> Models:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    falls = {
        kind: {
            int(v): Fall(kind, int(v), tuple(f["min"]), tuple(f["max"]), float(f["base_z"]), tuple((float(x), float(y)) for x, y in f["splashes"]))
            for v, f in variations.items()
        }
        for kind, variations in data["falls"].items()
    }
    pipes = {
        name: Pipe(
            float(p["model_scale"]),
            tuple(Tube(tuple(t["mouth"]), float(t["lip_z"]), float(t["top_z"]), tuple(t["dir"]), float(t["radius"]), float(t["length"])) for t in p["tubes"]),
        )
        for name, p in data["pipes"].items()
    }
    rocks = {
        kind: {int(v): Rock(kind, int(v), tuple(r["min"]), tuple(r["max"])) for v, r in variations.items()}
        for kind, variations in data.get("rocks", {}).items()
    }
    return Models(falls, pipes, rocks)


def turned(p: Point, rotation: float) -> Point:
    """A model-plane vector in the world: Rz(rotation)."""
    c, s = math.cos(rotation), math.sin(rotation)
    return (p[0] * c - p[1] * s, p[0] * s + p[1] * c)


def rotation_facing(direction: Point) -> float:
    """Rotation that points a model's front (-y) along a world direction."""
    return math.atan2(direction[0], -direction[1]) % math.tau


def to_world(p: Point, x: float, y: float, rotation: float, scale: float) -> Point:
    """A model-plane point of a placed doodad, in the world."""
    tx, ty = turned((p[0] * scale, p[1] * scale), rotation)
    return (x + tx, y + ty)


def footprint(fall: Fall, x: float, y: float, rotation: float, scale: float) -> list[Point]:
    """World corners of the model's bounds on the ground plane, counter-clockwise."""
    corners = ((fall.lo[0], fall.lo[1]), (fall.hi[0], fall.lo[1]), (fall.hi[0], fall.hi[1]), (fall.lo[0], fall.hi[1]))
    return [to_world(c, x, y, rotation, scale) for c in corners]


def area(polygon: list[Point]) -> float:
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(polygon, polygon[1:] + polygon[:1]))) / 2


def clip(subject: list[Point], clipper: list[Point]) -> list[Point]:
    """Intersection of two convex counter-clockwise polygons (Sutherland-Hodgman)."""
    out = list(subject)
    for a, b in zip(clipper, clipper[1:] + clipper[:1]):
        if not out:
            break
        ex, ey = b[0] - a[0], b[1] - a[1]

        def side(p: Point) -> float:
            return ex * (p[1] - a[1]) - ey * (p[0] - a[0])

        def crossing(p: Point, q: Point) -> Point:
            sp, sq = side(p), side(q)
            t = sp / (sp - sq)
            return (p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1]))

        points, out = out, []
        for prev, cur in zip(points[-1:] + points[:-1], points):
            if side(cur) >= 0:
                if side(prev) < 0:
                    out.append(crossing(prev, cur))
                out.append(cur)
            elif side(prev) >= 0:
                out.append(crossing(prev, cur))
    return out


def overlap_share(a: list[Point], b: list[Point]) -> float:
    """Shared area of two footprints as a share of the smaller one."""
    shared = clip(a, b)
    if len(shared) < 3:
        return 0.0
    return area(shared) / min(area(a), area(b))


def segment_distance(p: Point, a: Point, b: Point) -> float:
    """Distance from a point to a segment."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    span = dx * dx + dy * dy
    t = 0.0 if span == 0 else min(1.0, max(0.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / span))
    return math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy))
