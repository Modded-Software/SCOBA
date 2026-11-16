#!/usr/bin/env python3
"""Footfall effects for walking units, from one table (FOOTFALL_UNITS).

Operator 2026-11-16: Goliath footfalls get a heavy thump; the Queen's six
legs get the same effects, lighter and smaller. Everything a footfall needs
is generated into the built map from the table, so another unit is one
more FootfallUnit row:

- m3: a stock model copy with one attach point per foot (Ref_Hardpoint
  <tag>, on its own zero-offset bone under the foot bone; attach keywords
  are a fixed engine set, so feet are told apart by Left/Right or an index);
- ModelData: Custom "Walk" events, one per measured contact
  (footfall/m3_footfalls.py), named ScobaFoot<n> for foot n; effect models
  <Unit>FootDust/Splash/Ripple at the unit's scales;
- AttachMethodData: an index filter per indexed foot;
- SoundData: <Unit>Footstep from the unit's wave files;
- ActorData: per foot a site op (attach, hold, drop to ground or water) and
  dust, splash, ripple and sound actors; the unit actor answers each
  footstep event (splash in water, dust elsewhere, the sound always) and
  the script's "Signal ScobaRipple" (idle ripples at every foot).

The water state comes from systems/quake.galaxy (StatusSet ScobaInWater):
the engine's own water detection never fired for these units.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import tempfile
import copy
from typing import NamedTuple
from pathlib import Path

from character_anim_assets import extract_model
from project_root import project_root

ROOT = project_root()
sys.path.insert(0, str(ROOT / "scripts" / "vendor" / "m3addon"))

import m3

from footfall import m3_footfalls

MARKER = ".footfall_fx"
MARKER_VERSION = "4\n"  # 4: engine squibs off; 3: per-foot engine water check removed
EXTRACT_ROOT = Path("/mnt/ws-fast/sc2res/tmp")  # operator: extract into ws-fast
NO_ADDON = 0xFFFF
STATUS = "ScobaInWater"
RIPPLE_SIGNAL = "ScobaRipple"
DROP_OP = "SOpHigherOfTerrainAndWater"


class Foot(NamedTuple):
    bone: str  # foot bone in the stock model
    tag: str  # attach point "Ref_Hardpoint <tag>": "Left", "Right" or "01".."99"

    @property
    def point(self) -> str:
        return f"Ref_Hardpoint {self.tag}"

    def filter_id(self, unit: str) -> str:
        """Stock filters for Left/Right; an own index filter otherwise."""
        if self.tag in ("Left", "Right"):
            return f"AMFilterHardpoint{self.tag}"
        return f"ScobaAMFilter{unit}Foot{self.tag}"


class Sound(NamedTuple):
    files: tuple[str, ...]  # wave assets (Assets\Sounds\...)
    volume: tuple[float, float]  # dB range
    pitch: tuple[float, float]  # semitone range


class FootfallUnit(NamedTuple):
    unit: str  # CUnit / CActorUnit / CModel id
    entry: str  # stock m3 in CASC
    target: Path  # model path inside the map
    feet: tuple[Foot, ...]
    dust: tuple[float, float]  # scale range of JumpLandDust
    splash: tuple[float, float]  # scale range of WaterSplashLarge
    ripple: tuple[float, float]  # scale range of WaterRippleMedium
    sound: Sound
    clip: str = "Walk"


HEAVY = Sound(tuple(f"Assets\\Sounds\\MonsterHuge_BaseFootstepFS0{i}.wav" for i in range(1, 9)), (0.0, 2.0), (-2.0, 0.0))
LIGHT = Sound(tuple(f"Assets\\Sounds\\StoneZealot_Footstep0{i}.wav" for i in range(1, 10)), (-8.0, -5.0), (0.0, 2.0))

FOOTFALL_UNITS = (
    FootfallUnit(
        unit="Goliath",
        entry=r"mods\liberty.sc2mod\base.sc2assets\assets\units\terran\goliath\goliath.m3",
        target=Path("Assets") / "Units" / "Terran" / "Goliath" / "Goliath.m3",
        feet=(Foot("Bone Foot L", "Left"), Foot("Bone Foot R", "Right")),
        dust=(1.25, 1.5),
        splash=(1.25, 1.5),
        ripple=(1.0, 1.0),
        sound=HEAVY,
    ),
    FootfallUnit(
        unit="Queen",
        entry=r"mods\liberty.sc2mod\base.sc2assets\assets\units\zerg\queen\queen.m3",
        target=Path("Assets") / "Units" / "Zerg" / "Queen" / "Queen.m3",
        # Six legs: the lower segment of each pelvis leg chain.
        feet=tuple(
            Foot(bone, f"{i:02d}")
            for i, bone in enumerate(
                ("Bone03", "Bone07", "Bone11", "Bone03(mirrored)", "Bone07(mirrored)", "Bone11(mirrored)"), start=1
            )
        ),
        dust=(0.75, 0.9),
        splash=(0.75, 0.9),
        ripple=(0.7, 0.7),
        sound=LIGHT,
    ),
)


def event_name(index: int) -> str:
    return f"ScobaFoot{index + 1}"


# --- m3 --------------------------------------------------------------------


def clone(structure):
    """Copy of an m3 structure that shares its structure descriptions."""
    # The shared structure descriptions are pre-seeded in the memo, so
    # deepcopy keeps them shared and copies only the instance data.
    memo = {}
    for history in m3.structures.values():
        for description in history.versionToStructureDescriptionMap.values():
            memo[id(description)] = description
    return copy.deepcopy(structure, memo)


def anim_ids(model) -> set[int]:
    return {track.header.animId for bone in model.bones for track in (bone.location, bone.rotation, bone.scale, bone.ar1)}


def template_bone(model):
    """A Ref_ bone to copy (any: the copy is reset to zero offset)."""
    for bone in model.bones:
        if bone.name.lower().startswith("ref_"):
            return bone
    raise ValueError("model has no Ref_ bone to copy")


def add_points(model, feet: tuple[Foot, ...]) -> list[tuple[str, int]]:
    """Each point gets its own zero-offset bone under the foot bone.

    Stock models attach every Ref_ point to a bone of the same name (the
    Colossus Ref_Hardpoint 01..04 bones are children of its leg bones); a
    point on a plain skin bone is not picked up.
    """
    bones = [b.name for b in model.bones]
    have = {a.name for a in model.attachmentPoints} | set(bones)
    template = template_bone(model)
    next_id = max(anim_ids(model)) + 1
    added = []
    for foot in feet:
        if foot.point in have:
            raise ValueError(f"model already has {foot.point}")
        parent = bones.index(foot.bone)
        bone = clone(template)
        bone.name = foot.point
        bone.parent = parent
        for value in (bone.location.initValue, bone.location.nullValue):
            value.x = value.y = value.z = 0.0
        for value in (bone.rotation.initValue, bone.rotation.nullValue):
            value.x = value.y = value.z = 0.0
            value.w = 1.0
        for track in (bone.location, bone.rotation, bone.scale, bone.ar1):
            track.header.animId = next_id
            next_id += 1
        model.bones.append(bone)
        model.absoluteInverseBoneRestPositions.append(clone(model.absoluteInverseBoneRestPositions[parent]))
        index = len(model.bones) - 1
        point = clone(model.attachmentPoints[0])
        point.name = foot.point
        point.boneIndex = index
        model.attachmentPoints.append(point)
        model.attachmentPointAddons.append(NO_ADDON)
        added.append((foot.point, index))
    return added


def contacts(source: Path, spec: FootfallUnit) -> list[list[float]]:
    """Per foot: contact times (seconds) in the walk clip, measured."""
    measured = m3_footfalls.footfalls(source, spec.clip, [f.bone for f in spec.feet])
    out = [[round(ms / 1000.0, 3) for ms in measured[f.bone]] for f in spec.feet]
    for foot, times in zip(spec.feet, out):
        if not times:
            raise ValueError(f"{spec.unit} {foot.bone}: no contact in {spec.clip}")
    return out


# --- XML ---------------------------------------------------------------------


def scale_xml(lo: float, hi: float) -> str:
    return f'        <ScaleMax value="{hi:.6f},{hi:.6f},{hi:.6f}"/>\n        <ScaleMin value="{lo:.6f},{lo:.6f},{lo:.6f}"/>\n'


def model_events_xml(spec: FootfallUnit, times: list[list[float]]) -> str:
    out = ""
    for i, foot_times in enumerate(times):
        for t in foot_times:
            out += (
                "        <Events>\n"
                f'            <Anim value="{spec.clip}"/>\n'
                f'            <Name value="{event_name(i)}"/>\n'
                '            <Type value="Custom"/>\n'
                f'            <Time value="{t:.6f}"/>\n'
                "        </Events>\n"
            )
    return out


def fx_models_xml(spec: FootfallUnit) -> str:
    u = spec.unit
    return (
        f'    <CModel id="{u}FootDust" parent="JumpLandDust" Race="Other">\n'
        '        <Model value="Assets\\Effects\\Other\\JumpLandDust\\JumpLandDust.m3"/>\n'
        + scale_xml(*spec.dust)
        + "    </CModel>\n"
        f'    <CModel id="{u}FootSplash" parent="WaterSplashLarge">\n'
        '        <Model value="Assets\\Doodads\\WaterSplashLarge\\WaterSplashLarge.m3"/>\n'
        + scale_xml(*spec.splash)
        + "    </CModel>\n"
        f'    <CModel id="{u}FootRipple" parent="WaterRippleMedium">\n'
        '        <Model value="Assets\\Doodads\\WaterRippleLarge\\WaterRippleLarge.m3"/>\n'
        + scale_xml(*spec.ripple)
        + "    </CModel>\n"
    )


def sound_xml(spec: FootfallUnit) -> str:
    s = spec.sound
    assets = "".join(f'        <AssetArray File="{f}" FacialGroup=""/>\n' for f in s.files)
    return (
        f'    <CSound id="{spec.unit}Footstep" parent="Spell">\n'
        + assets
        + '        <Category value="Combat"/>\n'
        f'        <Pitch value="{s.pitch[0]:.6f},{s.pitch[1]:.6f}"/>\n'
        f'        <Volume value="{s.volume[0]:.6f},{s.volume[1]:.6f}"/>\n'
        "    </CSound>\n"
    )


def filters_xml(spec: FootfallUnit) -> str:
    out = ""
    for foot in spec.feet:
        if foot.tag in ("Left", "Right"):
            continue
        out += (
            f'    <CAttachMethodFilter id="{foot.filter_id(spec.unit)}">\n'
            f'        <Keys Keyword="Hardpoint" Index="{int(foot.tag)}"/>\n'
            "    </CAttachMethodFilter>\n"
        )
    return out


def site_op(spec: FootfallUnit, i: int) -> str:
    return f"SOpAttachScoba{spec.unit}Foot{i + 1}"


def fx_actors_xml(spec: FootfallUnit) -> str:
    u = spec.unit
    out = ""
    for i, foot in enumerate(spec.feet):
        op = site_op(spec, i)
        out += (
            f'    <CActorSiteOpAttach id="{op}">\n'
            f'        <AttachQuery Methods="{foot.filter_id(u)}"/>\n'
            '        <HoldPosition value="1"/>\n'
            '        <HoldRotation value="1"/>\n'
            "    </CActorSiteOpAttach>\n"
        )
        for kind in ("Dust", "Splash", "Ripple"):
            out += (
                f'    <CActorModel id="{u}Foot{kind}{i + 1}" parent="ModelAnimationStyleOneShotUNIT">\n'
                f'        <Model value="{u}Foot{kind}"/>\n'
                f'        <HostSiteOps Ops="{op} {DROP_OP}"/>\n'
                "    </CActorModel>\n"
            )
        out += (
            f'    <CActorSound id="{u}FootSound{i + 1}" parent="SoundOneShot">\n'
            f'        <Sound value="{u}Footstep"/>\n'
            f'        <HostSiteOps Ops="{op} {DROP_OP}"/>\n'
            "    </CActorSound>\n"
        )
    return out


def unit_on_xml(spec: FootfallUnit) -> str:
    """Splash in water (ScobaInWater, set by the script), dust elsewhere."""
    u = spec.unit
    out = f'        <On Terms="ActorCreation" Send="StatusSet {STATUS} 0"/>\n'
    # Engine ripples off (stock Queen activates them on birth): the script's
    # ripples, which check water above the ground, are the only ones.
    out += f'        <On Terms="ActorCreation" Send="TerrainSquibDeactivate"/>\n'
    out += f'        <On Terms="UnitBirth.{u}" Send="TerrainSquibDeactivate"/>\n'
    for i in range(len(spec.feet)):
        ev = f"ModelEvent; ModelEventName {event_name(i)}"
        out += (
            f'        <On Terms="{ev}; IsStatus {STATUS} 1" Send="Create {u}FootSplash{i + 1}"/>\n'
            f'        <On Terms="{ev}; IsStatus {STATUS} 0" Send="Create {u}FootDust{i + 1}"/>\n'
            f'        <On Terms="{ev}" Send="Create {u}FootSound{i + 1}"/>\n'
            f'        <On Terms="Signal.*.{RIPPLE_SIGNAL}" Send="Create {u}FootRipple{i + 1}"/>\n'
        )
    return out


def merge_block(text: str, tag: str, ident: str, inner: str, opening: str | None = None) -> str:
    """Add inner to the <tag id="ident"> block, or append a new block."""
    pattern = re.compile(r'(<' + tag + r' id="' + re.escape(ident) + r'"[^>]*?)(/>|>(.*?)</' + tag + r'>)', re.S)
    match = pattern.search(text)
    if match is None:
        head = opening or f'<{tag} id="{ident}">'
        return text.replace("</Catalog>", f"    {head}\n{inner}    </{tag}>\n</Catalog>", 1)
    if match.group(2) == "/>":
        block = f"{match.group(1)}>\n{inner}    </{tag}>"
    else:
        block = f"{match.group(1)}>{match.group(3).rstrip()}\n{inner}    </{tag}>"
    return text[: match.start()] + block + text[match.end() :]


def catalog(path: Path) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    return '<?xml version="1.0" encoding="us-ascii"?>\n<Catalog>\n</Catalog>\n'


def append(text: str, entries: str) -> str:
    if "</Catalog>" not in text:
        raise ValueError("catalog has no </Catalog>")
    return text.replace("</Catalog>", entries + "</Catalog>", 1)


def write_data(root: Path, spec: FootfallUnit, times: list[list[float]]) -> None:
    data = root / "Base.SC2Data" / "GameData"
    models = data / "ModelData.xml"
    text = merge_block(catalog(models), "CModel", spec.unit, model_events_xml(spec, times))
    models.write_text(append(text, fx_models_xml(spec)), encoding="utf-8")
    sounds = data / "SoundData.xml"
    sounds.write_text(append(catalog(sounds), sound_xml(spec)), encoding="utf-8")
    filters = filters_xml(spec)
    if filters:
        methods = data / "AttachMethodData.xml"
        methods.write_text(append(catalog(methods), filters), encoding="utf-8")
    actors = data / "ActorData.xml"
    text = merge_block(catalog(actors), "CActorUnit", spec.unit, unit_on_xml(spec))
    actors.write_text(append(text, fx_actors_xml(spec)), encoding="utf-8")


# --- build -------------------------------------------------------------------


def generate_unit(root: Path, spec: FootfallUnit, temp_root: Path) -> None:
    source = extract_model(spec.entry, temp_root)
    model = m3.loadModel(str(source))
    print(f"{spec.unit}: attach points {add_points(model, spec.feet)}")
    target = root / spec.target
    target.parent.mkdir(parents=True, exist_ok=True)
    m3.saveAndInvalidateModel(model, str(target))
    times = contacts(source, spec)
    print(f"{spec.unit}: contacts {times}")
    write_data(root, spec, times)


def generate(root: Path, force: bool) -> None:
    marker = root / MARKER
    if marker.exists() and not force and marker.read_text() == MARKER_VERSION:
        return
    if marker.exists():
        raise ValueError(f"{root} already has footfall data ({MARKER}); rebuild the map from src")
    EXTRACT_ROOT.mkdir(parents=True, exist_ok=True)
    temp_root = Path(tempfile.mkdtemp(prefix="footfall-", dir=EXTRACT_ROOT))
    try:
        for spec in FOOTFALL_UNITS:
            generate_unit(root, spec, temp_root)
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
