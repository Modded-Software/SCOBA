"""baseai gas group: 6x6 geysers and gas buildings (R-BASE-35).

Two questions, kept apart (scripts/testkit/galaxy/baseai/baseai_gas.galaxy):

- direct: a script worker of lanes 1 (Terran) and 4 (Zerg) is ordered to
  build on the nearest placed geyser of its base. Negative: the same order
  on bare ground builds nothing.
- ai: the stock AI of lanes 2, 3, 5, 6 is left alone and must own a gas
  building by the last snapshot (about 230 game s).

Raw values are printed first: this probes engine behaviour that is not
confirmed (what the AI sees of a 6x6 geyser).
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
FACT_KEYS = ("Race", "Geysers", "GeyserDist100", "GeyserRes")
SNAP_KEYS = ("Gas", "RawSpots", "HarvestSpots", "Place100", "TownState", "TownAt100", "Minerals", "GasCollected",
             "Workers", "Allowed")
DIRECT_KEYS = ("GeyserFound", "GeyserAt100", "GasFoot", "GasPlaceFoot", "GeyserFoot", "Before", "BareIssued",
               "BareBuilt", "BeforeGeyser", "Issued", "OrderAfterIssue", "OrderAfterWait", "Built", "BuiltAt100",
               "BuiltOff100", "GeyserLeft")


CORE = 12                  # 6x6 cells = 12x12 sub-cells of 0.5, centred on the geyser point
RING = 2                   # sub-cells just outside the core (1 cell)
GRID_TAGS = ("Geyser", "Build", "Done")


def core_counts(grid: tuple[str, ...]) -> tuple[int, int, int]:
    """(blocked in the 12x12 core, blocked in the 1-cell ring around it, ring size) of a sub-cell grid."""
    lo, hi = GRID - CORE // 2, GRID + CORE // 2
    core = ring = size = 0
    for r in range(lo - RING, hi + RING):
        for c in range(lo - RING, hi + RING):
            x = grid[r][c] == "x"
            if lo <= r < hi and lo <= c < hi:
                core += x
            else:
                ring += x
                size += 1
    return core, ring, size


def check_gas_grid(checks, owner: int, tag: str) -> None:
    """The engine blocks the whole 6x6 at the geyser point, and not a cell ring more (negative)."""
    k = f"p{owner}{tag}"
    grid = _grid(checks, S, k)
    print(show_grid(checks, S, k, f"{S} raw {k} grid"))
    if tag != "Geyser":
        _raw(checks, k, ("Found", "Building", "Radius100"))
        checks.eq(S, k, "Found", 1)
        checks.eq(S, k, "Building", 1 if tag == "Build" else 0)
    if not grid:
        _ok(checks, S, f"{k} grid read", False, "no grid")
        return
    core, ring, size = core_counts(grid)
    _ok(checks, S, f"{k} 6x6 core blocked", core == CORE * CORE, f"core={core}/{CORE * CORE}")
    _ok(checks, S, f"{k} ring mostly open", ring * 2 < size, f"ring={ring}/{size}")


def _raw(checks, prefix: str, keys: tuple[str, ...]) -> None:
    print(f"{S} raw {prefix}: " + " ".join(f"{k}={checks.value(S, prefix, k)}" for k in keys))


def check_direct(checks, owner: int) -> None:
    k = f"p{owner}"
    _raw(checks, k, DIRECT_KEYS)
    checks.eq(S, k, "GeyserFound", 1)
    checks.eq(S, k, "GeyserFoot", GEYSER_FOOT)
    checks.eq(S, k, "GasFoot", GAS_FOOT)
    checks.eq(S, k, "GasPlaceFoot", GAS_PLACE_FOOT)
    # Negative: bare ground takes no gas building, and the AI had built none here before.
    checks.eq(S, k, "BareBuilt", 0)
    checks.eq(S, k, "BeforeGeyser", 0)
    checks.eq(S, k, "Issued", 1)
    checks.eq(S, k, "Built", 1)
    checks.lt(S, k, "BuiltOff100", ON_GEYSER_100)
    checks.eq(S, k, "GeyserLeft", 0)
    for tag in GRID_TAGS:
        check_gas_grid(checks, owner, tag)


def check_gas(checks) -> None:
    for owner in OWNERS:
        k = f"p{owner}"
        _raw(checks, k, FACT_KEYS)
        for tag in SNAPS:
            _raw(checks, k + tag, SNAP_KEYS)
        checks.eq(S, k, "Geysers", GEYSERS)
        checks.eq(S, k + "t1", "Allowed", 1)
        # Negative: no owner starts with a gas building.
        checks.eq(S, k + "t1", "Gas", 0)
    for owner in DIRECT_OWNERS:
        check_direct(checks, owner)
    for owner in AI_OWNERS:
        checks.gt(S, f"p{owner}{LAST}", "Gas", 0)
        checks.gt(S, f"p{owner}{LAST}", "GasCollected", 0)
