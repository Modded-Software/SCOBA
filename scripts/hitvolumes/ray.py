"""Host reference of the TPS pick ray tests (systems/hit_volumes.galaxy).

Same rules as the Galaxy code: the distance along a unit ray where it enters
a shape, 0 when the ray starts inside, None for a miss. Model space as in
scripts/data/hit_volumes.json; the unit's facing is model -y (MODEL_YAW).
Used by the host tests and to choose the in-game aim points.
"""

from __future__ import annotations

import math
from typing import TypedDict

Vec3 = tuple[float, float, float]
MODEL_YAW = 90.0
PARALLEL = 0.001


class Shape(TypedDict, total=False):
    """One hit volume as stored in hit_volumes.json. k: sphere, capsule or box.

    sphere: c centre, r radius. capsule: a, b segment ends, r radius.
    box: c centre, u three unit axes, h three half sizes.
    """

    k: str
    c: list[float]
    r: float
    a: list[float]
    b: list[float]
    u: list[list[float]]
    h: list[float]


def dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def add_scaled(a: Vec3, b: Vec3, s: float) -> Vec3:
    return (a[0] + b[0] * s, a[1] + b[1] * s, a[2] + b[2] * s)


def nearer(a: float | None, b: float | None) -> float | None:
    if a is None:
        return b
    if b is None:
        return a
    return min(a, b)


def sphere(o: Vec3, d: Vec3, c: Vec3, r: float) -> float | None:
    lv = sub(c, o)
    ll = dot(lv, lv)
    if ll <= r * r:
        return 0.0
    t = dot(lv, d)
    if t < 0.0:
        return None
    pp = ll - t * t
    if pp > r * r:
        return None
    return t - math.sqrt(r * r - pp)


def capsule(o: Vec3, d: Vec3, a: Vec3, b: Vec3, r: float) -> float | None:
    span = math.sqrt(dot(sub(b, a), sub(b, a)))
    if span == 0.0:
        return sphere(o, d, a, r)
    n = tuple(x / span for x in sub(b, a))
    oa = sub(o, a)
    no = dot(n, oa)
    q = min(span, max(0.0, no))
    near = sub(oa, tuple(x * q for x in n))
    if dot(near, near) <= r * r:
        return 0.0
    nd = dot(n, d)
    k = 1.0 - nd * nd
    if k < PARALLEL:
        return nearer(sphere(o, d, a, r), sphere(o, d, b, r))
    hb = dot(d, oa) - no * nd
    c = dot(oa, oa) - no * no - r * r
    h = hb * hb - k * c
    if h < 0.0:
        return None
    t = (-hb - math.sqrt(h)) / k
    y = no + t * nd
    if 0.0 < y < span:
        return t if t >= 0.0 else None
    return sphere(o, d, a if y <= 0.0 else b, r)


def box(o: Vec3, d: Vec3, c: Vec3, axes: list[Vec3], halves: Vec3) -> float | None:
    lv = sub(c, o)
    lo, hi = -math.inf, math.inf
    for u, h in zip(axes, halves):
        e = dot(u, lv)
        f = dot(u, d)
        if abs(f) > PARALLEL:
            t1, t2 = sorted(((e + h) / f, (e - h) / f))
            lo, hi = max(lo, t1), min(hi, t2)
        elif e + h < 0.0 or e - h > 0.0:
            return None
    if hi < 0.0 or lo > hi:
        return None
    return max(lo, 0.0)


def shape(o: Vec3, d: Vec3, s: dict) -> float | None:
    if s["k"] == "sphere":
        return sphere(o, d, tuple(s["c"]), s["r"])
    if s["k"] == "capsule":
        return capsule(o, d, tuple(s["a"]), tuple(s["b"]), s["r"])
    return box(o, d, tuple(s["c"]), [tuple(u) for u in s["u"]], tuple(s["h"]))


def to_model(v: Vec3, facing: float) -> Vec3:
    """A world vector in the model space of a unit with this facing."""
    a = math.radians(facing + MODEL_YAW)
    return (v[0] * math.cos(a) + v[1] * math.sin(a), v[1] * math.cos(a) - v[0] * math.sin(a), v[2])


def to_world(v: Vec3, facing: float) -> Vec3:
    a = math.radians(facing + MODEL_YAW)
    return (v[0] * math.cos(a) - v[1] * math.sin(a), v[0] * math.sin(a) + v[1] * math.cos(a), v[2])


def unit_hit(shapes: list[Shape], at: Vec3, facing: float, o: Vec3, d: Vec3) -> float | None:
    """Entry distance of a world ray into the volume of a unit at `at`."""
    mo = to_model(sub(o, at), facing)
    md = to_model(d, facing)
    best = None
    for s in shapes:
        best = nearer(best, shape(mo, md, s))
    return best


def aim(o: Vec3, p: Vec3) -> Vec3:
    """The unit ray from o through p."""
    v = sub(p, o)
    n = math.sqrt(dot(v, v))
    return (v[0] / n, v[1] / n, v[2] / n)
