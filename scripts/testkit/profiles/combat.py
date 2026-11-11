"""Combat test profile."""

from __future__ import annotations

import time
from pathlib import Path

from project_root import project_root

from ..map_builder import TestMapSpec
from ..runner import TestRunSpec
from .registry import PROFILE_BANKS, PROFILE_OUTPUTS

ROOT = project_root()


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
        init_calls=("gt_DbgTest_Init();",),
    )


def _bank_value(data: dict, section: str, key: str):
    return data.get(section, {}).get(key)


def on_ready(ctx, data: dict) -> None:
    from .. import input_driver

    input_driver.focus()
    point = input_driver.center_point()
    debug_bank = None
    from ..bank import find_latest_bank
    import os

    docs = Path(
        os.environ.get(
            "SC2_DOCUMENTS",
            str(Path.home() / "Games" / "battlenet-prefix/pfx/drive_c/users/steamuser/Documents/StarCraft II"),
        )
    )
    debug_bank = find_latest_bank(docs, "SCOBADBG", 0)
    if debug_bank is None:
        ctx.errors.append("real input: debug bank not found")
        return

    def read_debug() -> dict:
        from ..bank import read_bank
        return read_bank(debug_bank) or {}

    input_driver.click(*point)
    time.sleep(1.2)
    debug = read_debug()
    if debug.get("input", {}).get("leftDrag") != "no":
        ctx.errors.append(f"real input left drag: {debug.get('input', {}).get('leftDrag')}")
    if debug.get("input", {}).get("leftCancel") != "no":
        ctx.errors.append(f"real input left cancel: {debug.get('input', {}).get('leftCancel')}")

    input_driver.rclick(*point)
    time.sleep(1.2)
    debug = read_debug()
    if debug.get("input", {}).get("rightDrag") != "no":
        ctx.errors.append(f"real input right drag: {debug.get('input', {}).get('rightDrag')}")
    if debug.get("input", {}).get("rightCancel") != "no":
        ctx.errors.append(f"real input right cancel: {debug.get('input', {}).get('rightCancel')}")
    if debug.get("input", {}).get("rightRan") != "yes":
        ctx.errors.append(f"real input right ran: {debug.get('input', {}).get('rightRan')}")

    input_driver.ldrag(point[0] - 60, point[1], point[0] + 60, point[1])
    time.sleep(1.2)
    debug = read_debug()
    if debug.get("input", {}).get("leftDrag") != "yes":
        ctx.errors.append(f"real input left camera drag: {debug.get('input', {}).get('leftDrag')}")
    if int(debug.get("input", {}).get("leftDx") or 0) < 5:
        ctx.errors.append(f"real input left camera dx: {debug.get('input', {}).get('leftDx')}")
    if int(debug.get("input", {}).get("leftDy") or 0) != 0:
        ctx.errors.append(f"real input left camera dy: {debug.get('input', {}).get('leftDy')}")
    if debug.get("input", {}).get("leftCancel") != "no":
        ctx.errors.append(f"real input left camera cancel: {debug.get('input', {}).get('leftCancel')}")

    input_driver.rdrag(point[0] - 60, point[1], point[0] + 60, point[1])
    time.sleep(1.2)
    debug = read_debug()
    if debug.get("input", {}).get("rightDrag") != "yes":
        ctx.errors.append(f"real input right camera drag: {debug.get('input', {}).get('rightDrag')}")
    if int(debug.get("input", {}).get("rightDx") or 0) < 5:
        ctx.errors.append(f"real input right camera dx: {debug.get('input', {}).get('rightDx')}")
    if int(debug.get("input", {}).get("rightDy") or 0) != 0:
        ctx.errors.append(f"real input right camera dy: {debug.get('input', {}).get('rightDy')}")
    if debug.get("input", {}).get("rightCancel") != "no":
        ctx.errors.append(f"real input right camera cancel: {debug.get('input', {}).get('rightCancel')}")


def check(ctx, data: dict, checks) -> None:
    for error in ctx.errors:
        print(f"{error} FAIL")
        checks.failures += 1

    meta = data.get("meta", {})
    checks.eq("meta", "", "done", 1)
    print(f"done: {meta.get('done')}  anchor: ({meta.get('anchorX')},{meta.get('anchorY')})")
    engine = data.get("engine", {})
    print(
        f"engine entire bounds: ({engine.get('entire_min_x')},{engine.get('entire_min_y')}).."
        f"({engine.get('entire_max_x')},{engine.get('entire_max_y')})"
    )
    print(
        f"engine playable bounds: ({engine.get('play_min_x')},{engine.get('play_min_y')}).."
        f"({engine.get('play_max_x')},{engine.get('play_max_y')})"
    )
    grid = data.get("grid")
    if grid:
        print("pathing grid (33x33, 8..232 step 7):")
        for gy in range(33):
            print("  " + "".join("#" if grid.get(str(gy * 33 + gx)) == 1 else "." for gx in range(33)))

    checks.displacement("real_input", "t0000", "after")
    checks.between("camera_heading", "", "facing", 85, 95)

    checks.eq("startup", "t0000", "Auto", 0)
    checks.eq("startup", "t0000", "Stand", 1)
    checks.eq("startup", "t0000", "Root", 1)
    checks.true("startup", "t0000", "MoveSuppressed")
    checks.false("startup", "t0000", "AttackOrder")

    checks.eq("auto_off", "t0000", "Auto", 0)
    checks.false("auto_off", "t3000", "AttackOrder")
    checks.eq("auto_off", "t0000", "EnemyHp", checks.value("auto_off", "t3000", "EnemyHp"))
    checks.displacement("auto_off", "t0000", "t3000", minimum=0)
    if checks.value("auto_off", "t0000", "HeroX") is not None and checks.value("auto_off", "t3000", "HeroX") is not None:
        if abs(checks.value("auto_off", "t3000", "HeroX") - checks.value("auto_off", "t0000", "HeroX")) + abs(
            checks.value("auto_off", "t3000", "HeroY") - checks.value("auto_off", "t0000", "HeroY")
        ) > 1:
            print("auto_off displacement: want<=1 FAIL")
            checks.failures += 1

    checks.eq("stand_in", "t0000", "Stand", 1)
    checks.eq("stand_in", "t0000", "Root", 1)
    checks.true("stand_in", "t0000", "MoveSuppressed")
    checks.true("stand_in", "t0500", "AttackOrder")
    checks.damage("stand_in", "t0000", "t2500")
    checks.displacement("stand_in", "t0000", "t2500", minimum=0)
    if abs(
        (checks.value("stand_in", "t2500", "HeroX") or 0) - (checks.value("stand_in", "t0000", "HeroX") or 0)
    ) + abs(
        (checks.value("stand_in", "t2500", "HeroY") or 0) - (checks.value("stand_in", "t0000", "HeroY") or 0)
    ) > 1:
        print("stand_in displacement: want<=1 FAIL")
        checks.failures += 1

    checks.eq("stand_out", "t2500", "Root", 1)
    checks.true("stand_out", "t2500", "MoveSuppressed")
    checks.displacement("stand_out", "t0000", "t2500", minimum=0)
    if abs(
        (checks.value("stand_out", "t2500", "HeroX") or 0) - (checks.value("stand_out", "t0000", "HeroX") or 0)
    ) + abs(
        (checks.value("stand_out", "t2500", "HeroY") or 0) - (checks.value("stand_out", "t0000", "HeroY") or 0)
    ) > 1:
        print("stand_out displacement: want<=1 FAIL")
        checks.failures += 1

    checks.eq("stand_outside", "t2000", "Root", 1)
    checks.true("stand_outside", "t2000", "MoveSuppressed")
    checks.false("stand_outside", "t2000", "AttackOrder")
    checks.displacement("stand_outside", "t0000", "t2000", minimum=0)
    if abs(
        (checks.value("stand_outside", "t2000", "HeroX") or 0) - (checks.value("stand_outside", "t0000", "HeroX") or 0)
    ) + abs(
        (checks.value("stand_outside", "t2000", "HeroY") or 0) - (checks.value("stand_outside", "t0000", "HeroY") or 0)
    ) > 1:
        print("stand_outside displacement: want<=1 FAIL")
        checks.failures += 1

    checks.eq("stand_auto_off", "t0000", "Auto", 0)
    checks.eq("stand_auto_off", "t0000", "Root", 1)
    checks.true("stand_auto_off", "t0000", "MoveSuppressed")
    checks.eq("stand_auto_off", "t2000", "Root", 1)
    checks.displacement("stand_auto_off", "t0000", "t2000", minimum=0)
    if abs(
        (checks.value("stand_auto_off", "t2000", "HeroX") or 0) - (checks.value("stand_auto_off", "t0000", "HeroX") or 0)
    ) + abs(
        (checks.value("stand_auto_off", "t2000", "HeroY") or 0) - (checks.value("stand_auto_off", "t0000", "HeroY") or 0)
    ) > 1:
        print("stand_auto_off displacement: want<=1 FAIL")
        checks.failures += 1

    checks.eq("stand_wake_manual", "t0200", "Root", 0)
    checks.eq("stand_wake_manual", "t1000", "Root", 1)
    checks.eq("stand_wake_manual", "t2000", "Root", 1)
    checks.displacement("stand_wake_manual", "t0000", "t2000", minimum=0)
    if abs(
        (checks.value("stand_wake_manual", "t2000", "HeroX") or 0) - (checks.value("stand_wake_manual", "t0000", "HeroX") or 0)
    ) + abs(
        (checks.value("stand_wake_manual", "t2000", "HeroY") or 0) - (checks.value("stand_wake_manual", "t0000", "HeroY") or 0)
    ) > 1:
        print("stand_wake_manual displacement: want<=1 FAIL")
        checks.failures += 1

    checks.true("right_click", "", "ran")
    checks.true("right_click", "t0200", "AttackOrder")
    checks.true("right_click", "t0200", "TargetEnemy")
    checks.eq("right_click", "t0200", "Root", 1)

    checks.false("right_drag", "", "ran")
    checks.false("right_drag", "t0000", "AttackOrder")
    checks.false("right_drag", "t0500", "AttackOrder")
    checks.eq("right_drag", "t0000", "Root", 1)

    checks.true("right_point", "", "pickValid")

    checks.true("right_ground_walk", "", "ran")
    checks.displacement("right_ground_walk", "t0000", "t1000")

    checks.true("right_ground_stand", "", "ran")
    checks.eq("right_ground_stand", "t0500", "Root", 1)
    checks.displacement("right_ground_stand", "t0000", "t0500", minimum=0)
    if abs(
        (checks.value("right_ground_stand", "t0500", "HeroX") or 0) - (checks.value("right_ground_stand", "t0000", "HeroX") or 0)
    ) + abs(
        (checks.value("right_ground_stand", "t0500", "HeroY") or 0) - (checks.value("right_ground_stand", "t0000", "HeroY") or 0)
    ) > 1:
        print("right_ground_stand displacement: want<=1 FAIL")
        checks.failures += 1

    checks.true("right_target_kept", "t0200", "TargetEnemy")
    checks.true("both_forward", "tkey", "Forward")
    checks.false("both_forward", "tmouse", "Forward")

    checks.displacement("walk_ground", "t0000", "t1000")
    checks.eq("stand_ground", "t1000", "Root", 1)
    checks.displacement("stand_ground", "t0000", "t1000", minimum=0)
    if abs(
        (checks.value("stand_ground", "t1000", "HeroX") or 0) - (checks.value("stand_ground", "t0000", "HeroX") or 0)
    ) + abs(
        (checks.value("stand_ground", "t1000", "HeroY") or 0) - (checks.value("stand_ground", "t0000", "HeroY") or 0)
    ) > 1:
        print("stand_ground displacement: want<=1 FAIL")
        checks.failures += 1

    checks.eq("move_wake", "t0000", "Root", 1)
    checks.true("move_wake", "t0000", "MoveSuppressed")
    checks.eq("move_wake", "t0200", "Root", 0)
    checks.false("move_wake", "t0200", "MoveSuppressed")
    checks.displacement("move_wake", "t0000", "t1200")
    checks.eq("move_wake", "t2200", "Root", 1)

    checks.eq("walk_chase", "t0000", "Root", 0)
    checks.false("walk_chase", "t0000", "MoveSuppressed")
    checks.decrease("walk_chase", "t0000", "t3000", "Distance")
    checks.true("walk_chase", "t3000", "AttackOrder")
    checks.damage("walk_chase", "t0000", "t3000")

    checks.eq("walk_idle", "t0000", "Root", 0)
    checks.false("walk_idle", "t2000", "AttackOrder")
    checks.displacement("walk_idle", "t0000", "t2000", minimum=0)
    if abs(
        (checks.value("walk_idle", "t2000", "HeroX") or 0) - (checks.value("walk_idle", "t0000", "HeroX") or 0)
    ) + abs(
        (checks.value("walk_idle", "t2000", "HeroY") or 0) - (checks.value("walk_idle", "t0000", "HeroY") or 0)
    ) > 1:
        print("walk_idle displacement: want<=1 FAIL")
        checks.failures += 1

    checks.eq("weapon", "t0000", "CooldownMs", 0)
    checks.false("weapon", "t0000", "CmdCooldown")
    cooldown = checks.value("weapon", "t0500", "CooldownMs")
    if cooldown is None or cooldown <= 0:
        print(f"weapon t0500 CooldownMs: got={cooldown} want>0 FAIL")
        checks.failures += 1
    checks.true("weapon", "t0500", "CmdCooldown")


def run_spec(launch_timeout_s: float, case_timeout_s: float, run_root: Path) -> TestRunSpec:
    return TestRunSpec(
        profile="combat",
        map_name="SCOBA.SC2Map",
        map_source=PROFILE_OUTPUTS["combat"],
        map_cache_name="SCOBA.SC2Map",
        bank_names=PROFILE_BANKS["combat"],
        ready_section="real_input",
        ready_key="ready",
        launch_timeout_s=launch_timeout_s,
        case_timeout_s=case_timeout_s,
        run_root=run_root,
        on_ready=on_ready,
        check=check,
    )