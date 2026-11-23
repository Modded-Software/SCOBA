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
from hdtex.check import check_hd_textures
from flora.build import check_flora
from flora.config import MARKER as FLORA_MARKER
from mapgen.footprints.build import check_scaled_footprints
from mapgen.melee_map import check as check_melee_map
from mapgen.resources.build import check as check_resources
from mapgen.player_slots import check as check_player_slots, check_script as check_roster_script
from input_gate_check import gated as check_input_gate
from hitvolumes.drop_path_check import check as check_drop_path
from validate_aim_shot import TOSH_CLOCK, check_aim_shot_data, check_aim_shot_script
from validate_assets import check_actor_events, check_control_icons, check_footfall_fx, check_skybox_flip, check_stamp
from jumpanim.validate import check_jump
from heroanim.rig import HEROES
from heroanim.validate import check_heroes
from validate_slow_deaths import check_slow_deaths
from hitvolumes.validate_pod_actor import check_pod_actor
from validate_tps_overlay import check_tps_overlay
from hitvolumes.validate_intro import animation_actor_problems, intro_problems
from terrain import sync_height

GENERATED_MODELS = [rig.target for rig in HEROES.values()]

NATIVE_GROUPS = (
    "Attack",
    "Spell",
    "Stand Work",
    "Stand",
    "Walk",
    "Stand Left",
    "Stand Right",
)

UPPER_GROUPS = (
    "Attack Arm Alternate",
    "Spell Arm Alternate",
    "Attack Arm Alternate 01",
    "Spell Arm Alternate 01",
)

GAMEPLAY_ACTORS = (
    ("ToshSCOBAUnit", "ToshSCOBA", "ToshSCOBA"),
    ("KerriganSCOBAUnit", "KerriganSCOBA", "KerriganSCOBA"),
)

AIM_ATTACK_PITCH = {rig.target: rig.pitch_bones[0] for rig in HEROES.values()}

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
    "Base.SC2Data/GameData/ActorData.xml",
    "Base.SC2Data/GameData/AbilData.xml",
    "Base.SC2Data/GameData/BehaviorData.xml",
    "Base.SC2Data/GameData/ButtonData.xml",
    "Base.SC2Data/GameData/EffectData.xml",
    "Base.SC2Data/GameData/WeaponData.xml",
    "scripts/app/systems/aim_shooting.galaxy",
    "scripts/app/systems/combat_cooldown.galaxy",
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
    "SCOBATPSToggle",
    "SCOBAAutoAttackStatus",
]

CUSTOM_BEHAVIORS = [
    "SCOBAAttackSingle",
    "SCOBARightClickStandBehavior",
    "SCOBATPSBehavior",
    "SCOBAStandRoot",
]

CUSTOM_BUTTONS = [
    "SCOBAAutoAttackOn",
    "SCOBAAutoAttackOff",
    "SCOBARightClickMove",
    "SCOBARightClickStand",
    "SCOBAControlPNC",
    "SCOBAControlTPS",
    "SCOBAAutoAttackStatus",
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

    # Baked from the render ground; absent only with SC2_SYNC_HEIGHT=0.
    for problem in sync_height.problems(map_dir):
        fail(problem)

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

    # Control mode icons: checked by validate_assets.check_control_icons.

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

    check_aim_shot_data(map_dir)

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
    for unit_id, parent_id in (("ToshSCOBA", "Tosh"), ("KerriganSCOBA", "Kerrigan")):
        unit = None
        for candidate in unit_tree.getroot().iter("CUnit"):
            if candidate.get("id") == unit_id:
                unit = candidate
                break
        if unit is None:
            fail(f"missing unit: {unit_id}")
        if unit.get("parent") != parent_id:
            fail(f"{unit_id} parent must be {parent_id}")
        # A toggle behavior on the unit leaves its button out of step.
        for element in unit.findall("BehaviorArray"):
            if element.get("Link") in ("SCOBAAttackSingle", "SCOBARightClickStandBehavior"):
                fail(f"{unit_id} must not carry a toggle behavior: {element.get('Link')}")

    # The card layout face overrides the ability face. Each toggle face must
    # name the state the hero is in while that command is shown.
    faces = {
        "SCOBAAutoAttackToggle,On": "SCOBAAutoAttackOn",
        "SCOBAAutoAttackToggle,Off": "SCOBAAutoAttackOff",
        "SCOBARightClickToggle,On": "SCOBARightClickMove",
        "SCOBARightClickToggle,Off": "SCOBARightClickStand",
    }
    seen = 0
    for button in unit_tree.getroot().iter("LayoutButtons"):
        want = faces.get(button.get("AbilCmd", ""))
        if want is None:
            continue
        seen += 1
        if button.get("Face") != want:
            fail(f"card layout face for {button.get('AbilCmd')} must be {want}")
    if seen < len(faces) * 2:
        fail("card layout missing toggle buttons")
    # The control mode toggle is a HUD button next to the minimap, not a card button.
    for button in unit_tree.getroot().iter("LayoutButtons"):
        if button.get("AbilCmd", "").startswith("SCOBATPSToggle,"):
            fail("SCOBATPSToggle must not be on the command card")

    weapon_tree = ET.parse(gamedata / "WeaponData.xml")
    behavior_text = (gamedata / "BehaviorData.xml").read_text(encoding="utf-8")
    start = behavior_text.find('<CBehaviorBuff id="SCOBAAttackSingle">')
    if start < 0:
        fail("missing behavior: SCOBAAttackSingle")
    single_behavior = behavior_text[start : behavior_text.find("</CBehaviorBuff>", start)]
    for weapon_id in ("Tosh", "RazorTalons", "QueenOfBladesPsiBlast"):
        # The stock weapon is order-bound and serves Attack `single`.
        weapon = weapon_tree.getroot().find(f"CWeaponLegacy[@id='{weapon_id}']")
        if weapon is None:
            fail(f"missing weapon override: {weapon_id}")
        if weapon.findall("Options") or weapon.find("AllowedMovement") is not None:
            fail(f"{weapon_id} must keep the stock order-bound options")
        # The auto twin fires outside attack orders. `single` disables it.
        auto_id = f"{weapon_id}Auto"
        auto = weapon_tree.getroot().find(f"CWeaponLegacy[@id='{auto_id}']")
        if auto is None or auto.get("parent") != weapon_id:
            fail(f"missing auto weapon: {auto_id}")
        allowed = auto.find("AllowedMovement")
        if allowed is None or allowed.get("value") != "Moving":
            fail(f"{auto_id} must allow moving fire")
        arc = auto.find("Arc")
        if arc is None or arc.get("value") != "360":
            fail(f"{auto_id} must fire at any facing")
        options = {o.get("index"): o.get("value") for o in auto.findall("Options")}
        if options.get("OnlyFireWhileInAttackOrder") != "0":
            fail(f"{auto_id} must fire outside attack orders")
        if options.get("OnlyFireAtAttackOrderTarget") != "0":
            fail(f"{auto_id} must fire outside attack-order targets")
        if f'<WeaponDisableArray value="{auto_id}"/>' not in single_behavior:
            fail(f"SCOBAAttackSingle must disable weapon: {auto_id}")

    # Ranged hero weapons: twice the stock in-game range, less the +2 of
    # UnitDirectControl. The auto twins inherit.
    for weapon_id, hero_range in (("Tosh", "12"), ("QueenOfBladesPsiBlast", "10"), ("RazorTalons", None)):
        own, twin = (weapon_tree.getroot().find(f"CWeaponLegacy[@id='{w}']/Range") for w in (weapon_id, f"{weapon_id}Auto"))
        if (None if own is None else own.get("value")) != hero_range or twin is not None:
            fail(f"{weapon_id} range must be {hero_range} and its auto twin must inherit it")
    # Cooldown clock: every hero weapon shot sets the Weapon Attack button
    # cooldown to the weapon period, in data.
    effects = ET.parse(gamedata / "EffectData.xml").getroot()
    for effect_id, period in (("SCOBAAttackCooldown10", "1"), TOSH_CLOCK):
        cost = effects.find(f"CEffectModifyUnit[@id='{effect_id}']/Cost")
        if cost is None:
            fail(f"missing cooldown effect: {effect_id}")
        if cost.get("Abil") != "SCOBAAutoAttackStatus,Execute" or cost.get("CooldownOperation") != "Set":
            fail(f"{effect_id} must set the Weapon Attack button cooldown")
        if cost.get("CooldownTimeUse") != period:
            fail(f"{effect_id} must set the cooldown to {period}")
    tosh_effect = weapon_tree.getroot().find("CWeaponLegacy[@id='Tosh']/Effect")
    if tosh_effect is None or tosh_effect.get("value") != "SCOBAToshShot":
        fail("Tosh weapon must fire SCOBAToshShot")
    tosh_set = [e.get("value") for e in effects.findall("CEffectSet[@id='SCOBAToshShot']/EffectArray")]
    if tosh_set != ["ToshU", TOSH_CLOCK[0]]:
        fail(f"SCOBAToshShot must run ToshU and {TOSH_CLOCK[0]}")
    tosh_time = weapon_tree.getroot().find("CWeaponLegacy[@id='Tosh']/Cost/Cooldown")
    if tosh_time is None or tosh_time.get("TimeUse") != TOSH_CLOCK[1]:
        fail(f"Tosh weapon cooldown must be {TOSH_CLOCK[1]}, as its button clock")
    talons = effects.find("CEffectCreatePersistent[@id='RazorTalonsPersistent']/InitialEffect")
    if talons is None or talons.get("value") != "SCOBAAttackCooldown10":
        fail("RazorTalonsPersistent must start SCOBAAttackCooldown10")
    psi_effect = weapon_tree.getroot().find("CWeaponLegacy[@id='QueenOfBladesPsiBlast']/Effect")
    if psi_effect is None or psi_effect.get("value") != "SCOBAPsiBlastShot":
        fail("QueenOfBladesPsiBlast must fire SCOBAPsiBlastShot")
    psi_set = [e.get("value") for e in effects.findall("CEffectSet[@id='SCOBAPsiBlastShot']/EffectArray")]
    if psi_set != ["PsiBlastLaunchMissile", "SCOBAAttackCooldown10"]:
        fail("SCOBAPsiBlastShot must run PsiBlastLaunchMissile and SCOBAAttackCooldown10")


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
        for name in NATIVE_GROUPS:
            if normalized_animation_name(name) not in groups:
                fail(f"{relative} missing native animation group {name!r}")
        for name in UPPER_GROUPS:
            if normalized_animation_name(name) not in groups:
                fail(f"{relative} missing upper animation group {name!r}")
        for name in ("Turn Left", "Turn Right"):
            if normalized_animation_name(name) in groups:
                fail(f"{relative} has upper turn group {name!r}")
        # Head look clips (R-TPS-13, 16): one per pitch x yaw step the script can ask for.
        head_steps = int(re.search(r"c_ANIM_HEAD_STEPS = (\d+);", text).group(1))
        head_steps *= int(re.search(r"c_ANIM_HEAD_YAW_STEPS = (\d+);", text).group(1))
        for step in range(1, head_steps + 1):
            if normalized_animation_name(f"Ready Cover {step:02d}") not in groups:
                fail(f"{relative} missing head tilt group Ready Cover {step:02d}")
        if head_steps < 99 and normalized_animation_name(f"Ready Cover {head_steps + 1:02d}") in groups:
            fail(f"{relative} has more head tilt groups than c_ANIM_HEAD_STEPS")
        pitch_bone = AIM_ATTACK_PITCH.get(relative)
        if pitch_bone is not None:
            pitch_ids = set()
            for bone in model.bones:
                if bone.name == pitch_bone:
                    pitch_ids.update(
                        (
                            bone.location.header.animId,
                            bone.rotation.header.animId,
                            bone.scale.header.animId,
                        )
                    )
            for aim_group in ("Attack Arm Alternate 01", "Spell Arm Alternate 01"):
                group = next(
                    candidate
                    for candidate in model.sequenceTransformationGroups
                    if normalized_animation_name(candidate.name) == normalized_animation_name(aim_group)
                )
                stc = model.sequenceTransformationCollections[group.stcIndices[0]]
                if pitch_ids & set(stc.animIds):
                    fail(f"{relative} {aim_group} contains pitch root {pitch_bone}")
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
    behavior_text = (map_dir / "Base.SC2Data/GameData/BehaviorData.xml").read_text(
        encoding="utf-8", errors="replace"
    )
    if "RegionPlayableMapSet(RegionRect(0.0, 0.0, 254.0, 254.0));" not in combined:
        fail("MapScript.galaxy missing expanded playable region")
    if "CameraSetBounds(PlayerGroupAll(), RegionRect(0.0, 0.0, 254.0, 254.0), true);" not in combined:
        fail("MapScript.galaxy missing expanded camera bounds")
    if "void InitTriggers ()" not in script:
        fail("MapScript.galaxy missing InitTriggers")
    if "gt_ToggleCommands_Init();" not in combined:
        fail("scripts missing toggle command init")
    if "gf_ChaseStandSet(gv_tPSUNIT[lv_localPlayer], true);" not in combined:
        fail("scripts missing default Chase stand")
    if "gf_AttackSingleSet(gv_tPSUNIT[lv_localPlayer], true);" not in combined:
        fail("scripts missing default Attack single")
    if "UISetFrameVisible(PlayerGroupAll(), c_syncFrameTypeTextTag, true);" not in combined:
        fail("scripts must keep the text tag frame visible")
    if "gf_AimShotPress" not in combined:
        fail("scripts missing aim shot press handler")
    if "gf_AimCrosshairPoint" not in combined:
        fail("scripts missing aim crosshair point")
    check_aim_shot_script(map_dir, combined)
    if "gf_SelectionUIApply" not in combined or "UISetSelectionTypeEnabled" not in combined:
        fail("scripts missing aim UI selection gate")
    if "gf_AimSelectBlock" in combined or "gf_AimSelectClear" in combined:
        fail("aim must not change per-unit Selectable state")
    if "gf_AimNoAttackApply" in combined or "SCOBAAimNoAttack" in combined or "SCOBAAimNoAttack" in behavior_text:
        fail("aiming must not suppress the hero attack: the aim shot is a hero attack")
    if "gf_SelectHeroForce" not in combined or "gf_TpsStatusIs" not in combined:
        fail("scripts missing selection and action status helpers")
    check_tps_overlay(map_dir, combined)
    if "gf_AnimTargetPitchTick" not in combined:
        fail("scripts missing PNC target pitch")
    if "gf_PncAttack" not in combined or "gf_PncCancel" not in combined:
        fail("scripts missing point and click attack and cancel")
    if 'AbilityCommand("move", 3)' in combined or "gf_CombatStep" in combined:
        fail("scripts must not run a script combat loop or acquire-move")
    # Toggles change through their toggle commands only (gf_ToggleSet).
    for constant in ("c_SCOBA_SINGLE_BEHAVIOR", "c_SCOBA_STAND_BEHAVIOR"):
        if re.search(rf"UnitBehavior(Add|Remove)\s*\([^;]*{constant}", combined):
            fail(f"scripts must not add or remove a toggle behavior directly: {constant}")
    if "gf_AttackSingleSet" not in combined or "gf_ChaseStandSet" not in combined:
        fail("scripts missing toggle setters")
    if "c_ANIM_ATTACK_START_TIME" not in combined or combined.count("AnimSetTime ") < 2:
        fail("scripts missing attack windup skip")
    
    if "gf_FloaterCreate" not in combined:
        fail("scripts missing shared floater helper")


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
    check_skybox_flip(map_dir)
    check_footfall_fx(map_dir)
    check_actor_events(map_dir)
    check_animation_names(map_dir)
    for problem in animation_actor_problems(map_dir, GAMEPLAY_ACTORS):
        fail(problem)
    check_jump(map_dir, galaxy_text(map_dir))
    check_heroes(map_dir, galaxy_text(map_dir), fail)
    check_slow_deaths(map_dir)
    for problem in check_pod_actor(map_dir):
        fail(problem)
    check_hd_textures(map_dir)
    for problem in check_scaled_footprints(map_dir):
        fail(problem)
    for problem in check_player_slots(map_dir):
        fail(problem)
    for problem in check_melee_map(map_dir):
        fail(problem)
    for problem in check_resources(map_dir):
        fail(problem)
    for problem in check_roster_script(galaxy_text(map_dir)):
        fail(problem)
    for problem in [*check_input_gate(galaxy_text(map_dir)), *check_drop_path(map_dir)]:
        fail(problem)
    # A build with SC2_NO_FLORA=1 has no flora marker and no flora to check.
    if (map_dir / FLORA_MARKER).exists():
        for problem in check_flora(map_dir):
            fail(problem)
    check_script(map_dir)
    for problem in intro_problems(map_dir):
        fail(problem)
    check_animation_names(map_dir)
    check_stamp(map_dir)
    print(f"OK: validated {map_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())