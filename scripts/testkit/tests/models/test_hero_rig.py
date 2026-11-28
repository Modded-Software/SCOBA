"""Host tests for the hero rig bake helpers and their checks (operator
2026-11-22: Kerrigan's aim breathing, her own strafing; 2026-11-23: talons on F)."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as Part

from heroanim import breath
from heroanim.rig import FRAME_MS, HEROES
from heroanim.validate import MELEE_CONFIG, check_breath_script
from testkit.checks import Checks
from testkit.profiles.combat_parts import combat_kerrigan
from validate_aim_shot import check_aim_shot_data
from walkanim.strafe import subtree

ROOT = Path(__file__).resolve().parents[4]
MAP = ROOT / "src" / "SCOBA.SC2Map"
PSI = "QueenOfBladesPsiBlast"


class Failed(Exception):
    pass


def fail(message: str) -> None:
    raise Failed(message)


def galaxy() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in sorted((MAP / "scripts").rglob("*.galaxy")))


class BreathSamplingTest(unittest.TestCase):
    def test_loop_times_span_one_breath(self) -> None:
        times = breath.loop_times(4000)
        self.assertEqual(len(times), breath.BREATH_SAMPLES + 1)
        self.assertEqual((times[0], times[-1]), (0, 4000))
        self.assertEqual(times, sorted(set(times)))

    def test_swing_is_a_sine_about_the_pose_frame(self) -> None:
        quarter = breath.BREATH_SAMPLES // 4
        self.assertAlmostEqual(breath.source_ms(350.0, 4, 0), 350.0)
        self.assertAlmostEqual(breath.source_ms(350.0, 4, quarter), 350.0 + 4 * FRAME_MS)
        self.assertAlmostEqual(breath.source_ms(350.0, 4, 3 * quarter), 350.0 - 4 * FRAME_MS)

    def test_loop_closes_and_stays_inside_the_swing(self) -> None:
        self.assertAlmostEqual(breath.source_ms(350.0, 4, breath.BREATH_SAMPLES), breath.source_ms(350.0, 4, 0))
        for step in range(breath.BREATH_SAMPLES + 1):
            # Negative: never past the asked frames.
            self.assertLessEqual(abs(breath.source_ms(350.0, 4, step) - 350.0), 4 * FRAME_MS + 1e-9)


class RigTest(unittest.TestCase):
    def test_kerrigan_breathes_on_the_psi_blast_pose(self) -> None:
        rig = HEROES["kerrigan"]
        self.assertEqual((rig.aim_source, rig.breath_frames, rig.breath_ms), ("Spell", 4, 4000))
        self.assertEqual(rig.leg_roots, ("Dummy01", "Dummy02"))

    def test_kerrigan_swings_attack_01(self) -> None:
        # Operator 2026-11-23: the talons swing is Attack 01.
        self.assertEqual(HEROES["kerrigan"].melee_source, "Attack 01")
        self.assertEqual(HEROES["tosh"].melee_source, "")
        # Her back talons swing with it.
        self.assertEqual(HEROES["kerrigan"].melee_roots, ("Bone34", "Bone34(mirrored)"))
        self.assertTrue(set(HEROES["kerrigan"].melee_roots) <= set(HEROES["kerrigan"].lower_roots))

    def test_the_swing_clip_is_configured(self) -> None:
        text = galaxy()
        self.assertIn(MELEE_CONFIG, text)
        self.assertIn("const fixed c_ANIM_MELEE_CLIP_LENGTH = 2.0;", text)

    def test_tosh_is_unchanged(self) -> None:
        rig = HEROES["tosh"]
        self.assertEqual((rig.aim_source, rig.breath_frames, rig.breath_ms, rig.leg_roots), ("Attack", 0, 0, ()))

    def test_subtree_takes_the_roots_and_all_below(self) -> None:
        # Root > Pelvis > Thigh; Root > Link > FootRoot > Foot; Root > Spine.
        names = ["Root", "Pelvis", "Thigh", "Link", "FootRoot", "Foot", "Spine"]
        parents = [-1, 0, 1, 0, 3, 4, 0]
        model = Part(bones=[Part(name=name, parent=parent) for name, parent in zip(names, parents)])
        self.assertEqual(subtree(model, ("Pelvis", "FootRoot")), ["Pelvis", "Thigh", "FootRoot", "Foot"])
        # Negative: the spine and the link above the foot root are not legs.
        self.assertNotIn("Spine", subtree(model, ("Pelvis", "FootRoot")))
        self.assertNotIn("Link", subtree(model, ("Pelvis", "FootRoot")))


class BreathScriptTest(unittest.TestCase):
    def test_script_periods_match_the_rigs(self) -> None:
        self.assertIn("KERRIGAN", check_breath_script(galaxy(), fail))

    def test_a_different_period_is_refused(self) -> None:
        text = galaxy().replace("c_ANIM_BREATH_KERRIGAN = 4.0;", "c_ANIM_BREATH_KERRIGAN = 3.0;")
        with self.assertRaises(Failed):
            check_breath_script(text, fail)

    def test_a_play_without_sync_is_refused(self) -> None:
        text = galaxy().replace("gf_AnimAimBreathSync(lp_player, lv_hero);", "")
        with self.assertRaises(Failed):
            check_breath_script(text, fail)

    def test_both_pitch_clip_plays_sync(self) -> None:
        text = (MAP / "scripts" / "app" / "systems" / "animation_aim.galaxy").read_text(encoding="utf-8")
        play = "ActorSend(lv_actor, MakeMsgAnimPlay(c_ANIM_BRACKET_UPPER, lv_clip, c_animFlagPlayForever, 0.06, 0.06, c_animTimeDefault, c_animTimeVariantAsAutomatic));\n"
        self.assertEqual(text.count(play), 2)
        self.assertEqual(text.count(play + "    gf_AnimAimBreathSync(lp_player, lv_hero);\n"), 2)


class KerriganWeaponDataTest(unittest.TestCase):
    def _copy(self, old: str, new: str, name: str) -> Path:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root)
        shutil.copytree(MAP / "Base.SC2Data", root / "Base.SC2Data")
        shutil.copytree(MAP / "scripts", root / "scripts")
        path = root / "Base.SC2Data" / "GameData" / name
        text = path.read_text(encoding="utf-8")
        self.assertEqual(text.count(old), 1)
        path.write_text(text.replace(old, new), encoding="utf-8")
        return root

    def test_map_data_passes(self) -> None:
        check_aim_shot_data(MAP)

    def test_the_stock_talons_slot_is_refused(self) -> None:
        root = self._copy('<WeaponArray Link="RazorTalonsAuto"/>', '<WeaponArray Link="RazorTalons"/>', "UnitData.xml")
        with self.assertRaises(SystemExit):
            check_aim_shot_data(root)

    def test_a_missing_talons_twin_is_refused(self) -> None:
        root = self._copy('        <WeaponArray Link="RazorTalonsAuto"/>\n', "", "UnitData.xml")
        with self.assertRaises(SystemExit):
            check_aim_shot_data(root)

    def test_a_single_swing_hit_is_refused(self) -> None:
        root = self._copy('<PeriodCount value="2"/>\n        <PeriodicEffectArray value="RazorTalonsDamage"/>', '<PeriodCount value="1"/>\n        <PeriodicEffectArray value="RazorTalonsDamage"/>', "EffectData.xml")
        with self.assertRaises(SystemExit):
            check_aim_shot_data(root)

    def test_a_wide_swing_arc_is_refused(self) -> None:
        root = self._copy('<WeaponArray Link="RazorTalonsAuto"/>', '<WeaponArray Link="RazorTalonsAuto"/>', "UnitData.xml")
        path = root / "scripts" / "app" / "core" / "constants.galaxy"
        path.write_text(path.read_text(encoding="utf-8").replace("c_SCOBA_TALONS_ARC = 90.0;", "c_SCOBA_TALONS_ARC = 360.0;"), encoding="utf-8")
        with self.assertRaises(SystemExit):
            check_aim_shot_data(root)

    def test_a_point_impact_is_refused(self) -> None:
        launch = '<CEffectSet id="SCOBAPsiBlastShot">'
        root = self._copy(launch, '<CEffectLaunchMissile id="PsiBlastLaunchMissile"><ImpactLocation Value="TargetUnitOrPoint"/></CEffectLaunchMissile>\n    ' + launch, "EffectData.xml")
        with self.assertRaises(SystemExit):
            check_aim_shot_data(root)

    def test_a_launch_offset_is_refused(self) -> None:
        launch = '<CEffectSet id="SCOBAPsiBlastShot">'
        root = self._copy(launch, '<CEffectLaunchMissile id="PsiBlastLaunchMissile"><LaunchOffset value="0,0.5,0.87"/></CEffectLaunchMissile>\n    ' + launch, "EffectData.xml")
        with self.assertRaises(SystemExit):
            check_aim_shot_data(root)

    def test_a_launch_effect_in_the_missile_is_refused(self) -> None:
        launch = '<CEffectSet id="SCOBAPsiBlastShot">'
        root = self._copy(launch, '<CEffectLaunchMissile id="PsiBlastLaunchMissile"><LaunchEffect value="SCOBAAttackCooldown10"/></CEffectLaunchMissile>\n    ' + launch, "EffectData.xml")
        with self.assertRaises(SystemExit):
            check_aim_shot_data(root)

    def test_poison_nova_on_kerrigan_is_refused(self) -> None:
        slot = '<WeaponArray index="1" Link="QueenOfBladesPsiBlastAuto"/>'
        root = self._copy(slot, slot + '\n        <AbilArray Link="PoisonNova"/>', "UnitData.xml")
        with self.assertRaises(SystemExit):
            check_aim_shot_data(root)

    def test_a_minimum_range_is_refused(self) -> None:
        root = self._copy('<MinimumRange value="0"/>', '<MinimumRange value="2"/>', "WeaponData.xml")
        with self.assertRaises(SystemExit):
            check_aim_shot_data(root)

    def _script(self, root: Path, name: str, old: str, new: str) -> None:
        path = root / "scripts" / "app" / "systems" / name
        text = path.read_text(encoding="utf-8")
        self.assertEqual(text.count(old), 1)
        path.write_text(text.replace(old, new), encoding="utf-8")

    def test_f_on_the_order_key_is_refused(self) -> None:
        root = self._copy('<WeaponArray Link="RazorTalonsAuto"/>', '<WeaponArray Link="RazorTalonsAuto"/>', "UnitData.xml")
        key = "    TriggerAddEventKeyPressed(gt_OrderKey, c_playerAny, c_keyE,"
        self._script(root, "input.galaxy", key, key.replace("c_keyE", "c_keyF") + " c_keyModifierStateIgnore);\n" + key)
        with self.assertRaises(SystemExit):
            check_aim_shot_data(root)

    def test_a_kept_stock_talons_weapon_is_refused(self) -> None:
        root = self._copy('<WeaponArray Link="RazorTalonsAuto"/>', '<WeaponArray Link="RazorTalonsAuto"/>', "UnitData.xml")
        self._script(root, "hero_return.galaxy", "UnitWeaponRemove(lp_hero, c_SCOBA_WEAPON_TALONS);", "")
        with self.assertRaises(SystemExit):
            check_aim_shot_data(root)


def weapon_rows(talons: tuple[int, int] = (4, 4), psi: tuple[int, int] = (0, 3), third: str = "RazorTalonsAuto", count: int = 3, nova: bool = False) -> dict:
    rows = {}
    for tag, shots, cuts in zip(("w0", "w1"), psi, talons):
        rows.update({tag + "Type": "KerriganSCOBA", tag + "Weapons": count, tag + "Weapon1": PSI, tag + "Weapon2": PSI + "Auto", tag + "Weapon3": third, tag + "MinRange1000": 0, tag + "Nova": nova, tag + "PsiFx": shots, tag + "TalonsFx": cuts})
    return {"s": rows}


def swing_rows(**change) -> dict:
    """Every swing section healthy; `change` maps section to changed keys."""
    data = {}
    for section, (hit, missed, swings, kerrigan) in combat_kerrigan.SWING_CASES.items():
        tps, aim = combat_kerrigan.SWING_MODES.get(section, (True, False))
        row = {"tps": tps, "aim": aim, "heroType": "KerriganSCOBA" if kerrigan else "ToshSCOBA", "swings": swings, "damages": 2 * len(hit), "cd0Ms": 0, "cd1Ms": 1000, "animState": 5, "attackState": 5, "weapons": 3, "clipLenMs": 2000, "pitchStep": 0, "rate100": 266, "holdMs": 750, "clipRemMs": 1700, "clipRem2Ms": 700, "clipAtMs": 1000, "clipAt2Ms": 1500}
        for i in hit:
            row.update({f"life0_{i}": 500, f"life1_{i}": 450, f"angle_{i}": 22 - 45 * (i % 2)})
        for i in missed:
            row.update({f"life0_{i}": 500, f"life1_{i}": 500, f"angle_{i}": 0 if section in combat_kerrigan.SWING_REACH_CASES else 180})
        row.update(change.get(section, {}))
        data[section] = row
    return data


def breath_rows(shift: int = 0, tosh_syncs: int = 0, still_sync: int = 0) -> dict:
    """`shift`: ms the engine's clip is off the game clock."""
    rows = {"type": "KerriganSCOBA", "t0AimUpper": True}
    plan = {"tpre": (0, 0, 0, 0), "t0": (1, 1, 40, 500), "t1": (9, 9, 20, 1800), "t2": (20, 20, 60, 3100), "t3": (20 + still_sync, 20, 60, 100)}
    for tag, (syncs, sends, step, clock) in plan.items():
        rows.update({tag + "Syncs": syncs, tag + "Sends": sends, tag + "Step": step, tag + "PhaseMs": clock, tag + "ClockMs": clock, tag + "LenMs": 4000, tag + "RemMs": (4000 - clock - shift) % 4000})
    tosh = {"type": "ToshSCOBA", "tpreSends": 0, "t2Sends": 12, "tpreSyncs": 0, "t3Syncs": tosh_syncs}
    return {"breath_kerrigan": rows, "breath_tosh": tosh}


def psi_rows(far: int | None = None, damages: int = 1, loss: int = 25, missile_loops: int = 5, hits: str = "25.0:PsiBlastDamage:KerriganSCOBA ", nova: bool = False, location: str = "TargetUnit", direct_launches: int = 0, missile_actor: bool = True) -> dict:
    """Every probe section healthy, unless an argument breaks all of them."""
    data = {}
    for section, dist in (("psi_fx_02", 200), ("psi_fx_03", 300), ("psi_fx_035", 350), ("psi_fx_04", 400), ("psi_fx_08", 800), ("psi_order_04", 400), ("psi_order_08", 800), ("psi_fx_proxy", 600), ("psi_aim", 900)):
        proxy = section in combat_kerrigan.PSI_PROXY
        data[section] = {"missileActorValid": missile_actor, "attackActorValid": True, "missileModelValid": True, "impactModelValid": True, "heroType": "KerriganSCOBA", "lmImpactLocation": location, "novaExists": nova, "hits": hits, "targetDist100": dist, "targetZ100": 200 if proxy else 0, "launches": 1, "missileLoops": missile_loops, "missileFar100": dist - 40 if far is None else far, "missilesMade": 1, "missileLastLoop": 6, "damages": damages, "damageOnTarget": damages > 0, "damageDelayMs": 400, "damageFromTarget100": 20 if damages else None, "damageFromHero100": dist - 20, "talons0": 0, "talons1": 0, "life0": 1000 if proxy else 500, "life1": 1000 if proxy else 500 - loss, "loop00": "1 d30 z80 a1 fx1 dmg0"}
    data["psi_direct_04"] = {"damages": damages, "damageOnTarget": damages > 0, "launches": direct_launches, "missileLoops": 0, "life0": 500, "life1": 500 - loss}
    return data


class KerriganProfileTest(unittest.TestCase):
    def test_psi_probe_healthy_passes(self) -> None:
        checks = Checks(psi_rows())
        combat_kerrigan.check_psi_probe(checks)
        self.assertEqual(checks.failures, 0)

    def test_psi_probe_missile_that_stays_at_the_hero_fails(self) -> None:
        checks = Checks(psi_rows(far=20))
        combat_kerrigan.check_psi_probe(checks)
        self.assertGreater(checks.failures, 0)

    def test_psi_probe_no_missile_fails(self) -> None:
        checks = Checks(psi_rows(missile_loops=0))
        combat_kerrigan.check_psi_probe(checks)
        self.assertGreater(checks.failures, 0)

    def test_psi_probe_nova_damage_fails(self) -> None:
        checks = Checks(psi_rows(hits="20.0:PoisonNovaDirectDamage:KerriganSCOBA "))
        combat_kerrigan.check_psi_probe(checks)
        self.assertEqual(checks.failures, len(combat_kerrigan.PSI_ENEMY + combat_kerrigan.PSI_PROXY))

    def test_psi_probe_a_nova_ability_fails(self) -> None:
        checks = Checks(psi_rows(nova=True))
        combat_kerrigan.check_psi_probe(checks)
        self.assertEqual(checks.failures, len(combat_kerrigan.PSI_ENEMY + combat_kerrigan.PSI_PROXY))

    def test_psi_probe_a_point_impact_fails(self) -> None:
        checks = Checks(psi_rows(location="TargetUnitOrPoint"))
        combat_kerrigan.check_psi_probe(checks)
        self.assertEqual(checks.failures, len(combat_kerrigan.PSI_ENEMY + combat_kerrigan.PSI_PROXY))

    def test_psi_probe_a_missing_missile_actor_fails(self) -> None:
        checks = Checks(psi_rows(missile_actor=False))
        combat_kerrigan.check_psi_probe(checks)
        self.assertEqual(checks.failures, 1)

    def test_psi_probe_direct_damage_that_launches_fails(self) -> None:
        checks = Checks(psi_rows(direct_launches=1))
        combat_kerrigan.check_psi_probe(checks)
        self.assertEqual(checks.failures, 1)

    def test_psi_probe_no_damage_fails(self) -> None:
        checks = Checks(psi_rows(damages=0, loss=0))
        combat_kerrigan.check_psi_probe(checks)
        self.assertGreater(checks.failures, 0)

    def test_single_weapons_pass(self) -> None:
        checks = Checks(weapon_rows())
        combat_kerrigan.check_weapons(checks, "s", 3)
        self.assertEqual(checks.failures, 0)

    def test_auto_with_talons_passes(self) -> None:
        checks = Checks(weapon_rows(talons=(4, 6), psi=(0, 0)))
        combat_kerrigan.check_weapons(checks, "s", 0, auto=True)
        self.assertEqual(checks.failures, 0)

    def test_auto_without_talons_fails(self) -> None:
        checks = Checks(weapon_rows(psi=(0, 2)))
        combat_kerrigan.check_weapons(checks, "s", 0, auto=True)
        self.assertEqual(checks.failures, 1)

    def test_the_stock_talons_weapon_fails(self) -> None:
        checks = Checks(weapon_rows(third="RazorTalons", count=4))
        combat_kerrigan.check_weapons(checks, "s", 3)
        self.assertEqual(checks.failures, 4)

    def test_swings_healthy_pass(self) -> None:
        checks = Checks(swing_rows())
        combat_kerrigan.check_talons(checks)
        self.assertEqual(checks.failures, 0)

    def test_a_hit_behind_her_fails(self) -> None:
        checks = Checks(swing_rows(talons_back={"damages": 2, "life1_0": 450}))
        combat_kerrigan.check_talons(checks)
        self.assertEqual(checks.failures, 2)

    def test_a_hit_beside_her_fails(self) -> None:
        checks = Checks(swing_rows(talons_side={"damages": 2, "life1_1": 450}))
        combat_kerrigan.check_talons(checks)
        self.assertEqual(checks.failures, 2)

    def test_no_swing_without_a_target_fails(self) -> None:
        checks = Checks(swing_rows(talons_empty={"swings": 0, "cd1Ms": 0}))
        combat_kerrigan.check_talons(checks)
        self.assertEqual(checks.failures, 2)

    def test_a_swing_inside_the_cooldown_fails(self) -> None:
        checks = Checks(swing_rows(talons_cd={"swings": 2, "damages": 4, "life1_0": 400}))
        combat_kerrigan.check_talons(checks)
        self.assertEqual(checks.failures, 3)

    def test_the_old_swing_speed_fails(self) -> None:
        checks = Checks(swing_rows(talons_front={"rate100": 133, "holdMs": 1500, "clipRem2Ms": 1200}))
        combat_kerrigan.check_talons(checks)
        self.assertEqual(checks.failures, 3)

    def test_the_old_cooldown_fails(self) -> None:
        checks = Checks(swing_rows(talons_front={"cd1Ms": 1500}))
        combat_kerrigan.check_talons(checks)
        self.assertEqual(checks.failures, 1)

    def test_a_swing_while_aiming_fails(self) -> None:
        checks = Checks(swing_rows(talons_click_aim={"swings": 1}))
        combat_kerrigan.check_talons(checks)
        self.assertEqual(checks.failures, 1)

    def test_a_swing_in_pnc_fails(self) -> None:
        checks = Checks(swing_rows(talons_click_pnc={"swings": 1, "damages": 2, "life1_0": 450}))
        combat_kerrigan.check_talons(checks)
        self.assertEqual(checks.failures, 3)

    def test_a_swing_on_tosh_fails(self) -> None:
        checks = Checks(swing_rows(talons_tosh={"swings": 1}))
        combat_kerrigan.check_talons(checks)
        self.assertEqual(checks.failures, 1)

    def test_the_default_attack_clip_fails(self) -> None:
        checks = Checks(swing_rows(talons_front={"clipLenMs": 1000}))
        combat_kerrigan.check_talons(checks)
        self.assertEqual(checks.failures, 1)

    def test_the_cast_pose_over_the_swing_fails(self) -> None:
        checks = Checks(swing_rows(talons_front={"pitchStep": 40}))
        combat_kerrigan.check_talons(checks)
        self.assertEqual(checks.failures, 1)

    def test_an_enemy_moved_into_the_arc_fails(self) -> None:
        checks = Checks(swing_rows(talons_side={"angle_0": 30}))
        combat_kerrigan.check_talons(checks)
        self.assertEqual(checks.failures, 1)

    def test_one_hit_instead_of_two_fails(self) -> None:
        checks = Checks(swing_rows(talons_front={"damages": 1, "life1_0": 475}))
        combat_kerrigan.check_talons(checks)
        self.assertEqual(checks.failures, 2)

    def test_a_nova_ability_on_the_unit_fails(self) -> None:
        checks = Checks(weapon_rows(nova=True))
        combat_kerrigan.check_weapons(checks, "s", 3)
        self.assertEqual(checks.failures, 2)

    def test_a_talons_effect_in_single_fails(self) -> None:
        checks = Checks(weapon_rows(talons=(4, 5)))
        combat_kerrigan.check_weapons(checks, "s", 3)
        self.assertEqual(checks.failures, 1)

    def test_too_few_psi_blast_effects_fail(self) -> None:
        checks = Checks(weapon_rows(psi=(0, 2)))
        combat_kerrigan.check_weapons(checks, "s", 3)
        self.assertGreater(checks.failures, 0)

    def test_breath_in_step_passes(self) -> None:
        checks = Checks(breath_rows())
        combat_kerrigan.check_breath(checks)
        self.assertEqual(checks.failures, 0)

    def test_breath_restarted_by_a_pitch_step_fails(self) -> None:
        checks = Checks(breath_rows(shift=1500))
        combat_kerrigan.check_breath(checks)
        self.assertGreater(checks.failures, 0)

    def test_a_sync_on_tosh_fails(self) -> None:
        checks = Checks(breath_rows(tosh_syncs=3))
        combat_kerrigan.check_breath(checks)
        self.assertGreater(checks.failures, 0)

    def test_a_sync_under_a_still_camera_fails(self) -> None:
        checks = Checks(breath_rows(still_sync=1))
        combat_kerrigan.check_breath(checks)
        self.assertGreater(checks.failures, 0)


if __name__ == "__main__":
    unittest.main()
