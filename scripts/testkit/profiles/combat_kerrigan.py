"""Kerrigan checks of the combat group `kerrigan` (operator 2026-11-22).

Psi Blast is her only attack: the engine holds no talons weapon on her, the
shots are Psi Blast effects at any distance, and no talons effect runs.
Her aim pose breathes (R-TPS-19): every pitch clip play is followed by one
breath sync, and the engine's clip stands at the game clock's place in the
breath. Tosh's aim pose is still: no sync.
"""

from __future__ import annotations


from heroanim.rig import HEROES

from .bank_checks import _report

PSI = "QueenOfBladesPsiBlast"
BREATH_MS = HEROES["kerrigan"].breath_ms
# The clip position is read some game loops after the clock (query wait).
PHASE_TOL_MS = 400


def check_weapons(checks, section: str, shots: int) -> None:
    """`shots`: the Psi Blast effects the scenario must add, at least."""
    for tag in ("w0", "w1"):
        checks.eq(section, tag, "Type", "KerriganSCOBA")
        checks.eq(section, tag, "Weapons", 2)
        checks.eq(section, tag, "Weapon1", PSI)
        checks.eq(section, tag, "Weapon2", PSI + "Auto")
        checks.eq(section, tag, "Weapon3", "")
        checks.eq(section, tag, "MinRange1000", 0)
        # Negative (R-TPS-65): the engine holds no Poison Nova on her.
        checks.false(section, tag, "Nova")
    psi = [checks.value(section, tag, "PsiFx") for tag in ("w0", "w1")]
    talons = [checks.value(section, tag, "TalonsFx") for tag in ("w0", "w1")]
    ok = None not in psi and psi[1] - psi[0] >= shots
    _report(checks, f"{section} shots are Psi Blast effects", ok, f"psi={psi} want +{shots}")
    # Negative: no talons effect, in the whole run so far.
    ok = None not in talons and talons[1] == 0
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
