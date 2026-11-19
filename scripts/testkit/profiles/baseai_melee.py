"""Base AI macro: melee map and live game checks (REQ-BASE-AI 3.5, 3.6;
SPEC-BASE-AI A11-A13, R-BASE-33, 34).

Raw values first, so a failure shows what the stock melee scripts read.
"""

from __future__ import annotations

MELEE_KEYS = ("StartLoc100", "GroundStartLocs", "TotalStartLocs", "NumEnemies", "NumAllies", "NumTeams",
              "EnemyBuildings", "OpeningType", "BuildIndex", "MainState", "AttackState", "WaveMain", "WaveAttack",
              "WaveAttackState", "TownStates", "MineralsLeft", "NearbyOpen", "NextTownSlot",
              "SupplyUsed", "SupplyLost", "UnitsLost", "AttackEntries", "LostTypes", "LostHalls", "HallTries", "Town1At", "Town1Place")
START_TOL_100 = 400          # hall centre within 4 of its start location
ATTACK_STATE = 3             # e_attackState_Attack (core meleeai.galaxy)
WAVE_ATTACK = 4              # c_waveStateAttack (core ai.galaxy)
ATTACKERS_MIN = 4            # R-BASE-34: owners in attack state by the end
REPEAT_ATTACKS = 2           # R-BASE-34: one owner enters attack state this often


def _xy(raw) -> tuple[int, int] | None:
    """"x,y" in hundredths; None for a missing or "null" bank value."""
    parts = str(raw).split(",")
    if len(parts) != 2 or not all(p.lstrip("-").isdigit() for p in parts):
        return None
    return int(parts[0]), int(parts[1])


def check_growth(checks, s: str, k: str, tags: tuple[str, ...], ok) -> None:
    """R-BASE-33: supply used plus supply lost grows within every two
    minutes. Losses do not lower it, so a flat line after a loss means the
    owner did not replace what it lost. Window wider than any build time."""
    used = [checks.value(s, k + t, "SupplyUsed") for t in tags]
    lost = [checks.value(s, k + t, "SupplyLost") for t in tags]
    made = [None if u is None or v is None else u + v for u, v in zip(used, lost)]
    stalls = [tags[i + 2] for i in range(1, len(made) - 2)
              if None not in made[i:i + 3] and max(made[i + 1], made[i + 2]) <= made[i]]
    ok(checks, s, f"{k} supply used + lost grows within 2 min", not stalls and None not in made,
       f"used={used} lost={lost} stalls at={stalls}")


def check_melee(checks, owners: tuple[int, ...], tags: tuple[str, ...], ok) -> None:
    s = "ba_macro"
    end = tags[-1]
    attackers, repeats, losers = [], [], []
    for p in owners:
        for t in tags:
            k = f"p{p}{t}"
            print(f"{s} raw {k} melee: " + " ".join(f"{n}={checks.value(s, k, n)}" for n in MELEE_KEYS))
    for p in owners:
        k = f"p{p}"
        start = _xy(checks.value(s, k + "t1", "StartLoc100"))
        hall = _xy(checks.value(s, k, "HallAt100"))
        near = start is not None and hall is not None and max(abs(start[0] - hall[0]), abs(start[1] - hall[1])) <= START_TOL_100
        ok(checks, s, f"{k} hall at its start location", near, f"start={start} hall={hall}")
        # A12: ground start locations seen, so no forced air opening (F20).
        checks.gt(s, k + "t1", "GroundStartLocs", 0)
        # A13: the other team is the enemy.
        checks.gt(s, k + "t1", "NumEnemies", 0)
        if any(checks.value(s, f"{k}{t}", "WaveAttackState") == WAVE_ATTACK
               or checks.value(s, f"{k}{t}", "AttackState") == ATTACK_STATE for t in tags):
            attackers.append(p)
        if (checks.value(s, k + end, "AttackEntries") or 0) >= REPEAT_ATTACKS:
            repeats.append(p)
        if (checks.value(s, k + end, "UnitsLost") or 0) > 0:
            losers.append(p)
    ok(checks, s, f"at least {ATTACKERS_MIN} owners attacked by {end}", len(attackers) >= ATTACKERS_MIN,
       f"attackers={attackers}")
    ok(checks, s, f"an owner attacked {REPEAT_ATTACKS} times by {end}", bool(repeats), f"repeats={repeats}")
    # The loss counter works: an owner that attacked lost units (a fight costs units).
    ok(checks, s, "an attacker lost units (losses counted)", bool(set(attackers) & set(losers)),
       f"attackers={attackers} lost={losers}")
