#!/usr/bin/env python3
"""Validate an expanded SCOBA map folder before staging."""

from __future__ import annotations

import argparse
import re
import struct
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR / "vendor" / "m3addon"))

import m3
from animation_tokens import normalized_animation_name, validate_animation_name

GENERATED_MODELS = [
    Path("Assets") / "Units" / "Terran" / "Tosh" / "ToshSCOBA.m3",
    Path("Assets") / "Units" / "Zerg" / "Kerrigan" / "KerriganSCOBA.m3",
]

ANIM_CONFIG_RE = re.compile(r'gf_AnimConfig(?:Upper|Lower)\([^,]+,[^,]+,\s*"([^"]+)"')
HERO_CONFIG_RE = re.compile(
    r'gf_AnimConfig(?:Upper|Lower)\((c_ANIM_HERO_TOSH|c_ANIM_HERO_KERRIGAN),[^,]+,\s*"([^"]+)"'
)

REQUIRED = [
    "MapScript.galaxy",
    "MapInfo",
    "t3Terrain.xml",
    "t3HeightMap",
    "t3CellFlags",
    "Minimap.tga",
    "Objects",
    "Regions",
    "ComponentList.SC2Components",
    "Base.SC2Data/GameData/UnitData.xml",
    "Base.SC2Data/GameData/AbilData.xml",
    "Base.SC2Data/GameData/BehaviorData.xml",
    "Base.SC2Data/GameData/ButtonData.xml",
]

XML_FILES = [
    "Objects",
    "Regions",
    "Attributes",
    "Triggers",
    "DocumentInfo",
    "ComponentList.SC2Components",
    "Preload.xml",
    "BankList.xml",
]

CUSTOM_ABILITIES = [
    "SCOBAAutoAttackToggle",
    "SCOBARightClickToggle",
    "SCOBAActionModeToggle",
    "SCOBAAutoAttackStatus",
]

CUSTOM_BEHAVIORS = [
    "SCOBAAutoAttackBehavior",
    "SCOBARightClickStandBehavior",
    "SCOBAActionModeBehavior",
    "SCOBAStandRoot",
]

CUSTOM_BUTTONS = [
    "SCOBAAutoAttackOn",
    "SCOBAAutoAttackOff",
    "SCOBARightClickMove",
    "SCOBARightClickStand",
    "SCOBAActionModeRPG",
    "SCOBAActionModeActions",
    "SCOBAAutoAttackStatus",
]

CONTROL_ICONS = [
    "SCOBAModeRPG.dds",
    "SCOBAModeActions.dds",
]


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def check_required(map_dir: Path) -> None:
    for name in REQUIRED:
        if not (map_dir / name).exists():
            fail(f"missing required file: {name}")


def check_xml(map_dir: Path) -> None:
    paths = {map_dir / name for name in XML_FILES}
    paths.update(map_dir.rglob("*.xml"))
    for path in sorted(paths):
        if not path.is_file():
            continue
        try:
            ET.parse(path)
        except ET.ParseError as exc:
            fail(f"invalid XML: {path.relative_to(map_dir)}: {exc}")


def check_dimensions(map_dir: Path) -> None:
    terrain = (map_dir / "t3Terrain.xml").read_text(encoding="utf-8", errors="replace")
    if 'dim="257 257 ' not in terrain:
        fail("t3Terrain.xml does not declare 257x257")

    data = (map_dir / "t3HeightMap").read_bytes()
    magic, _version, sx, sy = struct.unpack_from("<4sIII", data, 0)
    if magic != b"HMAP" or (sx, sy) != (257, 257):
        fail(f"t3HeightMap is not HMAP 257x257: {magic!r} {sx}x{sy}")

    if (map_dir / "t3SyncHeightMap").exists():
        fail("t3SyncHeightMap must not exist for the 256 map")

    mini = (map_dir / "Minimap.tga").read_bytes()
    width, height = struct.unpack_from("<HH", mini, 12)
    if (width, height) != (256, 256):
        fail(f"Minimap.tga is not 256x256: {width}x{height}")


def ids_from(path: Path, tag: str) -> set[str]:
    tree = ET.parse(path)
    return {element.get("id") for element in tree.getroot().iter(tag) if element.get("id")}


def check_catalogs(map_dir: Path) -> None:
    gamedata = map_dir / "Base.SC2Data" / "GameData"
    abilities = ids_from(gamedata / "AbilData.xml", "CAbilBehavior")
    abilities |= ids_from(gamedata / "AbilData.xml", "CAbilEffectInstant")
    abilities |= ids_from(gamedata / "AbilData.xml", "CAbilEffectTarget")
    behaviors = ids_from(gamedata / "BehaviorData.xml", "CBehaviorBuff")
    buttons = ids_from(gamedata / "ButtonData.xml", "CButton")

    for ability in CUSTOM_ABILITIES:
        if ability not in abilities:
            fail(f"missing ability: {ability}")
    for behavior in CUSTOM_BEHAVIORS:
        if behavior not in behaviors:
            fail(f"missing behavior: {behavior}")
    for button in CUSTOM_BUTTONS:
        if button not in buttons:
            fail(f"missing button: {button}")

    button_tree = ET.parse(gamedata / "ButtonData.xml")
    button_icons = {
        'SCOBAActionModeRPG': r'Assets\Textures\SCOBAModeRPG.dds',
        'SCOBAActionModeActions': r'Assets\Textures\SCOBAModeActions.dds',
    }
    for button_id, icon_path in button_icons.items():
        button = None
        for candidate in button_tree.getroot().iter("CButton"):
            if candidate.get("id") == button_id:
                button = candidate
                break
        if button is None:
            fail(f"missing button: {button_id}")
        icon = button.find("Icon")
        if icon is None or icon.get("value") != icon_path:
            fail(f"{button_id} has wrong control icon")

    behavior_tree = ET.parse(gamedata / "BehaviorData.xml")
    stand_root = None
    for candidate in behavior_tree.getroot().iter("CBehaviorBuff"):
        if candidate.get("id") == "SCOBAStandRoot":
            stand_root = candidate
            break
    if stand_root is None:
        fail("missing behavior: SCOBAStandRoot")
    modification = stand_root.find("Modification")
    if modification is None:
        fail("SCOBAStandRoot missing Modification")
    suppress = modification.find("ModifyFlags[@index='SuppressMoving']")
    if suppress is None or suppress.get("value") != "1":
        fail("SCOBAStandRoot missing SuppressMoving")
    if modification.find("MoveSpeedMultiplier") is not None:
        fail("SCOBAStandRoot must not use MoveSpeedMultiplier")

    ability_tree = ET.parse(gamedata / "AbilData.xml")
    weapon_ability = None
    for candidate in ability_tree.getroot().iter("CAbilEffectTarget"):
        if candidate.get("id") == "SCOBAAutoAttackStatus":
            weapon_ability = candidate
            break
    if weapon_ability is None:
        fail("SCOBAAutoAttackStatus must be CAbilEffectTarget")
    cooldown = weapon_ability.find("Cost/Cooldown")
    if cooldown is None:
        fail("SCOBAAutoAttackStatus missing Cost/Cooldown")
    if cooldown.get("Location") != "Ability":
        fail("SCOBAAutoAttackStatus cooldown Location must be Ability")
    time_use = cooldown.get("TimeUse")
    if time_use is None or float(time_use) <= 0.0:
        fail("SCOBAAutoAttackStatus cooldown TimeUse must be positive")

    unit_tree = ET.parse(gamedata / "UnitData.xml")
    for unit_id in ("Kerrigan", "Tosh"):
        unit = None
        for candidate in unit_tree.getroot().iter("CUnit"):
            if candidate.get("id") == unit_id:
                unit = candidate
                break
        if unit is None:
            fail(f"missing unit: {unit_id}")
        links = [element.get("Link") for element in unit.findall("AbilArray")]
        for ability in CUSTOM_ABILITIES:
            if ability not in links:
                fail(f"{unit_id} missing AbilArray link: {ability}")
        


def check_control_icons(map_dir: Path) -> None:
    icon_dir = map_dir / "Assets" / "Textures"
    hashes = []
    for name in CONTROL_ICONS:
        path = icon_dir / name
        if not path.is_file():
            fail(f"missing control icon: {name}")
        data = path.read_bytes()
        if len(data) < 128 or data[:4] != b"DDS ":
            fail(f"invalid control icon: {name}")
        hashes.append(data)
    if hashes[0] == hashes[1]:
        fail("control mode icons must differ")


def galaxy_text(map_dir: Path) -> str:
    script = (map_dir / "MapScript.galaxy").read_text(encoding="utf-8", errors="replace")
    galaxy = [script]
    for path in sorted((map_dir / "scripts").rglob("*.galaxy")):
        galaxy.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(galaxy)


def check_animation_names(map_dir: Path) -> None:
    text = galaxy_text(map_dir)
    for clip in ANIM_CONFIG_RE.findall(text):
        try:
            validate_animation_name(clip)
        except ValueError as exc:
            fail(str(exc))

    model_groups: list[set[str]] = []
    for relative in GENERATED_MODELS:
        path = map_dir / relative
        if not path.is_file():
            fail(f"missing generated model: {relative}")
        model = m3.loadModel(str(path))
        groups = set()
        for group in model.sequenceTransformationGroups:
            try:
                groups.add(normalized_animation_name(group.name))
            except ValueError as exc:
                fail(f"{relative}: {exc}")
        for name in ("Stand Left", "Stand Right"):
            if normalized_animation_name(name) not in groups:
                fail(f"{relative} missing native turn group {name!r}")
        for name in ("Turn Left", "Turn Right"):
            if normalized_animation_name(name) in groups:
                fail(f"{relative} has upper turn group {name!r}")
        model_groups.append(groups)

    for profile, clip in HERO_CONFIG_RE.findall(text):
        try:
            name = normalized_animation_name(clip)
        except ValueError as exc:
            fail(str(exc))
        for relative, groups in zip(GENERATED_MODELS, model_groups):
            if name not in groups:
                fail(f"{profile} clip {clip!r} missing from {relative}")


def check_script(map_dir: Path) -> None:
    script = (map_dir / "MapScript.galaxy").read_text(encoding="utf-8", errors="replace")
    combined = galaxy_text(map_dir)
    if "RegionPlayableMapSet(RegionRect(0.0, 0.0, 254.0, 254.0));" not in combined:
        fail("MapScript.galaxy missing expanded playable region")
    if "CameraSetBounds(PlayerGroupAll(), RegionRect(0.0, 0.0, 254.0, 254.0), true);" not in combined:
        fail("MapScript.galaxy missing expanded camera bounds")
    if "void InitTriggers ()" not in script:
        fail("MapScript.galaxy missing InitTriggers")
    if "gt_CombatTick_Init();" not in combined:
        fail("scripts missing combat tick init")
    if "gt_ToggleCommands_Init();" not in combined:
        fail("scripts missing toggle command init")
    if 'UnitIssueOrder(gv_tPSUNIT[lv_localPlayer], Order(AbilityCommand("SCOBARightClickToggle", 0))' not in combined:
        fail("scripts missing default stand behavior")


def check_stamp(map_dir: Path) -> None:
    stamp_path = map_dir / "BuildStamp.txt"
    if not stamp_path.is_file():
        fail("missing BuildStamp.txt")
    stamp = stamp_path.read_text(encoding="utf-8").strip()
    if not stamp:
        fail("empty BuildStamp.txt")
    stamp_file = (map_dir / "scripts" / "app" / "core" / "build_stamp.galaxy").read_text(encoding="utf-8", errors="replace")
    if f'const string c_SCOBA_BUILD_STAMP = "{stamp}";' not in stamp_file:
        fail("build_stamp.galaxy build stamp does not match BuildStamp.txt")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("map_dir", type=Path)
    args = parser.parse_args()
    map_dir = args.map_dir
    if not map_dir.is_dir():
        fail(f"map folder not found: {map_dir}")
    check_required(map_dir)
    check_xml(map_dir)
    check_dimensions(map_dir)
    check_catalogs(map_dir)
    check_control_icons(map_dir)
    check_script(map_dir)
    check_animation_names(map_dir)
    check_stamp(map_dir)
    print(f"OK: validated {map_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())