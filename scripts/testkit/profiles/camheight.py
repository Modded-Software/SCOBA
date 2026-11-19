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
    # Unit: no unit falls back to Tosh's values.
    checks.between("cam_null", "", "offset1000", 900 - TOL, 900 + TOL)
    checks.between("cam_null", "", "arm1000", 1500 - TOL, 1500 + TOL)
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
