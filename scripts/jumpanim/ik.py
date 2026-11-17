"""Jump pose shaping: two-bone leg IK, the rig, crouch, tuck, point and
gather (jumpanim.bake). Joint angles from motion capture: see the
jumpanim.bake docstring."""

from __future__ import annotations

import copy
import math
from typing import NamedTuple

from character_anim_m3 import quat_multiply
from jumpanim.kin import (
    FEET,
    LEGS,
    PELVIS,
    Pose,
    add,
    bone_world,
    conj,
    cross,
    dot,
    leg_length,
    length,
    mul,
    quat_tuple,
    rotate,
    shortest_arc,
    smoothstep,
    sub,
    unit,
)

# Joint angle changes from the standing pose, degrees (module docstring of
# jumpanim.bake). Operator 2026-11-17: the jump was stiff; the targets are
# the strongest real trials: crouch and landing of the high jumps (16_03,
# 16_04), air knee of the tucked hops and run jumps (75_03, 75_12).
# jumpanim/validate.py checks the built clips against the range of all trials.
CROUCH_KNEE_DEG = 72.0
CROUCH_ANKLE_DEG = -19.0
LAND_KNEE_DEG = 52.0
LAND_ANKLE_DEG = -18.0
AIR_KNEE_DEG = 35.0
AIR_ANKLE_DEG = 32.0
# Reference ranges (min, max) over the trials, for the build checks.
# "air hip" (thigh forward) is not a target: a foot rise under the hip gives
# about half the knee bend, as in the reference, where the feet stay under the hips.
REFERENCE = {
    "crouch knee": (51.5, 84.6),
    "landing knee": (37.5, 64.3),
    "air knee": (7.6, 45.4),
    "air ankle": (24.9, 36.5),
    "air hip": (5.5, 17.4),
    "crouch ankle": (-21.0, -15.4),
    "landing ankle": (-22.8, -8.7),
}
# Stand jump, at the apogee: the feet are this many hip widths apart (the
# hip width is the distance between the hip joints). Reference at the flight
# peak, feet 1.12 0.92 0.32 and knees 1.11 1.00 0.68 hip widths: the legs
# hang under the hips. GATHER_FEET and GATHER_KNEES are the means.
GATHER_FEET = 0.8
GATHER_KNEES = 0.93
GATHER_REFERENCE = {"feet": (0.32, 1.12), "knees": (0.68, 1.11)}
MIN_REACH = 0.25  # the hip to foot distance never goes below this part of the leg
# A foot is on the ground up to PLANT_LOW above its standing height, and in
# the air from PLANT_HIGH (parts of the leg length).
PLANT_LOW = 0.03
PLANT_HIGH = 0.15


# --- Pose shaping: pelvis drop and two-bone leg IK ---


def bone_named(model, name: str):
    for bone in model.bones:
        if bone.name == name:
            return bone
    raise KeyError(f"no bone {name}")


def local_rotation(bone, pose: Pose):
    return pose.get(bone.rotation.header.animId, bone.rotation.initValue)


def turn_bone(model, pose: Pose, name: str, turn) -> None:
    """Applies a model-space rotation to a bone, about its own joint."""
    bone = bone_named(model, name)
    key = local_rotation(bone, pose)
    local = quat_tuple(key)
    parent = quat_multiply(bone_world(model, pose, (name,))[name][1], conj(local))
    out = copy.copy(key)
    out.x, out.y, out.z, out.w = quat_multiply(conj(parent), quat_multiply(turn, quat_multiply(parent, local)))
    pose[bone.rotation.header.animId] = out


def set_world_rotation(model, pose: Pose, name: str, rotation) -> None:
    bone = bone_named(model, name)
    key = local_rotation(bone, pose)
    parent = quat_multiply(bone_world(model, pose, (name,))[name][1], conj(quat_tuple(key)))
    out = copy.copy(key)
    out.x, out.y, out.z, out.w = quat_multiply(conj(parent), rotation)
    pose[bone.rotation.header.animId] = out


def move_pelvis(model, pose: Pose, shift) -> None:
    """Moves the pelvis by shift (model space, model units)."""
    bone = bone_named(model, PELVIS)
    parent_rot, parent_scale = (0.0, 0.0, 0.0, 1.0), 1.0
    if bone.parent >= 0:
        _, parent_rot, parent_scale = bone_world(model, pose, (model.bones[bone.parent].name,))[model.bones[bone.parent].name]
    step = mul(rotate(conj(parent_rot), shift), 1.0 / parent_scale)
    key = pose.get(bone.location.header.animId, bone.location.initValue)
    out = copy.copy(key)
    out.x, out.y, out.z = key.x + step[0], key.y + step[1], key.z + step[2]
    pose[bone.location.header.animId] = out


def knee_position(hip, knee, foot, target, min_reach: float = 0.0):
    """Two-bone IK: the knee position that puts the foot at target.

    The bone lengths are kept. The knee stays on the side it bends to now
    (the part of hip->knee across hip->foot). The reach is clamped to what
    the leg can do; returns (knee, reached foot)."""
    upper, lower = length(sub(knee, hip)), length(sub(foot, knee))
    reach = sub(target, hip)
    lo = max(abs(upper - lower) + 1e-5, min_reach)
    distance = min(max(length(reach), lo), upper + lower - 1e-5)
    along = unit(reach)
    now = unit(sub(foot, hip))
    bend = sub(sub(knee, hip), mul(now, dot(sub(knee, hip), now)))  # how the knee bends now
    pole = sub(bend, mul(along, dot(bend, along)))
    if length(pole) < 1e-6:
        raise ValueError("straight leg: the knee side is not defined")
    pole = unit(pole)
    a = (upper * upper - lower * lower + distance * distance) / (2.0 * distance)
    h = math.sqrt(max(0.0, upper * upper - a * a))
    return add(hip, add(mul(along, a), mul(pole, h))), add(hip, mul(along, distance))


def solve_leg(model, pose: Pose, leg: tuple[str, str, str], target, foot_rotation, min_reach: float) -> None:
    """Turns the thigh and calf so the foot is at target; the foot keeps foot_rotation."""
    thigh, calf, foot = leg
    world = bone_world(model, pose, leg)
    hip, knee, at = world[thigh][0], world[calf][0], world[foot][0]
    new_knee, reached = knee_position(hip, knee, at, target, min_reach)
    turn_bone(model, pose, thigh, shortest_arc(unit(sub(knee, hip)), unit(sub(new_knee, hip))))
    world = bone_world(model, pose, (calf, foot))
    knee, at = world[calf][0], world[foot][0]
    turn_bone(model, pose, calf, shortest_arc(unit(sub(at, knee)), unit(sub(reached, knee))))
    set_world_rotation(model, pose, foot, foot_rotation)


def angle_between(a, b) -> float:
    """Angle between two vectors, degrees."""
    return math.degrees(math.acos(max(-1.0, min(1.0, dot(unit(a), unit(b))))))


def knee_flexion(model, pose: Pose, leg: tuple[str, str, str]) -> float:
    """Knee bend, degrees: 0 with the thigh and the shin in line."""
    world = bone_world(model, pose, leg)
    hip, knee, foot = (world[name][0] for name in leg)
    return angle_between(sub(knee, hip), sub(foot, knee))


def ankle_angle(model, pose: Pose, leg: tuple[str, str, str], foot_forward) -> float:
    """Angle between the shin (ankle to knee) and the foot's forward axis, degrees.

    It grows as the toes go down (plantarflexion) and shrinks as the shin
    leans over a flat foot (dorsiflexion)."""
    world = bone_world(model, pose, leg)
    knee, (ankle, rotation, _) = world[leg[1]][0], world[leg[2]]
    return angle_between(sub(knee, ankle), rotate(rotation, foot_forward))


class Rig(NamedTuple):
    """What the pose shaping needs from the standing pose (model units, degrees)."""

    leg: float                 # hip joint to foot, mean
    ground: dict               # foot -> standing height
    foot_forward: dict         # foot -> forward axis in the foot bone's frame
    knee: dict                 # foot -> standing knee bend
    ankle: dict                # foot -> standing ankle angle
    forward: tuple             # the way the standing knees bend, along the ground
    hips: float                # distance between the hip joints
    crouch: tuple = (0.0, 0.0)  # pelvis (down, back) of the takeoff crouch
    land: tuple = (0.0, 0.0)    # pelvis (down, back) of the landing crouch
    tuck: float = 0.0          # foot rise in the air


def body_forward(model, pose: Pose) -> tuple[float, float, float]:
    """The way the knees bend, along the ground: forward."""
    total = (0.0, 0.0, 0.0)
    for leg in LEGS:
        world = bone_world(model, pose, leg)
        hip, knee, foot = (world[name][0] for name in leg)
        along = unit(sub(foot, hip))
        bend = sub(sub(knee, hip), mul(along, dot(sub(knee, hip), along)))
        total = add(total, bend)
    return unit((total[0], total[1], 0.0))


def side_axis(forward) -> tuple[float, float, float]:
    """Left-right along the ground, across forward."""
    return unit(cross(forward, (0.0, 0.0, 1.0)))


def joint_width(model, pose: Pose, forward, joint: int) -> float:
    """Left-right distance between the legs at a joint: 0 hip, 1 knee, 2 foot."""
    names = tuple(leg[joint] for leg in LEGS)
    world = bone_world(model, pose, names)
    return abs(dot(sub(world[names[0]][0], world[names[1]][0]), side_axis(forward)))


def measure_rig(model, stand: Pose) -> Rig:
    forward = body_forward(model, stand)
    feet = bone_world(model, stand, FEET)
    foot_forward = {foot: rotate(conj(feet[foot][1]), forward) for foot in FEET}
    return Rig(
        leg=leg_length(model, stand),
        ground={foot: feet[foot][0][2] for foot in FEET},
        foot_forward=foot_forward,
        knee={leg[2]: knee_flexion(model, stand, leg) for leg in LEGS},
        ankle={leg[2]: ankle_angle(model, stand, leg, foot_forward[leg[2]]) for leg in LEGS},
        forward=forward,
        hips=joint_width(model, stand, forward, 0),
    )


def knee_change(model, pose: Pose, rig: Rig) -> float:
    """Mean knee bend change from the standing pose, degrees."""
    return sum(knee_flexion(model, pose, leg) - rig.knee[leg[2]] for leg in LEGS) / len(LEGS)


def ankle_change(model, pose: Pose, rig: Rig) -> float:
    """Mean ankle angle change from the standing pose, degrees (+ toes down)."""
    return sum(ankle_angle(model, pose, leg, rig.foot_forward[leg[2]]) - rig.ankle[leg[2]] for leg in LEGS) / len(LEGS)


def thigh_pitch(model, pose: Pose, leg: tuple[str, str, str], forward) -> float:
    """Thigh (hip to knee) angle from straight down, toward forward, degrees."""
    world = bone_world(model, pose, leg)
    thigh = sub(world[leg[1]][0], world[leg[0]][0])
    return math.degrees(math.atan2(dot(thigh, forward), -thigh[2]))


def hip_change(model, pose: Pose, stand: Pose, rig: Rig) -> float:
    """Mean hip flexion change from the standing pose, degrees (+ thigh forward).

    The pelvis does not turn in a jump clip, so the thigh pitch change is
    the hip flexion change."""
    return sum(
        thigh_pitch(model, pose, leg, rig.forward) - thigh_pitch(model, stand, leg, rig.forward) for leg in LEGS
    ) / len(LEGS)


SOLVE_STEPS = 24  # bisection steps: the leg length / 2^24


def bisect(value, target: float, low: float, high: float, what: str) -> float:
    """The x in [low, high] where the rising function value(x) reaches target."""
    if value(high) < target:
        raise ValueError(f"{what}: {target} is out of reach ({value(high):.1f} at the limit)")
    for _ in range(SOLVE_STEPS):
        middle = (low + high) / 2.0
        if value(middle) < target:
            low = middle
        else:
            high = middle
    return (low + high) / 2.0


def crouch_shift(forward, depth: tuple, weight: float) -> tuple[float, float, float]:
    """Pelvis shift of a crouch: depth (down, back) along forward, scaled by weight."""
    down, back = depth
    return (-forward[0] * back * weight, -forward[1] * back * weight, -down * weight)


def crouch_for(model, stand: Pose, rig: Rig, knee: float, ankle: float) -> tuple[float, float]:
    """The pelvis (down, back) that gives the standing legs the knee and ankle changes.

    Down bends the knees; back keeps the shins upright. For each back, down
    is solved for the knee; back is solved for the ankle."""

    def crouched(down: float, back: float) -> dict:
        pose = dict(stand)
        shape_pose(model, pose, rig, crouch_shift(rig.forward, (down, back), 1.0), 0.0, 0.0)
        return pose

    def down_for(back: float) -> float:
        return bisect(lambda down: knee_change(model, crouched(down, back), rig), knee, 0.0, (1.0 - MIN_REACH) * rig.leg, "knee bend")

    def ankle_at(back: float) -> float:
        return ankle_change(model, crouched(down_for(back), back), rig)

    if ankle_at(0.0) >= ankle:
        return down_for(0.0), 0.0  # the shins lean no further than the reference
    # The farther back the pelvis, the less the deepest drop bends the knees:
    # the ankle is searched only where the knee bend is still reachable.
    deepest = (1.0 - MIN_REACH) * rig.leg
    limit = 0.5 * rig.leg
    if knee_change(model, crouched(deepest, limit), rig) < knee:
        limit = bisect(lambda back: -knee_change(model, crouched(deepest, back), rig), -knee, 0.0, limit, "knee bend with the pelvis back")
    back = bisect(ankle_at, ankle, 0.0, limit * (1.0 - 1e-6), "ankle bend")
    return down_for(back), back


def tuck_for(model, stand: Pose, rig: Rig, knee: float) -> float:
    """The foot rise that bends the standing knees by knee degrees."""

    def bend(rise: float) -> float:
        pose = dict(stand)
        shape_pose(model, pose, rig, (0.0, 0.0, 0.0), rise, 0.0)
        return knee_change(model, pose, rig)

    return bisect(bend, knee, 0.0, (1.0 - MIN_REACH) * rig.leg, "air knee bend")


def make_rig(model, stand: Pose) -> Rig:
    """The rig with the depths that give the reference angles on the standing pose."""
    rig = measure_rig(model, stand)
    return rig._replace(
        crouch=crouch_for(model, stand, rig, CROUCH_KNEE_DEG, CROUCH_ANKLE_DEG),
        land=crouch_for(model, stand, rig, LAND_KNEE_DEG, LAND_ANKLE_DEG),
        tuck=tuck_for(model, stand, rig, AIR_KNEE_DEG),
    )


def point_foot(model, pose: Pose, rig: Rig, leg: tuple[str, str, str], weight: float) -> None:
    """Turns the foot at the ankle toward the reference flight angle (toes down)."""
    foot = leg[2]
    world = bone_world(model, pose, leg)
    knee, (ankle, rotation, _) = world[leg[1]][0], world[foot]
    shin, forward = unit(sub(knee, ankle)), rotate(rotation, rig.foot_forward[foot])
    now = angle_between(shin, forward)
    turn = math.radians(weight * (rig.ankle[foot] + AIR_ANKLE_DEG - now))
    # About shin x forward: the angle between them grows by the turn.
    spin = axis_turn(unit(cross(shin, forward)), turn)
    set_world_rotation(model, pose, foot, quat_multiply(spin, rotation))


def gather_foot(rig: Rig, target, middle: float, weight: float):
    """Moves a foot target sideways toward GATHER_FEET hip widths; never outward."""
    side = side_axis(rig.forward)
    offset = dot(target, side) - middle
    want = math.copysign(0.5 * GATHER_FEET * rig.hips, offset)
    if abs(offset) <= abs(want):
        return target
    return add(target, mul(side, (want - offset) * weight))


def axis_turn(axis, radians: float) -> tuple[float, float, float, float]:
    """The rotation by radians about a unit axis."""
    half = radians / 2.0
    return (axis[0] * math.sin(half), axis[1] * math.sin(half), axis[2] * math.sin(half), math.cos(half))


SWIVEL_MAX = math.radians(80.0)


def gather_knee(model, pose: Pose, rig: Rig, leg: tuple[str, str, str], middle: float, weight: float) -> None:
    """Swivels the leg about the hip to foot line so the knee moves sideways
    toward GATHER_KNEES hip widths; never outward. Hip and foot stay."""
    thigh, calf, foot = leg
    world = bone_world(model, pose, leg)
    hip, knee, (at, rotation, _) = world[thigh][0], world[calf][0], world[foot]
    side = side_axis(rig.forward)
    offset = dot(knee, side) - middle
    want = math.copysign(0.5 * GATHER_KNEES * rig.hips, offset)
    if abs(offset) <= abs(want):
        return
    goal = offset + (want - offset) * weight
    axis = unit(sub(at, hip))
    arm = sub(knee, hip)

    def offset_at(radians: float) -> float:
        return dot(add(hip, rotate(axis_turn(axis, radians), arm)), side) - middle

    # The way that brings the knee in, then the angle that reaches the goal.
    sign = 1.0 if abs(offset_at(0.01)) < abs(offset_at(-0.01)) else -1.0
    low, high = 0.0, SWIVEL_MAX
    if abs(offset_at(sign * high)) < abs(goal):
        for _ in range(SOLVE_STEPS):
            middle_angle = (low + high) / 2.0
            if abs(offset_at(sign * middle_angle)) > abs(goal):
                low = middle_angle
            else:
                high = middle_angle
    turn_bone(model, pose, thigh, axis_turn(axis, sign * high))
    set_world_rotation(model, pose, foot, rotation)


def shape_pose(model, pose: Pose, rig: Rig, shift, tuck: float, point: float, gather: float = 0.0) -> None:
    """Crouch (pelvis moved by shift), tuck (feet up), model units; point
    (toes down) and gather (legs together), 0..1.

    A foot on the ground stays in place under the crouch; a foot in the air
    moves with the pelvis."""
    crouched = length(shift) >= 1e-7
    if not crouched and tuck < 1e-7 and point < 1e-7 and gather < 1e-7:
        return
    feet = bone_world(model, pose, FEET)
    if crouched:
        move_pelvis(model, pose, shift)
    hips = bone_world(model, pose, tuple(leg[0] for leg in LEGS))
    middle = sum(dot(hips[leg[0]][0], side_axis(rig.forward)) for leg in LEGS) / len(LEGS)
    for leg in LEGS:
        position, rotation, _ = feet[leg[2]]
        lifted = smoothstep(PLANT_LOW * rig.leg, PLANT_HIGH * rig.leg, position[2] - rig.ground[leg[2]])
        target = add(add(position, mul(shift, lifted)), (0.0, 0.0, tuck))
        if gather >= 1e-7:
            target = gather_foot(rig, target, middle, gather)
        solve_leg(model, pose, leg, target, rotation, MIN_REACH * rig.leg)
        if gather >= 1e-7:
            gather_knee(model, pose, rig, leg, middle, gather)
        if point >= 1e-7:
            point_foot(model, pose, rig, leg, point)
