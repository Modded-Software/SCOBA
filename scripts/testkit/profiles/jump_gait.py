"""Jump gait checks (R-JUMP-18): the tracked walk phase, the takeoff stride,
and the clip time messages. Split from jump.py for the file length limit."""

from __future__ import annotations

import re

from .bank_checks import _report
from .jump_rates import JUMP_CORE, STRAFE_RATE

# Gait (R-JUMP-18): walk cycle; tracker vs harness walk start, in walk ms at
# rate 1: free walk one game loop and a margin; aim walk adds the anim tick
# (the clip starts on intent, before the harness sees movement).
CYCLE_MS = 667
KERRIGAN_CYCLE_MS = 1000  # c_JUMP_GAIT_CYCLE_KERRIGAN
GAIT_WINDOW_MS = 80
GAIT_WINDOW_AIM_MS = 140
# The walk resume is sent on the anim tick after the release; the tracker
# runs on until then.
RESUME_WINDOW_MS = 150


def gait_const(name: str) -> float:
    """A c_JUMP_GAIT_* value from the map script."""
    match = re.search(rf"const (?:fixed|int) c_JUMP_GAIT_{name} = ([0-9.]+);", JUMP_CORE.read_text(encoding="utf-8"))
    if match is None:
        raise SystemExit(f"c_JUMP_GAIT_{name} not in {JUMP_CORE}")
    return float(match.group(1))


def strides_for(gait_ms: int, cycle_ms: int = CYCLE_MS) -> set[int]:
    """The stride whose Start clip begins nearest a forward walk phase.

    Mirror of gf_JumpGaitStride. The bank holds whole ms: within 3 ms of a
    stride boundary both strides are accepted."""
    count = int(gait_const("STRIDES"))
    out = set()
    for ms in (gait_ms - 3, gait_ms, gait_ms + 3):
        x = (ms / cycle_ms + gait_const("PUSH") - gait_const("FLIGHT") + 1.0) * count
        out.add(int(x + 0.5) % count)
    return out


def check_gait(checks, section: str, aim: bool, cycle_ms: int = CYCLE_MS) -> None:
    """R-JUMP-18: tracked walk phase, takeoff stride, and clip time messages."""
    gait, rate, walk, stride = (checks.value(section, "", k) for k in ("pressGaitMs", "pressRate100", "walkMs", "pressStride"))
    log = checks.value(section, "", "setTimeLog") or ""
    clips = [clip for clip in (checks.value(section, "", "clipLog") or "").split(";") if clip]
    print(f"{section} gait: gaitMs={gait} rate100={rate} walkMs={walk} stride={stride} setTimeLog={log}")
    # The tracked phase matches the walk time the harness measured (engine
    # position), within one game loop and one anim tick of clip start.
    ok = None not in (gait, rate, walk) and walk >= 0
    if ok:
        expected = (walk * rate / 100.0) % cycle_ms
        diff = abs(gait - expected)
        diff = min(diff, cycle_ms - diff)
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
    want = set() if gait is None else strides_for(gait, cycle_ms)
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
        stop = ((gait_const("FLIGHT") + stride / gait_const("STRIDES") + gait_const("LAND")) % 1.0) * cycle_ms
        late = (resume[0] - stop) % cycle_ms
        window = RESUME_WINDOW_MS * rate / 100.0
        _report(checks, f"{section} walk resumes where the landing stops", late <= window or cycle_ms - late <= 5, f"resume={resume[0]} stop={stop:.0f} late={late:.0f} window={window:.0f}")
    checks.false(section, "", "resumePending")
    checks.eq(section, "", "endStride", -1)


def check_no_gait(checks, section: str) -> None:
    """Negative: an idle jump sets no clip time and uses no stride."""
    checks.eq(section, "", "setTimes", 0)
    checks.eq(section, "", "pressStride", -1)
