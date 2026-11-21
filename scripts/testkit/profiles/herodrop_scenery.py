"""Scenery and escort checks (operator 2026-11-20).

Groups of the herodrop profile (harness: galaxy/herodrop_scenery.galaxy).
- scenery (REQ-SCENERY): storms around the Overmind, the S6 foreground
  pods; no orbit Wraiths.
- escort (REQ-HERO-DROP R-DROP-14): the lane wave with a hero drop.
Engine reads. How storms and pods look is an operator check.
"""

from __future__ import annotations

from .herodrop_zoom import _report

STORM_MIN = 5  # the operator's "at least 5"
STORM_RADIUS_100 = 1600  # c_STORM_RADIUS (operator 2026-11-20: was 32)
S6_PODS = 3
S7_LAND_TOL_MS = 150  # two game ticks and the trigger start
S6_SEARCH_100 = 1600  # the spot search may leave the 3-cell circle (ring search)
ESCORT_TURN_100 = 100  # pods face as the hero pod, within 1 degree
DROP_YAW = 225.0  # c_DROP_YAW: southwest
POD_SPACING_100 = 400  # c_POD_SPOT_SPACING


def check_scenery(checks) -> None:
    s = "scenery"
    print(f"{s} raw storms={checks.value(s, '', 'stormRaw')} far100={checks.value(s, '', 'stormFar100')}")
    # Storms (R-SCN-1).
    checks.true(s, "", "stormHomeValid")
    checks.true(s, "", "stormActorValid")
    count = checks.value(s, "", "stormCount") or 0
    checks.between(s, "", "stormCount", STORM_MIN, 999)
    checks.eq(s, "", "stormActors", count)
    checks.eq(s, "", "stormInMap", count)
    # Negative: none past the radius.
    checks.between(s, "", "stormFar100", 1, STORM_RADIUS_100)
    # S6 pods (R-SCN-2): three on the first call; negative: none more after.
    checks.eq(s, "", "s6Before", 0)
    checks.eq(s, "", "s6Made", S6_PODS)
    # Spread in time (1 s apart): made 1, 2, 3 at 0.5, 1.5, 2.5 s. Negative: not all at once.
    trace = str(checks.value(s, "", "s6MadeTrace") or "")
    _report(checks, f"{s} S6 pods one by one", trace[:1] == "1" and "2" in trace and trace[-1:] == "3", f"made every 0.5 s={trace}")
    # Apart on the ground.
    checks.between(s, "", "s6Gap100", 800, 999999)
    checks.eq(s, "", "s6PodUnits", S6_PODS)
    checks.between(s, "", "s6Off100", 0, S6_SEARCH_100)
    checks.eq(s, "", "s6MadeAgain", S6_PODS)
    # The three S6 pods and the S7 camera pod; negative: no more.
    checks.eq(s, "", "s6PodUnitsAgain", S6_PODS + 1)
    # S7 camera pod (R-SCN-4): one, on the S7 eye, landing at the cut into
    # S7 (the S6 length after the S6 cut). Negative: none in the first 3 s.
    print(f"{s} raw s7: " + " ".join(f"{k}={checks.value(s, '', k)}" for k in ("s7MadeEarly", "s7Made", "s7DelayMs", "s7LandMs", "s6LengthMs", "s7Off100", "s7NearUnits")))
    checks.eq(s, "", "s7MadeEarly", 0)
    checks.eq(s, "", "s7Made", 1)
    checks.eq(s, "", "s7Off100", 0)
    checks.eq(s, "", "s7NearUnits", 1)
    length = checks.value(s, "", "s6LengthMs") or 0
    checks.between(s, "", "s7LandMs", length - S7_LAND_TOL_MS, length + S7_LAND_TOL_MS)
    # Negative (R-SCN-3 withdrawn): no neutral Wraith; every Wraith on the
    # map is an air creep of the Terran side.
    checks.eq(s, "", "orbitNeutral", 0)
    checks.eq(s, "", "wraithsAll", checks.value(s, "", "airAlive") or 0)


def check_escort(checks) -> None:
    s = "drop_escort"
    keys = ("aliveWaves", "alivePods", "waves", "heroFacing100", "heroTravel100", "escortFacing100", "podReads", "podTurn100", "podNear100", "podGap100", "units", "unitsAlive", "unitsOwned", "unitsHidden", "unitsOrdered", "unitTypes", "podsLeft", "goliathsBefore", "ownGoliathInWave")
    print(f"{s} raw " + " ".join(f"{k}={checks.value(s, '', k)}" for k in keys))
    # Negative: the hero alive, no escort and no pod.
    checks.eq(s, "", "aliveWaves", 0)
    checks.eq(s, "", "alivePods", 0)
    checks.true(s, "", "podSeen")
    checks.eq(s, "", "waves", 1)
    # The hero pod travels southwest; the escort pods face as it does.
    travel = ((checks.value(s, "", "heroTravel100") or 0) / 100.0) % 360.0
    _report(checks, f"{s} hero pod travels southwest", abs(travel - DROP_YAW) <= 1.0, f"travel={travel:.2f}")
    checks.gt(s, "", "podReads", 0)
    checks.between(s, "", "podTurn100", 0, ESCORT_TURN_100)
    # Off the hero pod and off each other.
    checks.between(s, "", "podNear100", POD_SPACING_100, 999999)
    checks.between(s, "", "podGap100", POD_SPACING_100, 999999)
    checks.true(s, "", "landed")
    checks.true(s, "", "heroAlive")
    # The wave's own units: 4 Marines, 2 Marauders, 1 Firebat and always a
    # Goliath (operator 2026-11-20), here with the seat already owning one
    # (a reinforcement wave would bring none). All alive, the seat's, out
    # of the pods (shown), with their lane order.
    checks.between(s, "", "goliathsBefore", 1, 99)
    # Negative: the wave's Goliath is not the one the seat had.
    checks.false(s, "", "ownGoliathInWave")
    types = str(checks.value(s, "", "unitTypes") or "").split()
    counts = {k: types.count(k) for k in ("Marine", "Marauder", "Firebat", "Goliath")}
    _report(checks, f"{s} wave units", counts["Marine"] == 4 and counts["Marauder"] == 2 and counts["Firebat"] == 1 and counts["Goliath"] == 1 and sum(counts.values()) == len(types), f"types={types}")
    n = len(types)
    checks.eq(s, "", "units", n)
    checks.eq(s, "", "unitsAlive", n)
    checks.eq(s, "", "unitsOwned", n)
    checks.eq(s, "", "unitsHidden", 0)
    checks.eq(s, "", "unitsOrdered", n)
    checks.eq(s, "", "podsLeft", 0)
