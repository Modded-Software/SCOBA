#!/usr/bin/env python3
"""Footfall times of a walk clip, measured from the foot bones.

The Goliath Walk clip carries no footstep events (only Evt_SeqEnd), so the
contacts are measured: each foot bone's world height is sampled through the
clip (bone keys interpolated linearly, chained to the root), and a footfall
is the time a foot reaches its lowest point after descending.

Usage: uv run -m footfall.m3_footfalls MODEL.m3 --clip Walk --bone "Bone Foot L" --bone "Bone Foot R"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from project_root import project_root

sys.path.insert(0, str(project_root() / "scripts" / "vendor" / "m3addon"))

import m3

SD3V_KIND = 2
SD4Q_KIND = 3


def qmul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    )


def qrot(q, v):
    x, y, z, w = q
    tx = 2 * (y * v[2] - z * v[1])
    ty = 2 * (z * v[0] - x * v[2])
    tz = 2 * (x * v[1] - y * v[0])
    return (
        v[0] + w * tx + (y * tz - z * ty),
        v[1] + w * ty + (z * tx - x * tz),
        v[2] + w * tz + (x * ty - y * tx),
    )


def lerp_keys(frames, keys, t, size):
    if t <= frames[0]:
        return keys[0]
    for i in range(1, len(frames)):
        if t <= frames[i]:
            a = (t - frames[i - 1]) / max(1, frames[i] - frames[i - 1])
            return tuple(keys[i - 1][k] + (keys[i][k] - keys[i - 1][k]) * a for k in range(size))
    return keys[-1]


def tracks(model, clip: str) -> dict[int, tuple[list[int], list[tuple]]]:
    index = [s.name for s in model.sequences].index(clip)
    out: dict[int, tuple[list[int], list[tuple]]] = {}
    for stc_index in model.sequenceTransformationGroups[index].stcIndices:
        stc = model.sequenceTransformationCollections[stc_index]
        for anim_id, ref in zip(stc.animIds, stc.animRefs):
            kind = (ref >> 16) & 0xFFFF
            if kind == SD3V_KIND:
                block = stc.sd3v[ref & 0xFFFF]
                keys = [(float(k.x), float(k.y), float(k.z)) for k in block.keys]
            elif kind == SD4Q_KIND:
                block = stc.sd4q[ref & 0xFFFF]
                keys = [(float(k.x), float(k.y), float(k.z), float(k.w)) for k in block.keys]
            else:
                continue
            out[anim_id] = ([int(f) for f in block.frames], keys)
    return out


def bone_value(ref, keyed, t, size):
    track = keyed.get(ref.header.animId)
    if track is None:
        v = ref.initValue
        return (float(v.x), float(v.y), float(v.z)) if size == 3 else (float(v.x), float(v.y), float(v.z), float(v.w))
    return lerp_keys(track[0], track[1], t, size)


def world_height(model, keyed, bone_index: int, t: float) -> float:
    chain = []
    i = bone_index
    while i != -1:
        chain.append(i)
        i = model.bones[i].parent
    pos = (0.0, 0.0, 0.0)
    rot = (0.0, 0.0, 0.0, 1.0)
    for i in reversed(chain):
        bone = model.bones[i]
        loc = bone_value(bone.location, keyed, t, 3)
        pos = tuple(p + d for p, d in zip(pos, qrot(rot, loc)))
        rot = qmul(rot, bone_value(bone.rotation, keyed, t, 4))
    return pos[2]


def footfalls(path: Path, clip: str, bones: list[str], step_ms: int = 10) -> dict[str, list[int]]:
    model = m3.loadModel(str(path))
    keyed = tracks(model, clip)
    sequence = model.sequences[[s.name for s in model.sequences].index(clip)]
    start, end = int(sequence.animStartInMS), int(sequence.animEndInMS)
    names = [b.name for b in model.bones]
    result = {}
    for bone in bones:
        index = names.index(bone)
        heights = [(t, world_height(model, keyed, index, t)) for t in range(start, end, step_ms)]
        low = min(h for _, h in heights)
        span = max(h for _, h in heights) - low
        contacts = []
        # Loop the clip: a footfall is the first sample in the lowest 20 % of
        # the swing after a sample above it (the foot coming down).
        band = low + 0.2 * span
        n = len(heights)
        for k in range(n):
            if heights[k][1] <= band and heights[k - 1][1] > band:
                contacts.append(heights[k][0] - start)
        result[bone] = contacts
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("--clip", default="Walk")
    parser.add_argument("--bone", action="append", required=True)
    args = parser.parse_args()
    for bone, times in footfalls(args.model, args.clip, args.bone).items():
        print(f"{bone}: {times}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
