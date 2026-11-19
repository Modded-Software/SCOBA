"""baseai hall group: the measured Command Center footprint (R-BASE-30, R-FP-10).

The build slices the scaled CC model at feet height and links the blocked
cells as the CC Footprint (scripts/mapgen/footprints/hall.py). The harness
records the engine pathing of the 19x19 whole cells around the hall; this
compares it with the same cells. Built, killed, created, mined, lifted,
landed 20 or more away, killed; and the starting hall. Scenarios in scripts/testkit/galaxy/baseai/baseai_hall.galaxy.
"""

from __future__ import annotations

from functools import cache

from mapgen import player_slots
from mapgen.footprints import config as footprint_config
from mapgen.footprints.hall import Hall, hall_footprint_id, hall_scale, hall_shape
from mapgen.footprints.slices import load_slices
from project_root import project_root

GRID = 18                 # c_BH_SUB: 36x36 sub-cells of 0.5 (9 cells each way)
LEGS = 4                  # leg centres probed with a Barracks
HALL_MODEL = "CommandCenter"
HALL_PLACE = "FootprintSCOBAHall1x1"
# The footprint is turned by this unit Facing (footprints.config); every
# grounded CC must face it, or its drawn feet leave the blocked ones.
HALL_FACING = round(footprint_config.HALL_FACING[HALL_MODEL])
SNAPS = ("t0", "built", "builtDead", "made", "lifted", "landed", "dead")
# Terran lane owners 1-3 (scripts/mapgen/player_slots.py).
START_OWNERS = tuple(player_slots.LANES[lane][1] for lane in range(1, 4))


def _ok(checks, s: str, name: str, ok: bool, detail: str) -> None:
    print(f"{s} {name}: {detail} {'PASS' if ok else 'FAIL'}")
    if not ok:
        checks.failures += 1


@cache
def hall_rows() -> Hall:
    """The CC rows the build generates, at the built map's drawn scale."""
    actors = project_root() / "out" / "SCOBA256.SC2Map" / "Base.SC2Data" / "GameData" / "ActorData.xml"
    data = load_slices()
    return hall_shape(data, HALL_MODEL, hall_scale(data, actors.read_text(encoding="utf-8"), HALL_MODEL, HALL_MODEL))


def expected_grid() -> tuple[str, ...]:
    """The sub-cell rows of hall_rows() padded to the harness grid, top (+y) first."""
    rows = hall_rows().sub
    pad = GRID - len(rows) // 2
    if pad < 0:
        raise ValueError(f"hall footprint {len(rows)} wider than the {2 * GRID} grid")
    edge = "." * (2 * GRID)
    return (edge,) * pad + tuple("." * pad + r + "." * pad for r in rows) + (edge,) * pad


def open_grid() -> tuple[str, ...]:
    return ("." * (2 * GRID),) * (2 * GRID)


def _offset(at: str | None, start: str | None) -> int | None:
    """Largest per-axis distance, in 1/100 cells, of two "x,y" bank points."""
    if not at or not start:
        return None
    a = [int(v) for v in at.split(",")]
    b = [int(v) for v in start.split(",")]
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def _grid(checks, s: str, k: str) -> tuple[str, ...]:
    rows = tuple(checks.value(s, k, f"Grid{n}") for n in range(2 * GRID))
    return rows if all(isinstance(r, str) for r in rows) else ()


def _show(name: str, grid: tuple[str, ...]) -> str:
    return f"{name}:\n" + "\n".join(f"    {row}" for row in grid)


def show_grid(checks, s: str, k: str, name: str) -> str:
    """The raw engine sub-cell grid of k, for the run log."""
    return _show(name, _grid(checks, s, k))


def check_grid(checks, s: str, k: str, want: tuple[str, ...], exact: bool = True) -> None:
    """Engine sub-cell grid of k against want. exact: every sub-cell; else every 'x' of want is blocked."""
    got = _grid(checks, s, k)
    if exact:
        ok = got == want
    else:
        ok = len(got) == len(want) and all(g == "x" for gr, wr in zip(got, want, strict=True) for g, w in zip(gr, wr, strict=True) if w == "x")
    _ok(checks, s, f"{k} grid {'equals' if exact else 'covers'} the measured footprint" if want != open_grid() else f"{k} grid open",
        ok, "" if ok else "\n" + _show("got", got) + "\n" + _show("want", want))


def check_legs(checks, s: str, k: str, exact: bool = True) -> None:
    """A grounded CC at its point: the measured cells blocked, the legs refuse a Barracks, the origin open."""
    check_grid(checks, s, k, expected_grid(), exact)
    checks.eq(s, k, "Refused", LEGS)
    checks.eq(s, k, "Hub", 0)


def check_paint(checks) -> None:
    """R-FP-11: Alt+0 marks every engine-blocked 0.5 sub-cell, nothing else; off clears."""
    s = "ba_hall_paint"
    print(f"{s} raw: " + " ".join(f"{n}={checks.value(s, '', n)!r}" for n in (
        "At100", "ActorScale", "Model", "ModelScaleMax", "Scale100")))
    for tag in ("before", "on", "off"):
        print(f"{s} raw {tag}: " + " ".join(f"{n}={checks.value(s, tag, n)}" for n in (
            "Hit", "Miss", "Extra", "Halls", "Cells", "Tags")))
    # The F marks use actor x model scale: 3.6 x 0.8.
    checks.eq(s, "", "Scale100", 288)
    # Negative: no marks before and after.
    for tag in ("before", "off"):
        checks.eq(s, tag, "Hit", 0)
        checks.eq(s, tag, "Extra", 0)
    checks.eq(s, "off", "Cells", 0)
    checks.eq(s, "off", "Tags", 0)
    # On: every blocked cell marked, no open cell marked; tags: one per
    # marked cell plus 9 per hall (O, four F, four A).
    checks.gt(s, "on", "Hit", 0)
    checks.eq(s, "on", "Miss", 0)
    checks.eq(s, "on", "Extra", 0)
    checks.gt(s, "on", "Halls", 0)
    halls = checks.value(s, "on", "Halls") or 0
    checks.eq(s, "on", "Tags", 9 * halls + (checks.value(s, "on", "Cells") or 0))


def check_open(checks, s: str, k: str) -> None:
    """No hall at this point: every cell open, a Barracks fits at each leg centre."""
    check_grid(checks, s, k, open_grid())
    checks.eq(s, k, "Refused", 0)
    checks.eq(s, k, "Hub", 0)


def check_hall(checks) -> None:
    s = "ba_hall"
    keys = ("Player", "A100", "B100", "Foot", "buildIssued", "buildScvOrder", "buildFound", "landIssued", "landSeconds",
            "madeMined", "madeMineOrder", "madeMineScvAt100")
    print(f"{s} raw: " + " ".join(f"{k}={checks.value(s, '', k)}" for k in keys))
    for t in SNAPS:
        print(f"{s} raw {t}: " + " ".join(f"{f}={checks.value(s, t, f)}" for f in ("Type", "Facing", "Alive", "At100", "Blocked10")))
    # The starting halls of the Terran lanes, by the game's lane start: on
    # their start point, every measured cell blocked.
    for p in START_OWNERS:
        k = f"p{p}Hall"
        print(f"{s} raw start hall p{p}: type={checks.value(s, k, 'Type')} facing={checks.value(s, k, 'Facing')} at={checks.value(s, k, 'At100')} "
              f"start={checks.value(s, f'p{p}', 'Start100')} foot={checks.value(s, k, 'Foot')}")
        print(_show(f"start hall p{p} grid", _grid(checks, s, k)))
        checks.eq(s, k, "Type", "CommandCenter")
        checks.eq(s, k, "Facing", HALL_FACING)
        # The engine puts an odd footprint on a cell centre; start points
        # sit on cell corners, so up to half a cell per axis is the snap.
        checks.data.setdefault(s, {})[k + "StartOffset100"] = _offset(
            checks.value(s, k, "At100"), checks.value(s, f"p{p}", "Start100"))
        checks.between(s, k, "StartOffset100", 0, 50)
        check_legs(checks, s, k, exact=False)
    _ok(checks, s, "clear test points found", checks.value(s, "", "A100") not in (None, "null") and checks.value(s, "", "B100") not in (None, "null"),
        f"a={checks.value(s, '', 'A100')} b={checks.value(s, '', 'B100')}")
    checks.eq(s, "", "Foot", hall_footprint_id(hall_rows()))
    # Positive control: before any hall both points are open and a Barracks fits.
    check_open(checks, s, "t0A")
    check_open(checks, s, "t0B")
    # Built by an SCV: the footprint from the construction start.
    checks.eq(s, "", "buildFound", 1)
    checks.eq(s, "built", "Alive", 1)
    checks.eq(s, "built", "Facing", HALL_FACING)
    check_legs(checks, s, "builtA")
    checks.eq(s, "built", "Blocked10", 0)
    # Killed under construction: nothing left.
    check_open(checks, s, "builtDeadA")
    # Created complete; the landing point still open.
    checks.eq(s, "made", "Type", "CommandCenter")
    checks.eq(s, "made", "Facing", HALL_FACING)
    check_legs(checks, s, "madeA")
    checks.eq(s, "made", "Blocked10", 0)
    check_open(checks, s, "madeB")
    # The hall stays a drop-off.
    _ok(checks, s, "one SCV mines at the hall", (checks.value(s, "", "madeMined") or 0) > 0, f"mined={checks.value(s, '', 'madeMined')}")
    # Flying: nothing anywhere.
    checks.eq(s, "lifted", "Type", "CommandCenterFlying")
    check_open(checks, s, "liftedA")
    check_open(checks, s, "liftedB")
    # Landed 20 or more away: the footprint there; nothing left at the old point.
    checks.eq(s, "", "landIssued", 1)
    checks.eq(s, "landed", "Type", "CommandCenter")
    checks.eq(s, "landed", "Facing", HALL_FACING)
    checks.eq(s, "landed", "At100", checks.value(s, "", "B100"))
    check_legs(checks, s, "landedB")
    checks.eq(s, "landed", "Blocked10", 0)
    check_open(checks, s, "landedA")
    # Killed: nothing left.
    check_open(checks, s, "deadB")
    check_paint(checks)
