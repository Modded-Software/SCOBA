"""baseai mode group: the base AI lane mode (R-BASE-37). Scenarios in
scripts/testkit/galaxy/baseai/baseai_mode.galaxy. SC2_BA_MODE picks the mode
of the test map; unset, the map's default."""

from __future__ import annotations

from mapgen import player_slots
from mapgen.base_mode import DEFAULT, MIDDLE_LANES, MODE_VALUES, lanes_with_base

from .baseai_common import WORKERS
from .baseai_env import base_mode

S = "ba_mode"
LANES = range(1, 7)
UNIT_LANES = range(8)


def check_unit(checks) -> None:
    """gf_BaseAiLaneHasBase: middle gives the middle lanes, 3v3 all six; no lane outside 1..6."""
    for lane in UNIT_LANES:
        checks.eq(S, "", f"middle{lane}", lane in MIDDLE_LANES)
        checks.eq(S, "", f"3v3{lane}", 1 <= lane <= 6)


def check_lanes(checks, mode: str) -> None:
    """The real map-init path: bases and AI on the mode's lanes only; waves on every lane."""
    with_base = lanes_with_base(mode)
    for lane in LANES:
        seat, owner, _race = player_slots.LANES[lane]
        k = f"p{owner}"
        print(f"{S} raw lane {lane} {k}: " + " ".join(
            f"{t}{n}={checks.value(S, k, t + n)}" for t in ("t0", "t1", "t120")
            for n in ("Started", "Halls", "Workers", "Mobile", "MinCollected", "GasBuilds", "GasGathers")))
        # Nothing before the init.
        checks.false(S, k, "t0Started")
        checks.eq(S, k, "t0Halls", 0)
        checks.eq(S, k, "t0Workers", 0)
        if lane in with_base:
            checks.true(S, k, "t1Started")
            checks.true(S, k, "t1HallSet")
            checks.eq(S, k, "t1Halls", 1)
            checks.eq(S, k, "t1Workers", WORKERS)
            checks.true(S, k, "t120Started")
            checks.gt(S, k, "t120Halls", 0)
            checks.gt(S, k, "t120MinCollected", 0)
        else:
            # Negative: no hall, no worker, no AI, no gas order, nothing mined.
            for t in ("t1", "t120"):
                checks.false(S, k, f"{t}Started")
                checks.false(S, k, f"{t}HallSet")
                checks.eq(S, k, f"{t}Halls", 0)
                checks.eq(S, k, f"{t}Workers", 0)
                # No new unit: placed map units, if any, stay as at t0.
                checks.eq(S, k, f"{t}Mobile", checks.value(S, k, "t0Mobile"))
                checks.eq(S, k, f"{t}GasBuilds", 0)
                checks.eq(S, k, f"{t}GasGathers", 0)
            checks.eq(S, k, "t120MinCollected", 0)
        # Every lane's seat still gets its waves (R-BASE-22): wave units seen
        # between t1 and t120 (peak of 2 s looks; a wave may die before t120).
        sk = f"p{seat}"
        print(f"{S} raw seat {seat}: t1SeatMobile={checks.value(S, sk, 't1SeatMobile')} "
              f"t120SeatMobile={checks.value(S, sk, 't120SeatMobile')}")
        checks.gt(S, sk, "SeatPeak", 0)


def check_mode(checks) -> None:
    mode = base_mode() or DEFAULT
    print(f"{S} mode: {mode}")
    checks.eq(S, "", "mode", MODE_VALUES[mode])
    check_unit(checks)
    check_lanes(checks, mode)
