"""baseai macro group: all six owners under real conditions (waves on, the
operator in the Alt+4 Wraith): growth, sites and expansions, Terran hall
footprints, the map's gas orders. Scenarios in
scripts/testkit/galaxy/baseai/baseai_macro.galaxy."""

from __future__ import annotations

from mapgen import player_slots
from mapgen.footprints.hall import hall_footprint_id

from .baseai_common import DIFFICULTY, PLACED_DEPOTS, PLAYER_TYPE_COMPUTER, SNAP_KEYS, WORKERS, _ok, _raw
from .baseai_flight import check_flight
from .baseai_hall import HALL_PLACE, check_legs, hall_rows, show_grid
from .baseai_melee import check_growth, check_melee
from .baseai_viking import check_viking_form

# Lane owners (core/roster.galaxy, scripts/mapgen/player_slots.py): lane 1..6.
MACRO_OWNERS = tuple(player_slots.LANES[lane][1] for lane in range(1, 7))
MACRO_TAGS = ("t1", "t60", "t120", "t180", "t240", "t300", "t360", "t420", "t480")
MACRO_END = "t480"
AI_KEYS = ("HallAlive", "HallLife", "Queue", "Obstruction", "TownAt100", "Threats", "EnemiesNear", "MissFood",
           "MissMaker", "MissFighter", "FighterMaker", "Makers", "Fighters", "FighterTypes", "Larva", "Eggs", "Food",
           "FoodQueued", "MakersRaw", "DepotsQueued")
TERRAN_OWNERS = MACRO_OWNERS[:3]


def check_hall_footprint(checks) -> None:
    """R-BASE-30, R-FP-10: the Command Center blocks its measured cells (legs);
    the middle stays open. So do the Orbital Command and the Planetary Fortress."""
    for s in ("ba_macro", "ba_macro_end"):
        for p in TERRAN_OWNERS:
            k = f"p{p}"
            print(f"{s} raw {k} hall: " + " ".join(f"{n}={checks.value(s, k, n)}" for n in
                                                  ("HallType", "HallAt100", "HallFoot", "HallPlace", "HallBlocked10",
                                                   "HallRefused", "HallHub")))
            print(show_grid(checks, s, k + "Hall", f"{s} raw {k} hall grid"))
            checks.eq(s, k, "HallPlace", HALL_PLACE)
            # Units walk under the middle.
            checks.eq(s, k, "HallBlocked10", 0)
            checks.eq(s, k, "HallFoot", hall_footprint_id(hall_rows()))
            # Minerals and buildings may block more cells: every measured cell is blocked.
            check_legs(checks, s, k + "Hall", exact=False)


SUPPLY_MAX = 200           # c_SUPPLY_MAX, systems/base/base_ai
SITES = 12                 # 4 jungles x 2 halls + 2 guarded camps x 2 (front, back)
LINES = SITES + 6          # plus the six mains
EXPANDERS_MIN = 3          # owners with a hall at a site by t480
SITE_HALL_R100 = 1600      # an expansion hall within 16 of its site


def check_sites(checks) -> None:
    """Expansion sites (systems/base/base_sites), pile amounts, AI expansions."""
    s = "ba_macro"
    print(f"{s} raw sites: " + " ".join(str(checks.value(s, '', f'site{i}')) for i in range(SITES)))
    print(f"{s} raw res: " + " ".join(f"{k}={checks.value(s, '', k)}" for k in
                                      ("mainFieldRes", "mainGeyserRes", "siteFieldRes", "siteGeyserRes", "resMult")))
    checks.eq(s, "", "siteCount", SITES)
    for i in range(SITES):
        checks.true(s, f"site{i}", "Ok")
    checks.eq(s, "", "siteFields", 8 * LINES)
    checks.eq(s, "", "siteGeysers", 2 * LINES)
    # 4x stock: MineralField 1500 (liberty MineralFieldMinerals), geyser 2500.
    for k, want in (("mainFieldRes", 6000), ("siteFieldRes", 6000), ("mainGeyserRes", 10000), ("siteGeyserRes", 10000)):
        checks.eq(s, "", k, want)
    checks.eq(s, "", "siteFieldRes", checks.value(s, "", "mainFieldRes"))
    expanders = []
    off_site = []
    for p in MACRO_OWNERS:
        k = f"p{p}{MACRO_END}"
        at = str(checks.value(s, k, "HallsAt") or "").split()
        print(f"{s} raw p{p} halls: " + " ".join(f"{t}={checks.value(s, f'p{p}{t}', 'Halls')}" for t in MACRO_TAGS[1:])
              + f" at={at}")
        print(f"{s} raw p{p} expand gate: " + " ".join(
            f"{t}={checks.value(s, f'p{p}{t}', 'NearbyOpen')}/{checks.value(s, f'p{p}{t}', 'NextTownSlot')}"
            f"/{checks.value(s, f'p{p}{t}', 'TownStates')}"
            for t in MACRO_TAGS) + f" siteNearest100={checks.value(s, f'p{p}t1', 'SiteNearest100')}")
        sites = [a for a in at if not a.startswith("main@")]
        if sites:
            expanders.append(p)
        off_site += [f"p{p}:{a}" for a in sites if int(a.split("@")[1]) > SITE_HALL_R100]
    _ok(checks, s, f"at least {EXPANDERS_MIN} owners expanded by {MACRO_END}", len(expanders) >= EXPANDERS_MIN,
        f"expanded={expanders}")
    # Negative: no expansion hall away from every site.
    _ok(checks, s, "expansion halls at sites", not off_site, f"off={off_site}")


def check_macro(checks) -> None:
    """All six owners under real conditions. Raw timeline first; then each
    owner must grow supply, finish a production structure and make units."""
    s = "ba_macro"
    print(f"{s} raw wraith: " + " ".join(f"{k}={checks.value(s, '', k)}" for k in
                                         ("switchWaitTicks", "wraithValid", "wraithType", "switchReady", "dropPending",
                                          "activeBefore", "toshValid", "activeAfter", "wraithTpsBefore", "wraithTpsOrder", "wraithHasToggle", "wraithTpsBehavior",
                                          "wraithIsTpsUnit")))
    checks.true(s, "", "wraithActive")
    checks.eq(s, "", "wraithTps", False)       # regular unit: PNC only
    check_viking_form(checks, s, "vikStart")
    check_flight(checks, s)
    check_hall_footprint(checks)
    check_sites(checks)
    check_melee(checks, MACRO_OWNERS, MACRO_TAGS, _ok)
    for p in MACRO_OWNERS:
        k = f"p{p}"
        print(f"{s} raw {k}: " + " ".join(f"{key}={checks.value(s, k, key)}" for key in
                                           ("Lane", "Type", "Status", "Race", "Started", "HallValid", "HallAt100",
                                            "Difficulty")))
        for t in MACRO_TAGS:
            _raw(checks, s, k + t, SNAP_KEYS + AI_KEYS)
    for p in MACRO_OWNERS:
        k = f"p{p}"
        checks.eq(s, k, "Type", PLAYER_TYPE_COMPUTER)
        checks.true(s, k, "Started")
        checks.true(s, k, "HallValid")
        checks.eq(s, k, "Difficulty", DIFFICULTY)
        checks.gt(s, k + "t60", "MinCollected", 0)
        checks.gt(s, k + "t240", "Fighters", 0)
        checks.gt(s, k + MACRO_END, "Workers", WORKERS)
        # Supply max for every player; no depots, no Overlords (operator).
        for t in MACRO_TAGS:
            checks.eq(s, k + t, "SupplyMade", SUPPLY_MAX)
            checks.eq(s, k + t, "FoodQueued", 0)
            # Terran: the two placed depots only (R-BASE-29); no new ones.
            checks.eq(s, k + t, "DepotsQueued", PLACED_DEPOTS if p in TERRAN_OWNERS else 0)
        checks.gt(s, k + MACRO_END, "Makers", 0)
        checks.gt(s, k + MACRO_END, "Fighters", 0)
        used = [checks.value(s, k + t, "SupplyUsed") for t in MACRO_TAGS]
        check_growth(checks, s, k, MACRO_TAGS, _ok)
        # Not capped: used below made at least once after t60, per 2 min.
        capped = [MACRO_TAGS[i] for i in range(2, len(used))
                  if None not in (used[i], used[i - 1]) and used[i] >= (checks.value(s, k + MACRO_TAGS[i], "SupplyMade") or 0) - 1
                  and used[i - 1] >= (checks.value(s, k + MACRO_TAGS[i - 1], "SupplyMade") or 0) - 1]
        _ok(checks, s, f"{k} not supply-capped 2 min", not capped, f"capped at={capped}")
        check_macro_gas(checks, s, k)


MACRO_GAS_MID = "t240"


def check_macro_gas(checks, s: str, k: str) -> None:
    """R-BASE-36 in a full game (waves, all six owners started by map init): the map gives gas
    orders, gas is collected and still grows in the second half, and no worker is left script
    controlled without gas work. Negative: no map gas order at t1 (c_BASE_GAS_FIRST is 30 s)."""
    print(f"{s} raw {k} gas: " + " ".join(
        f"{t}={checks.value(s, k + t, 'GasCollected')}/{checks.value(s, k + t, 'MapBuilds')}"
        f"/{checks.value(s, k + t, 'MapGathers')}/{checks.value(s, k + t, 'GasStuck')}" for t in MACRO_TAGS)
        + "  (collected/builds/gathers/stuck)")
    checks.eq(s, k + "t1", "MapBuilds", 0)
    checks.eq(s, k + "t1", "MapGathers", 0)
    checks.gt(s, k + MACRO_END, "MapBuilds", 0)
    checks.gt(s, k + MACRO_END, "MapGathers", 0)
    checks.gt(s, k + MACRO_GAS_MID, "GasCollected", 0)
    mid = checks.value(s, k + MACRO_GAS_MID, "GasCollected")
    checks.gt(s, k + MACRO_END, "GasCollected", mid if mid is not None else 0)
    for t in MACRO_TAGS:
        checks.eq(s, k + t, "GasStuck", 0)
