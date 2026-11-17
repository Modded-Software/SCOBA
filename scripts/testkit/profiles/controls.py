"""Controls test profile."""

from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from pathlib import Path

from project_root import project_root

from ..map_builder import TestMapSpec
from ..runner import TestRunSpec
from .bank_checks import _report
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
    time.sleep(1.9)


def _check_icons(checks) -> None:
    from control_mode_icons import ICONS

    if len(set(ICONS.values())) != len(ICONS):
        print("controls_icons: icons match FAIL")
        checks.failures += 1
    else:
        print("controls_icons: icons differ PASS")
    button_path = PROFILE_OUTPUTS["controls"] / "Base.SC2Data" / "GameData" / "ButtonData.xml"
    buttons = {element.get("id"): element for element in ET.parse(button_path).getroot().iter("CButton")}
    for button_id, icon_path in ICONS.items():
        icon = buttons[button_id].find("Icon")
        if icon is not None and icon.get("value") == icon_path:
            print(f"controls_icons: {button_id} PASS")
        else:
            print(f"controls_icons: {button_id} FAIL")
            checks.failures += 1


def _check_distances(checks) -> None:
    """Zoom and camera collision, read in thousandths: the Tosh arm is 1.5,
    so whole units hide a clamp to about 1.15. Reported to summary.txt."""
    def dist(section: str, tag: str):
        return checks.value(section, tag, "Distance1000")

    base = dist("controls_default", "t0000")
    zoom = dist("controls_zoom", "t0100")
    flat = dist("controls_collision", "t0200")
    clamp = dist("controls_collision_clamp", "t0500")
    restore = dist("controls_collision_restore", "t0800")
    raw = f"base={base} zoom={zoom} flat={flat} clamp={clamp} restore={restore} (raw: clampPitch={checks.value('controls_collision_clamp', 't0500', 'Pitch')})"
    have = None not in (base, zoom, flat, clamp, restore)
    _report(checks, "controls_zoom animated distance", have and zoom - base >= 750, raw)
    _report(checks, "controls_collision flat distance", have and abs(flat - base) <= 50, raw)
    # Looking up at pitch -60 puts the unclamped eye under the ground margin.
    _report(checks, "controls_collision_clamp distance", have and clamp <= flat - 100, raw)
    _report(checks, "controls_collision_restore distance", have and abs(restore - flat) <= 50, raw)


def check(ctx, data: dict, checks) -> None:
    for error in ctx.errors:
        print(f"{error} FAIL")
        checks.failures += 1
    
    

    checks.eq("meta", "", "done", 1)
    checks.eq("meta", "", "profile", "controls")
    checks.eq("controls_default", "t0000", "TpsMode", 0)
    checks.eq("controls_default", "t0000", "ControlRelative", 0)
    checks.eq("controls_default", "t0000", "RotateUnit", 0)
    checks.eq("controls_default", "t0000", "RotateCamera", 0)
    # Synthetic pointer warps do not emit mouse-moved events; hover is checked live.
    checks.eq("controls_pnc_hold", "t0800", "AimActive", 0)
    checks.eq("controls_pnc_hold", "t0800", "Fov", checks.value("controls_default", "t0000", "Fov"))
    move_dx = (checks.value("controls_pnc_move", "t1500", "HeroX") or 0) - (checks.value("controls_pnc_hold", "t0800", "HeroX") or 0)
    move_dy = (checks.value("controls_pnc_move", "t1500", "HeroY") or 0) - (checks.value("controls_pnc_hold", "t0800", "HeroY") or 0)
    if abs(move_dx) + abs(move_dy) >= 1:
        print("controls_pnc_move displacement: PASS")
    else:
        print("controls_pnc_move displacement: FAIL")
        checks.failures += 1
    # SPEC-PNC 5.8: without a right hold the script sets no lower clip, so the
    # engine plays its stock walk and stand. Negative case: no script clip.
    checks.eq("controls_pnc_move", "t1500", "LowerState", 0)
    checks.eq("controls_pnc_stop", "t3000", "LowerState", 0)
    checks.eq("controls_pnc_select", "t0100", "TargetType", "hostile")
    checks.eq("controls_pnc_target_idle", "t0300", "TargetType", "hostile")
    # R-PNC-28: a right click on the ground cancels. The UI target clears.
    checks.eq("controls_pnc_cancel", "t0100", "TargetType", "none")
    checks.false("controls_pnc_cancel", "t0100", "AttackOrder")
    checks.eq("controls_tps", "t0500", "TpsMode", 1)
    checks.false("controls_cursor", "t0000", "CursorVisible")
    checks.false("controls_cursor", "t0000", "MiddleHold")
    checks.eq("controls_cursor", "t0000", "ControlRelative", 1)
    checks.true("controls_middle", "t0000", "MiddleHold")
    checks.true("controls_middle", "t0000", "CursorVisible")
    checks.eq("controls_middle", "t0000", "ControlRelative", 0)
    checks.false("controls_middle_release", "t0000", "MiddleHold")
    checks.false("controls_middle_release", "t0000", "CursorVisible")
    checks.eq("controls_aim", "t0200", "AimActive", 1)
    checks.eq("controls_aim", "t0200", "AttackOrder", checks.value("controls_tps", "t0500", "AttackOrder"))
    checks.eq("controls_aim", "t0200", "Distance", checks.value("controls_tps", "t0500", "Distance"))
    checks.eq("controls_aim", "t0200", "MoveTarget", 3000)
    checks.eq("controls_aim", "t0200", "MoveRetarget", 200)
    checks.eq("controls_aim", "t0200", "MoveTick", 15)
    # The aim camera offset is asserted in the tps profile (tps_aim
    # AnchorRight100). CameraGetTarget is not used here: it read (12, 8) in
    # every snapshot of controls/20261114-210626 while the hero stood near
    # (184, 192), so it does not follow the hero camera.
    # R-PNC-45 with R-TPS-81: during a middle hold the attack command acts as
    # in PNC. One shot lands on the in-range enemy.
    checks.true("controls_attack", "t0000", "MiddleHold")
    checks.true("controls_attack", "t0000", "InRange")
    checks.eq("controls_attack", "t0000", "EnemyHp", 500)
    checks.eq("controls_attack", "tshot", "TargetType", "hostile")
    checks.true("controls_attack", "tshot", "ShotSeen")
    checks.lt("controls_attack", "tshot", "EnemyHp", 500)
    checks.eq("controls_ground", "t0000", "TargetType", checks.value("controls_ground", "t0100", "TargetType"))
    checks.eq("controls_ground", "t0000", "AttackOrder", checks.value("controls_ground", "t0100", "AttackOrder"))
    checks.eq("controls_middle_click", "t0000", "TargetType", checks.value("controls_middle_click", "t0100", "TargetType"))
    checks.eq("controls_middle_click", "t0000", "AttackOrder", checks.value("controls_middle_click", "t0100", "AttackOrder"))
    checks.eq("controls_pnc", "t0500", "TpsMode", 0)
    checks.eq("controls_pnc", "t0500", "AimActive", 0)
    checks.eq("controls_pnc", "t0500", "Fov", checks.value("controls_default", "t0000", "Fov"))
    checks.eq("controls_pnc", "t0500", "UpperState", 0)
    checks.eq("controls_pnc", "t0500", "LowerState", 0)
    checks.eq("controls_tps", "t0500", "CooldownMs", checks.value("controls_default", "t0000", "CooldownMs"))
    _check_distances(checks)
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
    # Upper state 6 is c_ANIM_UPPER_ATTACK. The one shot in controls_attack is
    # the only attack in this profile, so the state shows up, and only briefly.
    # Script state only: the look of the attack clip is an operator check.
    attack_frames = 0
    for text in ctx.frame_data.get("frames", {}).values():
        if " up=6 " in str(text):
            attack_frames += 1
    if 0 < attack_frames <= 40:
        print(f"controls_attack upper attack frames: {attack_frames} PASS")
    else:
        print(f"controls_attack upper attack frames: got={attack_frames} want=1..40 FAIL")
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