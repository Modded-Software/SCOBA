"""M3 clone and splitbody helpers for generated hero models."""

from __future__ import annotations

import copy
import math
import sys
from pathlib import Path

from animation_tokens import validate_animation_name

ROOT_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_HERE / "vendor" / "m3addon"))

import m3


def clone_key(value):
    return copy.copy(value)


def clone_block(value):
    result = copy.copy(value)
    result.frames = list(value.frames)
    result.keys = [clone_key(key) for key in value.keys]
    return result


def clone_stc(value):
    result = copy.copy(value)
    result.animIds = list(value.animIds)
    result.animRefs = list(value.animRefs)
    result.sdev = [clone_block(block) for block in value.sdev]
    result.sd2v = [clone_block(block) for block in value.sd2v]
    result.sd3v = [clone_block(block) for block in value.sd3v]
    result.sd4q = [clone_block(block) for block in value.sd4q]
    result.sdcc = [clone_block(block) for block in value.sdcc]
    result.sdr3 = [clone_block(block) for block in value.sdr3]
    result.unknownRef8 = list(value.unknownRef8)
    result.sds6 = [clone_block(block) for block in value.sds6]
    result.sdu6 = [clone_block(block) for block in value.sdu6]
    result.unknownRef11 = list(value.unknownRef11)
    result.sdu3 = [clone_block(block) for block in value.sdu3]
    result.sdfg = [clone_block(block) for block in value.sdfg]
    result.sdmb = [clone_block(block) for block in value.sdmb]
    return result


def clone_sequence(value):
    result = copy.copy(value)
    result.boundingSphere = copy.copy(value.boundingSphere)
    result.unknownRefSEQSBeta01 = list(value.unknownRefSEQSBeta01)
    return result


def clone_sts(value):
    result = copy.copy(value)
    result.animIds = list(value.animIds)
    return result


def clone_group(value):
    result = copy.copy(value)
    result.stcIndices = list(value.stcIndices)
    return result


def clone(value):
    if isinstance(value, list):
        return [clone(item) for item in value]
    if isinstance(value, (int, float, str, bool)):
        return value
    name = value.structureDescription.structureName
    if name == "SEQS":
        return clone_sequence(value)
    if name == "STC_":
        return clone_stc(value)
    if name == "STS_":
        return clone_sts(value)
    if name == "STG_":
        return clone_group(value)
    if name in ("SDEV", "SD2V", "SD3V", "SD4Q", "SDCC", "SDR3", "SDS6", "SDU6", "SDU3", "SDFG", "SDMB"):
        return clone_block(value)
    if name == "EVNT":
        return clone_key(value)
    if isinstance(value, m3.M3Structure):
        return copy.copy(value)
    if isinstance(value, bytearray):
        return bytearray(value)
    return value


BLOCK_KINDS = ("sdev", "sd2v", "sd3v", "sd4q", "sdcc", "sdr3", "sds6", "sdu6", "sdu3", "sdfg")


def freeze_block(block, hold_ms=0):
    keys = list(block.keys)
    if not keys:
        return
    if hold_ms > 0:
        block.frames = [0, hold_ms]
        block.keys = [clone(keys[0]), clone(keys[0])]
        block.fend = hold_ms
    else:
        block.frames = [0]
        block.keys = [clone(keys[0])]
        block.fend = 0
    block.flags = 0


def quat_multiply(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    )


def rotate_block_yaw(block, degrees):
    radians = math.radians(degrees)
    yaw = (0.0, 0.0, math.sin(radians / 2.0), math.cos(radians / 2.0))
    for key in block.keys:
        q = (float(key.x), float(key.y), float(key.z), float(key.w))
        rx, ry, rz, rw = quat_multiply(yaw, q)
        key.x = rx
        key.y = ry
        key.z = rz
        key.w = rw


def rotate_lower_root(stc, anim_id, degrees):
    if degrees == 0.0:
        return
    for target_id, anim_ref in zip(stc.animIds, stc.animRefs):
        if target_id != anim_id:
            continue
        if (anim_ref >> 16) & 0xFFFF != 3:
            continue
        rotate_block_yaw(stc.sd4q[anim_ref & 0xFFFF], degrees)


def reverse_block(block):
    keys = list(block.keys)
    frames = list(block.frames)
    if len(keys) < 2 or len(frames) < 2:
        return
    last = frames[-1]
    block.frames = [last - frame for frame in reversed(frames)]
    block.keys = list(reversed(keys))


def reverse_lower(stc):
    for block in stc.sd3v:
        reverse_block(block)
    for block in stc.sd4q:
        reverse_block(block)
    for block in stc.sdcc:
        reverse_block(block)
    for block in stc.sdr3:
        reverse_block(block)
    for block in stc.sds6:
        reverse_block(block)
    for block in stc.sdu6:
        reverse_block(block)
    for block in stc.sdu3:
        reverse_block(block)
    for block in stc.sdfg:
        reverse_block(block)


def sample_block(block, sample_ms):
    if not block.keys:
        return
    frames = list(block.frames)
    index = 0
    for i, frame in enumerate(frames):
        if frame <= sample_ms:
            index = i
        else:
            break
    key = clone(block.keys[index])
    block.frames = [0]
    block.keys = [key]
    block.fend = 0
    block.flags = 0


def sample_upper(stc, sample_ms):
    if sample_ms <= 0:
        return
    for block in stc.sd3v:
        sample_block(block, sample_ms)
    for block in stc.sd4q:
        sample_block(block, sample_ms)
    for block in stc.sdcc:
        sample_block(block, sample_ms)
    for block in stc.sdr3:
        sample_block(block, sample_ms)
    for block in stc.sds6:
        sample_block(block, sample_ms)
    for block in stc.sdu6:
        sample_block(block, sample_ms)
    for block in stc.sdu3:
        sample_block(block, sample_ms)
    for block in stc.sdfg:
        sample_block(block, sample_ms)
    for block in stc.sdmb:
        sample_block(block, sample_ms)
    stc.sdev = []


def freeze_upper(stc, hold_ms=0):
    for block in stc.sd3v:
        freeze_block(block, hold_ms)
    for block in stc.sd4q:
        freeze_block(block, hold_ms)
    for block in stc.sdcc:
        freeze_block(block, hold_ms)
    for block in stc.sdr3:
        freeze_block(block, hold_ms)
    for block in stc.sds6:
        freeze_block(block, hold_ms)
    for block in stc.sdu6:
        freeze_block(block, hold_ms)
    for block in stc.sdu3:
        freeze_block(block, hold_ms)
    for block in stc.sdfg:
        freeze_block(block, hold_ms)
    for block in stc.sdmb:
        freeze_block(block, hold_ms)
    stc.sdev = []


def append_stc(model, stc, priority):
    sts = clone(model.sts[stc.stsIndex])
    sts.animIds = list(stc.animIds)
    model.sts.append(sts)
    sts_index = len(model.sts) - 1
    stc.stsIndex = sts_index
    stc.stsIndexCopy = sts_index
    stc.runsConcurrent = 1
    stc.priority = priority
    model.sequenceTransformationCollections.append(stc)
    return len(model.sequenceTransformationCollections) - 1


def make_lower_group(model, groups, name, lower_name, yaw, reverse, turn_anim_id):
    validate_animation_name(name)
    lower_group = groups[lower_name]
    lower_source = model.sequenceTransformationCollections[lower_group.stcIndices[0]]

    lower_stc = clone(lower_source)
    lower_stc.name = name + " Lower"
    if reverse:
        reverse_lower(lower_stc)
    rotate_lower_root(lower_stc, turn_anim_id, yaw)
    lower_index = append_stc(model, lower_stc, 0)

    group = clone(lower_group)
    group.name = name
    group.stcIndices = [lower_index]
    model.sequenceTransformationGroups.append(group)
    groups[name] = group

    sequences = {sequence.name: sequence for sequence in model.sequences}
    target_sequence = clone(sequences[lower_name])
    target_sequence.name = name
    model.sequences.append(target_sequence)


def axis_quaternion(axis: str, degrees: float):
    radians = math.radians(degrees)
    half = radians / 2.0
    sin = math.sin(half)
    cos = math.cos(half)
    if axis == "X":
        return (sin, 0.0, 0.0, cos)
    if axis == "Y":
        return (0.0, sin, 0.0, cos)
    if axis == "Z":
        return (0.0, 0.0, sin, cos)
    raise ValueError(f"unsupported pitch axis {axis!r}")


def make_pitch_group(
    model,
    groups,
    name,
    upper_name,
    source_ms,
    pitch_bones,
    pitch_weights,
    pitch_axis,
    pitch_sign,
    min_degrees,
    max_degrees,
    duration_ms,
    samples,
):
    validate_animation_name(name)
    if len(pitch_bones) != len(pitch_weights):
        raise ValueError("pitch bone and weight counts differ")
    if samples < 2:
        raise ValueError("pitch sample count must be at least two")
    upper_group = groups[upper_name]
    upper_source = model.sequenceTransformationCollections[upper_group.stcIndices[0]]

    upper_stc = clone(upper_source)
    upper_stc.name = name + " Upper"
    sample_upper(upper_stc, source_ms)
    freeze_upper(upper_stc, duration_ms)

    bones = {bone.name: bone for bone in model.bones}
    for bone_name, weight in zip(pitch_bones, pitch_weights):
        bone = bones.get(bone_name)
        if bone is None:
            raise KeyError(bone_name)
        anim_id = bone.rotation.header.animId
        if anim_id not in upper_stc.animIds:
            raise ValueError(f"pitch bone {bone_name} is missing from {upper_name}")
        anim_index = upper_stc.animIds.index(anim_id)
        anim_ref = upper_stc.animRefs[anim_index]
        if (anim_ref >> 16) & 0xFFFF != 3:
            raise ValueError(f"pitch bone {bone_name} has no rotation track")
        block = upper_stc.sd4q[anim_ref & 0xFFFF]
        flags = block.flags
        if not block.keys:
            raise ValueError(f"pitch bone {bone_name} has an empty rotation track")
        base = clone(block.keys[0])
        base_q = (float(base.x), float(base.y), float(base.z), float(base.w))
        frames = []
        keys = []
        for sample in range(samples):
            t = sample / (samples - 1)
            angle = pitch_sign * (min_degrees + ((max_degrees - min_degrees) * t)) * weight
            pitch = axis_quaternion(pitch_axis, angle)
            qx, qy, qz, qw = quat_multiply(base_q, pitch)
            key = clone(base)
            key.x = qx
            key.y = qy
            key.z = qz
            key.w = qw
            frames.append(int(round(t * duration_ms)))
            keys.append(key)
        block.frames = frames
        block.keys = keys
        block.fend = duration_ms
        block.flags = flags

    upper_index = append_stc(model, upper_stc, 11)
    group = clone(upper_group)
    group.name = name
    group.stcIndices = [upper_index]
    model.sequenceTransformationGroups.append(group)
    groups[name] = group

    sequences = {sequence.name: sequence for sequence in model.sequences}
    target_sequence = clone(sequences[upper_name])
    target_sequence.name = name
    target_sequence.animStartInMS = 0
    target_sequence.animEndInMS = duration_ms
    target_sequence.movementSpeed = 0.0
    target_sequence.frequency = 100
    target_sequence.flags = 0
    model.sequences.append(target_sequence)

