"""Kerrigan checks of the combat group `kerrigan` (operator 2026-11-22).

Psi Blast is her ranged attack at any distance. Her talons are the F swing
(operator 2026-11-23) and the auto twin RazorTalonsAuto, which the engine
uses only with Attack auto; the stock RazorTalons is gone from her.
Her aim pose breathes (R-TPS-19): every pitch clip play is followed by one
breath sync, and the engine's clip stands at the game clock's place in the
breath. Tosh's aim pose is still: no sync.
"""

from __future__ import annotations


from heroanim.rig import HEROES

from ..bank_checks import _report

PSI = "QueenOfBladesPsiBlast"
TALONS_AUTO = "RazorTalonsAuto"
BREATH_MS = HEROES["kerrigan"].breath_ms
# The clip position is read some game loops after the clock (query wait).
PHASE_TOL_MS = 400


def check_weapons(checks, section: str, shots: int, auto: bool = False) -> None:
    """`shots`: the Psi Blast effects the scenario must add, at least.
    `auto`: Attack auto, where the engine must use the talons twin."""
    for tag in ("w0", "w1"):
        checks.eq(section, tag, "Type", "KerriganSCOBA")
        checks.eq(section, tag, "Weapons", 3)
        checks.eq(section, tag, "Weapon1", PSI)
        checks.eq(section, tag, "Weapon2", PSI + "Auto")
        checks.eq(section, tag, "Weapon3", TALONS_AUTO)
        checks.eq(section, tag, "MinRange1000", 0)
        # Negative (R-TPS-65): the engine holds no Poison Nova on her.
        checks.false(section, tag, "Nova")
    psi = [checks.value(section, tag, "PsiFx") for tag in ("w0", "w1")]
    talons = [checks.value(section, tag, "TalonsFx") for tag in ("w0", "w1")]
    ok = None not in psi and psi[1] - psi[0] >= shots
    _report(checks, f"{section} shots are Psi Blast effects", ok, f"psi={psi} want +{shots}")
    print(f"{section} raw: psi={psi} talons={talons}")
    if auto:
        ok = None not in talons and talons[1] > talons[0]
        _report(checks, f"{section} engine uses the talons with Attack auto", ok, f"talons={talons}")
        return
    # Negative: Attack single, no talons effect in the scenario.
    ok = None not in talons and talons[1] == talons[0]
    _report(checks, f"{section} no talons effect", ok, f"talons={talons}")


def _phase_gap(a: float, b: float) -> float:
    gap = abs(a - b) % BREATH_MS
    return min(gap, BREATH_MS - gap)


def check_breath(checks) -> None:
    s = "breath_kerrigan"
    checks.eq(s, "", "type", "KerriganSCOBA")
    values = {tag: {key: checks.value(s, tag, key) for key in ("Syncs", "Sends", "Step", "PhaseMs", "ClockMs", "LenMs", "RemMs")} for tag in ("tpre", "t0", "t1", "t2", "t3")}
    print(f"breath raw: {values}")
    if any(value is None for tag in values.values() for value in tag.values()):
        _report(checks, "breath values read", False, str(values))
        return
    checks.true(s, "t0", "AimUpper")
    # Every pitch clip play has one sync; each camera move plays new clips.
    for before, after in (("tpre", "t0"), ("t0", "t1"), ("t1", "t2")):
        sends = values[after]["Sends"] - values[before]["Sends"]
        syncs = values[after]["Syncs"] - values[before]["Syncs"]
        _report(checks, f"breath sync per pitch clip play {before}->{after}", sends > 0 and syncs == sends, f"sends={sends} syncs={syncs}")
    ok = values["t1"]["Step"] != values["t0"]["Step"] and values["t2"]["Step"] != values["t1"]["Step"]
    _report(checks, "breath pitch step follows the camera", ok, f"steps={[values[tag]['Step'] for tag in values]}")
    # Negative: a still camera sends nothing.
    ok = values["t3"]["Sends"] == values["t2"]["Sends"] and values["t3"]["Syncs"] == values["t2"]["Syncs"]
    _report(checks, "breath no sync while the camera is still", ok, f"t2={values['t2']} t3={values['t3']}")
    for tag in ("t0", "t1", "t2", "t3"):
        row = values[tag]
        # Engine state: the clip is one breath long and stands at the clock's
        # place in the breath, also after the pitch step changed.
        _report(checks, f"breath {tag} clip is one breath long", abs(row["LenMs"] - BREATH_MS) <= 50, f"len={row['LenMs']} want={BREATH_MS}")
        at = BREATH_MS - row["RemMs"]
        gap = _phase_gap(at, row["ClockMs"])
        _report(checks, f"breath {tag} clip is in step with the game clock", gap <= PHASE_TOL_MS, f"clip_at={at} clock={row['ClockMs']} gap={gap:.0f} tol={PHASE_TOL_MS}")
        _report(checks, f"breath {tag} sync phase inside the breath", 0 <= row["PhaseMs"] < BREATH_MS, f"phase={row['PhaseMs']}")
    # Negative: Tosh plays pitch clips and never syncs.
    t = "breath_tosh"
    checks.eq(t, "", "type", "ToshSCOBA")
    sends = [checks.value(t, tag, "Sends") for tag in ("tpre", "t2")]
    syncs = [checks.value(t, tag, "Syncs") for tag in ("tpre", "t3")]
    ok = None not in sends and None not in syncs and sends[1] > sends[0] and syncs[1] == syncs[0]
    _report(checks, "breath_tosh pitch clips play without a sync", ok, f"sends={sends} syncs={syncs}")


PSI_LOOPS = 48
PSI_ENEMY = ("psi_fx_02", "psi_fx_03", "psi_fx_035", "psi_fx_04", "psi_fx_08", "psi_order_04", "psi_order_08")
PSI_PROXY = ("psi_fx_proxy", "psi_aim")
# The damage effect alone at the unit, with no missile.
PSI_DIRECT = "psi_direct_04"
NOVA_HIT = "PoisonNovaDirectDamage"
# The missile must get this close to its target, hundredths of a unit.
PSI_REACH_100 = 150
PSI_DAMAGE = 25
# Catalog entries the missile needs to be drawn.
PSI_ASSETS = ("missileActorValid", "attackActorValid", "missileModelValid", "impactModelValid")
PSI_RAW = PSI_ASSETS + ("missileModelFile", "hits", "damageInfo", "lmImpactLocation", "lmImpactEffect", "lmAmmoUnit", "dmgAmount", "dmgImpactLocation", "novaExists", "targetVisible", "weaponRange100", "life0", "life1", "targetValid", "targetType", "targetOwner", "targetZ100", "heroCdMs", "missilesMade", "missileLastLoop", "damageDelayMs", "damageFromHero100", "damageFromTarget100", "aimEffect", "aimKind", "aimTargetIsProxy", "aimProxyZ100", "camPitch", "camYaw", "heroFacing")


def _psi_raw(checks, section: str) -> None:
    for loop in range(PSI_LOOPS):
        row = checks.value(section, "", f"loop{loop:02d}")
        if row is not None and (row.split()[0] != "0" or loop < 2 or "fx0 dmg0" not in row):
            print(f"{section} loop {loop:02d}: {row}")
    print(f"{section} raw: dist={checks.value(section, '', 'targetDist100')} " + " ".join(f"{key}={checks.value(section, '', key)}" for key in PSI_RAW))


def _psi_loss(checks, section: str) -> None:
    life = [checks.value(section, "", key) for key in ("life0", "life1")]
    ok = None not in life and life[0] - life[1] >= PSI_DAMAGE - 2
    _report(checks, f"{section} target loses the shot's damage", ok, f"life={life} want -{PSI_DAMAGE}")


def _psi_no_nova(checks, section: str) -> None:
    """Negative (R-TPS-65): no Poison Nova on her, and none of it hits."""
    checks.false(section, "", "novaExists")
    hits = checks.value(section, "", "hits")
    _report(checks, f"{section} no nova damage", hits is not None and NOVA_HIT not in hits, f"hits={hits!r}")


def check_psi_probe(checks) -> None:
    """One Psi Blast per section, at an enemy by effect and by order, and at
    the proxy. The missile exists, flies to its target, and its damage effect
    lands on that unit (R-TPS-64). The loop rows are the raw trace."""
    _psi_raw(checks, PSI_DIRECT)
    checks.eq(PSI_DIRECT, "", "damages", 1)
    checks.true(PSI_DIRECT, "", "damageOnTarget")
    _psi_loss(checks, PSI_DIRECT)
    # Negative: the damage effect alone launches no missile.
    checks.eq(PSI_DIRECT, "", "launches", 0)
    checks.eq(PSI_DIRECT, "", "missileLoops", 0)
    # The catalog holds the missile's actors and models. That it is drawn
    # on screen stays an operator check.
    for key in PSI_ASSETS:
        checks.true(PSI_ENEMY[0], "", key)
    for section in PSI_ENEMY + PSI_PROXY:
        _psi_raw(checks, section)
        checks.eq(section, "", "heroType", "KerriganSCOBA")
        # The engine's value of the launch effect: the impact gets the unit.
        checks.eq(section, "", "lmImpactLocation", "TargetUnit")
        _psi_no_nova(checks, section)
        dist = checks.value(section, "", "targetDist100")
        far = checks.value(section, "", "missileFar100")
        checks.eq(section, "", "launches", 1)
        checks.gt(section, "", "missileLoops", 0)
        ok = dist is not None and far is not None and far >= dist - PSI_REACH_100
        _report(checks, f"{section} missile flies to the target", ok, f"far={far} target={dist} reach={PSI_REACH_100}")
        checks.eq(section, "", "damages", 1)
        checks.true(section, "", "damageOnTarget")
        # The damage lands at the target, not at Kerrigan.
        landed = checks.value(section, "", "damageFromTarget100")
        _report(checks, f"{section} damage lands at the target", landed is not None and landed <= PSI_REACH_100, f"from_target={landed} from_hero={checks.value(section, '', 'damageFromHero100')}")
        # Negative: no talons effect.
        checks.eq(section, "", "talons1", checks.value(section, "", "talons0"))
        if section in PSI_PROXY:
            # Negative: the proxy is immune.
            life = [checks.value(section, "", key) for key in ("life0", "life1")]
            _report(checks, f"{section} proxy keeps its life", None not in life and life[0] == life[1], f"life={life}")
        else:
            _psi_loss(checks, section)


WATCH = (("stock", "Kerrigan"), ("scoba", "KerriganSCOBA"), ("hydra", "Hydralisk"), ("hydrapsi", "Hydralisk"), ("kerrneedle", "KerriganSCOBA"))


def check_psi_watch(checks) -> None:
    """Operator watch: each shooter is its type and its shots landed. Where
    the missile is drawn is an operator check, not asserted here."""
    section = "psi_watch"
    for tag, unit_type in WATCH:
        checks.eq(section, "", f"{tag}Type", unit_type)
        checks.lt(section, "", f"{tag}Life1", checks.value(section, "", f"{tag}Life0"))


# Talons swing on the TPS left click (operator 2026-11-23): the stock hits,
# 25 at 0 and 0.3 s. Cooldown 1 s; the 2 s clip plays in 0.75 s.
SWING_DAMAGE = 50
SWING_HITS = 2
SWING_COOLDOWN_MS = 1000
SWING_CLIP_MS = 2000
SWING_HOLD_MS = 750
SWING_RATE100 = (266, 267)
# Engine clip time over game time is about 0.72 x the scale (probe, run
# combat/20261123-112703): the old 1.33 reads 1.0, the new 2.67 reads 2.0.
# Over 0.5 s, +-125 ms of reading steps: 2.0 reads 1.75 to 2.25; scale 2.0
# (1.43) at most 1.68.
SWING_ENGINE_RATE = (1.72, 2.3)
# Presses inside the cooldown: no rate probe, it would delay them.
SWING_MULTI_PRESS = ("talons_cd",)
SWING_HALF_ARC = 45
SWING_ANGLE_MARGIN = 5
# Misses by reach or by hero, not by angle.
SWING_REACH_CASES = ("talons_out", "talons_tosh", "talons_click_pnc")
# section: (enemies hit, enemies not hit, swings, Kerrigan)
SWING_CASES = {
    "talons_front": ((0,), (), 1, True),
    "talons_arc": ((0, 1), (), 1, True),
    "talons_edge": ((0,), (), 1, True),
    "talons_out": ((), (0,), 1, True),
    "talons_side": ((), (0, 1), 1, True),
    "talons_back": ((), (0,), 1, True),
    "talons_empty": ((), (), 1, True),
    "talons_cd": ((0,), (), 1, True),
    "talons_tosh": ((), (0,), 0, False),
    # Ring of 8 every 45 degrees from 22.5 off her facing: +-22.5 are hit.
    "talons_ring_f50": ((0, 7), (1, 2, 3, 4, 5, 6), 1, True),
    "talons_ring_f140": ((0, 7), (1, 2, 3, 4, 5, 6), 1, True),
    # Negatives: the press while aiming, and in PNC, does not swing.
    "talons_click_aim": ((), (), 0, True),
    "talons_click_pnc": ((), (0,), 0, True),
}
# section: (TPS on, aiming) at the press.
SWING_MODES = {"talons_click_aim": (True, True), "talons_click_pnc": (False, False)}
SWING_RAW = ("heroType", "swings", "damages", "hits", "cd0Ms", "cd1Ms", "animState", "facing0", "facing1", "weapons", "dist100_0", "angle_0", "dist100_1", "angle_1", "life0_0", "life1_0", "life0_1", "life1_1") + tuple(f"angle_{i}" for i in range(2, 8)) + ("pressMs0", "pressMs1", "pressMs2")


def check_talons(checks) -> None:
    """Every enemy in her front arc and reach takes both hits; one beside,
    behind or out of reach takes none. She swings with no target, a press
    inside the cooldown starts nothing, and Tosh has no swing."""
    for section, (hit, missed, swings, kerrigan) in SWING_CASES.items():
        print(f"{section} raw: " + " ".join(f"{key}={checks.value(section, '', key)}" for key in SWING_RAW))
        checks.eq(section, "", "heroType", "KerriganSCOBA" if kerrigan else "ToshSCOBA")
        checks.eq(section, "", "swings", swings)
        checks.eq(section, "", "damages", SWING_HITS * len(hit))
        for i in hit:
            life = [checks.value(section, "", f"life{n}_{i}") for n in (0, 1)]
            ok = None not in life and life[0] - life[1] == SWING_DAMAGE
            _report(checks, f"{section} enemy {i} takes the swing", ok, f"life={life} want -{SWING_DAMAGE}")
        for i in missed:
            life = [checks.value(section, "", f"life{n}_{i}") for n in (0, 1)]
            ok = None not in life and life[0] == life[1]
            _report(checks, f"{section} enemy {i} is not hit", ok, f"life={life}")
        # The enemies stood where the case put them: in the arc or clear of it.
        for i in hit + (() if section in SWING_REACH_CASES else missed):
            angle = checks.value(section, "", f"angle_{i}")
            off = None if angle is None else abs((angle + 540) % 360 - 180)
            ok = off is not None and (off <= SWING_HALF_ARC - SWING_ANGLE_MARGIN if i in hit else off >= SWING_HALF_ARC + SWING_ANGLE_MARGIN)
            _report(checks, f"{section} enemy {i} placed {'in' if i in hit else 'outside'} the arc", ok, f"angle={angle}")
        tps, aim = SWING_MODES.get(section, (True, False))
        checks.eq(section, "", "tps", tps)
        checks.eq(section, "", "aim", aim)
        if not kerrigan or swings == 0:
            continue
        checks.eq(section, "", "cd0Ms", 0)
        cd = checks.value(section, "", "cd1Ms")
        ok = cd is not None and SWING_COOLDOWN_MS - 200 <= cd <= SWING_COOLDOWN_MS
        _report(checks, f"{section} swing starts the attack cooldown", ok, f"cd={cd} want ~{SWING_COOLDOWN_MS}")
        checks.eq(section, "", "animState", checks.value(section, "", "attackState"))
        # Engine state: the attack bracket holds the Attack 01 copy (2 s).
        length = checks.value(section, "", "clipLenMs")
        ok = length is not None and abs(length - SWING_CLIP_MS) <= 50
        checks.eq(section, "", "pitchStep", 0)
        _report(checks, f"{section} engine plays the Attack 01 swing clip", ok, f"len={length} rem={checks.value(section, '', 'clipRemMs')} clip={checks.value(section, '', 'clipName')} want {SWING_CLIP_MS}")
        checks.eq(section, "", "weapons", 3)
        rate = checks.value(section, "", "rate100")
        _report(checks, f"{section} swing play rate", rate in SWING_RATE100, f"rate100={rate} want {SWING_RATE100}")
        checks.eq(section, "", "holdMs", SWING_HOLD_MS)
        if section in SWING_MULTI_PRESS:
            continue
        clip = [checks.value(section, "", key) for key in ("clipRemMs", "clipRem2Ms", "clipAtMs", "clipAt2Ms")]
        engine = None if None in clip or clip[3] <= clip[2] else (clip[0] - clip[1]) / (clip[3] - clip[2])
        ok = engine is not None and SWING_ENGINE_RATE[0] <= engine <= SWING_ENGINE_RATE[1]
        _report(checks, f"{section} engine plays the swing at 2x the old rate", ok, f"rem,rem2,at,at2={clip} rate={engine} want {SWING_ENGINE_RATE}")

