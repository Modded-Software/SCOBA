#!/usr/bin/env python3
"""Generate split-body hero model assets."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from project_root import project_root
from animation_tokens import validate_animation_name
from jumpanim.bake import JUMP_HEROES, make_jump_groups
from walkanim.slow import LEG as SLOW_LEG, SLOW_HEROES, SOURCE as SLOW_SOURCE, make_slow_arms, make_slow_groups
from walkanim.strafe import leg_turner
from character_anim_m3 import add_kickback, axis_quaternion, clone, make_lower_group, make_pitch_group, quat_multiply
from heroanim.breath import make_breath_pitch_group
from heroanim.rig import HEROES, HeroRig, pitch_axis, shared_pitch_axis, yaw_axis

ROOT = project_root()
M3_VENDOR = ROOT / "scripts" / "vendor" / "m3addon"
sys.path.insert(0, str(M3_VENDOR))

import m3

MARKER = ".character_anim_assets"
MARKER_VERSION = "50\n"  # 50: the swing clip moves her back talons; 49: Kerrigan talons swing clip from Attack 01; 48: rigs in heroanim.rig, torso pitch axis from the rest pose, feet turn with the pelvis, aim pose breathing; 47: head pitch about the head's own left-right axis; 46: head pitch +-30 (R-TPS-16); 45: slow walk arm clips (R-SLOW-19); 44: slow walk leg clips from Walk Slow (R-SLOW-10, 11); 43: stand jump legs together at the apogee, walk plays on slowly in the air; 42: jump knee and ankle angles from motion capture; 41: jump poses from the hero's own stand and walk, two strides (R-JUMP-16, 18)
MODEL_DATA = Path("Base.SC2Data") / "GameData" / "ModelData.xml"
CLIP_JOBS = (
    ("Attack", "Attack Arm Alternate", "upper"),
    ("Spell", "Spell Arm Alternate", "upper"),
    ("Stand", "Stand Leg", "lower"),
    ("Walk", "Walk Leg", "lower"),
    ("Stand Left", "Stand Left Leg", "lower"),
    ("Stand Right", "Stand Right Leg", "lower"),
)

# The melee swing (rig.melee_source): spine up, legs left to the leg clips.
MELEE_CLIP = "Attack Arm Alternate Close"

AIM_ATTACK_JOBS = (
    ("Attack", "Attack Arm Alternate 01"),
    ("Spell", "Spell Arm Alternate 01"),
)

AIM_PITCH_GROUP = "Ready Alternate"
AIM_PITCH_SOURCE_MS = 350
AIM_PITCH_MIN_DEG = -95.0
AIM_PITCH_MAX_DEG = 50.0
AIM_PITCH_FRAME_MS = 100
AIM_PITCH_STEPS = 99

AIM_DIRECTIONS = (
    ("Forward", 0.0, False),
    ("Forward Left", 45.0, False),
    ("Left", 65.0, False),
    ("Back Left", -45.0, True),
    ("Back", 0.0, True),
    ("Back Right", 45.0, True),
    ("Right", -65.0, False),
    ("Forward Right", -45.0, False),
)


def bone_anim_ids(bone) -> list[int]:
    return [
        bone.location.header.animId,
        bone.rotation.header.animId,
        bone.scale.header.animId,
    ]


def bone_chain(model, name: str) -> str:
    """The bone and its parents, for the build log."""
    names = {bone.name: index for index, bone in enumerate(model.bones)}
    index = names[name]
    chain = []
    while index >= 0 and len(chain) < 8:
        chain.append(model.bones[index].name)
        index = model.bones[index].parent
    return ">".join(chain)


# Head look (R-TPS-13, 16): static head-only clips on a pitch x yaw grid.
# Group number = (yaw step - 1) * HEAD_TILT_STEPS + pitch step. They sit above
# every upper-body clip, so the head owns its bone while aiming and attacking.
HEAD_TILT_GROUP = "Ready Cover"
HEAD_TILT_SOURCE = "Stand"
HEAD_TILT_MAX_DEG = 30.0  # operator 2026-11-21 (was 15)
HEAD_TILT_STEPS = 9
HEAD_YAW_MAX_DEG = 25.0
HEAD_YAW_STEPS = 11
HEAD_TILT_FRAME_MS = 100
HEAD_TILT_PRIORITY = 14


def make_head_groups(model, groups, head: str) -> str:
    """One head-only clip per pitch x yaw step, from the stand pose."""
    if not any(bone.name == head for bone in model.bones):
        raise KeyError(f"head bone {head} not in the model")
    # Both axes come from the rest pose (heroanim.rig): the head's own.
    turn_axis, yaw_sign = yaw_axis(model, head)
    nod_axis, pitch_sign = pitch_axis(model, head)
    if turn_axis == nod_axis:
        raise ValueError(f"head {head}: yaw axis {turn_axis} equals the pitch axis")
    print(f"head {head}: pitch {nod_axis} {pitch_sign:+.0f}, yaw {turn_axis} {yaw_sign:+.0f}")
    head_id = next(bone.rotation.header.animId for bone in model.bones if bone.name == head)
    stand_source = model.sequenceTransformationCollections[groups[HEAD_TILT_SOURCE].stcIndices[0]]
    pairs = [pair for pair in zip(stand_source.animIds, stand_source.animRefs) if pair[0] == head_id]
    if not pairs:
        raise ValueError(f"{HEAD_TILT_SOURCE} does not animate the head bone {head}")
    head_source = clone(stand_source)
    head_source.animIds = [pair[0] for pair in pairs]
    head_source.animRefs = [pair[1] for pair in pairs]
    for yaw_step in range(HEAD_YAW_STEPS):
        yaw = HEAD_YAW_MAX_DEG * ((2.0 * yaw_step / (HEAD_YAW_STEPS - 1)) - 1.0)
        for step in range(HEAD_TILT_STEPS):
            angle = HEAD_TILT_MAX_DEG * ((2.0 * step / (HEAD_TILT_STEPS - 1)) - 1.0)
            name = f"{HEAD_TILT_GROUP} {yaw_step * HEAD_TILT_STEPS + step + 1:02d}"
            # Built level, then each key gets the yaw and the pitch, in that order.
            make_pitch_group(
                model,
                groups,
                name,
                HEAD_TILT_SOURCE,
                head_source,
                0,
                (head,),
                (1.0,),
                nod_axis,
                pitch_sign,
                0.0,
                0.0,
                HEAD_TILT_FRAME_MS,
                2,
                HEAD_TILT_PRIORITY,
            )
            stc = model.sequenceTransformationCollections[groups[name].stcIndices[0]]
            look = quat_multiply(axis_quaternion(turn_axis, yaw_sign * yaw), axis_quaternion(nod_axis, pitch_sign * angle))
            for anim_id, anim_ref in zip(stc.animIds, stc.animRefs):
                if anim_id != head_id or (anim_ref >> 16) & 0xFFFF != 3:
                    continue
                for key in stc.sd4q[anim_ref & 0xFFFF].keys:
                    key.x, key.y, key.z, key.w = quat_multiply((float(key.x), float(key.y), float(key.z), float(key.w)), look)
    return head


def classify_bones(model, upper_roots: tuple[str, ...], lower_roots: tuple[str, ...]) -> tuple[set[int], set[int]]:
    names = [bone.name for bone in model.bones]
    upper_names = set(upper_roots)
    lower_names = set(lower_roots)
    groups = {}
    for index, name in enumerate(names):
        if name in upper_names:
            groups[index] = "upper"
        elif name in lower_names:
            groups[index] = "lower"
    for index in range(len(names)):
        if index in groups:
            continue
        parent = model.bones[index].parent
        seen = set()
        while parent >= 0 and parent not in seen:
            seen.add(parent)
            if parent in groups:
                groups[index] = groups[parent]
                break
            parent = model.bones[parent].parent
        if index not in groups:
            groups[index] = "lower"
    upper_ids: set[int] = set()
    lower_ids: set[int] = set()
    for index, bone in enumerate(model.bones):
        target = upper_ids if groups.get(index) == "upper" else lower_ids
        target.update(bone_anim_ids(bone))
    return upper_ids, lower_ids





def make_clip(model, group, source_index: int, group_ids: set[int], name: str, bone_group: str, unit_speed: float) -> int:
    validate_animation_name(name)
    source = model.sequenceTransformationCollections[source_index]
    sequences = {sequence.name: sequence for sequence in model.sequences}
    source_sequence = sequences.get(source.name.replace("_full", ""))
    target_sequence = sequences.get(name)
    if target_sequence is None and source_sequence is not None:
        target_sequence = clone(source_sequence)
        target_sequence.name = name
        model.sequences.append(target_sequence)
    if source_sequence is not None and target_sequence is not None:
        target_sequence.animStartInMS = source_sequence.animStartInMS
        target_sequence.animEndInMS = source_sequence.animEndInMS
        target_sequence.movementSpeed = source_sequence.movementSpeed
        target_sequence.frequency = source_sequence.frequency
        target_sequence.flags = source_sequence.flags
    stc = clone(source)
    debug_filter = os.environ.get("SCOBA_ANIM_UNFILTERED", "")
    if debug_filter in {"all", bone_group}:
        pairs = list(zip(source.animIds, source.animRefs))
    else:
        pairs = [(anim_id, anim_ref) for anim_id, anim_ref in zip(source.animIds, source.animRefs) if anim_id in group_ids]
    if not pairs:
        raise ValueError(f"clip {source.name} has no ids for {name}")
    anim_ids = [pair[0] for pair in pairs]
    anim_refs = [pair[1] for pair in pairs]
    sts = clone(model.sts[source.stsIndex])
    sts.animIds = list(anim_ids)
    model.sts.append(sts)
    sts_index = len(model.sts) - 1
    stc.name = name
    stc.animIds = anim_ids
    stc.animRefs = anim_refs
    stc.stsIndex = sts_index
    stc.stsIndexCopy = sts_index
    if bone_group == "upper_aim":
        stc.priority = 12
    else:
        stc.priority = 10 if bone_group == "upper" else 0
    stc.runsConcurrent = 1
    model.sequenceTransformationCollections.append(stc)
    stc_index = len(model.sequenceTransformationCollections) - 1
    group.stcIndices = [stc_index]
    return stc_index


def validate_model_names(model) -> None:
    for group in model.sequenceTransformationGroups:
        validate_animation_name(group.name)



def generate_model(source: Path, target: Path, rig: HeroRig, jump: bool = False, slow: bool = False) -> None:
    """jump: add the jump leg clips (jumpanim.bake); slow: the slow walk legs (walkanim.slow)."""
    model = m3.loadModel(str(source))
    upper_ids, lower_ids = classify_bones(model, rig.upper_roots, rig.lower_roots)
    attack_ids, _ = classify_bones(model, rig.attack_roots, rig.lower_roots)
    groups = {group.name: group for group in model.sequenceTransformationGroups}
    validate_model_names(model)
    
    clips = {stc.name.replace("_full", ""): index for index, stc in enumerate(model.sequenceTransformationCollections)}
    for source_name, new_name, bone_group in CLIP_JOBS:
        group = groups.get(new_name)
        source_clip = clips.get(source_name)
        if group is None:
            source_group = groups.get(source_name)
            if source_group is None or source_clip is None:
                raise KeyError(new_name)
            group = clone(source_group)
            group.name = new_name
            model.sequenceTransformationGroups.append(group)
            groups[new_name] = group
        if source_clip is None:
            raise KeyError(new_name)
        group_ids = attack_ids if bone_group == "upper" else lower_ids
        make_clip(model, group, source_clip, group_ids, new_name, bone_group, rig.unit_speed)
    if rig.melee_source:
        if rig.melee_source not in groups or rig.melee_source not in clips:
            raise KeyError(rig.melee_source)
        group = clone(groups[rig.melee_source])
        group.name = MELEE_CLIP
        model.sequenceTransformationGroups.append(group)
        groups[MELEE_CLIP] = group
        melee_lower = tuple(root for root in rig.lower_roots if root not in rig.melee_roots)
        melee_ids, _ = classify_bones(model, rig.upper_roots + rig.melee_roots, melee_lower)
        make_clip(model, group, clips[rig.melee_source], melee_ids, MELEE_CLIP, "upper", rig.unit_speed)
    pitch_ids = set()
    for bone in model.bones:
        if bone.name in rig.pitch_bones:
            pitch_ids.update(bone_anim_ids(bone))
    aim_attack_ids = attack_ids - pitch_ids
    for source_name, new_name in AIM_ATTACK_JOBS:
        source_group = groups.get(source_name)
        source_clip = clips.get(source_name)
        if source_group is None or source_clip is None:
            raise KeyError(new_name)
        group = clone(source_group)
        group.name = new_name
        model.sequenceTransformationGroups.append(group)
        groups[new_name] = group
        stc_index = make_clip(model, group, source_clip, aim_attack_ids, new_name, "upper_aim", rig.unit_speed)
        add_kickback(model, model.sequenceTransformationCollections[stc_index], rig.kick_bones, rig.kick_axis, rig.kick_sign, rig.kick_degrees, 350, 500)
    turn_anim_id = next(bone.rotation.header.animId for bone in model.bones if bone.name == rig.turn_bone)
    # Feet keyed outside the pelvis turn with it (walkanim.strafe).
    leg_turn = leg_turner(model, rig.turn_bone, rig.leg_roots)
    make_lower_group(model, groups, "Attack Stand", "Stand Leg", 0.0, False, turn_anim_id)
    make_lower_group(model, groups, "Attack Stand Left", "Stand Left Leg", 0.0, False, turn_anim_id)
    make_lower_group(model, groups, "Attack Stand Right", "Stand Right Leg", 0.0, False, turn_anim_id)
    for direction_name, yaw, reverse in AIM_DIRECTIONS:
        make_lower_group(model, groups, "Attack Walk " + direction_name, "Walk Leg", yaw, reverse, turn_anim_id, leg_turn)
    # A walk clip shorter than the stock walk cuts the stride and hitches on every loop.
    lengths = {sequence.name: sequence.animEndInMS - sequence.animStartInMS for sequence in model.sequences}
    for direction_name, _, _ in AIM_DIRECTIONS:
        if lengths["Attack Walk " + direction_name] != lengths["Walk"]:
            raise ValueError(f"Attack Walk {direction_name} length differs from Walk")
    slow_log = "slow: none"
    if slow:
        group = clone(groups[SLOW_SOURCE])
        group.name = SLOW_LEG
        model.sequenceTransformationGroups.append(group)
        groups[SLOW_LEG] = group
        make_clip(model, group, clips[SLOW_SOURCE], lower_ids, SLOW_LEG, "lower", rig.unit_speed)
        slow_log = make_slow_groups(model, groups, AIM_DIRECTIONS, turn_anim_id, leg_turn)
        slow_log += ", " + make_slow_arms(model, groups, make_clip, clips[SLOW_SOURCE], upper_ids, rig.unit_speed)
    # The aim pose: one frame of the rig's aim source clip, upper body only.
    attack_source = model.sequenceTransformationCollections[groups[rig.aim_source].stcIndices[0]]
    pitch_source = clone(attack_source)
    pitch_pairs = [
        (anim_id, anim_ref)
        for anim_id, anim_ref in zip(attack_source.animIds, attack_source.animRefs)
        if anim_id in upper_ids
    ]
    pitch_source.animIds = [pair[0] for pair in pitch_pairs]
    pitch_source.animRefs = [pair[1] for pair in pitch_pairs]
    # The torso nods about its own left-right axis, read from the rest pose.
    nod_axis, nod_sign = shared_pitch_axis(model, rig.pitch_bones)
    breath_log = "breath: none"
    for step in range(AIM_PITCH_STEPS):
        t = step / (AIM_PITCH_STEPS - 1)
        angle = AIM_PITCH_MIN_DEG + (AIM_PITCH_MAX_DEG - AIM_PITCH_MIN_DEG) * t
        name = f"{AIM_PITCH_GROUP} {step + 1:02d}"
        if rig.breath_frames > 0:
            moving = make_breath_pitch_group(model, groups, name, rig.aim_pose_clip, pitch_source, AIM_PITCH_SOURCE_MS, rig.pitch_bones, rig.pitch_weights, nod_axis, nod_sign, angle, rig.breath_frames, rig.breath_ms)
            breath_log = f"breath: +-{rig.breath_frames} frames, {rig.breath_ms} ms, {moving} tracks move"
        else:
            make_pitch_group(model, groups, name, rig.aim_pose_clip, pitch_source, AIM_PITCH_SOURCE_MS, rig.pitch_bones, rig.pitch_weights, nod_axis, nod_sign, angle, angle, AIM_PITCH_FRAME_MS, 2)
    print(f"torso {rig.pitch_bones}: pitch {nod_axis} {nod_sign:+.0f}, legs turn {rig.turn_bone} + {rig.leg_roots}, aim pose {rig.aim_source} at {AIM_PITCH_SOURCE_MS} ms, {breath_log}")
    head = make_head_groups(model, groups, rig.head_bone)
    jump_log = "jump: none"
    if jump:
        jump_log = make_jump_groups(model, groups)
    print(f"{target.name}: upper={len(upper_ids)} lower={len(lower_ids)} head={bone_chain(model, head)} {jump_log} {slow_log}")
    target.parent.mkdir(parents=True, exist_ok=True)
    m3.saveAndInvalidateModel(model, str(target))


def extract_model(entry: str, temp_root: Path) -> Path:
    command = [
        sys.executable,
        str(ROOT / "scripts" / "sc2res.py"),
        "extract",
        entry,
        "--out",
        str(temp_root / "extract"),
        "--exact",
    ]
    subprocess.run(command, check=True, cwd=ROOT)
    expected = temp_root / "extract" / Path(entry.replace("\\", "/"))
    if expected.is_file():
        return expected
    matches = list((temp_root / "extract").rglob(Path(entry.replace("\\", "/")).name))
    if len(matches) != 1:
        raise FileNotFoundError(entry)
    return matches[0]


def model_data_text(root: Path, entries: list[tuple[str, str]]) -> str:
    path = root / MODEL_DATA
    text = path.read_text()
    for model_id, value in entries:
        if f'<CModel id="{model_id}">' in text:
            continue
        block = (
            f'    <CModel id="{model_id}">\n'
            f'        <Model value="{value}"/>\n'
            f'    </CModel>\n'
        )
        text = text.replace("</Catalog>", block + "</Catalog>")
    return text


def revert(root: Path) -> None:
    for rig in HEROES.values():
        (root / rig.target).unlink(missing_ok=True)
    marker = root / MARKER
    marker.unlink(missing_ok=True)
    path = root / MODEL_DATA
    text = path.read_text()
    for model_id in (rig.model_id for rig in HEROES.values()):
        start = text.find(f'    <CModel id="{model_id}">')
        if start < 0:
            continue
        end = text.find("    </CModel>", start)
        if end < 0:
            continue
        end += len("    </CModel>\n")
        text = text[:start] + text[end:]
    path.write_text(text)


def generate(root: Path, force: bool) -> None:
    marker = root / MARKER
    if marker.exists() and not force and marker.read_text() == MARKER_VERSION:
        return
    temp_root = Path(tempfile.mkdtemp(prefix="sco anim ", dir=root.parent))
    try:
        entries = []
        for key, rig in HEROES.items():
            generate_model(extract_model(rig.entry, temp_root), root / rig.target, rig, jump=key in JUMP_HEROES, slow=key in SLOW_HEROES)
            entries.append((rig.model_id, rig.model_value))
        (root / MODEL_DATA).write_text(model_data_text(root, entries))
        marker.write_text(MARKER_VERSION)
    finally:
        if temp_root.exists():
            shutil.rmtree(temp_root)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--map", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--revert", action="store_true")
    args = parser.parse_args()
    root = args.map.resolve()
    if args.revert:
        revert(root)
        return 0
    generate(root, args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
