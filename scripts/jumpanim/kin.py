"""Jump clip kinematics: vectors and quaternions, clip sampling, forward
kinematics of the leg chain (jumpanim.bake)."""

from __future__ import annotations

import copy
import math
from typing import Protocol

from character_anim_m3 import quat_multiply


class AnimKey(Protocol):
    """An m3 animation key: a VEC3 location, or a QUAT rotation (it has w too)."""

    x: float
    y: float
    z: float


class TrackBlock(Protocol):
    """An m3 key block of one track: key times (ms) and keys."""

    frames: list[int]
    keys: list[AnimKey]


# anim id -> key: the pose of the tracks a clip sets.
Pose = dict[int, AnimKey]

TRACK_LOC = 2
TRACK_ROT = 3
SAMPLE_MS = 33  # bake key spacing (about one 30 fps frame)
FEET = ("BoneFootL", "BoneFootR")
PELVIS = "Root"
# (thigh, calf, foot) per leg.
LEGS = (("BoneLegL", "BoneCalfL", "BoneFootL"), ("BoneLegR", "BoneCalfR", "BoneFootR"))


def smoothstep(edge0: float, edge1: float, x: float) -> float:
    if edge1 <= edge0:
        return 1.0 if x >= edge1 else 0.0
    t = min(1.0, max(0.0, (x - edge0) / (edge1 - edge0)))
    return t * t * (3.0 - 2.0 * t)


# --- Vectors and quaternions (x, y, z, w) ---


def quat_tuple(key) -> tuple[float, float, float, float]:
    return (float(key.x), float(key.y), float(key.z), float(key.w))


def conj(q) -> tuple[float, float, float, float]:
    return (-q[0], -q[1], -q[2], q[3])


def rotate(q, v) -> tuple[float, float, float]:
    out = quat_multiply(quat_multiply(q, (v[0], v[1], v[2], 0.0)), conj(q))
    return (out[0], out[1], out[2])


def dot(a, b) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b) -> tuple[float, float, float]:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def sub(a, b) -> tuple[float, float, float]:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def add(a, b) -> tuple[float, float, float]:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def mul(a, s: float) -> tuple[float, float, float]:
    return (a[0] * s, a[1] * s, a[2] * s)


def length(a) -> float:
    return math.sqrt(dot(a, a))


def unit(a) -> tuple[float, float, float]:
    size = length(a)
    if size < 1e-9:
        raise ValueError("zero vector")
    return mul(a, 1.0 / size)


def shortest_arc(a, b) -> tuple[float, float, float, float]:
    """The smallest rotation that turns unit vector a onto unit vector b."""
    w = 1.0 + dot(a, b)
    if w < 1e-8:
        raise ValueError("opposite vectors: the turn is not defined")
    c = cross(a, b)
    size = math.sqrt(dot(c, c) + w * w)
    return (c[0] / size, c[1] / size, c[2] / size, w / size)


def lerp_key(a, b, t: float, is_quat: bool):
    """Linear blend of two keys; quaternions take the short path and are normalized."""
    key = copy.copy(a)
    if not is_quat:
        key.x = a.x + (b.x - a.x) * t
        key.y = a.y + (b.y - a.y) * t
        key.z = a.z + (b.z - a.z) * t
        return key
    sign = 1.0 if (a.x * b.x + a.y * b.y + a.z * b.z + a.w * b.w) >= 0.0 else -1.0
    x = a.x + (sign * b.x - a.x) * t
    y = a.y + (sign * b.y - a.y) * t
    z = a.z + (sign * b.z - a.z) * t
    w = a.w + (sign * b.w - a.w) * t
    size = math.sqrt(x * x + y * y + z * z + w * w) or 1.0
    key.x, key.y, key.z, key.w = x / size, y / size, z / size, w / size
    return key


# --- Clip sampling ---


def sample_times(length_ms: int) -> list[int]:
    times = list(range(0, length_ms, SAMPLE_MS))
    if not times or times[-1] != length_ms:
        times.append(length_ms)
    return times


def base_ms(start: int, end: int, ms: float, looping: bool) -> float:
    span = end - start
    if span <= 0:
        return float(start)
    if looping:
        return start + (ms % span)
    return start + min(ms, span)


def sample_key(frames: list[int], keys: list, ms: float, is_quat: bool):
    if ms <= frames[0]:
        return copy.copy(keys[0])
    for index in range(len(frames) - 1):
        a, b = frames[index], frames[index + 1]
        if a <= ms <= b:
            t = 0.0 if b == a else (ms - a) / (b - a)
            return lerp_key(keys[index], keys[index + 1], t, is_quat)
    return copy.copy(keys[-1])


def base_tracks(stc) -> dict[int, tuple[int, TrackBlock]]:
    """anim id -> (kind, block) of a clip's loc and rot tracks."""
    out = {}
    for anim_id, ref in zip(stc.animIds, stc.animRefs):
        kind = (ref >> 16) & 0xFFFF
        if kind == TRACK_LOC:
            out[anim_id] = (kind, stc.sd3v[ref & 0xFFFF])
        elif kind == TRACK_ROT:
            out[anim_id] = (kind, stc.sd4q[ref & 0xFFFF])
    return out


def group_clip(model, name: str):
    """(stc, start ms, end ms, looping) of a model group."""
    groups = {group.name: group for group in model.sequenceTransformationGroups}
    sequences = {sequence.name: sequence for sequence in model.sequences}
    stc = model.sequenceTransformationCollections[groups[name].stcIndices[0]]
    sequence = sequences[name]
    return stc, sequence.animStartInMS, sequence.animEndInMS, not (sequence.flags & 1)


def clip_pose(model, name: str, ms: float) -> Pose:
    """anim id -> key of a clip at ms (wrapped when looping, clamped otherwise)."""
    stc, start, end, looping = group_clip(model, name)
    at = base_ms(start, end, ms, looping)
    return {
        anim_id: sample_key(list(block.frames), list(block.keys), at, kind == TRACK_ROT)
        for anim_id, (kind, block) in base_tracks(stc).items()
    }


# --- Forward kinematics ---


def bone_world(model, pose: Pose, names) -> dict[str, tuple[tuple, tuple, float]]:
    """Model-space (position, rotation, scale) of the named bones under pose.

    Bone scales are the rest values and are taken as uniform (the leg chain
    has 0.84 on the waist and 1.18 on the thighs)."""
    world: dict[int, tuple[tuple, tuple, float]] = {}

    def solve(index: int):
        if index in world:
            return world[index]
        bone = model.bones[index]
        loc = pose.get(bone.location.header.animId, bone.location.initValue)
        rot = pose.get(bone.rotation.header.animId, bone.rotation.initValue)
        lv = (float(loc.x), float(loc.y), float(loc.z))
        lq = quat_tuple(rot)
        scale = float(bone.scale.initValue.x)
        if bone.parent < 0:
            result = (lv, lq, scale)
        else:
            ppos, prot, pscale = solve(bone.parent)
            result = (add(ppos, mul(rotate(prot, lv), pscale)), quat_multiply(prot, lq), pscale * scale)
        world[index] = result
        return result

    index_of = {bone.name: index for index, bone in enumerate(model.bones)}
    return {name: solve(index_of[name]) for name in names}


def foot_positions(model, pose: Pose, names=FEET) -> dict[str, tuple[float, float, float]]:
    """Model-space positions of the named bones under pose (rest where unposed)."""
    return {name: value[0] for name, value in bone_world(model, pose, names).items()}


def feet_distance(model, a: dict, b: dict) -> float:
    """Largest foot position difference between two poses."""
    fa, fb = foot_positions(model, a), foot_positions(model, b)
    return max(math.dist(fa[name], fb[name]) for name in FEET)


def leg_length(model, pose: Pose) -> float:
    """Mean hip joint to foot distance under pose."""
    total = 0.0
    for thigh, _, foot in LEGS:
        world = bone_world(model, pose, (thigh, foot))
        total += length(sub(world[foot][0], world[thigh][0]))
    return total / len(LEGS)


def gait_flights(model, group: str) -> list[float]:
    """Walk phases (0..1) of the two flight frames: the pelvis height maxima."""
    _, start, end, _ = group_clip(model, group)
    cycle = end - start
    times = list(range(0, cycle, 5))
    heights = [bone_world(model, clip_pose(model, group, ms), (PELVIS,))[PELVIS][0][2] for ms in times]
    first = max(range(len(times)), key=lambda i: heights[i])
    # The other one: the highest sample in the opposite half of the cycle.
    quarter = len(times) // 4
    other = [(first + quarter + i) % len(times) for i in range(len(times) - 2 * quarter)]
    second = max(other, key=lambda i: heights[i])
    return sorted(times[i] / cycle for i in (first, second))
