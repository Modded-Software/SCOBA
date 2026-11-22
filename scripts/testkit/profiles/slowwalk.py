"""Slow walk on Shift profile (REQ-SLOW-WALK).

Every check reads the test bank: engine travel, behaviors, orders, facing,
and the animation and jump script state. How the legs look is an operator
check (AC-SLOW-1..4).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from project_root import project_root

from ..map_builder import TestMapSpec
from ..runner import TestRunSpec
from .registry import PROFILE_BANKS, PROFILE_OUTPUTS

ROOT = project_root()
SLOW_CORE = ROOT / "src" / "SCOBA.SC2Map" / "scripts" / "app" / "core" / "slow_walk.galaxy"
GROUPS = ("walk", "mode", "hero", "jump")
SECTIONS = {
    "walk": ("slow_free", "slow_pnc"),
    "mode": ("slow_strafe", "slow_back", "slow_aim"),
    "hero": ("slow_kerrigan", "slow_switch", "slow_intro"),
    "jump": ("slow_jump_aim", "slow_jump_pnc"),
}
# R-SLOW-2, 3, 5: travel ratios against the normal walk window.
SLOW_RATIO = (0.25, 0.35)  # operator 2026-11-22: 30 % (was 40 %)
SAME_RATIO = (0.95, 1.05)
# R-SLOW-21: speed ratio 0.25, 0.5, 0.75, 1.0 s after the key change.
RAMP_IN = (0.825, 0.65, 0.475, 0.3)
RAMP_OUT = (0.475, 0.65, 0.825, 1.0)
RAMP_TOLERANCE = 0.08
# R-SLOW-20: c_ANIM_SLOW_BLEND, 3 x the 0.15 s clip blend (operator 2026-11-21).
SLOW_BLEND_MS = 450
# R-SLOW-15: clip rate vs engine travel / stride, part of the rate.
RATE_TOLERANCE = 0.10
# R-SLOW-4: facing kept, degrees.
FACING_TOLERANCE = 10
LOWER_WALK, LOWER_WALK_BACK, LOWER_SLOW, LOWER_SLOW_BACK = 2, 3, 6, 7
LOWER_NONE = 0
UPPER_AIM_MID = 4
UPPER_SLOW, UPPER_SLOW_BACK = 10, 11
ARM, ARM_BACK = "Walk,Slow,Arm", "Walk,Slow,Arm,Back"
JUMP_NONE = 0


def slow_const(name: str) -> float:
    """A c_ANIM_SLOW_* or c_SLOW_WALK_* value from the map script."""
    match = re.search(rf"const fixed {name} = (-?[0-9.]+);", SLOW_CORE.read_text(encoding="utf-8"))
    if match is None:
        raise SystemExit(f"{name} not in {SLOW_CORE}")
    return float(match.group(1))


def selected_group() -> str:
    group = os.environ.get("SC2_TEST_GROUP", "all")
    if group != "all" and group not in GROUPS:
        raise SystemExit(f"unknown slowwalk group: {group}; choose all or one of {', '.join(GROUPS)}")
    return group


def map_spec() -> TestMapSpec:
    return TestMapSpec(
        profile="slowwalk",
        source=ROOT / "out" / "SCOBA256.SC2Map",
        output=PROFILE_OUTPUTS["slowwalk"],
        bank_names=PROFILE_BANKS["slowwalk"],
        galaxy_files=(
            ROOT / "scripts" / "testkit" / "galaxy" / "common.galaxy",
            ROOT / "scripts" / "testkit" / "galaxy" / "slowwalk.galaxy",
        ),
        galaxy_includes=(
            "scripts/test/slowwalk/common",
            "scripts/test/slowwalk/slowwalk",
        ),
        init_calls=(f'gv_dbgGroup = "{selected_group()}";', "gt_SlowWalkTest_Init();"),
    )


def on_ready(ctx, data: dict) -> None:
    return


def _report(checks, name: str, ok: bool, detail: str) -> None:
    status = "PASS" if ok else "FAIL"
    print(f"{name}: {detail} {status}")
    checks.results.append({"section": name, "tag": "", "key": "", "got": detail, "want": "", "status": status})
    if not ok:
        checks.failures += 1


def _ratio(checks, section: str, tag: str, window: tuple[float, float], label: str) -> None:
    ref, got = checks.value(section, "ref", "Speed1000"), checks.value(section, tag, "Speed1000")
    print(f"{section} raw steps: ref={checks.value(section, 'ref', 'Steps')} {tag}={checks.value(section, tag, 'Steps')}")
    ratio = None if not ref or got is None else got / ref
    ok = ratio is not None and window[0] <= ratio <= window[1]
    _report(checks, f"{section} {label}", ok, f"ref={ref} {tag}={got} ratio={ratio}")


def _facing_kept(checks, section: str) -> None:
    a, b = checks.value(section, "ref", "Facing"), checks.value(section, "slow", "Facing")
    gap = None if None in (a, b) else abs((a - b + 180) % 360 - 180)
    _report(checks, f"{section} facing kept", gap is not None and gap <= FACING_TOLERANCE, f"ref={a} slow={b} gap={gap}")


def _rate(checks, section: str) -> None:
    """R-SLOW-15: the slow clip rate = c_ANIM_SLOW_RATE x engine travel /
    stride (operator 2026-11-21: 1.33). Raw: the speed property and the scale."""
    speed, scale = checks.value(section, "slow", "Speed1000"), checks.value(section, "slow", "WalkScale1000")
    stride = slow_const("c_ANIM_SLOW_STRIDE")
    rate = slow_const("c_ANIM_SLOW_RATE")  # operator 2026-11-21: 33 % faster
    print(f"{section} rate raw: travel1000={speed} scale1000={scale} prop1000={checks.value(section, 'slow', 'UnitSpeed1000')} stride={stride} rate={rate}")
    want = None if speed is None else rate * speed / stride
    ok = None not in (want, scale) and want > 0 and abs(scale - want) <= RATE_TOLERANCE * want
    _report(checks, f"{section} slow clip rate matches the ground", ok, f"scale1000={scale} want1000={want}")


def _walk(checks, section: str, slow_state: int, clip: str | None, arm: str | None = ARM) -> None:
    """Normal, slow, released windows of one walk (R-SLOW-1..4, 13..17)."""
    checks.eq(section, "", "resetBuff", 0)
    # Normal walk: no buff, no slow clip (negative, R-SLOW-14).
    checks.eq(section, "ref", "Buff", 0)
    checks.false(section, "ref", "SlowOn")
    ref_clip = checks.value(section, "ref", "Clip") or ""
    _report(checks, f"{section} no slow clip without Shift", "Slow" not in ref_clip, f"clip={ref_clip!r}")
    # Slow walk.
    checks.eq(section, "slow", "Buff", 1)
    checks.true(section, "slow", "SlowOn")
    checks.eq(section, "slow", "FullState", slow_state)
    if clip is not None:
        checks.eq(section, "slow", "Clip", clip)
    _arms(checks, section, arm)
    _ratio(checks, section, "slow", SLOW_RATIO, "slow walk is 30 % speed")
    _rate(checks, section)
    checks.eq(section, "", "presses", 1)
    checks.eq(section, "", "starts", 1)
    # Released: the final buff off and no slow clip 0.25 s after (R-SLOW-16).
    checks.eq(section, "out1", "Buff", 0)
    release = checks.value(section, "out1", "FullState")
    _report(checks, f"{section} normal legs within 0.25 s", release not in (LOWER_SLOW, LOWER_SLOW_BACK), f"fullState={release}")
    _ramp(checks, section)
    checks.false(section, "after", "SlowOn")
    _ratio(checks, section, "after", SAME_RATIO, "normal speed after the release")
    _blends(checks, section, arm is not None)


def _ramp(checks, section: str) -> None:
    """R-SLOW-21: the speed property ramps linearly over 1 s, in and out.
    Expected ratio to the normal speed at each 0.25 s sample, within
    RAMP_TOLERANCE (tick and level steps). Negative: not at the end value
    after the first 0.25 s (no jump)."""
    ref = checks.value(section, "ref", "SpeedProp1000")
    for tag, want in (("in", RAMP_IN), ("out", RAMP_OUT)):
        got = [checks.value(section, f"{tag}{i}", "Prop1000") for i in range(1, 5)]
        levels = [checks.value(section, f"{tag}{i}", "Level") for i in range(1, 5)]
        ratios = None if not ref or None in got else [g / ref for g in got]
        ok = ratios is not None and all(abs(r - w) <= RAMP_TOLERANCE for r, w in zip(ratios, want))
        _report(checks, f"{section} speed ramps {tag} over 1 s", ok, f"ref={ref} props={got} ratios={ratios} want={want} levels={levels}")
        first = None if ratios is None else ratios[0]
        end = want[-1]
        _report(checks, f"{section} {tag} not at once", first is not None and abs(first - end) > 0.3, f"first={first} end={end}")


def _blends(checks, section: str, arms: bool) -> None:
    """R-SLOW-20: into and out of the slow walk with SLOW_BLEND_MS, legs and
    (not aiming) arms; the normal walk start does not use it (negative)."""
    keys = ("LowerBlendMs", "UpperBlendMs")
    print(f"{section} blends raw: " + " ".join(f"{tag}:{key}={checks.value(section, tag, key)}" for tag in ("ref", "slow", "after") for key in keys))
    for key in keys[: 2 if arms else 1]:
        checks.eq(section, "slow", key, SLOW_BLEND_MS)
        checks.eq(section, "after", key, SLOW_BLEND_MS)
        got = checks.value(section, "ref", key)
        _report(checks, f"{section} ref {key} not the slow blend", got is not None and got != SLOW_BLEND_MS, f"got={got}")


def _arms(checks, section: str, arm: str | None) -> None:
    """R-SLOW-19: not aiming, the upper body plays the slow arm clip; none
    without Shift and after the release (negative). Raw: plays, start time."""
    print(f"{section} arms raw: plays={checks.value(section, 'slow', 'ArmPlays')} timeMs={checks.value(section, 'slow', 'ArmTimeMs')}")
    for tag in ("ref", "after"):
        upper = checks.value(section, tag, "Upper")
        _report(checks, f"{section} {tag} no slow arms", upper not in (UPPER_SLOW, UPPER_SLOW_BACK), f"upper={upper}")
    if arm is None:
        upper = checks.value(section, "slow", "Upper")
        _report(checks, f"{section} slow no slow arms", upper not in (UPPER_SLOW, UPPER_SLOW_BACK), f"upper={upper}")
        return
    checks.eq(section, "slow", "Upper", UPPER_SLOW_BACK if arm == ARM_BACK else UPPER_SLOW)
    checks.eq(section, "slow", "UpperClip", arm)
    checks.gt(section, "slow", "ArmPlays", 0)


def check_free(checks) -> None:
    s = "slow_free"
    _walk(checks, s, LOWER_SLOW, "Attack,Walk,Slow,Forward")
    _facing_kept(checks, s)


def check_pnc(checks) -> None:
    s = "slow_pnc"
    _walk(checks, s, LOWER_SLOW, "Attack,Walk,Slow,Forward")
    # R-SLOW-4: the move order stays.
    checks.gt(s, "slow", "Orders", 0)
    checks.true(s, "slow", "MoveOrder")
    _facing_kept(checks, s)


def check_strafe(checks) -> None:
    s = "slow_strafe"
    _walk(checks, s, LOWER_SLOW, "Attack,Walk,Slow,Left")
    checks.true(s, "slow", "HoldStrafe")
    _facing_kept(checks, s)


def check_back(checks) -> None:
    s = "slow_back"
    _walk(checks, s, LOWER_SLOW_BACK, "Attack,Walk,Slow,Back", ARM_BACK)
    checks.true(s, "slow", "HoldStrafe")
    _facing_kept(checks, s)


def check_aim(checks) -> None:
    s = "slow_aim"
    _walk(checks, s, LOWER_SLOW, "Attack,Walk,Slow,Forward", None)
    # R-SLOW-17: the upper body stays on the aim.
    checks.true(s, "slow", "Aim")
    checks.eq(s, "slow", "UpperState", UPPER_AIM_MID)
    _facing_kept(checks, s)


def check_kerrigan(checks) -> None:
    s = "slow_kerrigan"
    checks.true(s, "", "heroIsKerrigan")
    checks.eq(s, "slow", "Buff", 0)
    checks.false(s, "slow", "SlowOn")
    checks.true(s, "slow", "SlowKey")
    _ratio(checks, s, "slow", SAME_RATIO, "Kerrigan keeps her speed")
    upper = checks.value(s, "slow", "Upper")
    _report(checks, f"{s} no slow arms", upper not in (UPPER_SLOW, UPPER_SLOW_BACK), f"upper={upper}")


def check_switch(checks) -> None:
    s = "slow_switch"
    checks.eq(s, "", "toshBuffBefore", 1)
    checks.eq(s, "", "toshBuffAway", 0)
    checks.eq(s, "", "kerriganBuff", 0)
    checks.eq(s, "", "levelAway", 0)
    checks.false(s, "", "slowOnAway")
    checks.eq(s, "", "toshBuffBack", 1)
    checks.true(s, "", "slowOnBack")
    checks.eq(s, "", "toshBuffEnd", 0)


def check_intro(checks) -> None:
    s = "slow_intro"
    checks.eq(s, "", "introBuff", 0)
    checks.false(s, "", "introSlowOn")
    checks.eq(s, "", "afterBuff", 1)
    checks.true(s, "", "afterSlowOn")


def _jump(checks, section: str, press_state: int) -> None:
    """R-SLOW-18: the jump takes off from the regular walk."""
    checks.eq(section, "", "preBuff", 1)
    checks.eq(section, "", "preFullState", LOWER_SLOW)
    checks.true(section, "", "pressOk")
    checks.eq(section, "", "slowJumps", 1)
    checks.eq(section, "", "pressBuff", 0)
    checks.eq(section, "", "pressLevel", 0)
    checks.eq(section, "", "pressFullState", press_state)
    checks.eq(section, "", "pressBase", LOWER_WALK)
    checks.eq(section, "", "pressBursts", 1)
    checks.eq(section, "", "airBuff", 0)
    checks.false(section, "", "airSlowOn")
    clips = [clip for clip in (checks.value(section, "", "clipLog") or "").split(";") if clip]
    print(f"{section} clips: {clips} gaitMs={checks.value(section, '', 'slowJumpGaitMs')} stride={checks.value(section, '', 'pressStride')}")
    ok = bool(clips) and re.fullmatch(r"Jump,Start,\w+(,\w+)?,0[12],Leg", clips[0]) is not None and "Slow" not in "".join(clips)
    _report(checks, f"{section} takes off from the regular walk", ok, f"first={clips[:1]}")
    # Back on the ground with Shift held: the slow walk returns.
    checks.eq(section, "", "endPhase", JUMP_NONE)
    checks.eq(section, "", "endBuff", 1)
    checks.eq(section, "", "endFullState", LOWER_SLOW)


def check_jump_aim(checks) -> None:
    _jump(checks, "slow_jump_aim", LOWER_WALK)


def check_jump_pnc(checks) -> None:
    _jump(checks, "slow_jump_pnc", LOWER_NONE)


CHECKS = {
    "slow_free": check_free,
    "slow_pnc": check_pnc,
    "slow_strafe": check_strafe,
    "slow_back": check_back,
    "slow_aim": check_aim,
    "slow_kerrigan": check_kerrigan,
    "slow_switch": check_switch,
    "slow_intro": check_intro,
    "slow_jump_aim": check_jump_aim,
    "slow_jump_pnc": check_jump_pnc,
}


def _common(checks, section: str) -> None:
    """Real mouse input makes a run invalid."""
    clicks = [checks.value(section, tag, "RealClicks") for tag in ("ref", "slow", "after", "end")]
    seen = [value for value in clicks if value is not None]
    _report(checks, f"{section} no real clicks", bool(seen) and all(value == 0 for value in seen), f"clicks={seen}")


def check(ctx, data: dict, checks) -> None:
    for error in ctx.errors:
        print(f"{error} FAIL")
        checks.failures += 1
    checks.eq("meta", "", "done", 1)
    group = selected_group()
    for name in GROUPS:
        if group not in ("all", name):
            continue
        for section in SECTIONS[name]:
            _common(checks, section)
            CHECKS[section](checks)


def run_spec(launch_timeout_s: float, case_timeout_s: float, run_root: Path) -> TestRunSpec:
    return TestRunSpec(
        profile="slowwalk",
        map_name="SCOBA.SC2Map",
        map_source=PROFILE_OUTPUTS["slowwalk"],
        map_cache_name="SCOBA.SC2Map",
        bank_names=PROFILE_BANKS["slowwalk"],
        ready_section="slow_start",
        ready_key="ready",
        launch_timeout_s=launch_timeout_s,
        case_timeout_s=case_timeout_s,
        run_root=run_root,
        on_ready=on_ready,
        check=check,
    )
