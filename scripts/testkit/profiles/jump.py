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
from .registry import PROFILE_BANKS, PROFILE_OUTPUTS

ROOT = project_root()
GROUPS = ("arc", "body", "hero")
SECTIONS = {
    "arc": ("jump_stand", "jump_none", "jump_double", "jump_rejump"),
    "body": ("jump_aimwalk", "jump_stopjump", "jump_freewalk", "jump_keystill"),
    "hero": ("jump_switch", "jump_kerrigan"),
}
# Windows wider than one game loop (62.5 ms) around REQ-JUMP R-JUMP-2, 3.
# Curve: crouch 133 ms on the ground, rise 300 ms to 0.6, fall 237 ms.
CROUCH_H100_MAX = 2
RISE_MS = (125, 250)
PEAK_H100 = (52, 62)
PEAK_MS = (370, 500)
AIRTIME_MS = (560, 720)
UPPER_AIM_MID = 4
# Touchdown: the air time (670 ms) up to the end of that game loop.
THUMP_MS = (670, 735)
# The camera part written at a sample is the hero's target for the next loop:
# it equals the engine height one loop later. No lead.
CAM_AHEAD_MS = 62


def _pairs(text) -> list[tuple[int, str]]:
    return [(int(ms), value) for ms, value in (item.split(":", 1) for item in (text or "").split())]


def _samples(text) -> dict[int, int]:
    return {ms: int(value) for ms, value in _pairs(text)}
BARE = ("Jump,Start,Leg", "Jump,Leg", "Jump,End,Leg")
# Gait (R-JUMP-18): walk cycle; tracker vs harness walk start, in walk ms at
# rate 1: free walk one game loop and a margin; aim walk adds the anim tick
# (the clip starts on intent, before the harness sees movement).
CYCLE_MS = 667
GAIT_WINDOW_MS = 80
GAIT_WINDOW_AIM_MS = 140
# The walk resume is sent on the anim tick after the release; the tracker
# runs on until then.
RESUME_WINDOW_MS = 150
# Strafe and backpedal walk clips vs the stock walk rate (operator 2026-11-16).
STRAFE_RATE = 1.25
# R-JUMP-22: takeoff crouch (c_JUMP_CROUCH), landing clip (c_JUMP_LAND_TIME),
# and the speed burst of a walk jump (BehaviorData SCOBAJumpBurst).
CROUCH_MS = 133
LAND_MS = 250
BURST = 1.4
JUMP_CORE = ROOT / "src" / "SCOBA.SC2Map" / "scripts" / "app" / "core" / "jump.galaxy"


def gait_const(name: str) -> float:
    """A c_JUMP_GAIT_* value from the map script."""
    match = re.search(rf"const (?:fixed|int) c_JUMP_GAIT_{name} = ([0-9.]+);", JUMP_CORE.read_text(encoding="utf-8"))
    if match is None:
        raise SystemExit(f"c_JUMP_GAIT_{name} not in {JUMP_CORE}")
    return float(match.group(1))


def strides_for(gait_ms: int) -> set[int]:
    """The stride whose Start clip begins nearest a forward walk phase.

    Mirror of gf_JumpGaitStride. The bank holds whole ms: within 3 ms of a
    stride boundary both strides are accepted."""
    count = int(gait_const("STRIDES"))
    out = set()
    for ms in (gait_ms - 3, gait_ms, gait_ms + 3):
        x = (ms / CYCLE_MS + gait_const("PUSH") - gait_const("FLIGHT") + 1.0) * count
        out.add(int(x + 0.5) % count)
    return out


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


def _gait(checks, section: str, aim: bool) -> None:
    """R-JUMP-18: tracked walk phase, takeoff stride, and clip time messages."""
    gait, rate, walk, stride = (checks.value(section, "", k) for k in ("pressGaitMs", "pressRate100", "walkMs", "pressStride"))
    log = checks.value(section, "", "setTimeLog") or ""
    clips = [clip for clip in (checks.value(section, "", "clipLog") or "").split(";") if clip]
    print(f"{section} gait: gaitMs={gait} rate100={rate} walkMs={walk} stride={stride} setTimeLog={log}")
    # The tracked phase matches the walk time the harness measured (engine
    # position), within one game loop and one anim tick of clip start.
    ok = None not in (gait, rate, walk) and walk >= 0
    if ok:
        expected = (walk * rate / 100.0) % CYCLE_MS
        diff = abs(gait - expected)
        diff = min(diff, CYCLE_MS - diff)
        window = (GAIT_WINDOW_AIM_MS if aim else GAIT_WINDOW_MS) * rate / 100.0
        ok = diff <= window
        detail = f"gait={gait} expected={expected:.0f} diff={diff:.0f} window={window:.0f}"
    else:
        detail = f"gait={gait} walk={walk}"
    _report(checks, f"{section} gait phase tracks the walk", ok, detail)
    # The tracker runs at the rate of the clip that plays: an aim or strafe
    # walk clip is STRAFE_RATE faster than the stock walk; the free walk is
    # the stock walk (negative: no speed-up there).
    stock, scale = checks.value(section, "", "pressStock100"), checks.value(section, "", "pressScale100")
    want_rate = None if stock is None else stock * (STRAFE_RATE if aim else 1.0)
    ok = None not in (rate, want_rate) and abs(rate - want_rate) <= 2
    _report(checks, f"{section} gait rate is the {'strafe' if aim else 'stock'} walk rate", ok, f"rate100={rate} stock100={stock} want={want_rate}")
    if aim:
        ok = None not in (scale, want_rate) and abs(scale - want_rate) <= 2
        _report(checks, f"{section} strafe walk clip plays {STRAFE_RATE}x the stock rate", ok, f"scale100={scale} stock100={stock} want={want_rate}")
    want = set() if gait is None else strides_for(gait)
    _report(checks, f"{section} takeoff stride is the nearest", stride in want, f"stride={stride} want={sorted(want)}")
    # One stride from takeoff to landing: the legs never swap in the air.
    suffix = None if stride is None else f",{stride + 1:02d},Leg"
    same = suffix is not None and len(clips) >= 3 and all(clip.endswith(suffix) for clip in clips[:3])
    _report(checks, f"{section} Start, Air, End use the takeoff stride", same, f"clips={clips[:3]}")
    # Negative: the held air pose gets no clip time.
    air = log.count("A:")
    _report(checks, f"{section} no clip time set in the air", air == 0, f"A={air}")
    resume = [int(item.split(":")[1]) for item in log.split(";") if item.startswith("R:")]
    _report(checks, f"{section} walk resume {'sent' if aim else 'absent (stock walk)'}", len(resume) == (1 if aim else 0), f"R={resume}")
    if aim and len(resume) == 1 and stride is not None and rate is not None:
        # The walk restarts where the End clip stops: flight frame + LAND.
        stop = ((gait_const("FLIGHT") + stride / gait_const("STRIDES") + gait_const("LAND")) % 1.0) * CYCLE_MS
        late = (resume[0] - stop) % CYCLE_MS
        window = RESUME_WINDOW_MS * rate / 100.0
        _report(checks, f"{section} walk resumes where the landing stops", late <= window or CYCLE_MS - late <= 5, f"resume={resume[0]} stop={stop:.0f} late={late:.0f} window={window:.0f}")
    checks.false(section, "", "resumePending")
    checks.eq(section, "", "endStride", -1)


def _rates(checks, section: str, walk: bool, aim: bool = False) -> None:
    """R-JUMP-22: takeoff burst, clip time scales, and a short landing.

    Walk jump: the burst raises the engine move speed at the press and is
    gone at the end; Start plays at the walk clip rate with the burst, End
    at the walk clip rate; Air at 1. Stand jump (negative): no burst, all 1."""
    v = {k: checks.value(section, "", k) for k in (
        "pressSpeed100", "burstSpeed100", "endSpeed100", "burstCount", "endBurstCount", "bursts",
        "startScale100", "landScale100", "pressStock100", "pressStep1000", "landMs", "doneMs")}
    scales = [int(x) for x in (checks.value(section, "", "scaleLog") or "").split(";") if x]
    steps = [int(x) for x in (checks.value(section, "", "steps") or "").split()]
    print(f"{section} rates: {v} scaleLog={scales} steps={steps}")
    checks.eq(section, "", "bursts", 1 if walk else 0)
    checks.eq(section, "", "burstCount", 1 if walk else 0)
    checks.eq(section, "", "endBurstCount", 0)
    press, burst, end = v["pressSpeed100"], v["burstSpeed100"], v["endSpeed100"]
    ok = None not in (press, burst, end) and abs(end - press) <= 2 and abs(burst - press * (BURST if walk else 1.0)) <= 3
    _report(checks, f"{section} move speed {'bursts at the press and' if walk else 'has no burst and'} is back at the end", ok, f"press={press} burst={burst} end={end}")
    stock = v["pressStock100"]
    rate = None if stock is None else stock * (STRAFE_RATE if aim else 1.0)
    want = [100, 100, 100] if not walk or rate is None else [rate * BURST, 100, rate]
    ok = len(scales) >= 3 and all(abs(got - exp) <= 4 for got, exp in zip(scales, want))
    _report(checks, f"{section} clip time scales Start, Air, End", ok, f"scales={scales[:3]} want={[round(x) for x in want]}")
    if walk:
        # Engine position: the first loops after the press are faster than
        # the walk before it; the last sampled loops are not.
        before = v["pressStep1000"]
        ok = before is not None and len(steps) >= 12 and max(steps[:3]) >= 1.2 * before
        _report(checks, f"{section} hero moves faster at the push-off", ok, f"before={before} first={steps[:3]}")
        ok = before is not None and len(steps) >= 12 and max(steps[8:12]) <= 1.1 * before + 3
        _report(checks, f"{section} burst is over in the air", ok, f"before={before} later={steps[8:12]}")
    # Landing recovery: the End clip length over its time scale; never the old 400 ms.
    land, done, scale = v["landMs"], v["doneMs"], v["landScale100"]
    took = None if None in (land, done) or land < 0 or done < 0 else done - land
    want_ms = None if not scale else LAND_MS * 100.0 / scale
    ok = None not in (took, want_ms) and want_ms - 70 <= took <= want_ms + 70 and took < 380
    _report(checks, f"{section} landing recovery is short", ok, f"took={took}ms want={want_ms}")


def _no_gait(checks, section: str) -> None:
    """Negative: an idle jump sets no clip time and uses no stride."""
    checks.eq(section, "", "setTimes", 0)
    checks.eq(section, "", "pressStride", -1)


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
    _rates(checks, s, walk=False)
    _camera(checks, s, True)
    checks.false(s, "", "endOwned")
    checks.eq(s, "", "endClip", "")
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
    _rates(checks, s, walk=True, aim=True)
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
    _rates(checks, s, walk=False)
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
    _rates(checks, s, walk=True)
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
    s = "jump_kerrigan"
    _arc(checks, s)
    checks.eq(s, "", "phaseSeq", "1230")
    _thump(checks, s, 1)
    checks.false(s, "", "midOwned")
    checks.eq(s, "", "midClip", "")
    checks.eq(s, "", "clipLog", "")
    _camera(checks, s, True)


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
