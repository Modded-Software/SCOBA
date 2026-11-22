"""baseai probe group: the engine assumptions A1, A3-A8 of SPEC-BASE-AI 3, on a
harness-made base for the base owners of lanes 2 (Terran) and 5 (Zerg). Raw
values are printed first, so a failure shows what the engine did. Scenarios
in scripts/testkit/galaxy/baseai/baseai.galaxy."""

from __future__ import annotations

from mapgen import player_slots

from .baseai_common import (DIFFICULTY, PLACED_DEPOTS, PLAYER_STATUS_ACTIVE, PLAYER_TYPE_COMPUTER, SNAP_KEYS,
                            WORKERS, _raw)

# The base owners of lanes 2 (Terran) and 5 (Zerg).
PROBE_PLAYERS = (player_slots.LANES[2][1], player_slots.LANES[5][1])
# LotV melee supply (voidmulti): CC 15; Hatchery 6 plus one Overlord 8.
START_SUPPLY = {PROBE_PLAYERS[0]: 15 + 8 * PLACED_DEPOTS, PROBE_PLAYERS[1]: 14}
SLOT_RACES = dict(player_slots.BASE_OWNERS)
MINERALS = 50
FIELDS = 8
GEYSERS = 2
TOWN_INVALID = -1  # c_townStateInvalid
# A unit that is left alone does not drift further than this (x100).
STILL_100 = 50
UNIT_KEYS = ("Valid", "Script", "InWave", "Moved100", "UsingSupply", "Orders", "O0",
             "From100", "At100", "Near", "NearAt100")


def check_probe(checks) -> None:
    s = "ba_probe"
    print(f"{s} raw excludedAtStart={checks.value(s, '', 'excludedAtStart')}")
    for p in PROBE_PLAYERS:
        k = f"p{p}"
        _raw(checks, s, k, ("Type", "Race", "StartLoc100", "DiffBefore", "DiffAfter", "AiDiff", "HallValid",
                            "HallAt100", "HallMoved100", "Fields", "Geysers"))
        for tag in ("t0", "t1", "t60", "t120", "t180"):
            _raw(checks, s, k + tag, SNAP_KEYS)
    for tag in ("t60Out", "t60In", "t120Out", "t120In"):
        _raw(checks, s, tag, UNIT_KEYS)
    print(f"{s} raw supply: before={checks.value(s, '', 'supplyBefore')} made2={checks.value(s, '', 'supplyMade2')} "
          f"excluded1={checks.value(s, '', 'supplyExcluded1')}")

    # Lane base owners: computer players with their race (player_slots.py).
    for p, race in SLOT_RACES.items():
        _raw(checks, s, f"p{p}", ("Type", "Race", "Status"))
        checks.eq(s, f"p{p}", "Type", PLAYER_TYPE_COMPUTER)
        checks.eq(s, f"p{p}", "Race", race)
        checks.eq(s, f"p{p}", "Status", PLAYER_STATUS_ACTIVE)

    # Setup: the harness base exists, so a failure below is the AI's.
    for p in PROBE_PLAYERS:
        k = f"p{p}"
        checks.true(s, k, "HallValid")
        checks.eq(s, k, "Fields", FIELDS)
        checks.eq(s, k, "Geysers", GEYSERS)
        checks.eq(s, k + "t0", "Workers", WORKERS)
        checks.eq(s, k + "t0", "Minerals", MINERALS)
        # Melee supply: the stock AI opens on 12 workers below the cap.
        checks.eq(s, k + "t0", "SupplyMade", START_SUPPLY[p])
        # A3: the difficulty takes.
        checks.eq(s, k, "DiffAfter", DIFFICULTY)
        checks.eq(s, k, "AiDiff", DIFFICULTY)
        # A4: the town at the base point is declared.
        checks.gt(s, k + "t1", "TownState", TOWN_INVALID)
        # A1: the AI gathers, builds and trains.
        checks.gt(s, k + "t60", "MinCollected", 0)
        checks.gt(s, k + "t120", "Workers", WORKERS)
        # A7, A8: new structures in the base.
        checks.gt(s, k + "t120", "Structures", 1)
        # Count includes the pre-existing script units, so compare with t1.
        # Barracks start near t60 (46 s build, 18 s Marine): read at t180.
        checks.gt(s, k + "t180", "Army", checks.value(s, k + "t1", "Army"))
        if p == 2:
            # The AI places depots with c_canLower: a spot must exist.
            place = checks.value(s, k + "t0", "PlaceDepotLow")
            checks._record(s, k + "t0", "PlaceDepotLowFound", place not in (None, "null"), True)
            depots = (checks.value(s, k + "t120", "Supply") or 0) + (checks.value(s, k + "t120", "SupplyLow") or 0)
            checks._record(s, k + "t120", "DepotsAny", depots > 0, True)
            checks.gt(s, k + "t120", "SupplyMade", START_SUPPLY[p])

    # A5: the excluded Marine stays out of AI waves and AI orders.
    for tag in ("t60Out", "t120Out"):
        checks.true(s, tag, "Valid")
        checks.true(s, tag, "Script")
        checks.false(s, tag, "InWave")
        checks.lt(s, tag, "Moved100", STILL_100)
        checks.eq(s, tag, "Orders", 0)
    # Negative control: the AI does take a unit that is not excluded.
    checks.true(s, "t120In", "Valid")
    checks.false(s, "t120In", "Script")
    checks.true(s, "t120In", "InWave")
    # A6: the excluded Marine frees its supply; the control keeps it.
    before = checks.value(s, "", "supplyBefore")
    made = checks.value(s, "", "supplyMade2")
    excluded = checks.value(s, "", "supplyExcluded1")
    ok = None not in (before, made, excluded) and made - before == 2 and made - excluded == 1
    print(f"{s} A6 supply: before={before} made2={made} excluded1={excluded} {'PASS' if ok else 'FAIL'}")
    if not ok:
        checks.failures += 1
    checks.false(s, "t120Out", "UsingSupply")
    checks.true(s, "t120In", "UsingSupply")
