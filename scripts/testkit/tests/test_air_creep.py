"""Host checks for the air creep data and profile (REQ-AIR-CREEP).

The actor scale has no engine getter; this test reads it from the data.
"""

from __future__ import annotations

import re
import unittest
import xml.etree.ElementTree as ET

from project_root import project_root
from testkit.profiles.registry import PROFILE_BANKS, PROFILE_OUTPUTS, profile_module

ROOT = project_root()
DATA = ROOT / "src" / "SCOBA.SC2Map" / "Base.SC2Data" / "GameData"
MODULE = ROOT / "src" / "SCOBA.SC2Map" / "scripts" / "app" / "systems" / "air_creep.galaxy"
AIR_ONLY = "Air,User1,Visible;"
UNITS = {"SCOBAMutalisk": ("Mutalisk", "SCOBAAirGlaive"), "SCOBAWraith": ("MengskWraith", "SCOBAWraithA")}
# Stock values the SCOBA data multiplies (sc2data extract, 2026-11-17):
# speed and acceleration (void.sc2mod Mutalisk, swarm.sc2campaign
# MengskWraith); weapon range and scan range (liberty GlaiveWurm Range 3; the
# rest are the Core CWeapon defaults, 5).
STOCK_MOVE = {"SCOBAMutalisk": (4.0, 3.5), "SCOBAWraith": (3.75, 2.625)}
STOCK_RANGE = {"SCOBAAirGlaive": (3.0, 5.0), "SCOBAWraithA": (5.0, 5.0)}
# Wraith 2x then 3x (operator 2026-11-17); ranges 5x then 4x. Mutalisk 2x
# then 1.5x (operator 2026-11-17).
SPEED_FACTOR = {"SCOBAMutalisk": 3.0, "SCOBAWraith": 6.0}
# Range and scan range. Glaive 20x stock (3 and 5). Wraith 60 and 60, the
# glaive range (operator 2026-11-17: down from 20x, 100).
WEAPON_RANGE = {"SCOBAAirGlaive": (60.0, 100.0), "SCOBAWraithA": (60.0, 60.0)}


def entries(catalog: str, tag: str) -> dict[str, ET.Element]:
    root = ET.parse(DATA / catalog).getroot()
    return {el.get("id"): el for el in root.iter(tag)}


def value(el: ET.Element, tag: str, **attrs: str) -> str | None:
    for child in el.iter(tag):
        if all(child.get(k) == v for k, v in attrs.items()):
            return child.get("value")
    return None


class AirCreepDataTest(unittest.TestCase):
    def test_units(self) -> None:
        units = entries("UnitData.xml", "CUnit")
        for name, (parent, weapon) in UNITS.items():
            unit = units[name]
            self.assertEqual(unit.get("parent"), parent)
            self.assertEqual(value(unit, "Height"), "72")
            self.assertEqual(value(unit, "Attributes", index="User1"), "1")
            links = [(w.get("index"), w.get("Link"), w.get("removed")) for w in unit.iter("WeaponArray")]
            self.assertEqual(links, [(None, weapon, None)])

    def test_speed(self) -> None:
        units = entries("UnitData.xml", "CUnit")
        for name, (speed, accel) in STOCK_MOVE.items():
            self.assertEqual(float(value(units[name], "Speed")), SPEED_FACTOR[name] * speed)
            self.assertEqual(float(value(units[name], "Acceleration")), SPEED_FACTOR[name] * accel)

    def test_range_and_sight(self) -> None:
        weapons = entries("WeaponData.xml", "CWeaponLegacy")
        units = entries("UnitData.xml", "CUnit")
        glaive_stock = STOCK_RANGE["SCOBAAirGlaive"]
        self.assertEqual(WEAPON_RANGE["SCOBAAirGlaive"], (20.0 * glaive_stock[0], 20.0 * glaive_stock[1]))
        for name, (_parent, weapon) in UNITS.items():
            rng, scan = WEAPON_RANGE[weapon]
            self.assertEqual(float(value(weapons[weapon], "Range")), rng)
            self.assertEqual(float(value(weapons[weapon], "MinScanRange")), scan)
            # The targets must be visible (filter Visible): sight covers the range.
            self.assertGreaterEqual(float(value(units[name], "Sight")), rng)
        # Negative: the Wraith no longer outranges the Mutalisk.
        self.assertLessEqual(WEAPON_RANGE["SCOBAWraithA"][0], WEAPON_RANGE["SCOBAAirGlaive"][0])

    def test_wraith_missile_2x(self) -> None:
        # The map's MissileDefault speed; the Wraith mover doubles it.
        movers = entries("MoverData.xml", "CMoverMissile")
        base = float(value(movers["MissileDefault"], "MaxSpeed"))
        wraith = movers["SCOBAWraithMissile"]
        self.assertEqual(wraith.get("parent"), "MissileDefault")
        self.assertEqual(float(value(wraith, "MaxSpeed")), 2.0 * base)
        units = entries("UnitData.xml", "CUnit")
        for ammo in ("MengskWraithAirWeaponLeft", "MengskWraithAirWeaponRight"):
            self.assertEqual(value(units[ammo], "Mover"), "SCOBAWraithMissile")
        # Negative: the shared default is not changed for every missile.
        self.assertEqual(base, 24.0)

    def test_stock_weapons_removed_on_create(self) -> None:
        # A data child keeps its parent's weapons (aircreep/20261117-164529),
        # so the module removes them; the in-game wave group checks the result.
        text = MODULE.read_text(encoding="utf-8")
        for weapon in ("GlaiveWurm", "MengskWraithA", "MengskWraithG"):
            self.assertIn(f'UnitWeaponRemove(lv_unit, "{weapon}");', text)

    def test_actors_scale_5(self) -> None:
        actors = entries("ActorData.xml", "CActorUnit")
        for name, (model, _weapon) in UNITS.items():
            actor = actors[name]
            self.assertEqual(actor.get("unitName"), name)
            self.assertEqual(float(value(actor, "Scale")), 5.0)
            # A concrete actor as parent is not created (validate_pod_actor).
            self.assertIn(actor.get("parent"), ("GenericUnitStandard", "GenericUnitBase"))
        self.assertEqual(value(actors["SCOBAMutalisk"], "Model"), "Mutalisk")
        self.assertEqual(value(actors["SCOBAWraith"], "Model"), "MengskWraith")

    def test_weapons_hit_air_creeps_only(self) -> None:
        weapons = entries("WeaponData.xml", "CWeaponLegacy")
        for _name, (_parent, weapon) in UNITS.items():
            filters = value(weapons[weapon], "TargetFilters")
            self.assertTrue(filters.startswith(AIR_ONLY), filters)
            # Negative: no ground target.
            self.assertNotIn("Ground", filters.split(";")[0])

    def test_glaive_bounces_hit_air_creeps_only(self) -> None:
        effects = entries("EffectData.xml", "CEffectEnumArea")
        for name in ("GlaiveWurmE1", "GlaiveWurmE2"):
            filters = value(effects[name], "SearchFilters")
            self.assertTrue(filters.startswith(AIR_ONLY), filters)
            self.assertIn("Ally", filters.split(";")[1])

    def test_schedule_constants(self) -> None:
        text = MODULE.read_text(encoding="utf-8")
        consts = dict(re.findall(r"const \w+ (c_AIR_CREEP_\w+) = ([^;]+);", text))
        self.assertEqual(consts["c_AIR_CREEP_PHASE"], "10.0")
        self.assertEqual(consts["c_AIR_CREEP_TERRAN_PER_DIR"], "3")
        self.assertEqual(consts["c_AIR_CREEP_ZERG_MIN_PER_DIR"], "4")
        self.assertEqual(consts["c_AIR_CREEP_ZERG_MAX_PER_DIR"], "6")
        self.assertEqual(consts["c_AIR_CREEP_MAX_PER_DIR"], "8")
        self.assertEqual(consts["c_AIR_CREEP_MAX_PER_WAVE"], "16")
        self.assertEqual(consts["c_AIR_CREEP_CAP"], "32")
        # Formation slots fit inside an X region (radius 16 on the built map).
        self.assertLessEqual(float(consts["c_AIR_CREEP_X_INNER"]) + float(consts["c_AIR_CREEP_SPACING"]), 16.0)
        self.assertIn("TimerStart(gv_airCreepTimer, c_AIR_CREEP_PHASE, true, c_timeReal)", text)

    def test_balance_read_before_spawn(self) -> None:
        # R-AIR-16: one step per formation (2 per wave), read once per wave
        # before the first unit is made; only air creeps count.
        text = MODULE.read_text(encoding="utf-8")
        consts = dict(re.findall(r"const \w+ (c_AIR_CREEP_\w+) = ([^;]+);", text))
        self.assertEqual(consts["c_AIR_CREEP_BALANCE_STEP"], "1")
        wave = text[text.index("int gf_AirCreepWave (int lp_side)"):text.index("bool gt_AirCreepStart_Func")]
        self.assertEqual(wave.count("gf_AirCreepBalance(lp_side)"), 1)
        self.assertLess(wave.index("gf_AirCreepBalance(lp_side)"), wave.index("gf_AirCreepFormation("))
        bal = text[text.index("int gf_AirCreepBalance (int lp_side)"):text.index("int gf_AirCreepBalanced")]
        self.assertIn("gf_AirCreepAlive(lp_side)", bal)
        self.assertIn("gf_AirCreepAlive(1 - lp_side)", bal)
        # Every balanced formation size stays inside 1..slot count, so the
        # clamp in gf_AirCreepBalanced never cuts the +-1.
        step = int(consts["c_AIR_CREEP_BALANCE_STEP"])
        smallest = min(int(consts["c_AIR_CREEP_TERRAN_PER_DIR"]), int(consts["c_AIR_CREEP_ZERG_MIN_PER_DIR"]))
        largest = max(int(consts["c_AIR_CREEP_TERRAN_PER_DIR"]), int(consts["c_AIR_CREEP_ZERG_MAX_PER_DIR"]))
        self.assertGreaterEqual(smallest - step, 1)
        self.assertLessEqual(largest + step, int(consts["c_AIR_CREEP_MAX_PER_DIR"]))

    def test_first_slot_zerg_after_one_phase(self) -> None:
        # Map start only arms the timer: the first slot (10 s) is Zerg, the
        # next (20 s) Terran. The in-game timer group checks the times.
        text = MODULE.read_text(encoding="utf-8")
        start = text[text.index("bool gt_AirCreepStart_Func"):text.index("bool gt_AirCreepTick_Func")]
        self.assertIn("gv_airCreepNextSide = c_AIR_CREEP_ZERG;", start)
        self.assertIn("TimerStart(gv_airCreepTimer, c_AIR_CREEP_PHASE, true, c_timeReal)", start)
        # Negative: no wave of either side at map start.
        self.assertNotIn("gf_AirCreepWave", start)


class AirCreepProfileTest(unittest.TestCase):
    def test_map_spec_matches_registry(self) -> None:
        spec = profile_module("aircreep").map_spec()
        self.assertEqual(spec.profile, "aircreep")
        self.assertEqual(spec.output, PROFILE_OUTPUTS["aircreep"])
        self.assertEqual(spec.bank_names, PROFILE_BANKS["aircreep"])


if __name__ == "__main__":
    unittest.main()
