"""Controls test profile."""

from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from pathlib import Path

from project_root import project_root

from ..map_builder import TestMapSpec
from ..runner import TestRunSpec
from .registry import PROFILE_BANKS, PROFILE_OUTPUTS

ROOT = project_root()


def map_spec() -> TestMapSpec:
    return TestMapSpec(
        profile="controls",
        source=ROOT / "out" / "SCOBA256.SC2Map",
        output=PROFILE_OUTPUTS["controls"],
        bank_names=PROFILE_BANKS["controls"],
        galaxy_files=(
            ROOT / "scripts" / "testkit" / "galaxy" / "common.galaxy",
            ROOT / "scripts" / "testkit" / "galaxy" / "controls.galaxy",
        ),
        galaxy_includes=(
            "scripts/test/controls/common",
            "scripts/test/controls/controls",
        ),
        init_calls=("gt_ControlsTest_Init();",),
    )


def on_ready(ctx, data: dict) -> None:
    from .. import input_driver

    input_driver.focus()
    time.sleep(0.1)
    point = input_driver.center_point()
    input_driver.rclick_fast(point[0] + 30, point[1])
    time.sleep(0.2)
    input_driver.rclick_fast(point[0] + 30, point[1])
    time.sleep(1.8)


def _check_icons(checks) -> None:
    icon_dir = PROFILE_OUTPUTS["controls"] / "Assets" / "Textures"
    rpg = (icon_dir / "SCOBAModeRPG.dds").read_bytes()
    actions = (icon_dir / "SCOBAModeActions.dds").read_bytes()
    if rpg == actions:
        print("controls_icons: icon files match FAIL")
        checks.failures += 1
    else:
        print("controls_icons: icon files differ PASS")
    button_path = PROFILE_OUTPUTS["controls"] / "Base.SC2Data" / "GameData" / "ButtonData.xml"
    buttons = {element.get("id"): element for element in ET.parse(button_path).getroot().iter("CButton")}
    expected = {
        "SCOBAActionModeRPG": r"Assets\Textures\SCOBAModeRPG.dds",
        "SCOBAActionModeActions": r"Assets\Textures\SCOBAModeActions.dds",
    }
    for button_id, icon_path in expected.items():
        icon = buttons[button_id].find("Icon")
        if icon is not None and icon.get("value") == icon_path:
            print(f"controls_icons: {button_id} PASS")
        else:
            print(f"controls_icons: {button_id} FAIL")
            checks.failures += 1


def check(ctx, data: dict, checks) -> None:
    for error in ctx.errors:
        print(f"{error} FAIL")
        checks.failures += 1
    
    

    checks.eq("meta", "", "done", 1)
    checks.eq("meta", "", "profile", "controls")
    checks.eq("controls_default", "t0000", "ActionMode", 0)
    checks.eq("controls_rpg_hold", "t0800", "AimActive", 0)
    checks.eq("controls_rpg_hold", "t0800", "Fov", checks.value("controls_default", "t0000", "Fov"))
    move_dx = (checks.value("controls_rpg_move", "t1500", "HeroX") or 0) - (checks.value("controls_rpg_hold", "t0800", "HeroX") or 0)
    move_dy = (checks.value("controls_rpg_move", "t1500", "HeroY") or 0) - (checks.value("controls_rpg_hold", "t0800", "HeroY") or 0)
    if abs(move_dx) + abs(move_dy) >= 1:
        print("controls_rpg_move displacement: PASS")
    else:
        print("controls_rpg_move displacement: FAIL")
        checks.failures += 1
    checks.eq("controls_rpg_move", "t1500", "LowerState", 2)
    checks.eq("controls_rpg_stop", "t3000", "LowerState", 1)
    checks.eq("controls_rpg_select", "t0100", "TargetType", "hostile")
    checks.eq("controls_rpg_target_idle", "t0300", "TargetType", "hostile")
    checks.eq("controls_rpg_stale", "t0100", "TargetType", "hostile")
    checks.false("controls_rpg_stale", "t0100", "AttackOrder")
    checks.eq("controls_action", "t0500", "ActionMode", 1)
    checks.eq("controls_cursor", "t0000", "CursorVisible", 1)
    checks.eq("controls_cursor", "t0000", "CursorCentered", 1)
    checks.eq("controls_alt", "t0000", "AltPaused", 1)
    checks.eq("controls_alt", "t0000", "CursorVisible", 1)
    checks.eq("controls_alt_release", "t0000", "AltPaused", 0)
    checks.eq("controls_aim", "t0200", "AimActive", 1)
    checks.eq("controls_aim", "t0200", "CombatState", checks.value("controls_action", "t0500", "CombatState"))
    checks.eq("controls_aim", "t0200", "Distance", checks.value("controls_action", "t0500", "Distance"))
    checks.eq("controls_aim", "t0200", "MoveTarget", 3000)
    checks.eq("controls_aim", "t0200", "MoveRetarget", 200)
    checks.eq("controls_aim", "t0200", "MoveTick", 15)
    checks.eq("controls_attack", "t0100", "TargetType", "hostile")
    checks.eq("controls_attack", "t0100", "CombatState", 4)
    checks.eq("controls_ground", "t0000", "TargetType", checks.value("controls_ground", "t0100", "TargetType"))
    checks.eq("controls_ground", "t0000", "CombatState", checks.value("controls_ground", "t0100", "CombatState"))
    checks.eq("controls_alt_click", "t0000", "TargetType", checks.value("controls_alt_click", "t0100", "TargetType"))
    checks.eq("controls_alt_click", "t0000", "CombatState", checks.value("controls_alt_click", "t0100", "CombatState"))
    checks.eq("controls_rpg", "t0500", "ActionMode", 0)
    checks.eq("controls_rpg", "t0500", "AimActive", 0)
    checks.eq("controls_rpg", "t0500", "Fov", checks.value("controls_default", "t0000", "Fov"))
    checks.eq("controls_rpg", "t0500", "UpperState", 0)
    checks.eq("controls_rpg", "t0500", "LowerState", 1)
    checks.eq("controls_action", "t0500", "CooldownMs", checks.value("controls_default", "t0000", "CooldownMs"))
    _check_icons(checks)

    yaw = checks.value("controls_mouselook", "t0200", "CameraYaw")
    checks.eq("controls_mouselook", "t0200", "CameraYaw", yaw)
    checks.between("controls_mouselook", "t0200", "UnitFacing", yaw - 6, yaw + 6)
    turn_yaw = checks.value("controls_turn", "t0100", "CameraYaw")
    checks.between("controls_turn", "t0100", "UnitFacing", turn_yaw - 6, turn_yaw + 6)
    checks.eq("controls_turn", "t0100", "UpperState", 0)
    turn_starts = 0
    for text in ctx.anim_data.get("events", {}).values():
        if "kind=upper_start" not in str(text):
            continue
        if "clip=Turn" in str(text):
            turn_starts += 1
    if turn_starts == 0:
        print("controls_turn upper_start count: PASS")
    else:
        print(f"controls_turn upper_start count: got={turn_starts} want=0 FAIL")
        checks.failures += 1
    turn_frames = 0
    for text in ctx.frame_data.get("frames", {}).values():
        if " up=6 " in str(text) or " up=7 " in str(text):
            turn_frames += 1
    if turn_frames == 0:
        print("controls_turn upper frame count: PASS")
    else:
        print(f"controls_turn upper frame count: got={turn_frames} want=0 FAIL")
        checks.failures += 1
    checks.displacement("controls_move", "t0000", "t0600", 2)
    move_yaw = checks.value("controls_move", "t0600", "CameraYaw")
    checks.between("controls_move", "t0600", "UnitFacing", move_yaw - 6, move_yaw + 6)


def run_spec(launch_timeout_s: float, case_timeout_s: float, run_root: Path) -> TestRunSpec:
    return TestRunSpec(
        profile="controls",
        map_name="SCOBA.SC2Map",
        map_source=PROFILE_OUTPUTS["controls"],
        map_cache_name="SCOBA.SC2Map",
        bank_names=PROFILE_BANKS["controls"],
        ready_section="controls_default",
        ready_key="ControlsReady",
        launch_timeout_s=launch_timeout_s,
        case_timeout_s=case_timeout_s,
        run_root=run_root,
        on_ready=on_ready,
        check=check,
    )