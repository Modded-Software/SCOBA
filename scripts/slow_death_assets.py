#!/usr/bin/env python3
"""Generate slow copies of death models.

A death model is one m3: hull meshes, particle emitters, ribbons, and lights
under one sequence. The engine time scale slows the sequence only. This copy
stretches the sequence and retimes the emitters and ribbons to match, so every
part of the death runs at the same slow rate.
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

MARKER = ".slow_death_assets"
MARKER_VERSION = "10\n"  # 10: Leviathan Stand 3x faster; 9: Leviathan tentacle simulation 40x slower; 8: Leviathan death like the BC; 7: Goliath death 2x slower; 6: Goliath 3x; 5: BC child stretch 12.5 (children 2x faster)

# (CASC entry, target in the map, time stretch, child stretch). Stretch 100
# is twice the earlier 50 (the old CModel AnimSpeed 0.02): every death runs
# 2x slower. The stretch sets the death length and when each child starts
# and stops, so the hull and the bursts stay in the original sync.
# The child stretch retimes only the particle and ribbon simulation inside
# each child; 12.5 runs it eight times as fast as the keyframes (2x the
# earlier 25).
SLOW_DEATHS = (
    (
        r"mods\liberty.sc2mod\base.sc2assets\assets\units\terran\battlecruiserlokideath\battlecruiserlokideath.m3",
        Path("Assets") / "Units" / "Terran" / "BattlecruiserLokiDeath" / "BattlecruiserLokiDeathSlow.m3",
        100,
        12.5,
    ),
    # Leviathan facing the MengskBC: the same timing as the BC death.
    (
        r"mods\liberty.sc2mod\base.sc2assets\assets\units\zerg\leviathandeath\leviathandeath.m3",
        Path("Assets") / "Units" / "Zerg" / "LeviathanDeath" / "LeviathanDeathSlow.m3",
        100,
        12.5,
    ),
    # Goliath: the whole death 2x slower, children included (operator
    # 2026-11-17; 3x was rejected).
    (
        r"mods\liberty.sc2mod\base.sc2assets\assets\units\terran\goliathdeath\goliathdeath.m3",
        Path("Assets") / "Units" / "Terran" / "GoliathDeath" / "GoliathDeathSlow.m3",
        2,
        2,
    ),
)

# (CASC entry, target in the map, simulation stretch). Keyframes keep their
# timing (the CModel AnimSpeed slows them); only the particle and ribbon
# simulation is retimed. LeviathanTentacle: AnimSpeed 0.025 = 1/40, so the
# ribbon physics (speed, gravity, drag, lifespan) runs 40x slower to match.
SLOW_SIMULATIONS = (
    (
        r"mods\liberty.sc2mod\base.sc2assets\assets\effects\zerg\leviathantentacle\leviathantentacle.m3",
        Path("Assets") / "Effects" / "Zerg" / "LeviathanTentacle" / "LeviathanTentacleSlow.m3",
        40,
    ),
)

# (CASC entry, target in the map, sequence names, speed-up). The named clips
# play `speed-up` times faster: their keyframes and length shrink by it. Other
# clips are untouched. Leviathan Stand (idle) 3x faster than the shared
# AnimSpeed 0.1 x actor 0.25 leaves it (operator 2026-11-17).
FAST_CLIPS = (
    (
        r"mods\liberty.sc2mod\base.sc2assets\assets\units\zerg\leviathan\leviathan.m3",
        Path("Assets") / "Units" / "Zerg" / "Leviathan" / "LeviathanSCOBA.m3",
        ("Stand",),
        3,
    ),
)

BLOCK_KINDS = ("sdev", "sd2v", "sd3v", "sd4q", "sdcc", "sdr3", "sds6", "sdu6", "sdu3", "sdfg", "sdmb")
SDR3_KIND = 5

# Field -> power of the stretch. Durations grow (+1). Speeds and rates
# shrink (-1). Accelerations shrink twice (-2).
PARTICLE_ANIMATED = {
    "emissionSpeed1": -1,
    "emissionSpeed2": -1,
    "lifespan1": 1,
    "lifespan2": 1,
    "emissionRate": -1,
    "trailingParticlesRate": -1,
}
PARTICLE_PLAIN = {
    "zAcceleration": -2,
    "drag": -1,
    "noiseFrequency": -1,
}
RIBBON_ANIMATED = {
    "speed": -1,
    "lifespan": 1,
}
RIBBON_PLAIN = {
    "gravity": -2,
    "drag": -1,
    "surfaceNoiseFrequency": -1,
}


# Build log only: keyed tracks retimed, per field.
KEYED: dict[str, int] = {}


def scaled(value: float, power: int, stretch: float) -> float:
    return float(value) * (float(stretch) ** power)


def stretch_sequences(model, stretch: int) -> None:
    for sequence in model.sequences:
        sequence.animStartInMS = int(sequence.animStartInMS) * stretch
        sequence.animEndInMS = int(sequence.animEndInMS) * stretch


def keyframe_blocks(stc) -> list:
    """The keyframe block lists of one clip, in BLOCK_KINDS order."""
    return [
        stc.sdev,
        stc.sd2v,
        stc.sd3v,
        stc.sd4q,
        stc.sdcc,
        stc.sdr3,
        stc.sds6,
        stc.sdu6,
        stc.sdu3,
        stc.sdfg,
        stc.sdmb,
    ]


def stretch_blocks(model, stretch: int) -> int:
    count = 0
    for stc in model.sequenceTransformationCollections:
        for blocks in keyframe_blocks(stc):
            for block in blocks:
                block.frames = [int(frame) * stretch for frame in block.frames]
                block.fend = int(block.fend) * stretch
                count += 1
    return count


def speed_up_clips(model, names: tuple[str, ...], factor: int) -> int:
    """Shrink the named sequences and their clips' key times by factor."""
    if factor < 1:
        raise ValueError("speed-up must be at least 1")
    found = set()
    for sequence in model.sequences:
        if str(sequence.name) in names:
            if int(sequence.animStartInMS) != 0:
                raise ValueError(f"{sequence.name} does not start at 0 ms")
            sequence.animEndInMS = round(int(sequence.animEndInMS) / factor)
            found.add(str(sequence.name))
    missing = set(names) - found
    if missing:
        raise ValueError(f"model lacks sequences {sorted(missing)}")
    count = 0
    for stc in model.sequenceTransformationCollections:
        clip = str(stc.name)
        if not any(clip == name or clip.startswith(name + "_") for name in names):
            continue
        for blocks in keyframe_blocks(stc):
            for block in blocks:
                frames = [round(int(frame) / factor) for frame in block.frames]
                if any(b <= a for a, b in zip(frames, frames[1:])):
                    raise ValueError(f"{clip}: keys merge at speed-up {factor}")
                block.frames = frames
                block.fend = round(int(block.fend) / factor)
                count += 1
    if count == 0:
        raise ValueError(f"no clip blocks for {sorted(names)}")
    return count


def scale_real_keys(model, anim_id: int, power: int, stretch: float) -> int:
    """Scale the float keys every clip holds for one animated property."""
    count = 0
    for stc in model.sequenceTransformationCollections:
        for target_id, anim_ref in zip(stc.animIds, stc.animRefs):
            if target_id != anim_id:
                continue
            kind = (anim_ref >> 16) & 0xFFFF
            if kind != SDR3_KIND:
                raise ValueError(f"animated float {anim_id:#x} has block kind {kind}, not sdr3")
            block = stc.sdr3[anim_ref & 0xFFFF]
            keys = []
            for key in block.keys:
                if isinstance(key, (int, float)):
                    keys.append(scaled(key, power, stretch))
                else:
                    key.value = scaled(key.value, power, stretch)
                    keys.append(key)
            block.keys = keys
            count += 1
    return count


def scale_reference(model, name: str, ref, power: int, stretch: float) -> None:
    """Scale one animated property: its base values and its keyed track."""
    ref.initValue = scaled(ref.initValue, power, stretch)
    ref.nullValue = scaled(ref.nullValue, power, stretch)
    KEYED[name] = KEYED.get(name, 0) + scale_real_keys(model, ref.header.animId, power, stretch)


def scale_particle(model, emitter, stretch: float) -> None:
    animated = PARTICLE_ANIMATED
    plain = PARTICLE_PLAIN
    scale_reference(model, "emissionSpeed1", emitter.emissionSpeed1, animated["emissionSpeed1"], stretch)
    scale_reference(model, "emissionSpeed2", emitter.emissionSpeed2, animated["emissionSpeed2"], stretch)
    scale_reference(model, "lifespan1", emitter.lifespan1, animated["lifespan1"], stretch)
    scale_reference(model, "lifespan2", emitter.lifespan2, animated["lifespan2"], stretch)
    scale_reference(model, "emissionRate", emitter.emissionRate, animated["emissionRate"], stretch)
    scale_reference(
        model, "trailingParticlesRate", emitter.trailingParticlesRate, animated["trailingParticlesRate"], stretch
    )
    emitter.zAcceleration = scaled(emitter.zAcceleration, plain["zAcceleration"], stretch)
    emitter.drag = scaled(emitter.drag, plain["drag"], stretch)
    emitter.noiseFrequency = scaled(emitter.noiseFrequency, plain["noiseFrequency"], stretch)


def scale_ribbon(model, ribbon, stretch: float) -> None:
    animated = RIBBON_ANIMATED
    plain = RIBBON_PLAIN
    scale_reference(model, "speed", ribbon.speed, animated["speed"], stretch)
    scale_reference(model, "lifespan", ribbon.lifespan, animated["lifespan"], stretch)
    ribbon.gravity = scaled(ribbon.gravity, plain["gravity"], stretch)
    ribbon.drag = scaled(ribbon.drag, plain["drag"], stretch)
    ribbon.surfaceNoiseFrequency = scaled(ribbon.surfaceNoiseFrequency, plain["surfaceNoiseFrequency"], stretch)


def retime_model(model, stretch: int, child_stretch: float | None = None) -> dict[str, int]:
    """Stretch the keyframes by stretch and the emitter simulation by child_stretch."""
    if child_stretch is None:
        child_stretch = stretch
    if stretch < 1 or child_stretch < 1:
        raise ValueError("stretch must be at least 1")
    stretch_sequences(model, stretch)
    blocks = stretch_blocks(model, stretch)
    try:
        for emitter in model.particles:
            scale_particle(model, emitter, child_stretch)
        for ribbon in model.ribbons:
            scale_ribbon(model, ribbon, child_stretch)
    except AttributeError as error:
        raise ValueError(f"model lacks a retime field: {error}") from error
    return {
        "sequences": len(model.sequences),
        "blocks": blocks,
        "particles": len(model.particles),
        "ribbons": len(model.ribbons),
        "lights": len(model.lights),
        "forces": len(model.forces),
        "bones": len(model.bones),
    }


def event_names(model) -> list[str]:
    names = []
    for stc in model.sequenceTransformationCollections:
        for block in stc.sdev:
            for key in block.keys:
                names.append(str(key.name))
    return names


def describe(model) -> str:
    lines = []
    for sequence in model.sequences:
        lines.append(
            f"  sequence {sequence.name}: {int(sequence.animStartInMS)}..{int(sequence.animEndInMS)} ms"
            f" flags={int(sequence.flags)}"
        )
    for index, emitter in enumerate(model.particles):
        lines.append(
            f"  particle {index}: bone={model.bones[emitter.boneIndex].name}"
            f" life={emitter.lifespan1.initValue:.3f}/{emitter.lifespan2.initValue:.3f}"
            f" rate={emitter.emissionRate.initValue:.3f}"
            f" speed={emitter.emissionSpeed1.initValue:.3f}/{emitter.emissionSpeed2.initValue:.3f}"
            f" zacc={emitter.zAcceleration:.3f} drag={emitter.drag:.3f}"
            f" burst={int(emitter.partEmit.initValue)} max={int(emitter.maxParticles)}"
        )
    for index, ribbon in enumerate(model.ribbons):
        lines.append(
            f"  ribbon {index}: bone={model.bones[ribbon.boneIndex].name}"
            f" life={ribbon.lifespan.initValue:.3f} speed={ribbon.speed.initValue:.3f}"
            f" gravity={ribbon.gravity:.3f} drag={ribbon.drag:.3f}"
        )
    lines.append(f"  events: {sorted(set(event_names(model)))}")
    return "\n".join(lines)


def generate_model(source: Path, target: Path, stretch: int, child_stretch: float) -> None:
    model = m3.loadModel(str(source))
    print(f"{target.name}: source")
    print(describe(model))
    counts = retime_model(model, stretch, child_stretch)
    print(f"{target.name}: stretch={stretch} child_stretch={child_stretch} {counts} keyed={KEYED}")
    print(describe(model))
    target.parent.mkdir(parents=True, exist_ok=True)
    m3.saveAndInvalidateModel(model, str(target))


def generate(root: Path, force: bool) -> None:
    marker = root / MARKER
    if marker.exists() and not force and marker.read_text() == MARKER_VERSION:
        return
    temp_root = Path(tempfile.mkdtemp(prefix="sco death ", dir=root.parent))
    try:
        for entry, target, stretch, child_stretch in SLOW_DEATHS:
            source = extract_model(entry, temp_root)
            generate_model(source, root / target, stretch, child_stretch)
        for entry, target, sim_stretch in SLOW_SIMULATIONS:
            source = extract_model(entry, temp_root)
            generate_model(source, root / target, 1, sim_stretch)
        for entry, target, names, factor in FAST_CLIPS:
            model = m3.loadModel(str(extract_model(entry, temp_root)))
            blocks = speed_up_clips(model, names, factor)
            print(f"{target.name}: {list(names)} x{factor} faster, blocks={blocks}")
            (root / target).parent.mkdir(parents=True, exist_ok=True)
            m3.saveAndInvalidateModel(model, str(root / target))
        marker.write_text(MARKER_VERSION)
    finally:
        if temp_root.exists():
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
