"""Jump leg clips from a hero's own source clip (REQ-JUMP R-JUMP-15, 23).

Kerrigan's model has no leg bones for the IK bake (jumpanim.bake). Her
jump takes the legs of her own `Burrow 01` (operator 2026-11-23): she leaps,
lands, then dives into the ground. Only the leap is used: the clip is cut at
the first moment after the apex where her lowest foot is back at its height
in the first frame (`cut_ms`). The clip's own rise of the body is removed:
the jump script alone sets the height ("just the legs").

The clip names are the ones jumpanim.bake makes for Tosh, so the script picks
them the same way (core/jump.galaxy, systems/jump.galaxy):

- the source time follows the jump: frame 0 through the takeoff crouch, the
  leap from liftoff to touchdown (`source_ms`), the cut frame after it;
- stand jump: the source pose as it is; End eases it back to the stand;
- walk jump: per bone, the walk (stride and phase as in jumpanim.bake) mixed
  with the source pose turned to the walk direction, at `WALK_WEIGHT`. The
  mix eases in over the crouch, from the walk, and out over End, to the walk.
"""

from __future__ import annotations

import copy
from typing import NamedTuple

from animation_tokens import validate_animation_name
from character_anim_m3 import append_stc, clone, rotate_lower_root

from jumpanim.bake import (
    AIR,
    CROUCH_MS,
    END,
    JUMP_BASES,
    START,
    TOUCHDOWN_MS,
    baked_name,
    base_time,
    clip_plan,
)
from jumpanim.kin import (
    TRACK_LOC,
    TRACK_ROT,
    AnimKey,
    base_ms,
    base_tracks,
    bone_world,
    clip_pose,
    group_clip,
    lerp_key,
    sample_key,
    sample_times,
    smoothstep,
)


class DonorJump(NamedTuple):
    source: str               # model clip the legs come from
    lift_bone: str            # the body bone whose rise is removed
    feet: tuple[str, ...]     # bones that touch the ground


# Heroes whose jump comes from a source clip (keys of heroanim.rig.HEROES).
DONOR_HEROES = {
    "kerrigan": DonorJump("Burrow 01", "Root", ("Bone04", "Bone05", "Bone04(mirrored)", "Bone05(mirrored)")),
}
# Walk jump: share of the source pose in the per-bone mix (operator
# 2026-11-23: a weighted blend; 0.5 was the proposed default).
WALK_WEIGHT = 0.5
# End: the legs ease back to the base over this part of the clip (operator
# 2026-11-23: back to stand or walk faster; was the whole 250 ms).
END_EASE_MS = 125
CUT_STEP_MS = 1


def lowest_foot(model, clip: str, ms: float, feet: tuple[str, ...]) -> float:
    world = bone_world(model, clip_pose(model, clip, ms), feet)
    return min(world[name][0][2] for name in feet)


def cut_ms(model, donor: DonorJump) -> int:
    """First ms after the apex (highest lift bone) at which the lowest foot is
    back at its first frame height."""
    _, start, end, _ = group_clip(model, donor.source)
    span = end - start
    ground = lowest_foot(model, donor.source, 0, donor.feet)
    apex = max(range(0, span + 1, 10), key=lambda ms: bone_world(model, clip_pose(model, donor.source, ms), (donor.lift_bone,))[donor.lift_bone][0][2])
    for ms in range(apex, span + 1, CUT_STEP_MS):
        if lowest_foot(model, donor.source, ms, donor.feet) <= ground:
            return ms
    raise ValueError(f"{donor.source}: the feet never come back to the ground after the apex at {apex} ms")


def jump_ms(phase, ms: float) -> float:
    """ms since the press under a Start or Air clip at ms (End: after touchdown)."""
    return ms + (START.length_ms if phase is AIR else 0)


def source_ms(phase, ms: float, cut: int) -> float:
    """Time in the source clip under a jump clip at ms."""
    if phase is END:
        return float(cut)
    flight = (jump_ms(phase, ms) - CROUCH_MS) / (TOUCHDOWN_MS - CROUCH_MS)
    return cut * min(1.0, max(0.0, flight))


def source_weight(phase, ms: float, base_weight: float) -> float:
    """Share of the source pose: eased in over the crouch, out over End."""
    if phase is START:
        return base_weight * smoothstep(0.0, CROUCH_MS, ms)
    if phase is END:
        return base_weight * (1.0 - smoothstep(0.0, END_EASE_MS, ms))
    return base_weight


def mix_pose(base: dict, source: dict, kinds: dict, weight: float) -> dict:
    """Per-track blend: location linear, rotation on the short arc."""
    return {anim_id: lerp_key(base[anim_id], source[anim_id], weight, kinds[anim_id] == TRACK_ROT) for anim_id in kinds}


def top_location(model, donor: DonorJump) -> int:
    """Location track of the lift bone's top ancestor (model space). The
    legs of this rig hang beside the body under that bone, so moving it
    moves the body and the legs together."""
    index = next(i for i, bone in enumerate(model.bones) if bone.name == donor.lift_bone)
    while model.bones[index].parent >= 0:
        index = model.bones[index].parent
    return model.bones[index].location.header.animId


def body_height(model, donor: DonorJump, pose: dict) -> float:
    return bone_world(model, pose, (donor.lift_bone,))[donor.lift_bone][0][2]


def remove_lift(pose: dict, top_id: int, rise: float) -> None:
    """Moves the whole rig down by rise (model up)."""
    key = copy.copy(pose[top_id])
    key.z = float(key.z) - rise
    pose[top_id] = key


def init_keys(model) -> dict[int, tuple[int, AnimKey]]:
    """anim id -> (kind, rest key) for every bone location, rotation and
    scale (scale keys are VEC3 blocks, as locations)."""
    out = {}
    for bone in model.bones:
        out[bone.location.header.animId] = (TRACK_LOC, bone.location.initValue)
        out[bone.scale.header.animId] = (TRACK_LOC, bone.scale.initValue)
        out[bone.rotation.header.animId] = (TRACK_ROT, bone.rotation.initValue)
    return out


def sample_stc(stc, ms: float, start: int, end: int, looping: bool, rest: dict, ids) -> dict:
    tracks = base_tracks(stc)
    at = base_ms(start, end, ms, looping)
    pose = {}
    for anim_id in ids:
        if anim_id in tracks:
            kind, block = tracks[anim_id]
            pose[anim_id] = sample_key(list(block.frames), list(block.keys), at, kind == TRACK_ROT)
        else:
            pose[anim_id] = copy.copy(rest[anim_id][1])
    return pose


def source_lower(model, groups, donor: DonorJump, lower_ids: set[int]):
    """The source clip on the lower bones only."""
    stc = clone(model.sequenceTransformationCollections[groups[donor.source].stcIndices[0]])
    pairs = [(anim_id, ref) for anim_id, ref in zip(stc.animIds, stc.animRefs) if anim_id in lower_ids and (ref >> 16) & 0xFFFF in (TRACK_LOC, TRACK_ROT)]
    if not pairs:
        raise ValueError(f"{donor.source} has no lower-body tracks")
    stc.animIds = [pair[0] for pair in pairs]
    stc.animRefs = [pair[1] for pair in pairs]
    return stc


def turned_source(stc, yaw: float, turn_anim_id: int, leg_turn):
    """The source turned to a walk direction, as make_lower_group turns a walk."""
    out = clone(stc)
    if yaw != 0.0:
        if leg_turn is not None:
            leg_turn(out, yaw)
        rotate_lower_root(out, turn_anim_id, yaw)
    return out


def write_clip(model, groups, name: str, template_group: str, template_stc, kinds: dict, blocks: dict, keys: dict, length_ms: int, looping: bool) -> int:
    validate_animation_name(name)
    times = sample_times(length_ms)
    stc = clone(template_stc)
    # Empty every key block list of the copy; the clip fills sd3v and sd4q.
    stc.sdev = []
    stc.sd2v = []
    stc.sd3v = []
    stc.sd4q = []
    stc.sdcc = []
    stc.sdr3 = []
    stc.sds6 = []
    stc.sdu6 = []
    stc.sdu3 = []
    stc.sdfg = []
    stc.sdmb = []
    stc.name = name
    stc.animIds = []
    stc.animRefs = []
    for anim_id in sorted(kinds):
        kind = kinds[anim_id]
        target = clone(blocks[anim_id])
        target.frames = list(times)
        target.keys = keys[anim_id]
        target.fend = length_ms
        target_list = stc.sd3v if kind == TRACK_LOC else stc.sd4q
        target_list.append(target)
        stc.animIds.append(anim_id)
        stc.animRefs.append((kind << 16) | (len(target_list) - 1))
    stc_index = append_stc(model, stc, 0)
    group = clone(groups[template_group])
    group.name = name
    group.stcIndices = [stc_index]
    model.sequenceTransformationGroups.append(group)
    groups[name] = group
    sequences = {sequence.name: sequence for sequence in model.sequences}
    sequence = clone(sequences[template_group])
    sequence.name = name
    sequence.animStartInMS = 0
    sequence.animEndInMS = length_ms
    sequence.movementSpeed = 0.0
    sequence.frequency = 100
    sequence.flags = 0 if looping else 1
    model.sequences.append(sequence)
    return len(stc.animIds)


def any_block(stcs, anim_id: int, kind: int):
    for stc in stcs:
        entry = base_tracks(stc).get(anim_id)
        if entry is not None and entry[0] == kind:
            return entry[1]
    raise ValueError(f"no {kind} key block for anim id {anim_id}")


def make_donor_groups(model, groups, donor: DonorJump, lower_ids: set[int], directions, turn_anim_id: int, leg_turn) -> str:
    """Adds every jump clip of jumpanim.bake.clip_plan. Returns a build log line."""
    cut = cut_ms(model, donor)
    _, src_start, src_end, _ = group_clip(model, donor.source)
    lower = source_lower(model, groups, donor, lower_ids)
    yaws = {"Walk " + name: yaw for name, yaw, _ in directions}
    if sorted(yaws) != sorted(base.token for base in JUMP_BASES if base.walk):
        raise ValueError("walk directions differ from the jump walk bases")
    rest = init_keys(model)
    top_id = top_location(model, donor)
    all_ids = set(base_tracks(lower)) | {top_id}
    rise0 = body_height(model, donor, sample_stc(lower, 0, src_start, src_end, False, rest, all_ids))
    turned = {token: turned_source(lower, yaw, turn_anim_id, leg_turn) for token, yaw in yaws.items()}
    counts = set()
    for phase, base, stride in clip_plan():
        name = baked_name(phase, base, stride)
        base_stc, start, end, looping = group_clip(model, base.group)
        source = turned[base.token] if base.walk else lower
        ids = {anim_id for anim_id in set(base_tracks(base_stc)) | set(base_tracks(source)) | {top_id} if anim_id in rest}
        kinds = {anim_id: rest[anim_id][0] for anim_id in ids}
        blocks = {anim_id: any_block((source, base_stc), anim_id, kinds[anim_id]) for anim_id in ids}
        weight = WALK_WEIGHT if base.walk else 1.0
        keys: dict[int, list] = {anim_id: [] for anim_id in ids}
        for ms in sample_times(phase.length_ms):
            at = source_ms(phase, ms, cut)
            pose_src = sample_stc(source, at, src_start, src_end, False, rest, ids)
            remove_lift(pose_src, top_id, body_height(model, donor, pose_src) - rise0)
            pose_base = sample_stc(base_stc, base_time(phase, base, stride, ms, end - start), start, end, looping, rest, ids)
            pose = mix_pose(pose_base, pose_src, kinds, source_weight(phase, ms, weight))
            for anim_id in ids:
                keys[anim_id].append(pose[anim_id])
        counts.add(write_clip(model, groups, name, base.group, base_stc, kinds, blocks, keys, phase.length_ms, phase.looping))
    return f"jump: {len(clip_plan())} clips from {donor.source} 0-{cut} ms, body rise removed, walk weight {WALK_WEIGHT}, tracks {sorted(counts)}"


__all__ = [
    "CUT_STEP_MS",
    "DONOR_HEROES",
    "END_EASE_MS",
    "WALK_WEIGHT",
    "DonorJump",
    "cut_ms",
    "jump_ms",
    "lowest_foot",
    "make_donor_groups",
    "mix_pose",
    "remove_lift",
    "source_ms",
    "source_weight",
]
