"""Touchdown start state (operator 2026-11-20): TPS, camera arm 1.0, pitch 0.

Split from herodrop.py (file length). Used by herodrop and intro. Reads
engine camera pitch and distance; the desired arm is the script value the
collision tick drives the engine distance to.
"""

from __future__ import annotations

from .herodrop_zoom import _report

LAND_ARM_100 = 100
# The collision clamp may shorten the arm where terrain rises behind the
# eye; at pitch 0 the eye is at the target height, so a short arm is raw.
LAND_DIST_100 = (90, 105)
LAND_PITCH_TOL = 2.0
START_PITCH = 30.0  # the scenario reset pitch (herodrop_land.galaxy)


def signed_pitch(raw100) -> float:
    return ((raw100 or 0) / 100.0 + 180.0) % 360.0 - 180.0


def check_start_state(checks, s: str, t: str, dist_key: str = "CamDist100", pitch_key: str = "CamPitch100") -> None:
    """TPS on, desired arm 1.0, engine distance near 1.0, engine pitch near 0."""
    print(f"{s} raw {t} pitch100={checks.value(s, t, pitch_key)} dist100={checks.value(s, t, dist_key)} desired100={checks.value(s, t, 'CamDesired100')}")
    checks.true(s, t, "TpsMode")
    checks.eq(s, t, "CamDesired100", LAND_ARM_100)
    checks.between(s, t, dist_key, *LAND_DIST_100)
    pitch = signed_pitch(checks.value(s, t, pitch_key))
    _report(checks, f"{s} {t} camera pitch level", abs(pitch) <= LAND_PITCH_TOL, f"pitch={pitch:.2f}")


def check_land(checks) -> None:
    s = "drop_land"
    checks.true(s, "", "podSeen")
    checks.true(s, "", "landed")
    print(f"{s} raw preTps={checks.value(s, '', 'preTps')} tpsOffOrderOk={checks.value(s, '', 'tpsOffOrderOk')} tpsOffDisabled={checks.value(s, '', 'tpsOffDisabled')} tpsOffHidden={checks.value(s, '', 'tpsOffHidden')} orders={checks.value(s, '', 'tpsOrders')} returns={checks.value(s, 't0', 'Returns')}")
    # Precondition, negative: Point & Click before, pitch 30, arm by height.
    checks.false(s, "t0", "TpsMode")
    checks.false(s, "tdead", "SavedTps")
    checks.gt(s, "t0", "CamDesired100", LAND_ARM_100)
    before = signed_pitch(checks.value(s, "t0", "CamPitch100"))
    _report(checks, f"{s} t0 camera pitch at the reset pitch", abs(before - START_PITCH) <= LAND_PITCH_TOL, f"pitch={before:.2f}")
    checks.eq(s, "tafter", "Landings", (checks.value(s, "t0", "Landings") or 0) + 1)
    checks.true(s, "tafter", "Alive")
    check_start_state(checks, s, "tafter")
    # TPS came on through its toggle command, so the toggle works after
    # the landing (operator 2026-11-20). Negative: the off order leaves TPS.
    print(f"{s} raw tpsOnOrders={checks.value(s, '', 'tpsOnOrders')}")
    checks.gt(s, "", "tpsOnOrders", 0)
    checks.false(s, "", "afterOffHidden")
    checks.false(s, "", "afterOffTps")
    checks.true(s, "", "afterOnTps")
    # The pod fall sound (operator 2026-11-20): one per drop, id valid.
    # Audibility is an operator check.
    checks.true(s, "tafter", "PodSoundValid")
    checks.eq(s, "tafter", "PodSounds", (checks.value(s, "t0", "PodSounds") or 0) + 1)


SPOT_PICKS = 6 * 4 * 3 + 1 + 24  # lanes x rounds x pods, the depot spot, the depot picks
SPOT_SPACING_100 = 400  # c_POD_SPOT_SPACING
SPOT_DEPOT_CHEB = 3.0  # 4x4 pod square vs 2x2 depot: overlap below 3


def check_spot(checks) -> None:
    """Pod spots: 4x4 pathable, no ground units, spaced; a depot is avoided."""
    s = "drop_spot"
    print(f"{s} raw first picks={checks.value(s, '', 'raw')} ring={checks.value(s, '', 'ring')} none={checks.value(s, '', 'none')} minGap100={checks.value(s, '', 'minGap100')} minDepot100={checks.value(s, '', 'minDepot100')}")
    checks.eq(s, "", "picks", (checks.value(s, "", "picks0") or 0) + SPOT_PICKS)
    checks.eq(s, "", "none", checks.value(s, "", "none0") or 0)
    checks.true(s, "", "treeSet")
    # The second tree: its own actor.
    checks.true(s, "", "tree2Set")
    checks.eq(s, "", "blockedCells", 0)
    checks.eq(s, "", "units", 0)
    checks.between(s, "", "minGap100", SPOT_SPACING_100, 999999)
    # Negative: the depot blocks its cells; no pick overlaps it.
    checks.true(s, "", "depotValid")
    checks.gt(s, "", "depotCellsBlocked", 0)
    checks.false(s, "", "depotSpotFree")
    checks.eq(s, "", "onDepot", 0)
    checks.between(s, "", "minDepot100", int(SPOT_DEPOT_CHEB * 100), 999999)
