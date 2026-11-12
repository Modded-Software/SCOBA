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
from character_anim_m3 import clone, make_lower_group, make_pitch_group

ROOT = project_root()
M3_VENDOR = ROOT / "scripts" / "vendor" / "m3addon"
sys.path.insert(0, str(M3_VENDOR))

import m3

MARKER = ".character_anim_assets"
MARKER_VERSION = "17\n"
MODEL_DATA = Path("Base.SC2Data") / "GameData" / "ModelData.xml"
SOURCE_MODELS = {
    "tosh": (
        r"mods\liberty.sc2mod\base.sc2assets\assets\units\terran\tosh\tosh.m3",
        Path("Assets") / "Units" / "Terran" / "Tosh" / "ToshSCOBA.m3",
        "ToshSCOBA",
        "Assets\\Units\\Terran\\Tosh\\ToshSCOBA.m3",
        ("BoneSpine01",),
        ("BoneWaist", "Root", "Main"),
        "BoneWaist",
        3.1015,
        ("BoneSpine01",),
        (1.0,),
        "Y",
        1.0,
    ),
    "kerrigan": (
        r"mods\liberty.sc2mod\base.sc2assets\assets\units\zerg\kerrigan\kerrigan.m3",
        Path("Assets") / "Units" / "Zerg" / "Kerrigan" / "KerriganSCOBA.m3",
        "KerriganSCOBA",
        "Assets\\Units\\Zerg\\Kerrigan\\KerriganSCOBA.m3",
        ("Bone07",),
        ("Box01", "Bone34", "Bone34(mirrored)", "Root", "Bone_Link_Object"),
        "Box01",
        2.5,
        ("Bone07",),
        (1.0,),
        "Y",
        1.0,
    ),
}

CLIP_JOBS = (
    ("Attack", "Attack", "upper"),
    ("Spell", "Spell", "upper"),
    ("Stand Work", "Stand Work", "upper"),
    ("Attack", "Attack Ready", "upper"),
    ("Stand", "Stand Leg", "lower"),
    ("Walk", "Walk Leg", "lower"),
    ("Stand Left", "Stand Left Leg", "lower"),
    ("Stand Right", "Stand Right Leg", "lower"),
)

HOLD_CLIP_MS = {
    "Attack Ready": 1,
}

AIM_PITCH_GROUP = "Ready"
AIM_PITCH_SOURCE = "Attack"
AIM_PITCH_SOURCE_MS = 350
AIM_PITCH_MIN_DEG = -95.0
AIM_PITCH_MAX_DEG = 50.0
AIM_PITCH_TIME_MS = 10000
AIM_PITCH_SAMPLES = 601

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
        if name == "Walk Leg" and source_sequence.movementSpeed > 0.0 and unit_speed > 0.0:
            duration_ms = source_sequence.animEndInMS - source_sequence.animStartInMS
            scaled_ms = int(round(duration_ms * source_sequence.movementSpeed / (unit_speed * 100.0)))
            target_sequence.animEndInMS = target_sequence.animStartInMS + scaled_ms
        hold_ms = HOLD_CLIP_MS.get(name)
        if hold_ms is not None:
            target_sequence.animEndInMS = target_sequence.animStartInMS + hold_ms
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
    stc.priority = 10 if bone_group == "upper" else 0
    model.sequenceTransformationCollections.append(stc)
    stc_index = len(model.sequenceTransformationCollections) - 1
    group.stcIndices = [stc_index]
    return stc_index


def validate_model_names(model) -> None:
    for group in model.sequenceTransformationGroups:
        validate_animation_name(group.name)



def generate_model(
    source: Path,
    target: Path,
    upper_roots: tuple[str, ...],
    lower_roots: tuple[str, ...],
    turn_bone: str,
    unit_speed: float,
    pitch_bones: tuple[str, ...],
    pitch_weights: tuple[float, ...],
    pitch_axis: str,
    pitch_sign: float,
) -> None:
    model = m3.loadModel(str(source))
    upper_ids, lower_ids = classify_bones(model, upper_roots, lower_roots)
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
        group_ids = upper_ids if bone_group == "upper" else lower_ids
        make_clip(model, group, source_clip, group_ids, new_name, bone_group, unit_speed)
    turn_anim_id = next(bone.rotation.header.animId for bone in model.bones if bone.name == turn_bone)
    make_lower_group(model, groups, "Attack Stand", "Stand Leg", 0.0, False, turn_anim_id)
    for direction_name, yaw, reverse in AIM_DIRECTIONS:
        make_lower_group(
            model,
            groups,
            "Attack Walk " + direction_name,
            "Walk Leg",
            yaw,
            reverse,
            turn_anim_id,
        )
    make_pitch_group(
        model,
        groups,
        AIM_PITCH_GROUP,
        AIM_PITCH_SOURCE,
        AIM_PITCH_SOURCE_MS,
        pitch_bones,
        pitch_weights,
        pitch_axis,
        pitch_sign,
        AIM_PITCH_MIN_DEG,
        AIM_PITCH_MAX_DEG,
        AIM_PITCH_TIME_MS,
        AIM_PITCH_SAMPLES,
    )
    print(f"{target.name}: upper={len(upper_ids)} lower={len(lower_ids)}")
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
    for data in SOURCE_MODELS.values():
        (root / data[1]).unlink(missing_ok=True)
    marker = root / MARKER
    marker.unlink(missing_ok=True)
    path = root / MODEL_DATA
    text = path.read_text()
    for model_id, _ in ((data[2], data[3]) for data in SOURCE_MODELS.values()):
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
        for (
            entry,
            target,
            model_id,
            model_value,
            upper_roots,
            lower_roots,
            turn_bone,
            unit_speed,
            pitch_bones,
            pitch_weights,
            pitch_axis,
            pitch_sign,
        ) in SOURCE_MODELS.values():
            source = extract_model(entry, temp_root)
            generate_model(
                source,
                root / target,
                upper_roots,
                lower_roots,
                turn_bone,
                unit_speed,
                pitch_bones,
                pitch_weights,
                pitch_axis,
                pitch_sign,
            )
            entries.append((model_id, model_value))
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
