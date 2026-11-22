"""Aim pose breathing (R-TPS-19, operator 2026-11-22).

The aim pose is one frame of a source clip, with the torso pitched to the
camera. A still pose looks frozen. A rig with `breath_frames` gets a looping
pose instead: the source frame swings `breath_frames` frames to each side of
the pose frame on a sine, once per `breath_ms`. Every pitch step is one such
clip; all have the same length, so the script can keep the phase when the
pitch step changes (gf_AnimAimBreathSync).
"""

from __future__ import annotations

import math

from animation_tokens import validate_animation_name
from character_anim_m3 import append_stc, axis_quaternion, clone, freeze_block, quat_multiply, sample_block
from heroanim.rig import FRAME_MS
from jumpanim.kin import sample_key

BREATH_SAMPLES = 16  # keys per breath; the engine blends between them
SAME = 1e-6


def loop_times(period_ms: int) -> list[int]:
    """Key times of one breath; the last key repeats the first (a loop)."""
    return [round(step * period_ms / BREATH_SAMPLES) for step in range(BREATH_SAMPLES + 1)]


def source_ms(center_ms: float, frames: int, step: int) -> float:
    """The source clip time shown at a loop key: a sine about the pose frame."""
    return center_ms + frames * FRAME_MS * math.sin(2.0 * math.pi * (step % BREATH_SAMPLES) / BREATH_SAMPLES)


def key_values(key, is_quat: bool) -> tuple[float, ...]:
    values = (float(key.x), float(key.y), float(key.z))
    return values + (float(key.w),) if is_quat else values


def breathe_block(block, center_ms: float, frames: int, period_ms: int, is_quat: bool) -> bool:
    """One track as one breath. A track that does not move inside the swing
    keeps two equal keys. Returns whether the track moves."""
    if not block.keys:
        return False
    times, keys = list(block.frames), list(block.keys)
    loop = [sample_key(times, keys, source_ms(center_ms, frames, step), is_quat) for step in range(BREATH_SAMPLES)]
    loop.append(clone(loop[0]))
    start = key_values(loop[0], is_quat)
    moves = any(max(abs(a - b) for a, b in zip(key_values(key, is_quat), start)) > SAME for key in loop)
    if moves:
        block.frames, block.keys = loop_times(period_ms), loop
    else:
        block.frames, block.keys = [0, period_ms], [loop[0], loop[-1]]
    block.fend = period_ms
    block.flags = 0
    return moves


def make_breath_pitch_group(model, groups, name, upper_name, upper_source, center_ms, pitch_bones, pitch_weights, pitch_axis, pitch_sign, degrees, frames, period_ms, priority=11) -> int:
    """One pitch step as a breathing loop (character_anim_m3.make_pitch_group
    makes the still one). Returns the number of tracks that move."""
    validate_animation_name(name)
    if len(pitch_bones) != len(pitch_weights):
        raise ValueError("pitch bone and weight counts differ")
    if frames <= 0 or period_ms <= 0:
        raise ValueError(f"breath needs frames and a period, got {frames} and {period_ms}")
    source = next(item for item in model.sequences if item.name == upper_name)
    swing = frames * FRAME_MS
    if center_ms - swing < 0.0 or center_ms + swing > source.animEndInMS - source.animStartInMS:
        raise ValueError(f"breath swing {center_ms - swing:.0f}..{center_ms + swing:.0f} ms leaves the clip {upper_name}")
    stc = clone(upper_source)
    stc.name = name + " Upper"
    # Only the tracks the clip plays breathe; the blocks it does not
    # reference stay still, as in the still pose.
    used = {(ref >> 16) & 0xFFFF: set() for ref in stc.animRefs}
    for ref in stc.animRefs:
        used[(ref >> 16) & 0xFFFF].add(ref & 0xFFFF)
    moving = 0
    for kind, blocks, is_quat in ((2, stc.sd3v, False), (3, stc.sd4q, True)):
        for index, block in enumerate(blocks):
            if index in used.get(kind, ()):
                moving += breathe_block(block, center_ms, frames, period_ms, is_quat)
            else:
                sample_block(block, center_ms)
                freeze_block(block, period_ms)
    # The other track kinds (colors, floats, flags, bounds) hold the pose.
    for blocks in (stc.sdcc, stc.sdr3, stc.sds6, stc.sdu6, stc.sdu3, stc.sdfg, stc.sdmb):
        for block in blocks:
            sample_block(block, center_ms)
            freeze_block(block, period_ms)
    stc.sdev = []
    bones = {bone.name: bone for bone in model.bones}
    for bone_name, weight in zip(pitch_bones, pitch_weights):
        anim_id = bones[bone_name].rotation.header.animId
        if anim_id not in stc.animIds:
            raise ValueError(f"pitch bone {bone_name} is missing from {upper_name}")
        anim_ref = stc.animRefs[stc.animIds.index(anim_id)]
        if (anim_ref >> 16) & 0xFFFF != 3:
            raise ValueError(f"pitch bone {bone_name} has no rotation track")
        pitch = axis_quaternion(pitch_axis, pitch_sign * degrees * weight)
        for key in stc.sd4q[anim_ref & 0xFFFF].keys:
            key.x, key.y, key.z, key.w = quat_multiply((float(key.x), float(key.y), float(key.z), float(key.w)), pitch)
    group = clone(groups[upper_name])
    group.name = name
    group.stcIndices = [append_stc(model, stc, priority)]
    model.sequenceTransformationGroups.append(group)
    groups[name] = group
    sequence = clone(source)
    sequence.name = name
    sequence.animStartInMS = 0
    sequence.animEndInMS = period_ms
    sequence.movementSpeed = 0.0
    sequence.frequency = 100
    sequence.flags = 0
    model.sequences.append(sequence)
    return moving
