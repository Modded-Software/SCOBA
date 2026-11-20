"""Base AI profile (REQ-BASE-AI, SPEC-BASE-AI 6).

Group probe: the engine assumptions A1, A3-A8 of SPEC-BASE-AI 3, on a
harness-made base for the base owners of lanes 2 (Terran) and 5 (Zerg). Raw
values are printed first, so a failure shows what the engine did.
"""

from __future__ import annotations

import os
from pathlib import Path

from mapgen import player_slots
from mapgen.footprints.hall import hall_footprint_id
from project_root import project_root

from ..map_builder import TestMapSpec
from ..runner import TestRunSpec
from .baseai_feel import check_feel_extra
from .baseai_gas import check_gas
from .baseai_hall import HALL_PLACE, check_hall, check_legs, hall_rows, show_grid
from .baseai_melee import check_growth, check_melee
from .baseai_viking import check_right_hold, check_side_keys, check_viking_form, check_viking_morph
from .registry import PROFILE_BANKS, PROFILE_OUTPUTS

ROOT = project_root()
GROUPS = ("probe", "macro", "flight", "hall", "gas")
# "all" runs these; macro (about 5 min, waves on) and gas (about 4 min) run by name only.
ALL_GROUPS = ("probe", "hall")
# Lane owners (core/roster.galaxy, scripts/mapgen/player_slots.py): lane 1..6.
MACRO_OWNERS = tuple(player_slots.LANES[lane][1] for lane in range(1, 7))
MACRO_TAGS = ("t1", "t60", "t120", "t180", "t240", "t300", "t360", "t420", "t480")
MACRO_END = "t480"
AI_KEYS = ("HallAlive", "HallLife", "Queue", "Obstruction", "TownAt100", "Threats", "EnemiesNear", "MissFood",
           "MissMaker", "MissFighter", "FighterMaker", "Makers", "Fighters", "FighterTypes", "Larva", "Eggs", "Food",
           "FoodQueued", "MakersRaw", "DepotsQueued")
# The base owners of lanes 2 (Terran) and 5 (Zerg).
PROBE_PLAYERS = (player_slots.LANES[2][1], player_slots.LANES[5][1])
# LotV melee supply (voidmulti): CC 15; Hatchery 6 plus one Overlord 8.
# The Terran owner also holds its two placed Supply Depots, 8 each (R-BASE-29).
PLACED_DEPOTS = 2
START_SUPPLY = {PROBE_PLAYERS[0]: 15 + 8 * PLACED_DEPOTS, PROBE_PLAYERS[1]: 14}
SLOT_RACES = dict(player_slots.BASE_OWNERS)
PLAYER_TYPE_COMPUTER = 2  # c_playerTypeComputer
PLAYER_STATUS_ACTIVE = 1  # c_playerStatusActive
WORKERS = 12
DIFFICULTY = 10  # c_skirChInsane
MINERALS = 50
FIELDS = 8
GEYSERS = 2
TOWN_INVALID = -1  # c_townStateInvalid
# A unit that is left alone does not drift further than this (x100).
STILL_100 = 50
SNAP_KEYS = ("Workers", "Minerals", "Vespene", "MinCollected", "GasCollected", "SupplyUsed", "SupplyMade",
             "Structures", "Army", "StructureTypes", "ArmyTypes", "Spread100", "WorkerOrders", "Difficulty",
             "TownState", "Supply", "SupplyLow", "AllWorkerOrders", "BuildOrder", "PlaceDepotLow", "PlaceDepotStd",
             "PlaceRax", "PlaceDepotNear", "DepotAllowed")
UNIT_KEYS = ("Valid", "Script", "InWave", "Moved100", "UsingSupply", "Orders", "O0")


def selected_group() -> str:
    group = os.environ.get("SC2_TEST_GROUP", "all")
    if group != "all" and group not in GROUPS:
        raise SystemExit(f"unknown baseai group: {group}; choose all or one of {', '.join(GROUPS)}")
    return group


def _raw(checks, s: str, prefix: str, keys: tuple[str, ...]) -> None:
    print(f"{s} raw {prefix}: " + " ".join(f"{k}={checks.value(s, prefix, k)}" for k in keys))


# --- probe ------------------------------------------------------------------
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


def _ok(checks, s: str, name: str, ok: bool, detail: str) -> None:
    print(f"{s} {name}: {detail} {'PASS' if ok else 'FAIL'}")
    if not ok:
        checks.failures += 1


FLIGHT_STEP_100 = 400  # c_FLIGHT_RATE 4 per s, held 1 s
FLIGHT_TOL_100 = 100   # one tick each end (0.0625 s x 8 = 0.5) plus blend


def check_flight(checks, s: str) -> None:
    """Wraith flight (systems/flight): climb, descend, camera follows, no jump."""
    keys = ("H100", "Flight100", "Cam100", "FlightIs", "JumpPhase")
    for t in ("fly0", "flyUp", "flyDown"):
        print(f"{s} raw {t}: " + " ".join(f"{k}={checks.value(s, t, k)}" for k in keys))
    base = checks.value(s, "", "camBase100") or 0
    h0 = checks.value(s, "fly0", "H100") or 0
    up = checks.value(s, "flyUp", "H100") or 0
    down = checks.value(s, "flyDown", "H100") or 0
    traces = {}
    for t in ("traceUp", "traceHoldUp", "traceDown", "traceHoldDown"):
        raw = checks.value(s, "", t) or ""
        traces[t] = [int(v) for v in str(raw).split()]
        print(f"{s} raw {t}: {traces[t]}")
    # Negative: no drift while no key is held.
    for t in ("traceHoldUp", "traceHoldDown"):
        v = traces[t]
        _ok(checks, s, f"{t} holds", len(v) == 4 and max(v) - min(v) <= FLIGHT_TOL_100, f"{t}={v}")
    checks.true(s, "fly0", "FlightIs")
    _ok(checks, s, "climb", abs(up - h0 - FLIGHT_STEP_100) <= FLIGHT_TOL_100, f"h0={h0} up={up}")
    _ok(checks, s, "descend", abs(up - down - FLIGHT_STEP_100) <= FLIGHT_TOL_100, f"up={up} down={down}")
    for t in ("flyUp", "flyDown"):
        cam = checks.value(s, t, "Cam100") or 0
        fl = checks.value(s, t, "Flight100") or 0
        _ok(checks, s, f"{t} camera = base + flight", abs(cam - base - fl) <= 2, f"cam={cam} base={base} flight={fl}")
        # The engine height matches the tracked flight height.
        _ok(checks, s, f"{t} engine height = flight", abs((checks.value(s, t, 'H100') or 0) - fl) <= FLIGHT_TOL_100,
            f"engine={checks.value(s, t, 'H100')} flight={fl}")
        # Negative: no jump on the flyer.
        checks.eq(s, t, "JumpPhase", checks.value(s, "fly0", "JumpPhase"))


# --- macro ------------------------------------------------------------------
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


SPEED_TOL = 0.10        # +-10 % of the reference ground speed
HEIGHT_KEYS = (("mA", "Blend", "After"), ("mB", "Blend", "After"), ("mC", "Climb", "After"), ("mD", "Climb", "After"),
               ("mE", "Blend", "After"), ("mF", "Blend", "After"))


VISTA_OVERLORDS = 2                 # SCOBAVistaOverlord in Objects


def check_flight_group(checks) -> None:
    """Viking speed through WASD and LMB+RMB, and the raw height methods."""
    s = "ba_flight"
    checks.true(s, "", "wraithActive")
    # Regular unit: PNC only. TPS on is refused (operator 2026-11-18).
    checks.eq(s, "", "wraithTps", False)
    checks.eq(s, "", "backTps", False)
    checks.eq(s, "", "tpsBehavior", 0)
    print(f"{s} raw tps refuse: " + " ".join(f"{k}={checks.value(s, '', k)}" for k in ("tpsOnOrder", "tpsRefused")))
    check_right_hold(checks, s)
    check_side_keys(checks, s)
    checks.eq(s, "", "chaseStand0", 0)       # regular unit: Chase always Move
    checks.eq(s, "", "chaseStand1", 0)
    moved = checks.value(s, "", "chaseMoved100")
    _ok(checks, s, "ground right click moves the regular unit", moved is not None and moved > 500,
        f"moved100={moved} refused={checks.value(s, '', 'chaseRefused')} move={checks.value(s, '', 'chaseMoveOrder')}")
    check_viking_form(checks, s, "vikStart")
    check_viking_form(checks, s, "vikEnd")
    # The two vista Overlords: special type, player 8, height 64; no stock
    # Overlord (it is tech-blocked and would give supply).
    vista = checks.value(s, "", "vistaOwnerHeight") or ""
    print(f"{s} raw vista: count={checks.value(s, '', 'vistaCount')} stock={checks.value(s, '', 'vistaStock')} at={vista}")
    checks.eq(s, "", "vistaCount", VISTA_OVERLORDS)
    checks.eq(s, "", "vistaStock", 0)
    _ok(checks, s, "vista Overlords player 8 at height 64", vista.split() == ["8@6400"] * VISTA_OVERLORDS, f"at={vista}")
    check_viking_morph(checks, s)
    check_feel_extra(checks, s)
    keys = ("speedData100", "speedProp100", "speedNormal100", "speedTosh100", "speedW100", "speedMouse100",
            "speedFree100")
    v = {k: checks.value(s, "", k) or 0 for k in keys}
    print(f"{s} raw speed: " + " ".join(f"{k}={v[k]}" for k in keys) +
          f" camYaw={checks.value(s, '', 'camYaw')} mouseForward={checks.value(s, '', 'mouseForward')}"
          f" forward={checks.value(s, '', 'forward')}")
    checks.eq(s, "", "freeTps", False)
    for t in ("W", "M", "F"):
        path = str(checks.value(s, t, "Path") or "")
        print(f"{s} raw {t}: move={checks.value(s, t, 'Move')} cur100={checks.value(s, t, 'Cur100')} path={path}")
        pts = [tuple(int(c) for c in p.split(",")) for p in path.replace("|", " ").split()]
        steps = [round(((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5) for a, b in zip(pts, pts[1:])]
        # Negative: no slow step (a stop between move orders). Each 0.25 s
        # step at least 90 % of full speed.
        floor = (1 - SPEED_TOL) * v["speedProp100"] * 0.25
        _ok(checks, s, f"{t} no slow step", len(steps) == 8 and min(steps) >= floor,
            f"steps100={steps} floor={floor:.0f}")
    # Reference: the controlled unit's own speed (engine property), which
    # is its data speed (no speed behavior on the Wraith).
    ref = v["speedProp100"]
    _ok(checks, s, "speed property = unit data speed", ref > 0 and abs(ref - v["speedData100"]) <= SPEED_TOL * ref,
        f"prop={ref} data={v['speedData100']}")
    for k in ("speedW100", "speedMouse100", "speedFree100"):
        _ok(checks, s, f"{k} = Wraith speed", ref > 0 and abs(v[k] - ref) <= SPEED_TOL * ref, f"{k}={v[k]} ref={ref}")
        # Negative: not the hero's (Tosh) speed.
        _ok(checks, s, f"{k} not Tosh speed", abs(v[k] - v["speedTosh100"]) > SPEED_TOL * ref,
            f"{k}={v[k]} tosh={v['speedTosh100']}")
    check_flight(checks, s)
    # Key repeat (release+press every tick) must not slow the climb.
    rep = checks.value(s, "", "repeatClimb100")
    _ok(checks, s, "climb with key repeat = rate", rep is not None and abs(rep - FLIGHT_STEP_100) <= 50,
        f"climb100={rep} want={FLIGHT_STEP_100}")
    for m, a, b in HEIGHT_KEYS:
        print(f"{s} raw {m}: start={checks.value(s, m, 'Start100')} stop={checks.value(s, m, 'Stop100')}")
        print(f"{s} raw {m}{a}: {checks.value(s, m, a)}")
        print(f"{s} raw {m}{b}: {checks.value(s, m, b)}")


CHECKS = {
    "probe": check_probe,
    "macro": check_macro,
    "flight": check_flight_group,
    "hall": check_hall,
    "gas": check_gas,
}


DEPOT_MAP = ('<CUnit id="SupplyDepot">\n        <Footprint value="Footprint4x4DepotContour"/>\n'
             '        <PlacementFootprint value="Footprint4x4Depot"/>\n    </CUnit>')
DEPOT_STOCK = ('<CUnit id="SupplyDepot">\n        <Footprint value="Footprint2x2Contour"/>\n'
               '        <PlacementFootprint value="Footprint2x2"/>\n    </CUnit>')


def depot_mode() -> str:
    """SC2_BA_DEPOT=stock: the probe map gets the stock 2x2 depot footprint
    (A/B probe of the c_canLower placement). Default: the map's 4x4."""
    mode = os.environ.get("SC2_BA_DEPOT", "map")
    if mode not in ("map", "stock"):
        raise SystemExit(f"SC2_BA_DEPOT must be map or stock, got {mode}")
    return mode


def patch_depot(map_dir: Path) -> None:
    path = map_dir / "Base.SC2Data" / "GameData" / "UnitData.xml"
    raw = path.read_bytes()
    eol = b"\r\n" if b"\r\n" in raw else b"\n"
    old = DEPOT_MAP.encode("utf-8").replace(b"\n", eol)
    if raw.count(old) != 1:
        raise SystemExit(f"{path}: expected one SupplyDepot 4x4 entry")
    path.write_bytes(raw.replace(old, DEPOT_STOCK.encode("utf-8").replace(b"\n", eol)))


def map_spec() -> TestMapSpec:
    return TestMapSpec(
        patch=patch_depot if depot_mode() == "stock" else None,
        profile="baseai",
        source=ROOT / "out" / "SCOBA256.SC2Map",
        output=PROFILE_OUTPUTS["baseai"],
        bank_names=PROFILE_BANKS["baseai"],
        galaxy_files=(
            ROOT / "scripts" / "testkit" / "galaxy" / "common.galaxy",
            ROOT / "scripts" / "testkit" / "galaxy" / "baseai" / "baseai.galaxy",
            ROOT / "scripts" / "testkit" / "galaxy" / "baseai" / "baseai_live.galaxy",
            ROOT / "scripts" / "testkit" / "galaxy" / "baseai" / "baseai_macro.galaxy",
            ROOT / "scripts" / "testkit" / "galaxy" / "baseai" / "baseai_land.galaxy",
            ROOT / "scripts" / "testkit" / "galaxy" / "baseai" / "baseai_feel.galaxy",
            ROOT / "scripts" / "testkit" / "galaxy" / "baseai" / "baseai_flight.galaxy",
            ROOT / "scripts" / "testkit" / "galaxy" / "baseai" / "baseai_hall.galaxy",
            ROOT / "scripts" / "testkit" / "galaxy" / "baseai" / "baseai_gas.galaxy",
        ),
        galaxy_includes=(
            "scripts/test/baseai/common",
            "scripts/test/baseai/baseai",
            "scripts/test/baseai/baseai_live",
            "scripts/test/baseai/baseai_macro",
            "scripts/test/baseai/baseai_land",
            "scripts/test/baseai/baseai_feel",
            "scripts/test/baseai/baseai_flight",
            "scripts/test/baseai/baseai_hall",
            "scripts/test/baseai/baseai_gas",
        ),
        init_calls=(f'gv_dbgGroup = "{selected_group()}";', "gt_BaseAiTest_Init();"),
    )


def on_ready(ctx, data: dict) -> None:
    return


def check(ctx, data: dict, checks) -> None:
    for error in ctx.errors:
        print(f"{error} FAIL")
        checks.failures += 1
    checks.eq("meta", "", "done", 1)
    group = selected_group()
    if group == "macro":
        # The operator flies the Wraith: input is expected; the macro checks
        # read AI engine state only.
        print(f"ba_end raw RealClicks={checks.value('ba_end', '', 'RealClicks')} (operator input, not asserted)")
    else:
        checks.eq("ba_end", "", "RealClicks", 0)
    print(f"group: {group}")
    for name in GROUPS:
        if (group == "all" and name in ALL_GROUPS) or group == name:
            CHECKS[name](checks)


def run_spec(launch_timeout_s: float, case_timeout_s: float, run_root: Path) -> TestRunSpec:
    return TestRunSpec(
        profile="baseai",
        map_name="SCOBA.SC2Map",
        map_source=PROFILE_OUTPUTS["baseai"],
        map_cache_name="SCOBA.SC2Map",
        bank_names=PROFILE_BANKS["baseai"],
        ready_section="ba_start",
        ready_key="ready",
        launch_timeout_s=launch_timeout_s,
        case_timeout_s=case_timeout_s,
        run_root=run_root,
        on_ready=on_ready,
        check=check,
    )
