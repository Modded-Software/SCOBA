"""Hero pod Birth path (SPEC-HERO-DROP 3). Single source for the map and the host tests.

The stock Terran pod falls in its model's Birth clip: the root bone Dummy19
(no parent, so its keys are model space) moves on linear keys from high and
to the side down to the pod's origin. No Galaxy getter reads a bone, so the
script replays those keys to put the camera on the drawn pod.

World offset of the root from the pod unit, t ms after Birth starts:
    scale x Rz(facing + MODEL_YAW) x key(t)
MODEL_YAW 90: model -y is the unit's facing (hit_volumes, checked in game by
the tps `pick` group). Scale: the SCOBADropPodArt actor Scale.

Writes src/SCOBA.SC2Map/scripts/app/data/pod_birth.galaxy. The build
validator checks that the file equals this output.

Run from scripts/: uv run python -m hitvolumes.pod_birth [--check | --extract]
"""

from __future__ import annotations

import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

DATA_FILE = Path("scripts") / "app" / "data" / "pod_birth.galaxy"
ACTORS = Path("Base.SC2Data") / "GameData" / "ActorData.xml"
MODEL = Path("/mnt/ws-fast/sc2res/pod/mods/liberty.sc2mod/base.sc2assets/assets/effects/terran/droppodfalling/droppodfalling.m3")
CLIP = "Birth"
ROOT_BONE = "Dummy19"
MODEL_YAW = 90.0
# Not mirrored: MODEL_X -1 turned the path ~92 deg off the drawn pod
# (operator view, podbirth/20261117-115552).
MODEL_X = 1.0
ACTOR_SCALE = 4.5

# Dummy19 location keys in Birth (ms, x, y, z), model units, from MODEL
# (--extract). The two keys at 0 ms are one key. Linear interpolation
# (m3 interpolationType 1).
KEYS: tuple[tuple[int, float, float, float], ...] = (
    (0, -9.8702, 9.4498, 19.0215),
    (1600, -0.5977, 0.5727, 1.1443),
    (2200, 0.0005, 0.0, -0.0091),
    (2333, 0.0005, -0.0325, -0.0614),
    (2533, 0.0005, 0.0, 0.0095),
    (2833, 0.0005, 0.0, -0.0091),
)
# Touchdown: the key where the root first reaches the ground.
LAND_MS = 2200
# Birth length (sequence end, ms). The engine's AnimLengthSync of the
# playing clip must equal it: that is how the map knows Birth plays.
LENGTH_MS = 3267


def extract_length(path: Path = MODEL) -> int:
    from project_root import project_root

    sys.path.insert(0, str(project_root() / "scripts" / "vendor" / "m3addon"))
    import m3

    seq = next(s for s in m3.loadModel(str(path)).sequences if s.name == CLIP)
    return int(seq.animEndInMS) - int(seq.animStartInMS)


def extract(path: Path = MODEL) -> tuple[tuple[int, float, float, float], ...]:
    """Root location keys of Birth from the m3, rounded as KEYS, duplicates dropped."""
    from project_root import project_root

    sys.path.insert(0, str(project_root() / "scripts" / "vendor" / "m3addon"))
    import m3

    model = m3.loadModel(str(path))
    bone = next(b for b in model.bones if b.name == ROOT_BONE)
    if bone.parent != -1:
        raise ValueError(f"{ROOT_BONE} has a parent: keys are not model space")
    if bone.location.header.interpolationType != 1:
        raise ValueError(f"{ROOT_BONE} location is not linear")
    anim_id = bone.location.header.animId
    group = next(g for g in model.sequenceTransformationGroups if g.name == CLIP)
    for index in group.stcIndices:
        stc = model.sequenceTransformationCollections[index]
        for aid, ref in zip(stc.animIds, stc.animRefs):
            if aid != anim_id or (ref >> 16) & 0xFFFF != 2:
                continue
            block = stc.sd3v[ref & 0xFFFF]
            seq = next(s for s in model.sequences if s.name == CLIP)
            out: list[tuple[int, float, float, float]] = []
            for frame, key in zip(block.frames, block.keys):
                frame = int(frame)
                if frame > int(seq.animEndInMS):
                    break
                row = (frame, round(key.x, 4), round(key.y, 4), round(key.z, 4))
                if out and out[-1][0] == frame:
                    continue
                out.append(row)
            return tuple(out)
    raise ValueError(f"{ROOT_BONE} has no location keys in {CLIP}")


def actor_scale(map_dir: Path) -> float:
    root = ET.parse(map_dir / ACTORS).getroot()
    for actor in root.iter("CActorUnit"):
        if actor.get("id") == "SCOBADropPodArt":
            scale = actor.find("Scale")
            if scale is not None:
                return float(scale.get("value", "1"))
    return 1.0


def local(ms: float) -> tuple[float, float, float]:
    """Root offset in model units at ms, linear between keys, held after the last."""
    if ms <= KEYS[0][0]:
        return KEYS[0][1:]
    for a, b in zip(KEYS, KEYS[1:]):
        if ms <= b[0]:
            u = (ms - a[0]) / (b[0] - a[0])
            return tuple(a[i] + (b[i] - a[i]) * u for i in (1, 2, 3))
    return KEYS[-1][1:]


def world(ms: float, facing: float) -> tuple[float, float, float]:
    """Root offset from the pod unit in world units at ms, for a unit facing."""
    x, y, z = local(ms)
    x *= MODEL_X
    a = math.radians(facing + MODEL_YAW)
    s = ACTOR_SCALE
    return (s * (x * math.cos(a) - y * math.sin(a)), s * (x * math.sin(a) + y * math.cos(a)), s * z)


def travel() -> tuple[float, float, float, float]:
    """Start-to-land in model axes: travel angle off the unit facing (deg),
    descent pitch of the fast part (deg), start horizontal and height (world)."""
    x0, y0, z0 = KEYS[0][1:]
    x1, y1, z1 = next(k for k in KEYS if k[0] == 1600)[1:]
    xl, yl, zl = next(k for k in KEYS if k[0] == LAND_MS)[1:]
    model_angle = math.degrees(math.atan2(yl - y0, MODEL_X * (xl - x0)))
    pitch = math.degrees(math.atan2(z0 - z1, math.hypot(x1 - x0, y1 - y0)))
    horiz = ACTOR_SCALE * math.hypot(x0 - xl, y0 - yl)
    return (model_angle + MODEL_YAW) % 360.0, pitch, horiz, ACTOR_SCALE * (z0 - zl)


def _f(v: float) -> str:
    return f"{v:.4f}"


def galaxy() -> str:
    n = len(KEYS)
    lines = [
        "// Generated by scripts/hitvolumes/pod_birth.py. Do not edit.",
        f"// {ROOT_BONE} location keys of the {CLIP} clip, model units, linear.",
        f"const int c_POD_BIRTH_KEYS = {n};",
        f"const fixed c_POD_BIRTH_SCALE = {_f(ACTOR_SCALE)};",
        f"const fixed c_POD_BIRTH_MODEL_YAW = {_f(MODEL_YAW)};",
        f"const fixed c_POD_BIRTH_MODEL_X = {_f(MODEL_X)};",
        f"const fixed c_POD_BIRTH_LAND = {_f(LAND_MS / 1000.0)};",
        f"const fixed c_POD_BIRTH_LENGTH = {_f(LENGTH_MS / 1000.0)};",
        "// Travel direction = unit facing + TRAVEL; descent pitch of the fast",
        "// part; the start point's horizontal distance and height (world).",
        f"const fixed c_POD_BIRTH_TRAVEL = {_f(travel()[0])};",
        f"const fixed c_POD_BIRTH_PITCH = {_f(travel()[1])};",
        f"const fixed c_POD_BIRTH_START_RANGE = {_f(travel()[2])};",
        f"const fixed c_POD_BIRTH_START_Z = {_f(travel()[3])};",
        f"fixed[{n}] gv_podBirthT;",
        f"fixed[{n}] gv_podBirthX;",
        f"fixed[{n}] gv_podBirthY;",
        f"fixed[{n}] gv_podBirthZ;",
        "",
        "void gf_PodBirthLoad () {",
    ]
    for i, (ms, x, y, z) in enumerate(KEYS):
        lines.append(f"    gv_podBirthT[{i}] = {_f(ms / 1000.0)};")
        lines.append(f"    gv_podBirthX[{i}] = {_f(x)};")
        lines.append(f"    gv_podBirthY[{i}] = {_f(y)};")
        lines.append(f"    gv_podBirthZ[{i}] = {_f(z)};")
    lines += ["}", ""]
    return "\n".join(lines)


def src_dir() -> Path:
    from project_root import project_root

    return project_root() / "src" / "SCOBA.SC2Map"


def check(map_dir: Path) -> list[str]:
    problems: list[str] = []
    path = map_dir / DATA_FILE
    have = path.read_text(encoding="utf-8").replace("\r\n", "\n") if path.exists() else ""
    if have != galaxy():
        problems.append(f"{DATA_FILE} does not match scripts/hitvolumes/pod_birth.py")
    scale = actor_scale(map_dir)
    if abs(scale - ACTOR_SCALE) > 1e-6:
        problems.append(f"SCOBADropPodArt actor Scale {scale} != pod_birth.ACTOR_SCALE {ACTOR_SCALE}")
    return problems


def main(argv: list[str]) -> int:
    if "--extract" in argv:
        for row in extract():
            print(row)
        return 0
    if "--check" in argv:
        bad = check(src_dir())
        for line in bad:
            print(line)
        return 1 if bad else 0
    path = src_dir() / DATA_FILE
    path.write_text(galaxy(), encoding="utf-8")
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
