#!/usr/bin/env python3
"""Print the model-space bounds and clip lengths of M3 models.

One line per sequence: name, length, bounding box size, sphere radius.
Used to size one unit against another (scale = target extent / own extent).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from project_root import project_root

ROOT = project_root()
sys.path.insert(0, str(ROOT / "scripts" / "vendor" / "m3addon"))

import m3


def vec(value) -> tuple[float, float, float]:
    return (float(value.x), float(value.y), float(value.z))


def mesh_extent(model) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """Min and max of the rest-pose vertex positions (model space)."""
    description = m3.structures["VertexFormat" + hex(model.vFlags)].getVersion(0)
    count = len(model.vertices) // description.size
    vertices = description.createInstances(buffer=model.vertices, count=count)
    points = [vec(v.position) for v in vertices]
    low = tuple(min(p[i] for p in points) for i in range(3))
    high = tuple(max(p[i] for p in points) for i in range(3))
    return low, high


def bone_rest(model, index: int) -> tuple[float, float, float]:
    """Model-space rest position of one bone, from its inverse rest matrix."""
    m = model.absoluteInverseBoneRestPositions[index].matrix
    cols = [m.x, m.y, m.z, m.w]
    r = [[float(cols[c].x), float(cols[c].y), float(cols[c].z)] for c in range(3)]
    t = (float(cols[3].x), float(cols[3].y), float(cols[3].z))
    # p = -R^T t for a rigid inverse; columns hold R's columns.
    return tuple(-(r[i][0] * t[0] + r[i][1] * t[1] + r[i][2] * t[2]) for i in range(3))


def rows(path: Path, bones: bool = False) -> list[str]:
    model = m3.loadModel(str(path))
    low, high = mesh_extent(model)
    out = [
        "  parts: "
        + " ".join(
            f"{name}={len(part)}"
            for name, part in (
                ("particles", model.particles),
                ("ribbons", model.ribbons),
                ("forces", model.forces),
                ("rigidBodies", model.rigidBodies),
                ("physicsJoints", model.physicsJoints),
                ("inverseKinematicChains", model.inverseKinematicChains),
            )
        ),
    ]
    if bones:
        for index, bone in enumerate(model.bones):
            p = bone_rest(model, index)
            out.append(f"  bone {index} {bone.name}: rest={p[0]:.3f},{p[1]:.3f},{p[2]:.3f}")
    out += [
        f"  mesh: size={high[0] - low[0]:.3f},{high[1] - low[1]:.3f},{high[2] - low[2]:.3f}"
        f" min={low[0]:.3f},{low[1]:.3f},{low[2]:.3f} max={high[0]:.3f},{high[1]:.3f},{high[2]:.3f}"
    ]
    for sequence in model.sequences:
        bounds = sequence.boundingSphere
        low = vec(bounds.minBorder)
        high = vec(bounds.maxBorder)
        size = tuple(h - l for l, h in zip(low, high))
        out.append(
            f"  {sequence.name}: {int(sequence.animEndInMS) - int(sequence.animStartInMS)} ms"
            f" size={size[0]:.3f},{size[1]:.3f},{size[2]:.3f}"
            f" min={low[0]:.3f},{low[1]:.3f},{low[2]:.3f}"
            f" max={high[0]:.3f},{high[1]:.3f},{high[2]:.3f}"
            f" radius={float(bounds.radius):.3f} flags={int(sequence.flags)}"
        )
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("models", type=Path, nargs="+")
    parser.add_argument("--bones", action="store_true", help="print every bone's rest position")
    args = parser.parse_args()
    for path in args.models:
        print(f"model: {path}")
        for line in rows(path, args.bones):
            print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
