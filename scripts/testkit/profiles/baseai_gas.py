"""baseai gas group: 6x6 geysers and gas buildings (R-BASE-35), and the map's
gas orders for the base owners (R-BASE-36).

By default the AI lanes run as in the game and R-BASE-36 is checked
(check_map_gas). The probe modes (SC2_BA_GAS_SCAN, _HELP, _TOWN, _EXTRA,
profiles/baseai_env.py, baseai_scan.py) turn the map's gas orders off and print raw values.

The questions, kept apart (scripts/testkit/galaxy/baseai/baseai_gas*.galaxy):

- direct: a script worker of lanes 1 (Terran) and 4 (Zerg), which have no
  base and no AI, builds on the nearest placed geyser of its start. Negative:
  the same build on bare ground builds nothing.
- ai: the stock AI of lanes 2, 3, 5, 6, started as in the game, must own a
  gas building and have collected gas by the last snapshot (240 game s).
  Printed raw beside it: the gas build orders the AI gave (watch) and how far
  it reaches for gas (reach: test towns at set distances from one geyser).
- baseline (diagnosis, raw only): lanes 2 and 5 also get two probe geysers 7
  from the AI town point, a stock 3x3 RichVespeneGeyser and a 6x6 one. Which
  one the AI builds on tells size from distance. Lanes 3 and 6 stay as in the
  game. Accept maps of the AI placement call for each size pair.

Raw values are printed first: this probes engine behaviour that is not
confirmed (what the AI sees of a 6x6 geyser, which order form builds).
"""

from __future__ import annotations

from mapgen import player_slots

from .baseai_hall import GRID, _grid, _ok, show_grid

S = "ba_gas"
DIRECT_OWNERS = tuple(player_slots.LANES[lane][1] for lane in (1, 4))
AI_OWNERS = tuple(player_slots.LANES[lane][1] for lane in (2, 3, 5, 6))
OWNERS = tuple(player_slots.LANES[lane][1] for lane in range(1, 7))
SNAPS = ("t1", "s0", "s1", "s2", "s3")
LAST = "s3"
GEYSERS = 2
GEYSER_FOOT = "FootprintScobaGeyser6x6"
GAS_FOOT = "FootprintScobaGeyser6x6Built"
GAS_PLACE_FOOT = "FootprintScoba6x6CappedGeyser"
# A gas building stands on its geyser's point (x100).
ON_GEYSER_100 = 50
# The engine reports as a structure's radius the larger of its footprint Shape's and the unit
# Radius field: 1.68 for the stock 3x3 gas building (run 20261122-081628), 4.25 for the 6x6
# square, half its diagonal (unit Radius 3); 3.00 for a probe with a small Shape and 4.75 with
# unit Radius 4.75 (runs 20261122-110629, -104133).
GAS_RADIUS_100 = (400, 450)
# R-BASE-36 (systems/base/base_gas): the map's own gas orders. Printed raw, and checked when no
# probe mode is on (bank key mapGas).
GEYSER_RES = 10000         # a placed geyser: stock 2500 times c_SITE_RES_MULT
CREW = 3                   # c_BASE_GAS_CREW
MAP_GAS_KEYS = (("MapBuilds", "MapGathers", "Stuck")
                + tuple(f"G{n}{k}" for n in range(2)
                        for k in ("Gas", "GasBuilding", "GasRes", "Crew", "CrewScript", "CrewAi")))
# The hand-back case: lane 2, its gas building on the first placed geyser is killed.
RELEASE_OWNER = player_slots.LANES[2][1]
RELEASE_KEYS = ("Found", "CrewBefore", "Crew", "Slot", "Stuck", "Rebuilds", "Wait", "Busy", "CrewScript", "Orders")
# The away case: lane 3, one crew member gets a move order.
AWAY_OWNER = player_slots.LANES[3][1]
AWAY_KEYS = ("Found", "CrewBefore", "ScriptAtOrder", "InCrew", "Script", "IsAi", "Crew", "Stuck", "Busy",
             "BusyWait", "Orders")
# The empty case: lane 5, its gas building on the first placed geyser is set to 0 gas.
EMPTY_OWNER = player_slots.LANES[5][1]
EMPTY_KEYS = ("Found", "CrewBefore", "Res", "Slot", "CrewScript", "Stuck", "SlotLate", "NewGathers", "Alive",
              "Targeted", "StuckLate", "Orders")
START_WORKERS = 12         # c_BASE_AI_WORKERS
FORMS = ("Point", "Place", "Unit")
FACT_KEYS = (("Race", "Start100", "Hall100", "Geysers")
             + tuple(f"G{n}{k}" for n in range(GEYSERS)
                     for k in ("At100", "Start100", "Town100", "Place100", "Res", "Radius", "Foot", "Clear100")))
SNAP_KEYS = ("Started", "Gas", "RawSpots", "HarvestSpots", "Place100", "TownState", "TownAt100", "Minerals",
             "GasCollected", "Workers", "Structures", "Allowed", "TechQueued", "WorkerOrders", "BuildOrder")
TRY_KEYS = (("Gas", "GeyserType", "GeyserAt100", "GeyserFoot", "GasFoot", "GasPlaceFoot", "Before")
            + tuple(f"{k}{f}{tail}" for f in FORMS for k, tail in (("Issued", ""), ("Order", ""), ("Built", ""), ("Worker", "Off100")))
            + ("Via", "Built", "BuiltAt100", "BuiltOff100", "GeyserLeft"))
FORM_KEYS = tuple(f"Valid{f}" for f in FORMS) + ("Fit100",)
BARE_KEYS = ("BareIssuedPoint", "BareIssuedPlace", "BareBuilt")
WATCH_KEYS = ("GasOrderTicks", "GasOrderSeen", "GasOrder0", "GasOrder1", "GasOrder2",
              "GasIssued", "GasIssued0", "GasIssued1", "GasIssued2")
ACCEPT_ROWS = 17           # 2 * c_BG_MAP_R + 1
# Lane 2: Refinery (6x6) and Assimilator (stock 3x3), around a placed 6x6 geyser (accept, accA6)
# and around the stock 3x3 probe geyser (accR3, accA3).
ACCEPT_MAPS = ("accept", "accA6", "accR3", "accA3")
# The stock baseline: lanes 2 and 5 get two probe geysers near the AI town point. In a radius
# scan map (SC2_BA_GAS_SCAN, profiles/baseai_scan.py) every AI lane gets one scan probe, X0, instead.
EXTRAS = 2                 # c_BG_EXTRAS: 0 RichVespeneGeyser (stock 3x3), 1 VespeneGeyser (6x6)
EXTRA_KEYS = ("Asked100", "Made", "Type", "At100", "Town100", "Res", "Radius100", "Clear100", "Built", "ClearEnd100",
              "Open100", "GasRadius", "GasFoot", "Ring", "RingIssued")
# The help probe (SC2_BA_GAS_HELP=1): a script worker builds on both placed geysers of an AI lane.
HELP_KEYS = ("At100", "Town100", "Hall100", "Issued", "Staffed", "StaffT", "Built", "Building", "Res200", "Res",
             "CrewAlive", "CrewOn")
# Blocker case (lane 1, its other geyser). The gas building checks a 6x6 square (half side 3).
# The engine put an SCV (radius 0.375) asked at 2.6 at 3.35 (run 20261122-091241): 0.35 outside
# the square, and the build started. Why 0.35 and not 0.375 is not known. The check: its
# centre is 3.25 or more off on one axis, so at most its rim touches the square.
BLOCK_OWNER = player_slots.LANES[1][1]
BLOCK_OUT_100 = 325
BLOCK_KEYS = ("Before", "BlockerDX100", "BlockerDY100", "BlockerRadius100", "Valid", "Issued", "Built",
              "WorkerAlive", "Order", "WorkerOff100", "BlockerAlive", "BlockerDX100After", "BlockerDY100After")
REACH_N = 12               # c_BG_REACH_N
REACH_KEYS = ("Centre100", "Town100", "State", "D100", "Raw", "Place100")

CORE = 12                  # 6x6 cells = 12x12 sub-cells of 0.5, centred on the geyser point
RING = 2                   # sub-cells just outside the core (1 cell)
# The sub-cells every gas footprint Shape of FootprintData.xml covers, centred: the whole 6x6
# square, 12x12 sub-cells, for the geyser and for the gas building (R-BASE-35: the pathing
# footprint is 6x6). The same square the gas building checks: no walkable strip inside it.
GEYSER_BOX = (12, 12)
GAS_BOX = (12, 12)
GRID_TAGS = ("Geyser", "Build", "Done")


def box_blocked(grid: tuple[str, ...], box: tuple[int, int]) -> int:
    """Blocked sub-cells in the centred box (columns, rows) of a sub-cell grid."""
    w, h = box
    return sum(grid[r][c] == "x" for r in range(GRID - h // 2, GRID + h // 2) for c in range(GRID - w // 2, GRID + w // 2))


def ring_blocked(grid: tuple[str, ...]) -> tuple[int, int]:
    """(blocked, size) of the 1-cell ring just outside the 12x12 core."""
    lo, hi = GRID - CORE // 2, GRID + CORE // 2
    ring = [grid[r][c] == "x" for r in range(lo - RING, hi + RING) for c in range(lo - RING, hi + RING)
            if not (lo <= r < hi and lo <= c < hi)]
    return sum(ring), len(ring)


def _raw(checks, prefix: str, keys: tuple[str, ...]) -> None:
    print(f"{S} raw {prefix}: " + " ".join(f"{k}={checks.value(S, prefix, k)}" for k in keys))


def raw_try(checks, k: str) -> None:
    """Everything one build attempt recorded, and its grids."""
    _raw(checks, k, TRY_KEYS)
    _raw(checks, k + "On", FORM_KEYS)
    for tag in ("Geyser", "Build"):
        print(show_grid(checks, S, k + tag, f"{S} raw {k}{tag} grid"))
    _raw(checks, k + "Build", ("Found", "Building", "Radius100"))


def check_gas_grid(checks, owner: int, tag: str) -> None:
    """The engine blocks the 6x6 Shape at the geyser point, and not a cell ring more (negative)."""
    k = f"p{owner}{tag}"
    grid = _grid(checks, S, k)
    if tag == "Done":
        print(show_grid(checks, S, k, f"{S} raw {k} grid"))
        _raw(checks, k, ("Found", "Building", "Radius100"))
    if tag != "Geyser":
        checks.eq(S, k, "Found", 1)
        checks.eq(S, k, "Building", 1 if tag == "Build" else 0)
        checks.between(S, k, "Radius100", *GAS_RADIUS_100)
    if not grid:
        _ok(checks, S, f"{k} grid read", False, "no grid")
        return
    box = GEYSER_BOX if tag == "Geyser" else GAS_BOX
    got = box_blocked(grid, box)
    ring, size = ring_blocked(grid)
    _ok(checks, S, f"{k} {box[0]}x{box[1]} sub-cells blocked", got == box[0] * box[1], f"blocked={got}/{box[0] * box[1]}")
    _ok(checks, S, f"{k} ring mostly open", ring * 2 < size, f"ring={ring}/{size}")


def check_direct(checks, owner: int) -> None:
    k = f"p{owner}"
    _raw(checks, k, BARE_KEYS)
    _raw(checks, k + "Bare", FORM_KEYS)
    raw_try(checks, k)
    checks.eq(S, k, "GeyserFound", 1)
    checks.eq(S, k, "GeyserFoot", GEYSER_FOOT)
    checks.eq(S, k, "GasFoot", GAS_FOOT)
    checks.eq(S, k, "GasPlaceFoot", GAS_PLACE_FOOT)
    # Negative: bare ground takes no gas building, and none stood on the geyser before.
    checks.eq(S, k, "BareBuilt", 0)
    checks.eq(S, k, "Before", 0)
    checks.eq(S, k, "Built", 1)
    checks.lt(S, k, "BuiltOff100", ON_GEYSER_100)
    for tag in GRID_TAGS:
        check_gas_grid(checks, owner, tag)


def check_block(checks, owner: int) -> None:
    """A unit of another player is made 2.6 from the geyser point, inside the 6x6 square the
    gas building checks. With the rounded geyser Shape it stood there and stopped the build
    (run 20261122-090349). The geyser now blocks the whole square: the engine must put the
    unit outside it (negative: no unit stands inside), and the build must start."""
    k = f"p{owner}BlockIn"
    _raw(checks, k, BLOCK_KEYS)
    checks.eq(S, f"p{owner}Block", "GeyserFound", 1)
    for tail in ("", "After"):
        dx, dy = checks.value(S, k, f"BlockerDX100{tail}"), checks.value(S, k, f"BlockerDY100{tail}")
        _ok(checks, S, f"{k} blocker outside the 6x6 square{' after' if tail else ''}",
            dx is not None and dy is not None and max(dx, dy) >= BLOCK_OUT_100, f"dx={dx} dy={dy} want>={BLOCK_OUT_100}")
    checks.eq(S, k, "Before", 0)
    checks.eq(S, k, "Issued", 1)
    checks.eq(S, k, "Built", 1)


def raw_reach(checks) -> None:
    """The reach probe, raw: per test town, what the AI reports."""
    print(f"{S} raw reach: geyser={checks.value(S, 'reach', 'Geyser100')}")
    for n in range(REACH_N):
        _raw(checks, f"reach{n}", REACH_KEYS)
    for k in ACCEPT_MAPS:
        print(f"{S} raw {k} map (C the asked centre, g the geyser point, o another point, . none), "
              f"gas={checks.value(S, k, 'Gas')} geyser={checks.value(S, k, 'Geyser100')}:")
        for n in range(ACCEPT_ROWS):
            print(f"    {checks.value(S, k, f'Row{n}')}")


def raw_extra(checks, owner: int) -> None:
    """The probe geysers of a baseline lane, raw: 0 the stock 3x3, 1 a 6x6."""
    for n in range(EXTRAS):
        _raw(checks, f"p{owner}X{n}", EXTRA_KEYS)
    grid = _grid(checks, S, f"p{owner}X0")
    if grid:
        print(f"{S} raw p{owner}X0 probe blocks {box_blocked(grid, GEYSER_BOX)}/{GEYSER_BOX[0] * GEYSER_BOX[1]} "
              f"sub-cells of its 6x6")


def check_map_gas(checks) -> None:
    """R-BASE-36: every AI lane owner has a gas building on both placed geysers of its base, each
    with a crew of its own workers, and the gas flows. Not checked in a probe mode, where the
    harness turns the map's gas orders off."""
    for owner in OWNERS:
        _raw(checks, f"p{owner}", MAP_GAS_KEYS)
    on = checks.value(S, "", "mapGas")
    print(f"{S} raw mapGas={on}")
    if on != 1:
        print(f"{S} probe mode: the map's gas orders are off, R-BASE-36 is not checked in this run")
        return
    for owner in AI_OWNERS:
        k = f"p{owner}"
        # Negative: no gas order before c_BASE_GAS_FIRST (t1 is 2 game s after the start).
        checks.eq(S, k + "t1", "MapBuilds", 0)
        checks.eq(S, k + "t1", "MapGathers", 0)
        for n in range(GEYSERS):
            checks.eq(S, k, f"G{n}Gas", 1)
            checks.eq(S, k, f"G{n}GasBuilding", 0)
            # Gas was taken from this very building.
            checks.lt(S, k, f"G{n}GasRes", GEYSER_RES)
            checks.eq(S, k, f"G{n}Crew", CREW)
            # The crew counts as AI units (the lane gates leave them alone). CrewScript is raw:
            # the engine marks an ordered worker script controlled (run 20261122-121438).
            checks.eq(S, k, f"G{n}CrewAi", CREW)
        # Negative: no worker is left script controlled without gas work.
        checks.eq(S, k, "Stuck", 0)
        checks.gt(S, k, "MapBuilds", GEYSERS - 1)
        checks.gt(S, k, "MapGathers", GEYSERS * CREW - 1)
        # The gas still flows in the last minute (s2 to s3).
        before = checks.value(S, k + "s2", "GasCollected")
        checks.gt(S, k + "s2", "GasCollected", 0)
        checks.gt(S, k + LAST, "GasCollected", before if before is not None else 0)
    for owner in DIRECT_OWNERS:
        # Negative: an owner without a started AI gets no gas order from the map.
        checks.eq(S, f"p{owner}", "MapBuilds", 0)
        checks.eq(S, f"p{owner}", "MapGathers", 0)
    # The hand-back case: the killed gas building had a full crew; after two looks its slot is
    # free, no worker of the owner is left script controlled without gas work, and within 30
    # game s the map orders a new build on the freed geyser.
    k = f"p{RELEASE_OWNER}rel"
    _raw(checks, k, RELEASE_KEYS)
    checks.eq(S, k, "Found", 1)
    checks.eq(S, k, "CrewBefore", CREW)
    checks.eq(S, k, "Slot", 0)
    checks.eq(S, k, "Stuck", 0)
    checks.gt(S, k, "Rebuilds", 0)
    # The handed-back crew is not script controlled; the AI uses at least one of them.
    checks.eq(S, k, "CrewScript", 0)
    checks.gt(S, k, "Busy", 0)
    # The away case: the moved member leaves the crew, goes back to the AI (not script
    # controlled, still an AI unit), the crew is full again, and within 30 game s the AI gives
    # the worker a gather or build order. ScriptAtOrder is raw.
    k = f"p{AWAY_OWNER}away"
    _raw(checks, k, AWAY_KEYS)
    checks.eq(S, k, "Found", 1)
    checks.eq(S, k, "CrewBefore", CREW)
    checks.eq(S, k, "InCrew", 0)
    checks.eq(S, k, "Script", 0)
    checks.eq(S, k, "IsAi", 1)
    checks.eq(S, k, "Crew", CREW)
    checks.eq(S, k, "Stuck", 0)
    checks.eq(S, k, "Busy", 1)
    # The empty case: after two looks the slot is free and the crew is handed back; ten looks
    # later the map has taken no slot for it and sends no builder to its geyser.
    # NewGathers is raw: other crews may be refilled in that time.
    k = f"p{EMPTY_OWNER}empty"
    _raw(checks, k, EMPTY_KEYS)
    checks.eq(S, k, "Found", 1)
    checks.eq(S, k, "CrewBefore", CREW)
    checks.eq(S, k, "Res", 0)
    checks.eq(S, k, "Slot", 0)
    checks.eq(S, k, "CrewScript", 0)
    checks.eq(S, k, "Stuck", 0)
    checks.eq(S, k, "SlotLate", 0)
    checks.eq(S, k, "Targeted", 0)
    checks.eq(S, k, "StuckLate", 0)


def check_gas(checks) -> None:
    for owner in OWNERS:
        k = f"p{owner}"
        _raw(checks, k, FACT_KEYS)
        for tag in SNAPS:
            _raw(checks, k + tag, SNAP_KEYS + ("MapBuilds", "MapGathers"))
        checks.eq(S, k, "Geysers", GEYSERS)
        checks.eq(S, k + "t1", "Allowed", 1)
        # Negative: no owner starts with a gas building.
        checks.eq(S, k + "t1", "Gas", 0)
    raw_reach(checks)
    print(f"{S} raw scan map: {checks.value(S, '', 'scan')} help probe: {checks.value(S, '', 'help')}")
    for owner in AI_OWNERS:
        raw_extra(checks, owner)
        for n in range(GEYSERS):
            _raw(checks, f"p{owner}H{n}", HELP_KEYS)
        _raw(checks, f"p{owner}", ("TownWas100", "TownSet100", "TownHarvest"))
    check_block(checks, BLOCK_OWNER)
    for owner in DIRECT_OWNERS:
        check_direct(checks, owner)
        # Negative: the direct owners have no base and no AI; the builds are the script worker's.
        checks.eq(S, f"p{owner}{LAST}", "Started", 0)
    for owner in AI_OWNERS:
        k = f"p{owner}"
        _raw(checks, k, WATCH_KEYS)
        # Positive control: the lane is live (base made, AI started, it trains workers).
        checks.eq(S, k, "HallValid", 1)
        checks.eq(S, k + "t1", "Started", 1)
        checks.eq(S, k + "t1", "Workers", START_WORKERS)
        checks.gt(S, k + LAST, "Workers", START_WORKERS)
        checks.gt(S, k + LAST, "Gas", 0)
        checks.gt(S, k + LAST, "GasCollected", 0)
    check_map_gas(checks)
