"""Camera by unit height (R-TPS-90), the combat group `camheight`.

Each section is one bound unit. The target height and the arm scale with the
unit's measured height against Tosh: offset = 0.9 * h / h_tosh,
arm = 1.5 * h / h_tosh. The heights must equal the generator's.
Values are thousandths.
"""

from __future__ import annotations

from hitvolumes import camera_heights

from .bank_checks import _report

BASE_OFFSET = 0.9
BASE_ARM = 1.5
# FixedToInt truncates the thousandths; fixed math rounds at 1/4096.
TOL = 10
# The engine distance blends and the collision clamp may shorten it.
DIST_TOL = 50


def _want(height1000: int, ref1000: int, base: float) -> float:
    return base * 1000.0 * height1000 / ref1000


VIKING_ARM = 6000  # c_HERO_VIKING_CAM_DIST: the Viking keeps its own arm


def _unit(checks, section: str, unit_type: str, table: dict[str, float], arm_fixed: int | None = None) -> None:
    checks.eq(section, "", "type", unit_type)
    h = checks.value(section, "", "height1000")
    ref = checks.value(section, "", "ref1000")
    gen = table.get(unit_type)
    ok = h is not None and gen is not None and abs(h - gen * 1000.0) <= 2
    _report(checks, f"{section} height is the generated one", ok, f"bank={h} generated={gen}")
    if not h or not ref:
        _report(checks, f"{section} heights read", False, f"height={h} ref={ref}")
        return
    parts = checks.value(section, "", "parts1000") or 0
    applied = checks.value(section, "", "applied1000")
    want = _want(h, ref, BASE_OFFSET) + parts
    ok = applied is not None and abs(applied - want) <= TOL
    _report(checks, f"{section} target height", ok, f"applied={applied} want={want:.0f} parts={parts}")
    desired = checks.value(section, "", "desired1000")
    arm = _want(h, ref, BASE_ARM) if arm_fixed is None else float(arm_fixed)
    ok = desired is not None and abs(desired - arm) <= TOL
    _report(checks, f"{section} arm", ok, f"desired={desired} want={arm:.0f}")
    # Engine state: the camera distance reached the arm, or the clamp.
    engine = checks.value(section, "", "engineDist1000")
    safe = checks.value(section, "", "safeDist1000")
    goal = min(arm, safe) if safe is not None else arm
    ok = engine is not None and abs(engine - goal) <= DIST_TOL
    _report(checks, f"{section} engine distance", ok, f"engine={engine} goal={goal:.0f} safe={safe}")
    # The aim pick eye uses the same offset.
    ground = checks.value(section, "", "groundZ1000") or 0
    pick = checks.value(section, "", "pickOz1000")
    ok = pick is not None and abs(pick - ground - _want(h, ref, BASE_OFFSET)) <= TOL
    _report(checks, f"{section} pick eye height", ok, f"pick={pick} ground={ground}")


def check_camheight(checks) -> None:
    table = camera_heights.heights(camera_heights.load_json())
    # Unit: a height is known only of a unit whose type has a row; none stands in.
    checks.true("cam_known", "", "heroKnown")
    checks.true("cam_known", "", "spawnKnown")
    checks.false("cam_known", "", "nullKnown")
    checks.false("cam_known", "", "rowlessKnown")
    checks.true("cam_known", "", "restoredKnown")
    # The row read is the generator's height of the spawned type (raw value recorded).
    spawned = round(table["Zergling"] * 1000)
    checks.between("cam_known", "", "spawnHeight1000", spawned - TOL, spawned + TOL)
    # Tosh keeps the old fixed values.
    _unit(checks, "cam_tosh", "ToshSCOBA", table)
    checks.between("cam_tosh", "", "applied1000", 900 - TOL, 900 + TOL)
    checks.between("cam_tosh", "", "desired1000", 1500 - TOL, 1500 + TOL)
    _unit(checks, "cam_kerrigan", "KerriganSCOBA", table)
    _unit(checks, "cam_scv", "SCV", table)
    # Negative: Kerrigan is not on Tosh's fixed values, nor the old 2.5 arm.
    applied = checks.value("cam_kerrigan", "", "applied1000")
    ok = applied is not None and applied > 900 + 100
    _report(checks, "cam_kerrigan not the fixed 0.9", ok, f"applied={applied}")
    desired = checks.value("cam_kerrigan", "", "desired1000")
    ok = desired is not None and abs(desired - 2500) > 100 and desired > 1500 + 100
    _report(checks, "cam_kerrigan not the fixed 1.5 or 2.5 arm", ok, f"desired={desired}")
    # Viking: both forms by their own height, arm fixed at 6.
    _unit(checks, "cam_viking_air", "SCOBAVikingHero", table, VIKING_ARM)
    checks.eq("cam_viking_land", "", "typeBefore", "SCOBAVikingHero")
    _unit(checks, "cam_viking_land", "SCOBAVikingHeroAssault", table, VIKING_ARM)
    # Landed: no flight part left, and the base is the landed form's
    # (negative: not Tosh's 0.9, not sunk to the ground).
    checks.eq("cam_viking_land", "", "parts1000", 0)
    applied = checks.value("cam_viking_land", "", "applied1000")
    want = 1000.0 * BASE_OFFSET * table["SCOBAVikingHeroAssault"] / table["ToshSCOBA"]
    ok = applied is not None and abs(applied - want) <= TOL and applied > 2000
    _report(checks, "cam_viking_land camera at the landed height", ok, f"applied={applied} want={want:.0f}")


# Camera ground clamp (operator 2026-11-23): raw traces per game loop.
CLAMP_CASES = ("clamp_tps_sweep", "clamp_pnc_sweep", "clamp_tps_walk", "clamp_tps_up", "clamp_tps_free")
CLAMP_LOOPS = 48
SETTLE_FROM = 36  # the sweep holds its pitch from loop 33; 0.2 s more for the blend
SETTLE_TOL = 60  # 0.06: the blend and the 0.03 deadband


def _series(checks, section: str, key: str) -> list[int]:
    return [int(v) for v in (checks.value(section, "", key) or "").split()]


def reversals(values: list[int], noise: int = 10) -> int:
    """Direction changes of a series, steps under noise ignored."""
    turns, last = 0, 0
    for a, b in zip(values, values[1:]):
        step = b - a
        if abs(step) <= noise:
            continue
        sign = 1 if step > 0 else -1
        if last and sign != last:
            turns += 1
        last = sign
    return turns


def check_camclamp(checks) -> None:
    for section in CLAMP_CASES:
        dist, safe, clear = (_series(checks, section, key) for key in ("dist", "safe", "clear"))
        print(f"{section} pitch x10: {_series(checks, section, 'pitches')}")
        print(f"{section} tick log (tick:safe/dist/pitch10/yaw/tx,ty,tz,ground): {checks.value(section, '', 'tickLog')}")
        raw = " ".join(f"{key}={checks.value(section, '', key)}" for key in ("pitch100", "desired1000", "height1000", "targetZ1000", "groundZ1000", "tps"))
        print(f"{section} raw: {raw}")
        print(f"{section} dist: {dist}")
        print(f"{section} safe: {safe}")
        print(f"{section} clear: {clear}")
        print(f"{section} dist reversals={reversals(dist)} safe reversals={reversals(safe)} eye below ground={sum(1 for c in clear if c < 0)}")
        _report(checks, f"{section} traced", len(dist) == len(safe) == len(clear) == CLAMP_LOOPS, f"n={len(dist)}")
        if len(dist) != CLAMP_LOOPS:
            continue
        # Engine state: the eye never under the ground (the bounce dipped it
        # to -0.43, run combat/20261123-144957).
        low = min(clear)
        _report(checks, f"{section} eye stays above the ground", low >= 0, f"min clear1000={low}")
        # Once the pitch holds: no bounce, and the distance settles on the clamp.
        tail = dist[SETTLE_FROM:]
        turns = reversals(tail)
        _report(checks, f"{section} distance settles, no bounce", turns == 0, f"reversals={turns} tail={tail}")
        last = safe[-1]
        _report(checks, f"{section} distance at the clamp", abs(dist[-1] - min(last, 6000)) <= SETTLE_TOL, f"dist={dist[-1]} safe={last}")
    # The negative case: clear of the ground, the full arm.
    checks.eq("clamp_tps_free", "", "desired1000", 6000)
    free = _series(checks, "clamp_tps_free", "safe")
    _report(checks, "clamp_tps_free no clamp", bool(free) and min(free) == 6000, f"min safe={min(free) if free else None}")
    # The sweeps reach the ground: the clamp must act (else the test proves nothing).
    for section in ("clamp_tps_sweep", "clamp_pnc_sweep"):
        safe = _series(checks, section, "safe")
        _report(checks, f"{section} clamp acts", bool(safe) and min(safe) < 6000, f"min safe={min(safe) if safe else None}")
