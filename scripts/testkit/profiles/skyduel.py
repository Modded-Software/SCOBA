"""Sky BC profile: one MengskBC over X Center at its unit height, two at the
map edge north and east of it at twice that height, all holding still
(no move, no turn, even when ordered), the Leviathan hidden.

Engine reads only. Size (actor scale) has no engine getter: operator check.
"""

from __future__ import annotations

import math
from pathlib import Path

from project_root import project_root

from ..map_builder import TestMapSpec
from ..runner import TestRunSpec
from .registry import PROFILE_BANKS, PROFILE_OUTPUTS

ROOT = project_root()
S = "sd_main"
ON_SPOT = 4.0  # world, from the region center
FACING_TOL = 5.0  # degrees
BC_FACING = math.degrees(5.547)  # placed rotation of all three
BASE_HEIGHT = 256.0  # MengskBC UnitData Height
HEIGHT_TOL = 2.0
SPOTS = (("center", BASE_HEIGHT), ("north", 2.0 * BASE_HEIGHT), ("east", 2.0 * BASE_HEIGHT))
HOLD_TOL = 0.1  # world: a held BC does not drift
SPREAD = 100.0  # world: the raised BCs are this far from the center one


def _xy(checks, key: str) -> tuple[float, float] | None:
    raw = checks.value(S, "", key)
    if not raw:
        return None
    x, y = (int(v) / 100.0 for v in str(raw).split(","))
    return x, y


def _report(checks, name: str, ok: bool, detail: str) -> None:
    print(f"{name}: {detail} {'PASS' if ok else 'FAIL'}")
    if not ok:
        checks.failures += 1


def _wrap(a: float) -> float:
    return (a + 180.0) % 360.0 - 180.0


def _num(checks, key: str) -> float | None:
    raw = checks.value(S, "", key)
    return None if raw is None else int(raw) / 100.0


def check_spot(checks, tag: str, height: float) -> None:
    for t in (tag, tag + "Late"):
        print(
            f"{S} raw {t} region={_xy(checks, t + 'Region100')} count={checks.value(S, '', t + 'Count')}"
            f" at={_xy(checks, t + 'At100')} height={_num(checks, t + 'Height100')}"
            f" facing={_num(checks, t + 'Facing100')} owner={checks.value(S, '', t + 'Owner')}"
        )
    checks.eq(S, "", tag + "Count", 1)
    checks.eq(S, "", tag + "Owner", 7)
    region = _xy(checks, tag + "Region100")
    at = _xy(checks, tag + "At100")
    d = math.dist(at, region) if at and region else 9999.0
    _report(checks, f"{S} BC over {tag}", d <= ON_SPOT, f"dist={d:.2f}")
    for t in (tag, tag + "Late"):
        h = _num(checks, t + "Height100")
        ok = h is not None and abs(h - height) <= HEIGHT_TOL
        _report(checks, f"{S} {t} height", ok, f"height={h} want={height}")
    f = _num(checks, tag + "Facing100")
    ok = f is not None and abs(_wrap(f - BC_FACING)) <= FACING_TOL
    _report(checks, f"{S} {tag} facing", ok, f"facing={f} want={BC_FACING:.2f}")
    # Hold: no drift, no turn over 2 s; suppressed states set; no live order.
    late = _xy(checks, tag + "LateAt100")
    drift = math.dist(at, late) if at and late else 9999.0
    _report(checks, f"{S} {tag} did not move", drift <= HOLD_TOL, f"drift={drift:.3f}")
    fl = _num(checks, tag + "LateFacing100")
    turn = abs(_wrap(fl - f)) if f is not None and fl is not None else 9999.0
    _report(checks, f"{S} {tag} did not turn", turn <= 0.01, f"turn={turn:.3f}")
    for t in (tag, tag + "Late"):
        checks.true(S, "", t + "MoveSup")
        checks.true(S, "", t + "TurnSup")
    checks.eq(S, "", tag + "LateOrders", 0)


def check_main(checks) -> None:
    print(f"{S} raw bcAll count={checks.value(S, '', 'bcAllCount')}")
    # Exactly three BCs (negative: none left at an old spot).
    checks.eq(S, "", "bcAllCount", 3)
    for tag, height in SPOTS:
        check_spot(checks, tag, height)
    # The move order sent to the center BC (raw; it must change nothing above).
    print(f"{S} raw pushMoveIssued={checks.value(S, '', 'pushMoveIssued')}")
    # Spread: north is due north of center, east due east, both far from it.
    c = _xy(checks, "centerAt100")
    n = _xy(checks, "northAt100")
    e = _xy(checks, "eastAt100")
    if c and n and e:
        _report(checks, f"{S} north BC north of center", n[1] - c[1] >= SPREAD and abs(n[0] - c[0]) <= ON_SPOT, f"d={n[0] - c[0]:.1f},{n[1] - c[1]:.1f}")
        _report(checks, f"{S} east BC east of center", e[0] - c[0] >= SPREAD and abs(e[1] - c[1]) <= ON_SPOT, f"d={e[0] - c[0]:.1f},{e[1] - c[1]:.1f}")
        # Negative: the two raised BCs are not stacked.
        _report(checks, f"{S} negative: north and east not stacked", math.dist(n, e) >= SPREAD, f"dist={math.dist(n, e):.1f}")
    else:
        _report(checks, f"{S} spread read", False, f"c={c} n={n} e={e}")
    # Negative: the center BC is not raised.
    hc = _num(checks, "centerHeight100")
    _report(checks, f"{S} negative: center BC not raised", hc is not None and hc < 1.5 * BASE_HEIGHT, f"height={hc}")
    # Leviathan: still placed and alive, hidden, and stays hidden.
    for t in ("lev", "levLate"):
        print(f"{S} raw {t} count={checks.value(S, '', t + 'Count')} hidden={checks.value(S, '', t + 'Hidden')} alive={checks.value(S, '', t + 'Alive')}")
        checks.eq(S, "", t + "Count", 1)
        checks.true(S, "", t + "Hidden")
        checks.true(S, "", t + "Alive")


def map_spec() -> TestMapSpec:
    return TestMapSpec(
        profile="skyduel",
        source=ROOT / "out" / "SCOBA256.SC2Map",
        output=PROFILE_OUTPUTS["skyduel"],
        bank_names=PROFILE_BANKS["skyduel"],
        galaxy_files=(
            ROOT / "scripts" / "testkit" / "galaxy" / "common.galaxy",
            ROOT / "scripts" / "testkit" / "galaxy" / "skyduel.galaxy",
        ),
        galaxy_includes=(
            "scripts/test/skyduel/common",
            "scripts/test/skyduel/skyduel",
        ),
        init_calls=("gt_SkyDuelTest_Init();",),
    )


def on_ready(ctx, data: dict) -> None:
    return


def check(ctx, data: dict, checks) -> None:
    for error in ctx.errors:
        print(f"{error} FAIL")
        checks.failures += 1
    checks.eq("meta", "", "done", 1)
    checks.eq("sd_end", "", "RealClicks", 0)
    check_main(checks)


def run_spec(launch_timeout_s: float, case_timeout_s: float, run_root: Path) -> TestRunSpec:
    return TestRunSpec(
        profile="skyduel",
        map_name="SCOBA.SC2Map",
        map_source=PROFILE_OUTPUTS["skyduel"],
        map_cache_name="SCOBA.SC2Map",
        bank_names=PROFILE_BANKS["skyduel"],
        ready_section="sd_start",
        ready_key="ready",
        launch_timeout_s=launch_timeout_s,
        case_timeout_s=case_timeout_s,
        run_root=run_root,
        on_ready=on_ready,
        check=check,
    )
