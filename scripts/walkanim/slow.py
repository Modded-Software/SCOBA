"""Slow walk leg clips on Alt (REQ-SLOW-WALK R-SLOW-10..12, 15, 18).

The bake turns `Walk Slow Leg` (the stock `Walk Slow` on the lower bones,
made by character_anim_assets CLIP_JOBS) into one clip per walk direction,
the same way the aim walk clips come from `Walk Leg`. The check reads the
built model and the map script: clip set, lengths, lower bones only, the
stride speed and the foot phase the script constants assume."""

from __future__ import annotations

import math
import re

from character_anim_m3 import append_stc, clone, make_lower_group, reverse_lower
from jumpanim.kin import FEET, clip_pose, foot_positions, group_clip

SLOW_HEROES = ("tosh",)
SOURCE = "Walk Slow"
LEG = "Walk Slow Leg"
PREFIX = "Attack Walk Slow "
WALK = "Walk Leg"
ARM = "Walk Slow Arm"
ARM_BACK = "Walk Slow Arm Back"
ARM_PRIORITY = 10  # as the other upper clips (make_clip "upper")
ARM_RE = re.compile(r'gf_AnimConfigUpper\(lp_profile, c_ANIM_UPPER_WALK_SLOW(?:_BACK)?, "(Walk,Slow,Arm[A-Za-z,]*)"')
# Engine walk calibration: the stock walk at clip rate 1 covers
# WalkAnimMoveSpeed game units/s (ActorData `ToshSCOBAUnit`).
WALK_ANIM_MOVE_SPEED = 3.0
STEP_MS = 10
STRIDE_TOLERANCE = 0.02  # part of the stride speed
PHASE_TOLERANCE = 0.02  # part of the walk cycle
CONST_RE = re.compile(r"const fixed (c_ANIM_SLOW_\w+) = (-?[0-9.]+);")
CLIP_RE = re.compile(r'gf_AnimConfigAimDir\(lp_profile, lp_state, (c_ANIM_DIR_\w+), "(Attack,Walk,Slow,[A-Za-z,]+)"\)')


def make_slow_groups(model, groups, directions, turn_anim_id, leg_turn=None) -> str:
    """Directional slow leg clips from `Walk Slow Leg` (R-SLOW-11, 12)."""
    for direction, yaw, reverse in directions:
        make_lower_group(model, groups, PREFIX + direction, LEG, yaw, reverse, turn_anim_id, leg_turn)
    lengths = {sequence.name: sequence.animEndInMS - sequence.animStartInMS for sequence in model.sequences}
    for name in [LEG] + [PREFIX + direction for direction, _, _ in directions]:
        if lengths[name] != lengths[SOURCE]:
            raise ValueError(f"{name} length {lengths[name]} differs from {SOURCE} {lengths[SOURCE]}")
    return f"slow: {len(directions) + 1} clips, {lengths[SOURCE]} ms"


def make_slow_arms(model, groups, make_clip, source_clip: int, arm_ids: set[int], unit_speed: float) -> str:
    """Upper-body slow walk (R-SLOW-19): `Walk Slow` on the attack bones, and
    the same played in reverse for the reversed (back) leg clips."""
    group = clone(groups[SOURCE])
    group.name = ARM
    model.sequenceTransformationGroups.append(group)
    groups[ARM] = group
    arm_index = make_clip(model, group, source_clip, arm_ids, ARM, "upper", unit_speed)
    back = clone(model.sequenceTransformationCollections[arm_index])
    back.name = ARM_BACK
    reverse_lower(back)
    back_group = clone(group)
    back_group.name = ARM_BACK
    back_group.stcIndices = [append_stc(model, back, ARM_PRIORITY)]
    model.sequenceTransformationGroups.append(back_group)
    groups[ARM_BACK] = back_group
    sequences = {sequence.name: sequence for sequence in model.sequences}
    back_sequence = clone(sequences[ARM])
    back_sequence.name = ARM_BACK
    model.sequences.append(back_sequence)
    return f"arms: {ARM}, {ARM_BACK}"


def planted_speed(model, name: str) -> float:
    """Median ground speed of the lower foot, model units/s."""
    _, start, end, _ = group_clip(model, name)
    rows = [foot_positions(model, clip_pose(model, name, ms)) for ms in range(0, end - start + 1, STEP_MS)]
    speeds = []
    for a, b in zip(rows, rows[1:]):
        low = min(FEET, key=lambda foot: a[foot][2])
        speeds.append(math.hypot(b[low][0] - a[low][0], b[low][1] - a[low][1]) / (STEP_MS / 1000.0))
    speeds.sort()
    return speeds[len(speeds) // 2]


def left_lead_phase(model, name: str) -> float:
    """Walk phase (0..1) where the left foot is furthest ahead (model forward is -Y)."""
    _, start, end, _ = group_clip(model, name)
    span = end - start
    best = max(range(0, span, 5), key=lambda ms: lead(model, name, ms))
    return best / span


def lead(model, name: str, ms: int) -> float:
    feet = foot_positions(model, clip_pose(model, name, ms))
    return feet["BoneFootR"][1] - feet["BoneFootL"][1]


def stride_speed(model) -> float:
    """Game units/s the slow clip covers at rate 1 (R-SLOW-15)."""
    return WALK_ANIM_MOVE_SPEED * planted_speed(model, LEG) / planted_speed(model, WALK)


def phase_gap(a: float, b: float) -> float:
    gap = abs(a - b) % 1.0
    return min(gap, 1.0 - gap)


def check_slow(model, galaxy: str, directions, upper_bones: set[str], fail) -> list[str]:
    """The baked slow clips and the script constants agree (R-SLOW-10..12, 15, 18)."""
    groups = {group.name: group for group in model.sequenceTransformationGroups}
    lengths = {sequence.name: sequence.animEndInMS - sequence.animStartInMS for sequence in model.sequences}
    owner = {}
    for bone in model.bones:
        for track in (bone.location, bone.rotation, bone.scale):
            owner[track.header.animId] = bone.name
    names = [LEG] + [PREFIX + direction for direction, _, _ in directions]
    for name in names:
        if name not in groups:
            fail(f"slow walk clip {name!r} is missing")
        if lengths.get(name) != lengths[SOURCE]:
            fail(f"slow walk clip {name} length {lengths.get(name)} differs from {SOURCE} {lengths[SOURCE]}")
        stc = model.sequenceTransformationCollections[groups[name].stcIndices[0]]
        bad = sorted({owner.get(anim_id, "?") for anim_id in stc.animIds} & upper_bones)
        if bad:
            fail(f"slow walk clip {name} animates non-leg bones: {bad}")
    consts = {name: float(value) for name, value in CONST_RE.findall(galaxy)}
    stride = stride_speed(model)
    script_stride = consts.get("c_ANIM_SLOW_STRIDE", -1.0)
    if abs(script_stride - stride) > STRIDE_TOLERANCE * stride:
        fail(f"c_ANIM_SLOW_STRIDE {script_stride} differs from the baked stride {stride:.4f}")
    offset = left_lead_phase(model, LEG) - left_lead_phase(model, WALK)
    script_offset = consts.get("c_ANIM_SLOW_GAIT_OFFSET", -9.0)
    if phase_gap(script_offset, offset) > PHASE_TOLERANCE:
        fail(f"c_ANIM_SLOW_GAIT_OFFSET {script_offset} differs from the foot phase offset {offset:.3f}")
    clips = sorted(clip.replace(",", " ") for _, clip in CLIP_RE.findall(galaxy))
    if clips != sorted(names[1:]):
        fail(f"script slow clips {clips} differ from the baked clips")
    # R-SLOW-19: the arm clips, upper bones only, the length of the legs.
    for name in (ARM, ARM_BACK):
        if name not in groups:
            fail(f"slow walk arm clip {name!r} is missing")
        if lengths.get(name) != lengths[SOURCE]:
            fail(f"slow walk arm clip {name} length {lengths.get(name)} differs from {SOURCE} {lengths[SOURCE]}")
        stc = model.sequenceTransformationCollections[groups[name].stcIndices[0]]
        legs = sorted({owner.get(anim_id, "?") for anim_id in stc.animIds} - upper_bones)
        if legs:
            fail(f"slow walk arm clip {name} animates non-upper bones: {legs}")
        if stc.priority != ARM_PRIORITY:
            fail(f"slow walk arm clip {name} priority {stc.priority}, want {ARM_PRIORITY}")
    arms = sorted(clip.replace(",", " ") for clip in ARM_RE.findall(galaxy))
    if arms != sorted((ARM, ARM_BACK)):
        fail(f"script slow arm clips {arms} differ from the baked clips")
    return [
        f"{len(names)} leg clips, {lengths[SOURCE]} ms, lower bones only; arms {ARM}, {ARM_BACK}, upper bones only",
        f"stride {stride:.4f} game units/s (script {script_stride}, +-{STRIDE_TOLERANCE * 100:.0f}%)",
        f"foot phase offset {offset:.3f} (script {script_offset}, +-{PHASE_TOLERANCE})",
    ]
