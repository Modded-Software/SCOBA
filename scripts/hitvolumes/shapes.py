"""The hit-test shapes of an m3 model at rest, in model space, scaled.

An m3 model carries "fuzzy" hit-test shapes, the volumes the engine's cursor
pick uses, and one "tight" shape. Each shape hangs on a bone and has its own
transform. Shape kinds (SSGS, m3addon shared.py): 0 cuboid with half sizes
size0..2, 1 sphere with radius size0, 2 capsule with radius size0 and a
straight part size1 long along its local z, centred.

Source order, as the engine's own pick: the fuzzy shapes; a model without
them uses its tight shape; a model without either uses its bounding box.
Model space: x is the unit's facing, z is up (checked in game by the tps
`pick` group).
"""

from __future__ import annotations

import sys
from pathlib import Path

from project_root import project_root

sys.path.insert(0, str(project_root() / "scripts" / "vendor" / "m3addon"))

import m3

from .ray import Shape

Vec3 = tuple[float, float, float]
Mat4 = list[list[float]]





DECIMALS = 4
KIND_BOX, KIND_SPHERE, KIND_CAPSULE = 0, 1, 2


def columns(m) -> Mat4:
    """An m3 Matrix44 (four column vectors) as a row-major 4x4."""
    cols = [(v.x, v.y, v.z, v.w) for v in (m.x, m.y, m.z, m.w)]
    return [[cols[c][r] for c in range(4)] for r in range(4)]


def mul(a: Mat4, b: Mat4) -> Mat4:
    return [[sum(a[r][k] * b[k][c] for k in range(4)) for c in range(4)] for r in range(4)]


def inverse(m: Mat4) -> Mat4:
    """Gauss-Jordan inverse of a 4x4."""
    n = 4
    a = [row[:] + [1.0 if r == c else 0.0 for c in range(n)] for r, row in enumerate(m)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
        if abs(a[pivot][col]) < 1e-12:
            raise ValueError("singular bone matrix")
        a[col], a[pivot] = a[pivot], a[col]
        p = a[col][col]
        a[col] = [v / p for v in a[col]]
        for r in range(n):
            if r != col:
                f = a[r][col]
                a[r] = [v - f * w for v, w in zip(a[r], a[col])]
    return [row[n:] for row in a]


def point(m: Mat4, p: Vec3) -> Vec3:
    x, y, z = (m[r][0] * p[0] + m[r][1] * p[1] + m[r][2] * p[2] + m[r][3] for r in range(3))
    return (x, y, z)


def axis(m: Mat4, c: int) -> Vec3:
    return (m[0][c], m[1][c], m[2][c])


def norm(v: Vec3) -> float:
    return (v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) ** 0.5


def scaled(p: Vec3, s: Vec3) -> Vec3:
    return (p[0] * s[0], p[1] * s[1], p[2] * s[2])


def rounded(v) -> list[float]:
    return [round(x, DECIMALS) + 0.0 for x in v]


def shape_transform(model, shape) -> Mat4:
    """Model-space transform of a shape: bone rest pose, then the shape's own."""
    local = columns(shape.matrix)
    bones = model.absoluteInverseBoneRestPositions
    if 0 <= shape.boneIndex < len(bones):
        return mul(inverse(columns(bones[shape.boneIndex].matrix)), local)
    return local


def shape_record(model, shape, scale: Vec3) -> Shape:
    """One shape in model space with the unit's data scale applied.

    A non-uniform data scale turns a sphere into an ellipsoid; the record
    keeps a sphere with the largest scaled radius, so it covers the model.
    """
    m = shape_transform(model, shape)
    if shape.shape == KIND_SPHERE:
        radius = shape.size0 * max(norm(axis(m, c)) for c in range(3)) * max(scale)
        return {"k": "sphere", "c": rounded(scaled(point(m, (0.0, 0.0, 0.0)), scale)), "r": round(radius, DECIMALS)}
    if shape.shape == KIND_CAPSULE:
        half = shape.size1 / 2.0
        a = scaled(point(m, (0.0, 0.0, -half)), scale)
        b = scaled(point(m, (0.0, 0.0, half)), scale)
        radius = shape.size0 * max(norm(axis(m, 0)), norm(axis(m, 1))) * max(scale)
        return {"k": "capsule", "a": rounded(a), "b": rounded(b), "r": round(radius, DECIMALS)}
    if shape.shape == KIND_BOX:
        sizes = (shape.size0, shape.size1, shape.size2)
        axes = []
        halves = []
        for c in range(3):
            v = scaled(axis(m, c), scale)
            length = norm(v)
            axes.append(rounded(tuple(x / length for x in v)))
            halves.append(round(sizes[c] * length, DECIMALS))
        return {"k": "box", "c": rounded(scaled(point(m, (0.0, 0.0, 0.0)), scale)), "u": axes, "h": halves}
    raise ValueError(f"unknown hit-test shape kind {shape.shape}")


def bounds_record(model, scale: Vec3) -> Shape:
    b = model.boundings
    lo = scaled((b.minBorder.x, b.minBorder.y, b.minBorder.z), scale)
    hi = scaled((b.maxBorder.x, b.maxBorder.y, b.maxBorder.z), scale)
    centre = tuple((x + y) / 2.0 for x, y in zip(lo, hi))
    half = tuple(abs(y - x) / 2.0 for x, y in zip(lo, hi))
    return {"k": "box", "c": rounded(centre), "u": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]], "h": rounded(half)}


def has_tight(model) -> bool:
    t = model.tightHitTest
    return max(t.size0, t.size1, t.size2) > 0.0


def model_shapes(path: Path, scale: Vec3) -> tuple[str, list[Shape]]:
    """(source, shapes) of one m3 file.

    checkExpectedValue off: m3addon asserts that fields it calls unknown
    hold the value its authors saw; newer stock models break that (PHSH,
    CREP, VOL_) in fields the shapes do not read. Unknown sections still
    fail."""
    model = m3.loadModel(str(path), checkExpectedValue=False)
    if model.fuzzyHitTestObjects:
        return "fuzzy", [shape_record(model, s, scale) for s in model.fuzzyHitTestObjects]
    if has_tight(model):
        return "tight", [shape_record(model, model.tightHitTest, scale)]
    return "bounds", [bounds_record(model, scale)]


def reach(shapes: list[Shape]) -> tuple[float, float, float]:
    """(horizontal reach from the unit origin, lowest z, highest z) of the volume."""
    xy = 0.0
    lo = float("inf")
    hi = float("-inf")
    for s in shapes:
        if s["k"] == "sphere":
            pts, r = [s["c"]], s["r"]
        elif s["k"] == "capsule":
            pts, r = [s["a"], s["b"]], s["r"]
        else:
            # Any corner of a box lies within its half-diagonal of the centre.
            r = norm(tuple(s["h"]))
            pts = [s["c"]]
        for p in pts:
            xy = max(xy, (p[0] ** 2 + p[1] ** 2) ** 0.5 + r)
            lo = min(lo, p[2] - r)
            hi = max(hi, p[2] + r)
    return round(xy, DECIMALS), round(lo, DECIMALS), round(hi, DECIMALS)
