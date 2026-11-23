"""Hero jump profile (REQ-JUMP).

Every check reads the test bank: engine height, position, facing, orders, and
the jump and animation script state. How the clips look is an operator check.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from project_root import project_root

from ..map_builder import TestMapSpec
from ..runner import TestRunSpec
from .jump_gait import CYCLE_MS, KERRIGAN_CYCLE_MS, strides_for
from .jump_gait import check_gait as _gait
from .jump_gait import check_no_gait as _no_gait
from .jump_rates import check_rates
from .registry import PROFILE_BANKS, PROFILE_OUTPUTS

ROOT = project_root()
GROUPS = ("arc", "body", "hero")
SECTIONS = {
    "arc": ("jump_stand", "jump_none", "jump_double", "jump_rejump"),
    "body": ("jump_aimwalk", "jump_stopjump", "jump_freewalk", "jump_keystill"),
    "hero": ("jump_switch", "jump_kerrigan", "jump_kerrigan_walk", "jump_kerrigan_none"),
}
# Windows wider than one game loop (62.5 ms) around REQ-JUMP R-JUMP-2, 3.
# Curve: crouch 150 ms on the ground, rise 300 ms to 0.6, fall 237 ms.
CROUCH_H100_MAX = 2
RISE_MS = (125, 250)
PEAK_H100 = (52, 62)
PEAK_MS = (370, 500)
AIRTIME_MS = (560, 720)
UPPER_AIM_MID = 4
# Touchdown: the air time (687 ms) up to the end of that game loop.
THUMP_MS = (687, 752)
# The camera part written at a sample is the hero's target for the next loop:
# it equals the engine height one loop later. No lead.
CAM_AHEAD_MS = 62


def _pairs(text) -> list[tuple[int, str]]:
    return [(int(ms), value) for ms, value in (item.split(":", 1) for item in (text or "").split())]


def _samples(text) -> dict[int, int]:
    return {ms: int(value) for ms, value in _pairs(text)}
BARE = ("Jump,Start,Leg", "Jump,Leg", "Jump,End,Leg")
# Gait (R-JUMP-18) windows and checks: jump_gait.py. strides_for and
# CYCLE_MS stay importable from here for the host tests.
__all__ = ["CYCLE_MS", "map_spec", "run_spec", "strides_for"]
# R-JUMP-22: takeoff crouch (c_JUMP_CROUCH). Burst and landing: jump_rates.py.
CROUCH_MS = 150
# R-JUMP-24: back to stand or walk (c_JUMP_RELEASE_BLEND, c_JUMP_RESUME_BLEND);
# a walk started outside a jump keeps 150 ms. Fixed point truncates the ms
# (0.15 s reads 149): windows of +-5 ms.
RELEASE_BLEND_MS = (45, 55)
WALK_BLEND_MS = (145, 155)


def _release(checks, section: str, aim_walk: bool) -> None:
    """R-JUMP-24: the jump legs blend out fast; no flag left behind."""
    checks.between(section, "", "releaseBlendMs", *RELEASE_BLEND_MS)
    checks.false(section, "", "releasedPending")
    if aim_walk:
        checks.between(section, "", "afterBlendMs", *RELEASE_BLEND_MS)
        # Negative: the walk clip before the jump had the normal blend.
        checks.between(section, "", "pressBlendMs", *WALK_BLEND_MS)


def selected_group() -> str:
    group = os.environ.get("SC2_TEST_GROUP", "all")
    if group != "all" and group not in GROUPS:
        raise SystemExit(f"unknown jump group: {group}; choose all or one of {', '.join(GROUPS)}")
    return group


def map_spec() -> TestMapSpec:
    return TestMapSpec(
        profile="jump",
        source=ROOT / "out" / "SCOBA256.SC2Map",
        output=PROFILE_OUTPUTS["jump"],
        bank_names=PROFILE_BANKS["jump"],
        galaxy_files=(
            ROOT / "scripts" / "testkit" / "galaxy" / "common.galaxy",
            ROOT / "scripts" / "testkit" / "galaxy" / "jump.galaxy",
        ),
        galaxy_includes=(
            "scripts/test/jump/common",
            "scripts/test/jump/jump",
        ),
        init_calls=(f'gv_dbgGroup = "{selected_group()}";', "gt_JumpTest_Init();"),
    )


def on_ready(ctx, data: dict) -> None:
    return


def _report(checks, name: str, ok: bool, detail: str) -> None:
    status = "PASS" if ok else "FAIL"
    print(f"{name}: {detail} {status}")
    checks.results.append({"section": name, "tag": "", "key": "", "got": detail, "want": "", "status": status})
    if not ok:
        checks.failures += 1


def _moved10(checks, section: str) -> int | None:
    """Hero travel in tenths from t0 to end (Manhattan)."""
    values = [checks.value(section, tag, key) for tag in ("t0", "end") for key in ("HeroX10", "HeroY10")]
    if any(value is None for value in values):
        return None
    return abs(values[2] - values[0]) + abs(values[3] - values[1])


def _early(checks, section: str) -> int:
    """ms the arc starts early: a walk jump plays the takeoff crouch at the
    walk clip rate (R-JUMP-22), so it is CROUCH_MS / rate long."""
    scale = checks.value(section, "", "startScale100") or 100
    return round(CROUCH_MS * (1.0 - 100.0 / scale))


def _window(checks, section: str, window: tuple[int, int]) -> tuple[int, int]:
    early = _early(checks, section)
    return window[0] - early, window[1] - early


def _arc(checks, section: str) -> None:
    """One full ballistic arc after the press (R-JUMP-2, 3)."""
    print(f"{section} raw: {checks.value(section, '', 'raw')} early={_early(checks, section)}ms")
    checks.true(section, "", "pressOk")
    checks.between(section, "", "crouchH100", 0, CROUCH_H100_MAX)
    checks.between(section, "", "firstUpMs", *_window(checks, section, RISE_MS))
    checks.between(section, "", "peakH100", *PEAK_H100)
    checks.between(section, "", "peakMs", *_window(checks, section, PEAK_MS))
    checks.between(section, "", "lastUpMs", *_window(checks, section, AIRTIME_MS))
    checks.between(section, "", "endH100", 0, 1)
    # Heavier fall: touchdown speed above launch speed.
    land, v0 = checks.value(section, "", "landSpeed100"), checks.value(section, "", "v0100")
    _report(checks, f"{section} falls faster than it rises", None not in (land, v0) and land > v0, f"land={land} v0={v0}")


def _camera(checks, section: str, jumped: bool) -> None:
    """R-JUMP-17: the camera height carries the jump elevation, loop by loop."""
    print(f"{section} cam: {checks.value(section, '', 'cam')}")
    checks.eq(section, "", "camEnd100", 0)
    if not jumped:
        checks.eq(section, "", "camMax100", 0)
        return
    checks.between(section, "", "camMax100", *PEAK_H100)
    # Written camera part at m = engine height at m + one loop (same target).
    raw = _samples(checks.value(section, "", "raw"))
    cam = {ms: int(v.split("/")[0]) for ms, v in _pairs(checks.value(section, "", "cam"))}
    bad = []
    for ms, value in cam.items():
        later = next((h for t, h in raw.items() if abs(t - (ms + CAM_AHEAD_MS)) <= 5), None)
        if later is not None and abs(value - later) > 2:
            bad.append(f"{ms}:{value}vs{later}")
    _report(checks, f"{section} camera matches the hero, no lead", cam != {} and not bad, f"mismatch={bad}")


def _clips(checks, section: str, base: str) -> None:
    """R-JUMP-16: every jump clip is built on the base; no bare clip plays.
    R-JUMP-18: walk jump clips carry a stride, 01 or 02."""
    log = checks.value(section, "", "clipLog") or ""
    clips = [clip for clip in log.split(";") if clip]
    print(f"{section} clips: {clips}")
    bare = [clip for clip in clips if clip in BARE or ("Stand" not in clip and "Walk" not in clip)]
    _report(checks, f"{section} no bare jump clip", not bare, f"bare={bare}")
    stride = r",0[12]" if base.startswith("Walk") else ""
    want = [rf"Jump,Start,{base}{stride},Leg", rf"Jump,{base}{stride},Leg", rf"Jump,End,{base}{stride},Leg"]
    ok = len(clips) >= 3 and all(re.fullmatch(pattern, clip) for pattern, clip in zip(want, clips))
    _report(checks, f"{section} clips built on {base}", ok, f"clips={clips[:3]}")
    if not stride:
        # Negative: a stand jump has no stride clip.
        strided = [clip for clip in clips if re.search(r",0\d,Leg$", clip)]
        _report(checks, f"{section} no stride clip", not strided, f"strided={strided}")


def _thump(checks, section: str, count: int) -> None:
    """R-JUMP-8: one thump per touchdown, in the touchdown game loop, on the ground."""
    checks.eq(section, "", "thumps", count)
    if count == 0:
        checks.false(section, "", "thumpActor")
        return
    checks.between(section, "", "thumpMs", *_window(checks, section, THUMP_MS))
    checks.between(section, "", "thumpH100", 0, 10)
    # Same game loop as the first engine sample back at height 0.
    thump, down = checks.value(section, "", "thumpMs"), checks.value(section, "", "firstDownMs")
    gap = None if thump is None or down is None or down < 0 else down - thump
    _report(checks, f"{section} thump in the touchdown loop", gap is not None and 0 <= gap < 62, f"firstDown-thump={gap}ms")
    # The test arena is dry: dust plays (a wet arena fails this check).
    checks.eq(section, "", "thumpsWet", 0)
    checks.true(section, "", "thumpActor")


def _common(checks, section: str) -> None:
    checks.between(section, "", "resetH100", 0, 1)
    checks.eq(section, "end", "RealClicks", 0)


def check_stand(checks) -> None:
    s = "jump_stand"
    _arc(checks, s)
    checks.eq(s, "", "phaseSeq", "1230")
    checks.eq(s, "", "starts", 1)
    checks.eq(s, "", "rejects", 0)
    _thump(checks, s, 1)
    checks.eq(s, "", "endPhase", 0)
    checks.true(s, "", "midOwned")
    checks.eq(s, "", "midClip", "Jump,Stand,Leg")
    _clips(checks, s, "Stand")
    _no_gait(checks, s)
    check_rates(checks, s, walk=False)
    _camera(checks, s, True)
    checks.false(s, "", "endOwned")
    checks.eq(s, "", "endClip", "")
    _release(checks, s, aim_walk=False)
    # R-JUMP-6: no order, no turn, no drift.
    checks.false(s, "end", "MoveOrder")
    checks.false(s, "end", "AttackOrder")
    moved = _moved10(checks, s)
    _report(checks, f"{s} stays in place", moved is not None and moved <= 5, f"moved10={moved}")
    t0, end = checks.value(s, "t0", "Facing"), checks.value(s, "end", "Facing")
    turn = None if t0 is None or end is None else min(abs(end - t0), 360 - abs(end - t0))
    _report(checks, f"{s} facing unchanged", turn is not None and turn <= 2, f"turn={turn}")


def check_none(checks) -> None:
    s = "jump_none"
    checks.lt(s, "", "peakH100", 2)
    checks.eq(s, "", "firstUpMs", -1)
    checks.eq(s, "", "phaseSeq", "0")
    checks.eq(s, "", "starts", 0)
    _thump(checks, s, 0)
    checks.eq(s, "", "clipLog", "")
    _camera(checks, s, False)


def check_double(checks) -> None:
    s = "jump_double"
    _arc(checks, s)
    checks.false(s, "", "actOk")
    checks.eq(s, "", "starts", 1)
    checks.eq(s, "", "rejects", 1)
    _thump(checks, s, 1)
    _camera(checks, s, True)


def check_rejump(checks) -> None:
    s = "jump_rejump"
    print(f"{s} raw: {checks.value(s, '', 'raw')}")
    checks.true(s, "", "pressOk")
    checks.true(s, "", "actOk")
    checks.eq(s, "", "starts", 2)
    seq = checks.value(s, "", "phaseSeq")
    _report(checks, f"{s} two arcs", isinstance(seq, str) and seq.startswith("123123"), f"phaseSeq={seq}")
    checks.gt(s, "", "lastUpMs", 1000)
    checks.eq(s, "", "thumps", 2)
    checks.eq(s, "", "camEnd100", 0)


def check_aimwalk(checks) -> None:
    s = "jump_aimwalk"
    _press_inputs(checks, s)
    _arc(checks, s)
    checks.gt(s, "", "pressStep100", WALK_STEP_H100)
    checks.true(s, "", "midAim")
    checks.eq(s, "", "midUpper", UPPER_AIM_MID)
    checks.true(s, "", "midOwned")
    checks.eq(s, "", "afterUpper", UPPER_AIM_MID)
    checks.gt(s, "", "afterFull", 0)
    moved = _moved10(checks, s)
    _report(checks, f"{s} walks while airborne", moved is not None and moved >= 15, f"moved10={moved}")
    checks.eq(s, "", "thumps", 1)
    checks.between(s, "", "thumpMs", *_window(checks, s, THUMP_MS))
    # Aimed forward walk: the air clip is a stride of the forward walk.
    mid = checks.value(s, "", "midClip") or ""
    _report(checks, f"{s} air clip is a forward walk stride", re.fullmatch(r"Jump,Walk,Forward,0[12],Leg", mid) is not None, f"midClip={mid}")
    _clips(checks, s, "Walk,Forward")
    _gait(checks, s, aim=True)
    _release(checks, s, aim_walk=True)
    check_rates(checks, s, walk=True, aim=True)
    _camera(checks, s, True)


WALK_STEP_H100 = 3  # c_JUMP_WALK_STEP


def _press_inputs(checks, section: str) -> None:
    keys, order, moving, step = (checks.value(section, "", k) for k in ("pressKeys", "pressMoveOrder", "pressMoving", "pressStep100"))
    applied, base = checks.value(section, "", "camApplied100"), checks.value(section, "", "camBase100")
    print(f"{section} press inputs: keys={keys} moveOrder={order} animMoving={moving} step100={step}; cam applied={applied} base={base}")


def check_stopjump(checks) -> None:
    """Negative: right after a stop, no walk clip is mixed in (R-JUMP-16)."""
    s = "jump_stopjump"
    _press_inputs(checks, s)
    checks.gt(s, "", "walked10", 5)  # it really walked before the stop
    _arc(checks, s)
    checks.false(s, "", "pressKeys")
    checks.between(s, "", "pressStep100", 0, WALK_STEP_H100)
    checks.eq(s, "", "midClip", "Jump,Stand,Leg")
    _clips(checks, s, "Stand")
    _no_gait(checks, s)
    check_rates(checks, s, walk=False)
    log = checks.value(s, "", "clipLog") or ""
    _report(checks, f"{s} no walk clip", "Walk" not in log, f"clipLog={log}")


def check_freewalk(checks) -> None:
    s = "jump_freewalk"
    _press_inputs(checks, s)
    _arc(checks, s)
    checks.true(s, "", "pressKeys")
    checks.gt(s, "", "pressStep100", WALK_STEP_H100)
    _clips(checks, s, "Walk,Forward")
    _gait(checks, s, aim=False)
    check_rates(checks, s, walk=True)
    moved = _moved10(checks, s)
    _report(checks, f"{s} walks while airborne", moved is not None and moved >= 10, f"moved10={moved}")


def check_keystill(checks) -> None:
    """Negative: key held, hero not moving: idle, not walk."""
    s = "jump_keystill"
    _press_inputs(checks, s)
    _arc(checks, s)
    checks.true(s, "", "pressKeys")
    checks.between(s, "", "pressStep100", 0, WALK_STEP_H100)
    _clips(checks, s, "Stand")
    _no_gait(checks, s)


def check_switch(checks) -> None:
    s = "jump_switch"
    checks.true(s, "", "pressOk")
    checks.gt(s, "", "peakH100", 30)
    checks.true(s, "", "endHeroIsKerrigan")
    checks.between(s, "", "endH100", 0, 1)
    checks.eq(s, "", "endPhase", 0)
    # Negative: the jump ended mid-air; no touchdown, no thump.
    _thump(checks, s, 0)
    # The camera drops the jump part with the jump.
    checks.eq(s, "", "camEnd100", 0)


def check_kerrigan(checks) -> None:
    """R-JUMP-23: Kerrigan's stand jump plays her clips from Burrow 01."""
    s = "jump_kerrigan"
    checks.true(s, "", "endHeroIsKerrigan")
    _arc(checks, s)
    checks.eq(s, "", "phaseSeq", "1230")
    _thump(checks, s, 1)
    checks.true(s, "", "midOwned")
    checks.eq(s, "", "midClip", "Jump,Stand,Leg")
    _clips(checks, s, "Stand")
    _no_gait(checks, s)
    _camera(checks, s, True)
    # The legs go back to the normal clip choice after landing (R-JUMP-14).
    checks.false(s, "", "endOwned")
    checks.eq(s, "", "endClip", "")
    _release(checks, s, aim_walk=False)


def check_kerrigan_walk(checks) -> None:
    """R-JUMP-23: Kerrigan's aimed forward walk jump: walk stride clips."""
    s = "jump_kerrigan_walk"
    checks.true(s, "", "endHeroIsKerrigan")
    _press_inputs(checks, s)
    _arc(checks, s)
    checks.gt(s, "", "pressStep100", WALK_STEP_H100)
    checks.true(s, "", "midOwned")
    mid = checks.value(s, "", "midClip") or ""
    _report(checks, f"{s} air clip is a forward walk stride", re.fullmatch(r"Jump,Walk,Forward,0[12],Leg", mid) is not None, f"midClip={mid}")
    _clips(checks, s, "Walk,Forward")
    _gait(checks, s, aim=True, cycle_ms=KERRIGAN_CYCLE_MS)
    _release(checks, s, aim_walk=True)
    moved = _moved10(checks, s)
    _report(checks, f"{s} walks while airborne", moved is not None and moved >= 15, f"moved10={moved}")
    _camera(checks, s, True)


def check_kerrigan_none(checks) -> None:
    """Negative: no press, no jump clip for Kerrigan."""
    s = "jump_kerrigan_none"
    checks.true(s, "", "endHeroIsKerrigan")
    checks.lt(s, "", "peakH100", 2)
    checks.eq(s, "", "phaseSeq", "0")
    checks.eq(s, "", "starts", 0)
    checks.eq(s, "", "clipLog", "")
    checks.false(s, "", "endOwned")
    # Negative: no jump, no release.
    checks.eq(s, "", "releaseBlendMs", -1)


CHECKS = {
    "jump_stand": check_stand,
    "jump_none": check_none,
    "jump_double": check_double,
    "jump_rejump": check_rejump,
    "jump_aimwalk": check_aimwalk,
    "jump_stopjump": check_stopjump,
    "jump_freewalk": check_freewalk,
    "jump_keystill": check_keystill,
    "jump_switch": check_switch,
    "jump_kerrigan": check_kerrigan,
    "jump_kerrigan_walk": check_kerrigan_walk,
    "jump_kerrigan_none": check_kerrigan_none,
}


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
        profile="jump",
        map_name="SCOBA.SC2Map",
        map_source=PROFILE_OUTPUTS["jump"],
        map_cache_name="SCOBA.SC2Map",
        bank_names=PROFILE_BANKS["jump"],
        ready_section="jump_start",
        ready_key="ready",
        launch_timeout_s=launch_timeout_s,
        case_timeout_s=case_timeout_s,
        run_root=run_root,
        on_ready=on_ready,
        check=check,
    )
