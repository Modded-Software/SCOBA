"""Walk direction clips: the legs turn as one body (R-TPS-18).

A walk direction clip is the walk clip with the legs turned about the pelvis
(character_anim_m3.make_lower_group turns the pelvis bone). On a rig whose
feet are keyed on bones outside the pelvis, those bones must make the same
turn, or the thighs turn and the feet keep walking forward (operator
2026-11-22, Kerrigan). `turn_leg_roots` gives them the pelvis turn; `check`
proves on a built model that every direction clip moves the legs rigidly.
"""

from __future__ import annotations

import copy
import math

from character_anim_m3 import axis_quaternion, quat_multiply
from jumpanim.kin import TRACK_LOC, TRACK_ROT, add, base_tracks, bone_world, clip_pose, conj, group_clip, mul, quat_tuple, rotate, sample_key, sub

RIGID_TOLERANCE = 0.01  # model units: joint distance change inside the legs
MIN_TURN_TRAVEL = 0.02  # model units: a turned foot must leave its forward path
CHECK_STEP_MS = 50


def ancestors(model, index: int) -> list[int]:
    out = []
    parent = model.bones[index].parent
    while parent >= 0:
        out.append(parent)
        parent = model.bones[parent].parent
    return out


def subtree(model, roots: tuple[str, ...]) -> list[str]:
    """The named bones and every bone below them."""
    names = {bone.name: index for index, bone in enumerate(model.bones)}
    keep = {names[root] for root in roots}
    return [bone.name for index, bone in enumerate(model.bones) if index in keep or keep & set(ancestors(model, index))]


def turn_leg_roots(model, stc, turn_bone: str, leg_roots: tuple[str, ...], degrees: float) -> None:
    """Give each leg root the turn the pelvis gets: `degrees` about the up
    axis of the pelvis' parent, through the pelvis. Call it before the pelvis
    bone itself is turned; both read the same untouched clip."""
    if degrees == 0.0 or not leg_roots:
        return
    names = {bone.name: index for index, bone in enumerate(model.bones)}
    turn_index = names[turn_bone]
    if model.bones[turn_index].parent < 0:
        raise ValueError(f"turn bone {turn_bone} has no parent")
    turn_parent = model.bones[model.bones[turn_index].parent].name
    turning = {turn_index} | {names[root] for root in leg_roots}
    tracks = base_tracks(stc)
    yaw = axis_quaternion("Z", degrees)
    poses: dict[int, dict] = {}

    def pose_at(ms: int) -> dict:
        if ms not in poses:
            poses[ms] = {
                anim_id: sample_key(list(block.frames), list(block.keys), ms, kind == TRACK_ROT)
                for anim_id, (kind, block) in tracks.items()
            }
        return poses[ms]

    turned = []
    for root in leg_roots:
        bone = model.bones[names[root]]
        if bone.parent < 0:
            raise ValueError(f"leg root {root} has no parent")
        if turning & set(ancestors(model, names[root])):
            raise ValueError(f"leg root {root} already hangs on a turned bone")
        parent = model.bones[bone.parent].name
        for kind, anim_id in ((TRACK_LOC, bone.location.header.animId), (TRACK_ROT, bone.rotation.header.animId)):
            if anim_id not in tracks or tracks[anim_id][0] != kind:
                raise ValueError(f"{stc.name}: leg root {root} has no {'location' if kind == TRACK_LOC else 'rotation'} track")
            block = tracks[anim_id][1]
            keys = []
            for ms, key in zip(block.frames, block.keys):
                world = bone_world(model, pose_at(int(ms)), (turn_bone, turn_parent, parent))
                pivot = world[turn_bone][0]
                frame = world[turn_parent][1]
                turn = quat_multiply(quat_multiply(frame, yaw), conj(frame))
                parent_pos, parent_rot, parent_scale = world[parent]
                out = copy.copy(key)
                if kind == TRACK_LOC:
                    at = add(parent_pos, mul(rotate(parent_rot, (float(key.x), float(key.y), float(key.z))), parent_scale))
                    moved = add(pivot, rotate(turn, sub(at, pivot)))
                    out.x, out.y, out.z = mul(rotate(conj(parent_rot), sub(moved, parent_pos)), 1.0 / parent_scale)
                else:
                    out.x, out.y, out.z, out.w = quat_multiply(conj(parent_rot), quat_multiply(turn, quat_multiply(parent_rot, quat_tuple(key))))
                keys.append(out)
            turned.append((block, keys))
    for block, keys in turned:
        block.keys = keys


def leg_turner(model, turn_bone: str, leg_roots: tuple[str, ...]):
    """The `leg_turn` hook of make_lower_group for a rig."""
    return lambda stc, degrees: turn_leg_roots(model, stc, turn_bone, leg_roots, degrees)


def joint_distances(model, clip: str, ms: float, bones: list[str]) -> list[float]:
    world = bone_world(model, clip_pose(model, clip, ms), bones)
    return [math.dist(world[a][0], world[b][0]) for i, a in enumerate(bones) for b in bones[i + 1 :]]


def check(model, label: str, turn_bone: str, leg_roots: tuple[str, ...], source: str, clips: list[tuple[str, float, bool]], fail) -> str:
    """Every direction clip keeps the legs rigid: the distance between any
    two leg bones is the walk clip's at the same stride time. A clip with a
    turn also moves the leg roots off their forward path (negative case: the
    feet do not stay where the forward walk has them)."""
    if not leg_roots:
        return f"{label}: the feet hang on the pelvis, no leg roots to turn"
    bones = subtree(model, (turn_bone,) + leg_roots)
    _, start, end, _ = group_clip(model, source)
    span = end - start
    worst = 0.0
    least = None
    for name, yaw, reverse in clips:
        travel = 0.0
        for ms in range(0, span, CHECK_STEP_MS):
            source_ms = (span - ms) if reverse else ms
            want = joint_distances(model, source, source_ms, bones)
            got = joint_distances(model, name, ms, bones)
            gap = max(abs(a - b) for a, b in zip(want, got))
            worst = max(worst, gap)
            if gap > RIGID_TOLERANCE:
                fail(f"{label} {name} at {ms} ms: the legs bend by {gap:.4f} (limit {RIGID_TOLERANCE}); a leg root does not turn with the pelvis")
            before = bone_world(model, clip_pose(model, source, source_ms), leg_roots)
            after = bone_world(model, clip_pose(model, name, ms), leg_roots)
            travel = max(travel, max(math.dist(before[root][0], after[root][0]) for root in leg_roots))
        if yaw != 0.0:
            least = travel if least is None else min(least, travel)
            if travel < MIN_TURN_TRAVEL:
                fail(f"{label} {name}: the leg roots stay on the forward walk path (moved {travel:.4f})")
    return f"{label}: {len(clips)} walk direction clips, legs rigid within {worst:.5f}/{RIGID_TOLERANCE}, turned feet move at least {least:.3f}"
