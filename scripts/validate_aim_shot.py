"""Aim-shot checks for scripts/validate-map.py."""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

GAMEDATA = Path("Base.SC2Data") / "GameData"
SYSTEMS = Path("scripts") / "app" / "systems"

ATTACK_COOLDOWN_LINK = "SCOBA/Attack"
STATUS_ABILITY = "SCOBAAutoAttackStatus"
HERO_WEAPONS = ("Tosh", "RazorTalons", "QueenOfBladesPsiBlast")

# Aim-shot ability -> (effect, cooldown TimeUse).
AIM_SHOT_ABILITIES = {
    "SCOBAAimShotTosh": ("ToshU", 1.0),
    "SCOBAAimShotToshPoint": ("SCOBAToshShotPoint", 1.0),
    "SCOBAAimShotTalons": ("SCOBATalonsShot", 1.5),
    "SCOBAAimShotPsiBlast": ("PsiBlastLaunchMissile", 1.0),
    "SCOBAAimShotPsiBlastPoint": ("SCOBAPsiBlastLaunchPoint", 1.0),
}

AIM_SHOT_UNITS = {
    "ToshSCOBA": ("SCOBAAimShotTosh", "SCOBAAimShotToshPoint"),
    "KerriganSCOBA": ("SCOBAAimShotTalons", "SCOBAAimShotPsiBlast", "SCOBAAimShotPsiBlastPoint"),
}

AIM_SHOT_EFFECTS = ("SCOBAToshShotPoint", "SCOBATalonsShot", "SCOBAPsiBlastLaunchPoint")

AIM_SHOT_ACTORS = ("SCOBAToshPointAttack", "SCOBAPsiBlastPointAttack")

REMOVED_SHOOTER_NAMES = (
    "SCOBAAimShooter",
    "SCOBAAimShotDummy",
    "gf_AimShooter",
    "gf_AimShotProxy",
    "gv_aimShooter",
    "gv_aimShotPending",
    "gv_aimShotProxy",
    "gf_WeaponReady",
    "gf_CombatCooldownStart",
    "gf_CombatCooldownClear",
    "UnitWeaponSetPeriodRemaining",
    "UnitAbilityAddCooldown",
    "UnitAbilityReset",
    "libNtve_gf_UnitAbilityRemoveCooldown",
    "TriggerAddEventUnitStartedAttack2",
)


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def check_link(cooldown: ET.Element | None, owner: str) -> ET.Element:
    if cooldown is None:
        fail(f"{owner} missing Cost/Cooldown")
    if cooldown.get("Location") != "Unit" or cooldown.get("Link") != ATTACK_COOLDOWN_LINK:
        fail(f"{owner} cooldown must use the unit attack link")
    return cooldown


def check_aim_shot_data(map_dir: Path) -> None:
    gamedata = map_dir / GAMEDATA
    abilities = {
        ability.get("id"): ability
        for ability in ET.parse(gamedata / "AbilData.xml").getroot().iter("CAbilEffectTarget")
    }
    status = abilities.get(STATUS_ABILITY)
    if status is None:
        fail(f"{STATUS_ABILITY} must be CAbilEffectTarget")
    # The button shows its own ability cooldown. Weapon effects set it.
    button = status.find("Cost/Cooldown")
    if button is None:
        fail(f"{STATUS_ABILITY} missing Cost/Cooldown")
    if button.get("Location") != "Ability" or button.get("Link") != f"Abil/{STATUS_ABILITY}":
        fail(f"{STATUS_ABILITY} cooldown must be its own ability cooldown")
    if button.get("TimeUse") != "1":
        fail(f"{STATUS_ABILITY} cooldown TimeUse must be 1")
    for ability_id, (effect_id, period) in AIM_SHOT_ABILITIES.items():
        ability = abilities.get(ability_id)
        if ability is None:
            fail(f"missing aim-shot ability: {ability_id}")
        effect = ability.find("Effect")
        if effect is None or effect.get("value") != effect_id:
            fail(f"{ability_id} effect must be {effect_id}")
        transient = ability.find("Flags[@index='Transient']")
        if transient is None or transient.get("value") != "1":
            fail(f"{ability_id} must be Transient")
        cooldown = check_link(ability.find("Cost/Cooldown"), ability_id)
        if float(cooldown.get("TimeUse", "0")) != period:
            fail(f"{ability_id} cooldown TimeUse must be {period}")

    weapons = {
        weapon.get("id"): weapon
        for weapon in ET.parse(gamedata / "WeaponData.xml").getroot().iter("CWeaponLegacy")
    }
    for weapon_id in HERO_WEAPONS:
        weapon = weapons.get(weapon_id)
        if weapon is None:
            fail(f"missing weapon override: {weapon_id}")
        check_link(weapon.find("Cost/Cooldown"), weapon_id)

    units = {unit.get("id"): unit for unit in ET.parse(gamedata / "UnitData.xml").getroot().iter("CUnit")}
    for unit_id, wanted in AIM_SHOT_UNITS.items():
        unit = units.get(unit_id)
        if unit is None:
            fail(f"missing unit: {unit_id}")
        links = [element.get("Link") for element in unit.findall("AbilArray")]
        for ability_id in wanted:
            if ability_id not in links:
                fail(f"{unit_id} missing AbilArray link: {ability_id}")

    effect_text = read(gamedata / "EffectData.xml")
    for effect_id in AIM_SHOT_EFFECTS:
        if f'id="{effect_id}"' not in effect_text:
            fail(f"missing aim-shot effect: {effect_id}")
    actor_text = read(gamedata / "ActorData.xml")
    for actor_id in AIM_SHOT_ACTORS:
        if f'id="{actor_id}"' not in actor_text:
            fail(f"missing aim-shot actor: {actor_id}")


def check_aim_shot_script(map_dir: Path, combined: str) -> None:
    aim_text = read(map_dir / SYSTEMS / "aim_shooting.galaxy")
    handler_text = read(map_dir / SYSTEMS / "combat_cooldown.galaxy")
    unit_text = read(map_dir / GAMEDATA / "UnitData.xml")
    actor_text = read(map_dir / GAMEDATA / "ActorData.xml")
    for name in REMOVED_SHOOTER_NAMES:
        if name in combined or name in unit_text or name in actor_text:
            fail(f"removed shooter design name still present: {name}")
    if (map_dir / SYSTEMS / "aim_shooter.galaxy").exists():
        fail("aim_shooter.galaxy must not exist")
    if "gf_AimShotFireUnit" not in aim_text or "gf_AimShotFirePoint" not in aim_text:
        fail("scripts missing aim shot order functions")
    if 'AbilityCommand("attack"' in aim_text:
        fail("aim shots must not issue attack orders")
    if "gf_AnimAttackStart" in aim_text or "gf_AnimAimAttackStart" in aim_text:
        fail("an aim press must not start the attack animation")
    if aim_text.count("UnitIssueOrder(") != 2:
        fail("aim shooting must issue exactly one unit order and one point order")
    if "if (gf_AimShotFirePoint(lp_player, lv_point))" not in aim_text:
        fail("Miss floater must depend on the accepted point order")
    if "gt_CombatAttackEffect_Func" not in handler_text or "gf_AnimAttackStart" not in handler_text:
        fail("effect handler must start the attack animation")
    if "EventPlayerEffectUsedUnit(c_effectUnitCaster)" not in handler_text:
        fail("effect handler must read the effect caster")
    if combined.count("TriggerAddEventPlayerEffectUsed(gt_CombatAttackEffect") != 6:
        fail("effect handler must register the six weapon effects")
