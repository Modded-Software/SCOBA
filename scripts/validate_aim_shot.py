"""Aim-shot checks for scripts/validate-map.py."""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from hitvolumes.galaxy import check_map as check_hit_volumes

GAMEDATA = Path("Base.SC2Data") / "GameData"
SYSTEMS = Path("scripts") / "app" / "systems"

ATTACK_COOLDOWN_LINK = "SCOBA/Attack"
STATUS_ABILITY = "SCOBAAutoAttackStatus"
HERO_WEAPONS = ("Tosh", "RazorTalons", "QueenOfBladesPsiBlast")
FRIENDLY_FIRE_BEHAVIOR = "SCOBAFriendlyFireBlock"

HERO_UNITS = ("ToshSCOBA", "KerriganSCOBA")

# The Tosh shot that ends in the air (R-TPS-62).
AIR_EFFECT = "SCOBAToshAirU"
AIR_SHOT = "SCOBAToshAirShot"
AIR_ACTOR = "SCOBAToshAirAttack"
# Tosh's button clock and its period. TESTING (operator 2026-11-16): 0.1 s;
# the release value is ("SCOBAAttackCooldown10", "1").
TOSH_CLOCK = ("SCOBAAttackCooldown01", "0.25")

# The aim shot runs the hero weapon's effect (R-TPS-1, R-TPS-3). The aim-shot
# abilities, their effects, and their actors are gone and must stay gone.
REMOVED_AIM_SHOT_IDS = (
    "SCOBAAimShot",
    "SCOBAToshShotPoint",
    "SCOBATalonsShot",
    "SCOBAPsiBlastLaunchPoint",
    "SCOBAToshPointAttack",
    "SCOBAPsiBlastPointAttack",
)

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

    weapons = {
        weapon.get("id"): weapon
        for weapon in ET.parse(gamedata / "WeaponData.xml").getroot().iter("CWeaponLegacy")
    }
    for weapon_id in HERO_WEAPONS:
        weapon = weapons.get(weapon_id)
        if weapon is None:
            fail(f"missing weapon override: {weapon_id}")
        check_link(weapon.find("Cost/Cooldown"), weapon_id)

    for name in ("AbilData.xml", "EffectData.xml", "ActorData.xml", "UnitData.xml"):
        text = read(gamedata / name)
        for removed in REMOVED_AIM_SHOT_IDS:
            if removed in text:
                fail(f"{name} still has the removed aim-shot data: {removed}")
    check_air_shot_data(gamedata)


def check_air_shot_data(gamedata: Path) -> None:
    """A shot that ends in the air launches like the weapon and has no hit."""
    effects = ET.parse(gamedata / "EffectData.xml").getroot()
    air = effects.find(f"CEffectDamage[@id='{AIR_EFFECT}']")
    if air is None or air.get("parent") != "ToshU":
        fail(f"{AIR_EFFECT} must be a CEffectDamage child of ToshU")
    amount = air.find("Amount")
    if amount is None or amount.get("value") != "0":
        fail(f"{AIR_EFFECT} must deal no damage")
    shot = effects.find(f"CEffectSet[@id='{AIR_SHOT}']")
    if shot is None:
        fail(f"missing effect set: {AIR_SHOT}")
    parts = [element.get("value") for element in shot.findall("EffectArray")]
    if parts != [AIR_EFFECT, TOSH_CLOCK[0]]:
        fail(f"{AIR_SHOT} must run {AIR_EFFECT} and the Tosh button clock, got {parts}")
    actors = ET.parse(gamedata / "ActorData.xml").getroot()
    actor = actors.find(f"CActorAction[@id='{AIR_ACTOR}']")
    if actor is None or actor.get("parent") != "GenericAttack" or actor.get("effectAttack") != AIR_EFFECT:
        fail(f"{AIR_ACTOR} must be a GenericAttack on {AIR_EFFECT}")
    launch = actor.find("LaunchAssets")
    if launch is None or launch.get("Model") != "ToshAttackLaunch" or launch.get("Sound") != "Tosh_AttackLaunch":
        fail(f"{AIR_ACTOR} must launch with the Tosh attack model and sound")
    impact = actor.find("ImpactMap[@index='None']")
    if impact is None or impact.get("Model") != "" or impact.get("Sound") != "":
        fail(f"{AIR_ACTOR} must have no impact model and no impact sound")


def check_aim_shot_script(map_dir: Path, combined: str) -> None:
    aim_text = read(map_dir / SYSTEMS / "aim_shooting.galaxy")
    handler_text = read(map_dir / SYSTEMS / "combat_cooldown.galaxy")
    unit_text = read(map_dir / GAMEDATA / "UnitData.xml")
    actor_text = read(map_dir / GAMEDATA / "ActorData.xml")
    for name in REMOVED_SHOOTER_NAMES + REMOVED_AIM_SHOT_IDS:
        if name in combined or name in unit_text or name in actor_text:
            fail(f"removed shooter design name still present: {name}")
    if (map_dir / SYSTEMS / "aim_shooter.galaxy").exists():
        fail("aim_shooter.galaxy must not exist")
    # The aim shot runs the weapon's effect once and holds no order, so it
    # cannot stop a walking hero (R-TPS-61).
    # Product scripts only: a test map also carries its harness.
    app_text = "\n".join(read(path) for path in sorted((map_dir / "scripts" / "app").rglob("*.galaxy")))
    if app_text.count("UnitCreateEffectUnit(") != 1 or "UnitCreateEffectUnit(lv_hero, lv_effect, lv_target);" not in aim_text:
        fail("the aim shot must run the weapon effect once, in aim_shooting.galaxy")
    if "UnitIssueOrder(" in aim_text or "gf_AttackOrder(" in aim_text:
        fail("aim shooting must not issue an order")
    if 'CatalogFieldValueGet(c_gameCatalogWeapon, lp_weapon, "Effect", lp_player)' not in aim_text:
        fail("the aim shot effect must be read from the weapon data")
    if app_text.count("UnitAddCooldown(") != 1 or '"Cost.Cooldown.TimeUse"' not in aim_text:
        fail("the aim shot must start the attack cooldown once, with the weapon's own cooldown time")
    if "c_TPS_PROXY_AIR_HEIGHT" not in aim_text or "c_SCOBA_SHOT_TOSH_AIR" not in aim_text:
        fail("a shot at the proxy in the air must run the air effect")
    for name in ("strafe.galaxy", "combat_fsm.galaxy"):
        if "gv_tpsShotKind" in read(map_dir / SYSTEMS / name):
            fail(f"{name} must not hold the hero for a pending aim shot")
    if "CameraLockInput(" in app_text:
        fail("the engine camera input must not be locked")
    if "gv_mOUSEMIDDLE[lp_player] = !gv_mOUSEMIDDLE[lp_player];" not in combined:
        fail("a TPS middle click must toggle the free-cursor state")
    # With mouse look off, a middle drag is the engine drag scroll. Its
    # scales are zero, so it cannot move the camera (R-TPS-37).
    camera = ET.parse(map_dir / GAMEDATA / "CameraData.xml").getroot().find("CCamera[@id='Dflt']")
    for field in ("ForwardScale", "StrafeScale"):
        for mode in ("Normal", "Follow"):
            scale = camera.find(f"{field}[@index='{mode}']")
            if scale is None or float(scale.get("value")) != 0.0:
                fail(f"camera {field} {mode} must be 0: the engine drag scroll must not move the camera")
    if "gf_AnimAttackStart" in aim_text or "gf_AnimAimAttackStart" in aim_text:
        fail("an aim press must not start the attack animation")
    if "gf_UnitTargetSet" in aim_text:
        fail("an aim click must not set the UI target")
    # Shot text comes from the fired weapon effect, never from the press.
    if combined.count("gf_UiFloaterShow(lp_player, lv_kind);") != 1 or "gf_TpsShotFired(lv_player" not in handler_text:
        fail("shot text must be created once, from the weapon effect event")
    behaviors = ET.parse(map_dir / GAMEDATA / "BehaviorData.xml").getroot()
    response = behaviors.find(f"CBehaviorBuff[@id='{FRIENDLY_FIRE_BEHAVIOR}']/DamageResponse")
    if response is None:
        fail(f"missing {FRIENDLY_FIRE_BEHAVIOR} damage response")
    wanted = {"Chance": "1", "Location": "Attacker", "ModifyFraction": "0", "TargetFilters": "-;Neutral,Enemy"}
    for key, value in wanted.items():
        if response.get(key) != value:
            fail(f"{FRIENDLY_FIRE_BEHAVIOR} DamageResponse {key} must be {value}")
    units = {unit.get("id"): unit for unit in ET.fromstring(unit_text).iter("CUnit")}
    for unit_id in HERO_UNITS:
        links = [element.get("Link") for element in units[unit_id].findall("BehaviorArray")]
        if FRIENDLY_FIRE_BEHAVIOR not in links:
            fail(f"{unit_id} missing BehaviorArray link: {FRIENDLY_FIRE_BEHAVIOR}")
    if "gt_CombatAttackEffect_Func" not in handler_text or "gf_AnimAttackStart" not in handler_text:
        fail("effect handler must start the attack animation")
    if "EventPlayerEffectUsedUnit(c_effectUnitCaster)" not in handler_text:
        fail("effect handler must read the effect caster")
    if combined.count("TriggerAddEventPlayerEffectUsed(gt_CombatAttackEffect") != 4:
        fail("effect handler must register the three hero weapon effects and the air shot")
    # The TPS pick uses the generated hit volumes, without a margin (R-TPS-84).
    for problem in check_hit_volumes(map_dir):
        fail(problem)
    if "c_unitPropRadius" in aim_text or "c_SCOBA_CLICK_MARGIN" in aim_text:
        fail("the TPS pick must use the hit volumes, not the unit radius and a margin")
    if "gf_HvRayUnit(" not in aim_text:
        fail("the TPS pick must test the ray against the hit volumes")
