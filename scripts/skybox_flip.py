#!/usr/bin/env python3
"""Generate sky models turned 180 degrees about the model y axis.

Operator 2026-11-16: the sky is flipped so south becomes north.
GameSetBackground takes no rotation and the skybox CModel has none, so the
map ships a turned copy of the stock model. Every root bone (no parent) is
turned about AXIS through the model origin: its rotation is premultiplied
by the half turn and its position is turned with it (about y: x and z
negated), in the base values and in every keyframe.
Child bones, meshes, and bind poses stay as they are and follow the root.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

from character_anim_assets import extract_model
from project_root import project_root

ROOT = project_root()
sys.path.insert(0, str(ROOT / "scripts" / "vendor" / "m3addon"))

import m3

MARKER = ".skybox_flip"
MARKER_VERSION = "2\n"  # 2: y axis (1 was z)
EXTRACT_ROOT = Path("/mnt/ws-fast/sc2res/tmp")  # operator: extract into ws-fast

# (CASC entry, target in the map). The CModel ids live in src ModelData.xml.
FLIPS = (
    (
        r"mods\liberty.sc2mod\base.sc2assets\assets\skyboxes\aiurskybox\aiurskybox.m3",
        Path("Assets") / "Skyboxes" / "AiurSkyboxFlipped" / "AiurSkyboxFlipped.m3",
    ),
)

SD3V_KIND = 2  # vec3 keys (BLOCK_KINDS order in slow_death_assets)
SD4Q_KIND = 3  # quaternion keys


# Operator 2026-11-16: a turn about z flipped the wrong way; the turn is about y.
AXIS = (0.0, 1.0, 0.0)


def half_turn_quat(x: float, y: float, z: float, w: float, axis: tuple[float, float, float] = AXIS) -> tuple[float, float, float, float]:
    """(axis, 0) * q: q followed by a 180 degree turn about the unit axis."""
    ax, ay, az = axis
    cx = ay * z - az * y
    cy = az * x - ax * z
    cz = ax * y - ay * x
    return (w * ax + cx, w * ay + cy, w * az + cz, -(ax * x + ay * y + az * z))


def half_turn_vec(x: float, y: float, z: float, axis: tuple[float, float, float] = AXIS) -> tuple[float, float, float]:
    """v turned 180 degrees about the unit axis: 2 (a.v) a - v."""
    ax, ay, az = axis
    d = 2.0 * (ax * x + ay * y + az * z)
    return (d * ax - x, d * ay - y, d * az - z)


def turn_quat(value) -> None:
    value.x, value.y, value.z, value.w = half_turn_quat(float(value.x), float(value.y), float(value.z), float(value.w))


def turn_vec(value) -> None:
    value.x, value.y, value.z = half_turn_vec(float(value.x), float(value.y), float(value.z))


def keyed_blocks(model, anim_id: int, kind: int) -> list:
    blocks = []
    for stc in model.sequenceTransformationCollections:
        for target_id, anim_ref in zip(stc.animIds, stc.animRefs):
            if target_id != anim_id:
                continue
            found = (anim_ref >> 16) & 0xFFFF
            if found != kind:
                raise ValueError(f"track {anim_id:#x} has block kind {found}, not {kind}")
            blocks.append((stc.sd3v if kind == SD3V_KIND else stc.sd4q)[anim_ref & 0xFFFF])
    return blocks


def flip_model(model) -> dict[str, int]:
    counts = {"roots": 0, "rotation_keys": 0, "location_keys": 0}
    for bone in model.bones:
        if bone.parent != -1:
            continue
        counts["roots"] += 1
        turn_quat(bone.rotation.initValue)
        turn_quat(bone.rotation.nullValue)
        turn_vec(bone.location.initValue)
        turn_vec(bone.location.nullValue)
        for block in keyed_blocks(model, bone.rotation.header.animId, SD4Q_KIND):
            for key in block.keys:
                turn_quat(key)
                counts["rotation_keys"] += 1
        for block in keyed_blocks(model, bone.location.header.animId, SD3V_KIND):
            for key in block.keys:
                turn_vec(key)
                counts["location_keys"] += 1
    if counts["roots"] == 0:
        raise ValueError("model has no root bone")
    return counts


def generate_model(source: Path, target: Path) -> None:
    model = m3.loadModel(str(source))
    counts = flip_model(model)
    print(f"{target.name}: flipped {counts}")
    target.parent.mkdir(parents=True, exist_ok=True)
    m3.saveAndInvalidateModel(model, str(target))


def generate(root: Path, force: bool) -> None:
    marker = root / MARKER
    if marker.exists() and not force and marker.read_text() == MARKER_VERSION:
        return
    EXTRACT_ROOT.mkdir(parents=True, exist_ok=True)
    temp_root = Path(tempfile.mkdtemp(prefix="skyflip-", dir=EXTRACT_ROOT))
    try:
        for entry, target in FLIPS:
            source = extract_model(entry, temp_root)
            generate_model(source, root / target)
        marker.write_text(MARKER_VERSION)
    finally:
        shutil.rmtree(temp_root)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--map", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    generate(args.map.resolve(), args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
