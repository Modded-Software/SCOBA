"""Air creep profile (REQ-AIR-CREEP): Mutalisks vs Wraiths.

Groups: timer (the live map-start schedule), wave, route, fight, ground,
cap. Engine reads only. Size (actor scale 5) has no engine getter: operator
check; a host test reads it from the data. Speed and weapon range: the host
test reads them from the data.
"""

from __future__ import annotations

import os
from pathlib import Path

import workpaths
from project_root import project_root

from ..map_builder import TestMapSpec
from ..runner import TestRunSpec
from .registry import PROFILE_BANKS, profile_output

ROOT = project_root()
GROUPS = ("timer", "wave", "route", "fight", "ground", "cap", "balance")
X_RADIUS = 16.0  # X Top / X Bottom region radius (src 8, built x2)
HEIGHT = 72.0
HEIGHT_TOL = 2.0
SPACING = 6.0  # c_AIR_CREEP_SPACING, slot to formation centre
# Spawn to home structure: the second formation centre is 3 x SPACING to the
# side; its farthest slot is 24 away. Slack 5.
HOME_TOL = 29.0
# Two targets of one formation: opposite octagon slots are 2 x SPACING
# apart. Slack for the engine moving an order point.
FORMATION_SPAN = 2.0 * SPACING + 1.0
TERRAN_PER_DIR = 3
ZERG_MIN_PER_DIR = 4
ZERG_MAX_PER_DIR = 6
BALANCE_STEP = 1  # c_AIR_CREEP_BALANCE_STEP, units per formation
WAVE_TOL_MS = 2500  # wider than the 0.25 s poll and the 0.5 s harness start
PERIOD_MS = 20000
PHASE_MS = 10000
# First (Zerg) slot: 1 s into the first S7 of the intro, the shot that
# looks up at the Overmind (50..57 s; operator 2026-11-20: the Mutalisks
# are born in that shot).
S7_START_MS = 50000
S7_END_MS = 57000
START_MS = 51000
EARLY_MS = 5000  # c_AIR_CREEP_EARLY: Mutalisks; Wraiths at twice this
EARLY_TOL_MS = 1500  # under half the stagger: 5 s and 10 s must differ
CAP = 32
SIDES = {
    "zerg": {"type": "SCOBAMutalisk", "owner": 4, "weapon": "SCOBAAirGlaive"},
    "terran": {"type": "SCOBAWraith", "owner": 1, "weapon": "SCOBAWraithA"},
}


def selected_group() -> str:
    group = os.environ.get("SC2_TEST_GROUP", "all")
    if group != "all" and group not in GROUPS:
        raise SystemExit(f"unknown aircreep group: {group}; choose all or one of {', '.join(GROUPS)}")
    return group


def _report(checks, name: str, ok: bool, detail: str) -> None:
    print(f"{name}: {detail} {'PASS' if ok else 'FAIL'}")
    if not ok:
        checks.failures += 1


def _num(checks, s: str, key: str) -> float | None:
    raw = checks.value(s, "", key)
    return None if raw is None else int(raw) / 100.0


def _in_x(checks, s: str, tag: str, which: str) -> bool:
    d = _num(checks, s, f"{tag}{which}100")
    return d is not None and d <= X_RADIUS


def _raw(checks, s: str, tag: str) -> None:
    keys = ("Type", "Owner", "At100", "Height100", "Life100", "LifeMax100", "Orders", "Weapons", "Weapon1", "Weapon2",
            "O0Abil", "O0Cmd", "O0Top100", "O0Bottom100", "O0Center100", "O1Abil", "O1Cmd", "O1Top100", "O1Bottom100")
    print(f"{s} raw {tag}: " + " ".join(f"{k}={checks.value(s, tag, k)}" for k in keys))


def _hits(checks, s: str) -> None:
    print(f"{s} raw hits: creep={checks.value(s, '', 'creepHits')} other={checks.value(s, '', 'otherHits')} sources={checks.value(s, '', 'hitSources')}")


def _balance_step(own: int, enemy: int) -> int:
    """REQ-AIR-CREEP R-AIR-16: per formation, +1 behind, -1 ahead, 0 equal."""
    if own < enemy:
        return BALANCE_STEP
    if own > enemy:
        return -BALANCE_STEP
    return 0


# --- timer ------------------------------------------------------------------
def check_timer(checks) -> None:
    s = "ac_timer"
    keys = ("firstMs", "firstZerg", "firstTerran", "firstWavesZerg", "firstWavesTerran", "zerg2Ms", "zerg4Ms", "terran2Ms",
            "terran4Ms", "at5Zerg", "at5Terran", "at15Zerg", "at15Terran", "at25Zerg", "at25Terran", "at35Zerg", "at35Terran",
            "at5AliveZerg", "at5AliveTerran", "at15AliveZerg", "at15AliveTerran", "at25AliveZerg", "at25AliveTerran",
            "at35AliveZerg", "at35AliveTerran", "endZerg", "endTerran", "wavesZerg", "wavesTerran", "timerDurationMs",
            "timerRemainMs")
    print(f"{s} raw: " + " ".join(f"{k}={checks.value(s, '', k)}" for k in keys))
    # zerg2Ms / terran2Ms: first wave seen; zerg4Ms / terran4Ms: second wave.
    # at*Zerg / at*Terran: units made so far (spawn counter), not live units.
    # Early waves (operator 2026-11-20): Mutalisks at 5 s, Wraiths at 10 s,
    # one each (read at 15 real s; negative: not two). Negative: nothing at
    # 3 s. The Mutalisks see no air creeps (8..12); the Wraiths see them
    # and are behind (+1: 8).
    print(f"{s} raw start: " + " ".join(f"{k}={checks.value(s, '', k)}" for k in ("start3Waves", "start3Alive", "earlyZergMs", "earlyTerranMs", "start5Zerg", "start5Terran", "start5WavesZerg", "start5WavesTerran", "start5BalTerran")))
    checks.eq(s, "", "start3Waves", 0)
    checks.eq(s, "", "start3Alive", 0)
    checks.between(s, "", "earlyZergMs", EARLY_MS - EARLY_TOL_MS, EARLY_MS + EARLY_TOL_MS)
    checks.between(s, "", "earlyTerranMs", 2 * EARLY_MS - EARLY_TOL_MS, 2 * EARLY_MS + EARLY_TOL_MS)
    checks.eq(s, "", "start5WavesZerg", 1)
    checks.eq(s, "", "start5WavesTerran", 1)
    checks.between(s, "", "start5Zerg", 2 * ZERG_MIN_PER_DIR, 2 * ZERG_MAX_PER_DIR)
    checks.eq(s, "", "start5Terran", 2 * (TERRAN_PER_DIR + BALANCE_STEP))
    z0, t0 = checks.value(s, "", "start5Zerg") or 0, checks.value(s, "", "start5Terran") or 0
    # Waves at START (Zerg), START + 10 (Terran), START + 20 (Zerg),
    # START + 30 (Terran) s.
    checks.eq(s, "", "shiftMs", START_MS - 10000)
    checks.between(s, "", "zerg2Ms", START_MS - WAVE_TOL_MS, START_MS + WAVE_TOL_MS)
    # Inside the first S7, with room for the 1.4 s Birth clip.
    checks.between(s, "", "zerg2Ms", S7_START_MS, S7_END_MS - 2000)
    checks.between(s, "", "terran2Ms", START_MS + PHASE_MS - WAVE_TOL_MS, START_MS + PHASE_MS + WAVE_TOL_MS)
    checks.between(s, "", "zerg4Ms", START_MS + PERIOD_MS - WAVE_TOL_MS, START_MS + PERIOD_MS + WAVE_TOL_MS)
    checks.between(s, "", "terran4Ms", START_MS + PHASE_MS + PERIOD_MS - WAVE_TOL_MS, START_MS + PHASE_MS + PERIOD_MS + WAVE_TOL_MS)
    z2, t2, z4, t4 = (checks.value(s, "", k) for k in ("zerg2Ms", "terran2Ms", "zerg4Ms", "terran4Ms"))
    if None not in (z2, t2, z4, t4) and min(z2, t2, z4, t4) >= 0:
        _report(checks, f"{s} Zerg period", abs((z4 - z2) - PERIOD_MS) <= WAVE_TOL_MS, f"period={z4 - z2}ms")
        _report(checks, f"{s} Terran period", abs((t4 - t2) - PERIOD_MS) <= WAVE_TOL_MS, f"period={t4 - t2}ms")
        _report(checks, f"{s} phase Terran after Zerg", abs((t2 - z2) - PHASE_MS) <= WAVE_TOL_MS, f"phase={t2 - z2}ms")
    else:
        _report(checks, f"{s} wave times read", False, f"z2={z2} t2={t2} z4={z4} t4={t4}")
    # Balance of each live wave: the rule applied to the counts it saw.
    bal = {}
    for side in ("zerg", "terran"):
        for n in (1, 2):
            p = f"{side}Bal"
            raw = {k: checks.value(s, "", f"{p}{k}{n}") for k in ("", "Own", "Enemy", "SizeA", "SizeB")}
            print(f"{s} raw balance {side} wave {n}: " + " ".join(f"{k or 'step'}={v}" for k, v in raw.items()))
            own, enemy, step = raw["Own"], raw["Enemy"], raw[""]
            ok = None not in (own, enemy, step) and step == _balance_step(own, enemy)
            _report(checks, f"{s} {side} wave {n} balance follows the counts", ok, f"own={own} enemy={enemy} step={step}")
            bal[(side, n)] = step if isinstance(step, int) else 0

    def zrange(step: int) -> tuple[int, int]:
        return 2 * (ZERG_MIN_PER_DIR + step), 2 * (ZERG_MAX_PER_DIR + step)

    # Units made between the waves. Negative: nothing between the start
    # waves and the first slot, and nothing outside a wave.
    checks.eq(s, "", "at5Zerg", z0)
    checks.eq(s, "", "at5Terran", t0)
    zr1 = zrange(bal[("zerg", 1)])
    checks.between(s, "", "at15Zerg", z0 + zr1[0], z0 + zr1[1])
    checks.eq(s, "", "at15Terran", t0)
    checks.eq(s, "", "at25Zerg", checks.value(s, "", "at15Zerg"))
    checks.eq(s, "", "at25Terran", t0 + 2 * (TERRAN_PER_DIR + bal[("terran", 1)]))
    z25, z35 = checks.value(s, "", "at25Zerg"), checks.value(s, "", "at35Zerg")
    zr2 = zrange(bal[("zerg", 2)])
    _report(checks, f"{s} second Zerg wave size", z25 is not None and z35 is not None and zr2[0] <= z35 - z25 <= zr2[1],
            f"made={None if None in (z25, z35) else z35 - z25} want={zr2[0]}..{zr2[1]}")
    checks.eq(s, "", "at35Terran", checks.value(s, "", "at25Terran"))
    checks.eq(s, "", "timerDurationMs", PHASE_MS)
    # The tick is real time like the reinforcement timer; the wave counters
    # agree with the engine counts.
    checks.eq(s, "", "wavesZerg", 3)
    checks.eq(s, "", "wavesTerran", 3)


# --- wave -------------------------------------------------------------------
def _check_wave_unit(checks, s: str, tag: str, side: str) -> None:
    want = SIDES[side]
    checks.true(s, tag, "Valid")
    checks.eq(s, tag, "Type", want["type"])
    checks.eq(s, tag, "Owner", want["owner"])
    home = _num(checks, s, f"{tag}Home100")
    _report(checks, f"{s} {tag} at home", home is not None and home <= HOME_TOL, f"dist={home}")
    # Negative: no stock weapon left once the unit is handed out.
    checks.eq(s, tag, "Weapons", 1)
    checks.eq(s, tag, "Weapon1", want["weapon"])
    # First order: attack-move into one X; then patrol (move, command 1) to the other.
    checks.eq(s, tag, "O0Abil", "attack")
    checks.eq(s, tag, "O1Abil", "move")
    checks.eq(s, tag, "O1Cmd", 1)
    top_first = _in_x(checks, s, tag, "O0Top")
    bottom_first = _in_x(checks, s, tag, "O0Bottom")
    _report(checks, f"{s} {tag} first X is Top or Bottom", top_first != bottom_first, f"top={top_first} bottom={bottom_first}")
    second_ok = _in_x(checks, s, tag, "O1Bottom") if top_first else _in_x(checks, s, tag, "O1Top")
    _report(checks, f"{s} {tag} patrol to the other X", second_ok, f"topFirst={top_first}")
    # Negative: never X Center.
    for o in ("O0", "O1"):
        c = _num(checks, s, f"{tag}{o}Center100")
        _report(checks, f"{s} {tag} negative: {o} not at X Center", c is not None and c > X_RADIUS, f"dist={c}")


def _xy(checks, s: str, tag: str, key: str) -> tuple[float, float] | None:
    raw = checks.value(s, tag, key)
    if not isinstance(raw, str) or "," not in raw:
        return None
    x, y = raw.split(",", 1)
    return int(x) / 100.0, int(y) / 100.0


def _span(points: list[tuple[float, float] | None]) -> float | None:
    if any(p is None for p in points):
        return None
    pts = [p for p in points if p is not None]
    return max((((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5 for a in pts for b in pts), default=0.0)


def check_sizes(checks) -> None:
    s = "ac_sizes"
    keys = ("draws", "zergMin", "zergMax", "zergMean100", "zergN4", "zergN5", "zergN6", "terranMin", "terranMax", "terranMean100")
    print(f"{s} raw: " + " ".join(f"{k}={checks.value(s, '', k)}" for k in keys))
    checks.eq(s, "", "terranMin", TERRAN_PER_DIR)
    checks.eq(s, "", "terranMax", TERRAN_PER_DIR)
    # Zerg: 4..6. Negative: never 3 or 7. All three sizes drawn; mean near 5
    # (600 draws of a uniform 4..6: sd of the mean 0.033; window 5 +- 0.2).
    checks.eq(s, "", "zergMin", ZERG_MIN_PER_DIR)
    checks.eq(s, "", "zergMax", ZERG_MAX_PER_DIR)
    for n in range(ZERG_MIN_PER_DIR, ZERG_MAX_PER_DIR + 1):
        checks.gt(s, "", f"zergN{n}", 0)
    checks.between(s, "", "zergMean100", 480, 520)


def check_wave(checks) -> None:
    check_sizes(checks)
    for side in ("zerg", "terran"):
        s = f"ac_wave_{side}"
        print(f"{s} raw home={checks.value(s, '', 'home100')} made={checks.value(s, '', 'made')} units={checks.value(s, '', 'units')} armTicks={checks.value(s, '', 'armTicks')} before={checks.value(s, '', 'before')} after={checks.value(s, '', 'after')} other={checks.value(s, '', 'otherSide')}")
        made = checks.value(s, "", "made")
        n = made if isinstance(made, int) else 0
        tags = [f"u{i}" for i in range(1, n + 1)]
        lates = [f"late{i}" for i in range(1, n + 1)]
        for tag in tags + lates:
            _raw(checks, s, tag)
        if side == "terran":
            checks.eq(s, "", "made", 2 * TERRAN_PER_DIR)
        else:
            checks.between(s, "", "made", 2 * ZERG_MIN_PER_DIR, 2 * ZERG_MAX_PER_DIR)
        checks.eq(s, "", "units", made)
        # The stock weapons went before the wait ran out (16 ticks).
        checks.lt(s, "", "armTicks", 16)
        checks.eq(s, "", "before", 0)
        checks.eq(s, "", "after", made)
        # Negative: a wave of one side makes none of the other.
        checks.eq(s, "", "otherSide", 0)
        # Birth (operator 2026-11-20): every Mutalisk starts its Birth clip
        # and the engine reports a clip in that slot. Negative: no Wraith does.
        print(f"{s} raw births={checks.value(s, '', 'births')} birthLen100={checks.value(s, '', 'birthLen100')}")
        if side == "zerg":
            checks.eq(s, "", "births", made)
            checks.gt(s, "", "birthLen100", 0)
        else:
            checks.eq(s, "", "births", 0)
            checks.between(s, "", "birthLen100", -999999, 0)
        for tag in tags:
            _check_wave_unit(checks, s, tag, side)
        # Formations: one per X, sized per side; each flies to one spot.
        top = [t for t in tags if _in_x(checks, s, t, "O0Top")]
        bottom = [t for t in tags if _in_x(checks, s, t, "O0Bottom")]
        lo, hi = (TERRAN_PER_DIR, TERRAN_PER_DIR) if side == "terran" else (ZERG_MIN_PER_DIR, ZERG_MAX_PER_DIR)
        for name, group in (("Top", top), ("Bottom", bottom)):
            _report(checks, f"{s} formation to X {name} size", lo <= len(group) <= hi, f"n={len(group)} want={lo}..{hi}")
            span = _span([_xy(checks, s, t, "O0At100") for t in group])
            _report(checks, f"{s} formation to X {name} first targets together", span is not None and span <= FORMATION_SPAN,
                    f"span={span} max={FORMATION_SPAN}")
            span2 = _span([_xy(checks, s, t, "O1At100") for t in group])
            _report(checks, f"{s} formation to X {name} patrol targets together", span2 is not None and span2 <= FORMATION_SPAN,
                    f"span={span2} max={FORMATION_SPAN}")
            # Negative: formation members do not share one point.
            pts = [_xy(checks, s, t, "O0At100") for t in group]
            distinct = len({p for p in pts if p is not None}) == len(group)
            _report(checks, f"{s} formation to X {name} negative: no shared slot", distinct, f"points={pts}")
        for tag in lates:
            h = _num(checks, s, f"{tag}Height100")
            _report(checks, f"{s} {tag} height", h is not None and abs(h - HEIGHT) <= HEIGHT_TOL, f"height={h} want={HEIGHT}")
            # One weapon, the air-only SCOBA weapon; no ground weapon (negative).
            checks.eq(s, tag, "Weapons", 1)
            checks.eq(s, tag, "Weapon1", SIDES[side]["weapon"])
            checks.eq(s, tag, "Weapon2", "")


# --- route ------------------------------------------------------------------
def check_route(checks) -> None:
    for side, first, second in (("zerg", "Top", "Bottom"), ("terran", "Bottom", "Top")):
        s = f"ac_route_{side}"
        for tag in ("t0", "p0", "p2", "p6"):
            _raw(checks, s, tag)
        print(f"{s} raw patrolMs={checks.value(s, '', 'patrolMs')} p2First={checks.value(s, '', 'p2First100')} p6First={checks.value(s, '', 'p6First100')}")
        checks.eq(s, "t0", "O0Abil", "attack")
        checks.eq(s, "t0", "Weapons", 1)
        _report(checks, f"{s} first leg to X {first}", _in_x(checks, s, "t0", f"O0{first}"), "")
        # Negative: the first leg does not go to the other X.
        _report(checks, f"{s} negative: first leg not to X {second}", not _in_x(checks, s, "t0", f"O0{second}"), "")
        checks.gt(s, "", "patrolMs", 0)
        # Patrol starts on arrival: one order left, move command 1, to the other X.
        checks.eq(s, "p0", "Orders", 1)
        checks.eq(s, "p0", "O0Abil", "move")
        checks.eq(s, "p0", "O0Cmd", 1)
        _report(checks, f"{s} patrol to X {second}", _in_x(checks, s, "p0", f"O0{second}"), "")
        d = _num(checks, s, f"p0{first}100")
        _report(checks, f"{s} patrol starts at X {first}", d is not None and d <= X_RADIUS + 2.0, f"dist={d}")
        # The X trigger does not send it down a lane (negative): it keeps its patrol.
        checks.false(s, "p0", "Attacking")
    # The loop: near the far end it turns back to the first X, still patrolling.
    s = "ac_route_zerg"
    checks.eq(s, "p6", "O0Abil", "move")
    checks.eq(s, "p6", "O0Cmd", 1)
    checks.eq(s, "p6", "Orders", 1)
    d2 = _num(checks, s, "p2First100")
    d6 = _num(checks, s, "p6First100")
    _report(checks, f"{s} patrol turns back to X Top", d2 is not None and d6 is not None and d6 < d2 - 5.0, f"d2={d2} d6={d6}")


# --- fight ------------------------------------------------------------------
def check_fight(checks) -> None:
    s = "ac_fight"
    for tag in ("m0", "w0", "m1", "w1"):
        _raw(checks, s, tag)
    print(f"{s} raw crowd={checks.value(s, '', 'crowd')} types={checks.value(s, '', 'crowdTypes')}")
    _hits(checks, s)
    checks.eq(s, "", "crowd", 0)
    # Engine damage events between the two: both directions together.
    checks.gt(s, "", "creepHits", 1)
    for tag in ("m", "w"):
        checks.eq(s, tag + "0", "Weapons", 1)
        start = checks.value(s, tag + "0", "Life100")
        checks.eq(s, tag + "0", "Life100", checks.value(s, tag + "0", "LifeMax100"))
        end = checks.value(s, tag + "1", "Life100")
        alive = checks.value(s, tag + "1", "Alive")
        hurt = start is not None and (alive is False or (end is not None and end < start))
        _report(checks, f"{s} {tag} hurt in the fight", hurt, f"start={start} end={end} alive={alive}")


# --- ground -----------------------------------------------------------------
def check_ground(checks) -> None:
    for name in ("wraith", "muta"):
        s = f"ac_ground_{name}"
        for tag in ("c0", "c1"):
            _raw(checks, s, tag)
        keys = ("crowd", "crowdTypes", "crowdEnd", "crowdEndTypes", "groundType", "airType", "groundLife0", "groundLife1", "airLife0", "airLife1", "groundAlive", "airAlive")
        print(f"{s} raw: " + " ".join(f"{k}={checks.value(s, '', k)}" for k in keys))
        _hits(checks, s)
        checks.eq(s, "", "crowd", 0)
        checks.eq(s, "", "crowdEnd", 0)
        checks.eq(s, "c0", "Weapons", 1)
        checks.gt(s, "", "groundLife0", 0)
        checks.gt(s, "", "airLife0", 0)
        # Negative: no damage event from the air creep on the ground unit or
        # on the other air unit. Other sources (lane spore cannons) are raw.
        checks.eq(s, "", "creepHits", 0)
        checks.true(s, "", "groundAlive")
        checks.true(s, "", "airAlive")
        checks.false(s, "c1", "Attacking")
    s = "ac_ground_bc"
    _raw(checks, s, "c1")
    _hits(checks, s)
    checks.eq(s, "", "creepHits", 0)
    print(f"{s} raw placedBcs={checks.value(s, '', 'placedBcs')} crowd={checks.value(s, '', 'crowd')} types={checks.value(s, '', 'crowdTypes')} bcValid={checks.value(s, '', 'bcValid')} owner={checks.value(s, '', 'bcOwner')} life0={checks.value(s, '', 'bcLife0')} life1={checks.value(s, '', 'bcLife1')}")
    checks.eq(s, "", "crowd", 0)
    checks.true(s, "", "bcValid")
    checks.gt(s, "", "bcLife0", 0)
    checks.false(s, "c1", "Attacking")


# --- cap --------------------------------------------------------------------
def check_cap(checks) -> None:
    s = "ac_cap_zerg"
    print(f"{s} raw: " + " ".join(f"{k}={checks.value(s, '', k)}" for k in ("preset", "made1", "after1", "made2", "after2")))
    checks.eq(s, "", "preset", CAP - 1)
    checks.eq(s, "", "made1", 1)
    checks.eq(s, "", "after1", CAP)
    # Negative: no unit past the cap.
    checks.eq(s, "", "made2", 0)
    checks.eq(s, "", "after2", CAP)
    s = "ac_cap_terran"
    print(f"{s} raw: " + " ".join(f"{k}={checks.value(s, '', k)}" for k in ("preset", "made1", "after1", "made2", "after2")))
    checks.eq(s, "", "preset", CAP)
    checks.eq(s, "", "made1", 0)
    checks.eq(s, "", "after1", CAP)


# --- balance ----------------------------------------------------------------
BALANCE_CASES = {
    # case: (own preset, enemy preset, expected step per formation)
    "behind": (2, 10, BALANCE_STEP),
    "ahead": (10, 2, -BALANCE_STEP),
    "equal": (5, 5, 0),
}


def check_balance(checks) -> None:
    for side in ("zerg", "terran"):
        base = (TERRAN_PER_DIR, TERRAN_PER_DIR) if side == "terran" else (ZERG_MIN_PER_DIR, ZERG_MAX_PER_DIR)
        for case, (own, enemy, step) in BALANCE_CASES.items():
            s = f"ac_bal_{side}_{case}"
            keys = ("presetOwn", "presetEnemy", "sawOwn", "sawEnemy", "balance", "sizeA", "sizeB", "made", "afterOwn", "afterEnemy")
            print(f"{s} raw: " + " ".join(f"{k}={checks.value(s, '', k)}" for k in keys))
            checks.eq(s, "", "presetOwn", own)
            checks.eq(s, "", "presetEnemy", enemy)
            # The wave read the counts before it made a unit.
            checks.eq(s, "", "sawOwn", own)
            checks.eq(s, "", "sawEnemy", enemy)
            checks.eq(s, "", "balance", step)
            for key in ("sizeA", "sizeB"):
                checks.between(s, "", key, base[0] + step, base[1] + step)
            # Negatives: ahead never above the base size, behind never below.
            if step < 0:
                for key in ("sizeA", "sizeB"):
                    checks.lt(s, "", key, base[1] + 1)
            if step > 0:
                for key in ("sizeA", "sizeB"):
                    checks.gt(s, "", key, base[0] - 1)
            a, b = checks.value(s, "", "sizeA"), checks.value(s, "", "sizeB")
            checks.eq(s, "", "made", None if None in (a, b) else a + b)
            made = checks.value(s, "", "made")
            checks.eq(s, "", "afterOwn", None if made is None else own + made)
            # Negative: a wave of one side makes none of the other.
            checks.eq(s, "", "afterEnemy", enemy)


CHECKS = {
    "timer": check_timer,
    "wave": check_wave,
    "route": check_route,
    "fight": check_fight,
    "ground": check_ground,
    "cap": check_cap,
    "balance": check_balance,
}


def map_spec() -> TestMapSpec:
    return TestMapSpec(
        profile="aircreep",
        source=workpaths.path("SC2_BUILT_MAP"),
        output=profile_output("aircreep"),
        bank_names=PROFILE_BANKS["aircreep"],
        galaxy_files=(
            ROOT / "scripts" / "testkit" / "galaxy" / "common.galaxy",
            ROOT / "scripts" / "testkit" / "galaxy" / "aircreep.galaxy",
            ROOT / "scripts" / "testkit" / "galaxy" / "aircreep_cases.galaxy",
        ),
        galaxy_includes=(
            "scripts/test/aircreep/common",
            "scripts/test/aircreep/aircreep",
            "scripts/test/aircreep/aircreep_cases",
        ),
        init_calls=(f'gv_dbgGroup = "{selected_group()}";', "gt_AirCreepTest_Init();"),
    )


def on_ready(ctx, data: dict) -> None:
    return


def check(ctx, data: dict, checks) -> None:
    for error in ctx.errors:
        print(f"{error} FAIL")
        checks.failures += 1
    checks.eq("meta", "", "done", 1)
    checks.eq("ac_end", "", "RealClicks", 0)
    group = selected_group()
    print(f"group: {group}")
    for name in GROUPS:
        if group in ("all", name):
            CHECKS[name](checks)


def run_spec(launch_timeout_s: float, case_timeout_s: float, run_root: Path) -> TestRunSpec:
    return TestRunSpec(
        profile="aircreep",
        map_name="SCOBA.SC2Map",
        map_source=profile_output("aircreep"),
        map_cache_name="SCOBA.SC2Map",
        bank_names=PROFILE_BANKS["aircreep"],
        ready_section="ac_start",
        ready_key="ready",
        launch_timeout_s=launch_timeout_s,
        case_timeout_s=case_timeout_s,
        run_root=run_root,
        on_ready=on_ready,
        check=check,
    )
