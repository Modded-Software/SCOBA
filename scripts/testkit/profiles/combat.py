"""WASD / Point & Click combat profile.

Every check reads the test bank. Nothing here needs visual inspection.
"""

from __future__ import annotations

import math
import os
from pathlib import Path

from project_root import project_root

from ..map_builder import TestMapSpec
from ..runner import TestRunSpec
from .registry import PROFILE_BANKS, PROFILE_OUTPUTS

ROOT = project_root()

GROUPS = ("idle", "single", "auto", "cancel", "wasd", "hold", "button", "switch", "kerrigan")


def selected_group() -> str:
    """One scenario group for a fast run, or `all` for the full suite."""
    group = os.environ.get("SC2_TEST_GROUP", "all")
    if group != "all" and group not in GROUPS:
        raise SystemExit(f"unknown combat group: {group}; choose all or one of {', '.join(GROUPS)}")
    return group


def map_spec() -> TestMapSpec:
    return TestMapSpec(
        profile="combat",
        source=ROOT / "out" / "SCOBA256.SC2Map",
        output=PROFILE_OUTPUTS["combat"],
        bank_names=PROFILE_BANKS["combat"],
        galaxy_files=(
            ROOT / "scripts" / "testkit" / "galaxy" / "common.galaxy",
            ROOT / "scripts" / "testkit" / "galaxy" / "combat.galaxy",
        ),
        galaxy_includes=(
            "scripts/test/combat/common",
            "scripts/test/combat/combat",
        ),
        init_calls=(f'gv_dbgGroup = "{selected_group()}";', "gt_DbgTest_Init();"),
    )


def on_ready(ctx, data: dict) -> None:
    return


def _report(checks, name: str, ok: bool, detail: str) -> None:
    status = "PASS" if ok else "FAIL"
    print(f"{name}: {detail} {status}")
    checks.results.append(
        {"section": name, "tag": "", "key": "", "got": detail, "want": "", "status": status}
    )
    if not ok:
        checks.failures += 1


def _delta(checks, section: str, tag_a: str, tag_b: str, key: str):
    before = checks.value(section, tag_a, key)
    after = checks.value(section, tag_b, key)
    if before is None or after is None:
        return None
    return after - before


def _still(checks, section: str, tag_a: str, tag_b: str) -> None:
    dx = _delta(checks, section, tag_a, tag_b, "HeroX")
    dy = _delta(checks, section, tag_a, tag_b, "HeroY")
    ok = dx is not None and dy is not None and abs(dx) + abs(dy) <= 1
    _report(checks, f"{section} hero still", ok, f"dx={dx} dy={dy}")


def _no_damage(checks, section: str, tag_a: str, tag_b: str) -> None:
    delta = _delta(checks, section, tag_a, tag_b, "EnemyHp")
    _report(checks, f"{section} {tag_a}->{tag_b} no damage", delta == 0, f"hpDelta={delta}")


def _shots(checks, section: str, tag_a: str, tag_b: str, want: int) -> None:
    delta = _delta(checks, section, tag_a, tag_b, "Shots")
    _report(checks, f"{section} {tag_a}->{tag_b} shots", delta == want, f"got={delta} want={want}")


def _buttons_match(checks, data: dict) -> None:
    """R-PNC-48: in every snapshot each toggle button shows the hero state."""
    count = 0
    bad = []
    for section, values in data.items():
        for key, auto in values.items():
            if not key.endswith("Auto") or key == "auto":
                continue
            tag = key[: -len("Auto")]
            attack = values.get(tag + "AttackBtnSingle")
            chase = values.get(tag + "ChaseBtnStand")
            stand = values.get(tag + "Stand")
            if attack is None or chase is None or stand is None:
                continue
            count += 1
            if bool(attack) == bool(auto) or bool(chase) != (stand > 0):
                bad.append(f"{section}.{tag}")
    ok = count > 0 and not bad
    _report(checks, "toggle buttons match hero state", ok, f"snapshots={count} mismatches={bad[:6]}")


def _button_after_shot(checks, section: str) -> None:
    """R-PNC-46: a shot the engine started on its own sets the button cooldown."""
    checks.true(section, "tshot", "ShotSeen")
    checks.gt(section, "tshot", "ButtonCdMs", 0)


def _single_shots(checks, section: str, damage: bool = True) -> None:
    """One command gives one full shot. Three commands give three."""
    _shots(checks, section, "t0000", "t1500", 1)
    _shots(checks, section, "t1500", "t4000", 0)
    _shots(checks, section, "t0000", "t8000", 3)
    checks.false(section, "t1500", "AttackOrder")
    checks.false(section, "t4000", "AttackOrder")
    checks.false(section, "t8000", "AttackOrder")
    one = _delta(checks, section, "t0000", "t4000", "EnemyHp")
    three = _delta(checks, section, "t0000", "t8000", "EnemyHp")
    # The target regenerates about one point between snapshots.
    if damage:
        ok = one is not None and three is not None and one < 0 and abs(three - 3 * one) <= 4
        _report(checks, f"{section} damage per shot", ok, f"one={one} three={three}")
    checks.gt(section, "t0500", "CooldownMs", 0)
    checks.gt(section, "t0500", "ButtonCdMs", 0)
    checks.eq(section, "t4000", "ButtonCdMs", 0)
    checks.eq(section, "t4000", "CooldownMs", 0)
    _still(checks, section, "t0000", "t8000")


def check(ctx, data: dict, checks) -> None:
    for error in ctx.errors:
        print(f"{error} FAIL")
        checks.failures += 1

    checks.eq("meta", "", "done", 1)

    # Real mouse input makes the run invalid.
    checks.eq("done", "tend", "RealClicks", 0)

    # R-PNC-47: defaults. R-PNC-48: the buttons show them.
    checks.false("startup", "t0000", "Auto")
    checks.eq("startup", "t0000", "Stand", 1)
    checks.eq("startup", "t0000", "Root", 1)
    checks.true("startup", "t0000", "AttackBtnSingle")
    checks.true("startup", "t0000", "ChaseBtnStand")
    _buttons_match(checks, data)

    group = selected_group()
    print(f"group: {group}")
    for name in GROUPS:
        if group in ("all", name):
            GROUP_CHECKS[name](checks)


def _check_idle(checks) -> None:
    # R-PNC-41: single never acquires.
    checks.true("single_idle", "t0000", "InRange")
    checks.false("single_idle", "tend", "AttackOrder")
    _no_damage(checks, "single_idle", "t0000", "tend")
    _shots(checks, "single_idle", "t0000", "tend", 0)
    _still(checks, "single_idle", "t0000", "tend")

    # R-PNC-41, R-PNC-15: no retaliation; the attacker is the UI target.
    # The UI target is set by the engine attacked event, so it proves the hit.
    checks.false("single_attacked", "tend", "AttackOrder")
    checks.false("single_attacked", "tend", "SinglePending")
    _no_damage(checks, "single_attacked", "t0000", "tend")
    _shots(checks, "single_attacked", "t0000", "tend", 0)
    checks.true("single_attacked", "tend", "TargetEnemy")
    _still(checks, "single_attacked", "t0000", "tend")


def _check_single(checks) -> None:
    checks.true("single_shot", "t0000", "HeroIsTosh")
    # R-PNC-21, R-PNC-46: one shot per command; the button cooldown runs.
    # The button cooldown is set by data on each shot. Its clock overlay is an
    # operator check.
    _single_shots(checks, "single_shot")

    # R-PNC-24: stand, out of range.
    checks.false("single_out_stand", "t0000", "InRange")
    checks.false("single_out_stand", "tend", "AttackOrder")
    checks.true("single_out_stand", "tend", "TargetEnemy")
    _no_damage(checks, "single_out_stand", "t0000", "tend")
    _still(checks, "single_out_stand", "t0000", "tend")

    # R-PNC-23 with single: walk in, one shot, idle.
    checks.decrease("single_out_move", "t0000", "t5000", "Distance")
    _shots(checks, "single_out_move", "t0000", "t5000", 1)
    _shots(checks, "single_out_move", "t5000", "tend", 0)
    checks.false("single_out_move", "tend", "AttackOrder")


def _check_auto(checks) -> None:
    # R-PNC-22: auto repeats a commanded attack.
    repeat = _delta(checks, "auto_click", "t0000", "tend", "Shots")
    _report(checks, "auto_click repeats", repeat is not None and repeat >= 3, f"shots={repeat}")
    checks.true("auto_click", "tend", "TargetEnemy")
    _button_after_shot(checks, "auto_click")

    # R-PNC-40, R-PNC-51: auto, stand.
    checks.damage("auto_stand_in", "t0000", "tend")
    _still(checks, "auto_stand_in", "t0000", "tend")
    _button_after_shot(checks, "auto_stand_in")
    checks.false("auto_stand_out", "t0000", "InRange")
    _no_damage(checks, "auto_stand_out", "t0000", "tend")
    _still(checks, "auto_stand_out", "t0000", "tend")

    # R-PNC-52: auto, move.
    checks.false("auto_move_near", "t0000", "InRange")
    checks.decrease("auto_move_near", "t0000", "tend", "Distance")
    checks.damage("auto_move_near", "t0000", "tend")
    far = _delta(checks, "auto_move_far", "t0000", "tend", "Distance")
    print(f"auto_move_far distance delta (info, engine scan range): {far}")

    # R-PNC-43: the toggle ability switches to single and stops the attack.
    checks.true("auto_to_single", "t0000", "Auto")
    checks.false("auto_to_single", "t0000", "AttackBtnSingle")
    checks.true("auto_to_single", "t1000", "AttackBtnSingle")
    checks.false("auto_to_single", "tback", "AttackBtnSingle")
    checks.false("auto_to_single", "t1000", "Auto")
    checks.false("auto_to_single", "t1000", "AttackOrder")
    _shots(checks, "auto_to_single", "t1000", "tend", 0)
    print(
        "auto_to_single raw: endSeenTicks="
        f"{checks.value('auto_to_single', '', 'endSeenTicks')}"
        f" endOrderCount={checks.value('auto_to_single', '', 'endOrderCount')}"
    )
    checks.true("auto_to_single", "tback", "Auto")


def _check_cancel(checks) -> None:
    # R-PNC-30: cancel.
    checks.true("cancel", "t0000", "AttackOrder")
    checks.true("cancel", "t0000", "TargetEnemy")
    checks.false("cancel", "tend", "AttackOrder")
    checks.true("cancel", "tend", "TargetNone")
    checks.false("cancel", "tend", "SinglePending")
    _no_damage(checks, "cancel", "t0000", "tend")

    # R-PNC-25, R-PNC-27, R-PNC-28: right click on the ground.
    checks.true("ground_move", "t0000", "TargetEnemy")
    checks.true("ground_move", "tend", "TargetNone")
    checks.displacement("ground_move", "t0000", "tend")
    checks.true("ground_stand", "tend", "TargetNone")
    _still(checks, "ground_stand", "t0000", "tend")


def _check_wasd(checks) -> None:
    # R-PNC-53: WASD moves in stand; the root returns on release.
    checks.eq("wasd_stand", "t0000", "Root", 1)
    checks.displacement("wasd_stand", "t0000", "tend")
    checks.eq("wasd_stand", "tend", "Root", 1)

    # R-PNC-54: the engine fires while WASD moves the hero.
    checks.displacement("move_fire_auto", "t0000", "tend")
    checks.damage("move_fire_auto", "t0000", "tend")
    checks.displacement("move_fire_single", "t0000", "tend")
    _no_damage(checks, "move_fire_single", "t0000", "tend")


def _yaw_off(checks, section: str, tag: str) -> float | None:
    facing = checks.value(section, tag, "Facing")
    yaw = checks.value(section, tag, "CamYaw")
    if facing is None or yaw is None:
        return None
    return abs((facing - yaw + 180) % 360 - 180)


def _walk_scale(checks, section: str, tag: str) -> None:
    """Strafe walk clips play at unit speed / WalkAnimMoveSpeed, as the stock walk does."""
    scale = checks.value(section, tag, "WalkScale1000") or 0
    speed = checks.value(section, tag, "UnitSpeed1000") or 0
    walk = checks.value(section, tag, "WalkAnim1000") or 0
    want = speed * 1000 / walk if walk else 0
    ok = walk > 0 and speed > 0 and abs(scale - want) <= 20
    _report(checks, f"{section} {tag} walk clip rate", ok, f"scale={scale} speed={speed} walk={walk} want={want:.0f}")


def _hold_match(checks, middle: str, right: str) -> None:
    """A right hold walks forward and turns as a middle hold does."""
    for tag in ("t0000", "tturn"):
        # No lower override: the engine plays the stock walk under both holds.
        checks.eq(middle, tag, "FullState", 0)
        checks.eq(right, tag, "FullState", 0)
    for key, rel, floor in (("Dist1000", 0.05, 0), ("MinStep1000", 0.15, 0), ("MaxOff10", 0.0, 20)):
        a = checks.value(middle, "", key)
        b = checks.value(right, "", key)
        ok = a is not None and b is not None and abs(a - b) <= max(floor, rel * a)
        _report(checks, f"{right} {key} matches {middle}", ok, f"middle={a} right={b}")
    dist = checks.value(middle, "", "Dist1000")
    _report(checks, f"{middle} walks", dist is not None and dist >= 1500, f"dist1000={dist}")


def _hold_turn(checks, section: str, strafe: bool = True) -> None:
    """Camera turns during a hold walk: facing follows, the hero keeps moving."""
    turned = checks.value(section, "", "YawTurned")
    off = checks.value(section, "", "MaxOff10")
    step = checks.value(section, "", "MinStep1000")
    _report(checks, f"{section} camera turned", turned is not None and turned >= 80, f"turned={turned}")
    _report(checks, f"{section} facing follows the camera", off is not None and off <= 60, f"max_off10={off}")
    _report(checks, f"{section} no stall while turning", step is not None and step >= 50, f"min_step1000={step}")
    checks.true(section, "tturn", "MoveOrder")
    if strafe:
        _walk_scale(checks, section, "tturn")
    checks.false(section, "tend", "MoveOrder")
    checks.eq(section, "tend", "NoTurn", 0)


def _hold_move(checks, section: str, want_forward: int, want_left: int, lower: int, direction: int) -> None:
    """R-PNC-64, R-PNC-65: facing stays on the camera yaw; the hero moves on the input axis."""
    start = _yaw_off(checks, section, "t0000")
    _report(checks, f"{section} starts turned away", start is not None and start >= 90, f"off={start}")
    checks.true(section, "thold", "HoldStrafe")
    checks.eq(section, "thold", "NoTurn", 1)
    for tag in ("thold", "tmove"):
        off = _yaw_off(checks, section, tag)
        _report(checks, f"{section} {tag} facing on camera yaw", off is not None and off <= 15, f"off={off}")
    yaw = math.radians(checks.value(section, "tmove", "CamYaw") or 0)
    dx = (_delta(checks, section, "thold", "tmove", "HeroX10") or 0) / 10
    dy = (_delta(checks, section, "thold", "tmove", "HeroY10") or 0) / 10
    forward = dx * math.cos(yaw) + dy * math.sin(yaw)
    left = -dx * math.sin(yaw) + dy * math.cos(yaw)
    # On the wanted axis at least 1.5 in the wanted direction. Off it under 1.
    ok = True
    for got, want in ((forward, want_forward), (left, want_left)):
        ok = ok and (got * want >= 1.5 if want else abs(got) < 1.0)
    _report(checks, f"{section} moves on the input axis", ok, f"forward={forward:.1f} left={left:.1f}")
    checks.eq(section, "tmove", "LowerState", lower)
    checks.eq(section, "tmove", "AimDir", direction)
    _walk_scale(checks, section, "tmove")
    # AC-PNC-24: releasing leaves no order. The root returns in Chase stand.
    checks.false(section, "tstop", "MoveOrder")
    checks.false(section, "tend", "HoldStrafe")
    checks.eq(section, "tend", "NoTurn", 0)
    checks.false(section, "tend", "MoveOrder")
    checks.false(section, "tend", "AttackOrder")
    checks.eq(section, "tend", "Root", 1)


def _check_hold(checks) -> None:
    # Lower state 3 is walk back, 2 is walk. Direction 4 is back, 2 is left.
    _hold_move(checks, "hold_right_back", -1, 0, 3, 4)
    _hold_move(checks, "hold_right_left", 0, 1, 2, 2)
    _hold_turn(checks, "hold_right_turn")
    _hold_turn(checks, "hold_middle_fwd", strafe=False)
    _hold_turn(checks, "hold_right_fwd", strafe=False)
    _hold_match(checks, "hold_middle_fwd", "hold_right_fwd")

    # R-PNC-62, R-PNC-63: a middle hold is not a strafe hold.
    for tag in ("tmiddle", "tboth", "tend"):
        checks.false("hold_middle", tag, "HoldStrafe")
        checks.eq("hold_middle", tag, "NoTurn", 0)


def _check_button(checks) -> None:
    checks.eq("done", "tend", "StatusExecs", 2)
    # R-PNC-45, R-PNC-46: Weapon Attack button.
    _shots(checks, "weapon_button", "t0000", "tend", 1)
    checks.damage("weapon_button", "t0000", "tend")
    checks.gt("weapon_button", "t0500", "ButtonCdMs", 0)
    checks.eq("weapon_button", "tend", "ButtonCdMs", 0)
    checks.gt("weapon_button", "t0500", "CooldownMs", 0)
    checks.eq("weapon_button", "tend", "CooldownMs", 0)
    checks.false("weapon_button", "tend", "AttackOrder")

    # R-PNC-49: a press that fires no shot starts no cooldown.
    checks.false("button_out", "t0000", "InRange")
    _shots(checks, "button_out", "t0000", "tend", 0)
    _no_damage(checks, "button_out", "t0000", "tend")
    checks.eq("button_out", "tend", "ButtonCdMs", 0)
    checks.true("button_out", "tend", "TargetEnemy")
    _still(checks, "button_out", "t0000", "tend")


def _check_switch(checks) -> None:
    # R-PNC-44: hero switch keeps both toggles.
    checks.false("switch_single_stand", "tend", "Auto")
    checks.eq("switch_single_stand", "tend", "Stand", 1)
    checks.false("switch_single_stand", "tend", "HeroIsTosh")
    checks.true("switch_single_stand", "tend", "AttackBtnSingle")
    checks.true("switch_single_stand", "tend", "ChaseBtnStand")
    checks.false("switch_auto_move", "tend", "HeroIsTosh")
    checks.true("switch_auto_move", "tend", "Auto")
    checks.eq("switch_auto_move", "tend", "Stand", 0)
    checks.false("switch_auto_move", "tend", "AttackBtnSingle")
    checks.false("switch_auto_move", "tend", "ChaseBtnStand")


def _check_kerrigan(checks) -> None:
    checks.false("talons_single", "t0000", "HeroIsTosh")
    # Kerrigan weapons: one full shot per command.
    _single_shots(checks, "talons_single", damage=False)
    _single_shots(checks, "psiblast_single")
    _button_after_shot(checks, "talons_auto")


GROUP_CHECKS = {
    "idle": _check_idle,
    "single": _check_single,
    "auto": _check_auto,
    "cancel": _check_cancel,
    "wasd": _check_wasd,
    "hold": _check_hold,
    "button": _check_button,
    "switch": _check_switch,
    "kerrigan": _check_kerrigan,
}


def run_spec(launch_timeout_s: float, case_timeout_s: float, run_root: Path) -> TestRunSpec:
    return TestRunSpec(
        profile="combat",
        map_name="SCOBA.SC2Map",
        map_source=PROFILE_OUTPUTS["combat"],
        map_cache_name="SCOBA.SC2Map",
        bank_names=PROFILE_BANKS["combat"],
        ready_section="meta",
        ready_key="ready",
        launch_timeout_s=launch_timeout_s,
        case_timeout_s=case_timeout_s,
        run_root=run_root,
        on_ready=on_ready,
        check=check,
    )
