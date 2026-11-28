from __future__ import annotations

import re
import unittest
from pathlib import Path

from character_anim_assets import AIM_DIRECTIONS
from character_anim_assets import (
    HEAD_TILT_GROUP,
    HEAD_TILT_MAX_DEG,
    HEAD_TILT_PRIORITY,
    HEAD_TILT_STEPS,
    HEAD_YAW_MAX_DEG,
    HEAD_YAW_STEPS,
)
from heroanim.rig import HEROES, pitch_axis, shared_pitch_axis, yaw_axis
from testkit.profiles import slowwalk, tps
from walkanim import slow

SCRIPTS = Path(__file__).resolve().parents[2]
ANIMATION_GALAXY = SCRIPTS.parent / "src" / "SCOBA.SC2Map" / "scripts" / "app" / "core" / "animation.galaxy"
ANIMATION_AIM_GALAXY = SCRIPTS.parent / "src" / "SCOBA.SC2Map" / "scripts" / "app" / "systems" / "animation_aim.galaxy"


def galaxy_const(name: str) -> float:
    text = ANIMATION_GALAXY.read_text(encoding="utf-8")
    match = re.search(rf"const (?:int|fixed) {name} = ([0-9.]+);", text)
    if match is None:
        raise AssertionError(f"{name} not found in {ANIMATION_GALAXY}")
    return float(match.group(1))


class HeadTiltTest(unittest.TestCase):
    """The script, the model clips, and the tps profile agree (R-TPS-13)."""

    def test_steps_match_script(self) -> None:
        self.assertEqual(galaxy_const("c_ANIM_HEAD_STEPS"), HEAD_TILT_STEPS)
        self.assertEqual(tps.HEAD_STEPS, HEAD_TILT_STEPS)

    def test_range_matches_script(self) -> None:
        self.assertEqual(galaxy_const("c_ANIM_HEAD_MAX"), HEAD_TILT_MAX_DEG)

    def test_odd_step_count_has_level_clip(self) -> None:
        self.assertEqual(HEAD_TILT_STEPS % 2, 1)

    def test_script_plays_the_generated_group(self) -> None:
        clip = '"' + HEAD_TILT_GROUP.replace(" ", ",") + ',"'
        self.assertIn(clip, ANIMATION_AIM_GALAXY.read_text(encoding="utf-8"))

    def test_yaw_matches_script(self) -> None:
        self.assertEqual(galaxy_const("c_ANIM_HEAD_YAW_STEPS"), HEAD_YAW_STEPS)
        self.assertEqual(galaxy_const("c_ANIM_HEAD_YAW_MAX"), HEAD_YAW_MAX_DEG)
        self.assertEqual(tps.HEAD_YAW_STEPS, HEAD_YAW_STEPS)
        self.assertEqual(HEAD_YAW_STEPS % 2, 1)

    def test_head_clips_sit_over_upper_body_clips(self) -> None:
        # Torso pitch 11, aim attack 12, kick 13 (R-TPS-16: the head leads while aiming).
        self.assertGreater(HEAD_TILT_PRIORITY, 13)

    def test_head_blend_spans_one_game_loop(self) -> None:
        # Smooth between per-loop steps (0.0625 s), no longer.
        self.assertEqual(galaxy_const("c_ANIM_HEAD_BLEND"), 0.0625)

    def test_head_pitch_range(self) -> None:
        # Operator 2026-11-21: 30 degrees up or down (was 15), 7.5 per step.
        self.assertEqual(HEAD_TILT_MAX_DEG, 30.0)
        self.assertEqual(tps.HEAD_MAX, HEAD_TILT_MAX_DEG)
        self.assertEqual(2.0 * HEAD_TILT_MAX_DEG / (HEAD_TILT_STEPS - 1), 7.5)

    def test_head_yaw_step_is_fine(self) -> None:
        self.assertLessEqual(2.0 * HEAD_YAW_MAX_DEG / (HEAD_YAW_STEPS - 1), 5.0)
        # Clip numbers are two-digit animation tokens.
        self.assertLessEqual(HEAD_YAW_STEPS * HEAD_TILT_STEPS, 99)


def _bone_model(name: str, rows: tuple) -> object:
    """A model with one bone whose rest local axes (model space) are the
    columns of the matrix with these rows; the file stores its inverse."""
    from types import SimpleNamespace as N

    inv = [[rows[c][r] for c in range(3)] for r in range(3)]  # transpose
    col = [N(x=inv[0][c], y=inv[1][c], z=inv[2][c], w=0.0) for c in range(3)]
    matrix = N(x=col[0], y=col[1], z=col[2], w=N(x=0.0, y=0.0, z=0.0, w=1.0))
    return N(bones=[N(name=name)], absoluteInverseBoneRestPositions=[N(matrix=matrix)])


class HeadAxisTest(unittest.TestCase):
    """Operator 2026-11-21: the head pitch tilted sideways. Pitch is the head's
    own left-right axis, signed so + is face up (forward -Y); yaw is up."""

    def test_tosh_head_axes(self) -> None:
        # BoneHead rest axes (stock tosh.m3): X=(1,0,0) Y=(0,.91,.40) Z=(0,-.40,.91).
        model = _bone_model("BoneHead", ((1.0, 0.0, 0.0), (0.0, 0.91, -0.40), (0.0, 0.40, 0.91)))
        self.assertEqual(yaw_axis(model, "BoneHead"), ("Z", 1.0))
        self.assertEqual(pitch_axis(model, "BoneHead"), ("X", -1.0))
        # Negative: not Y, the forward/back axis that rolled the head.
        self.assertNotEqual(pitch_axis(model, "BoneHead")[0], "Y")

    def test_kerrigan_head_axes(self) -> None:
        # Bone29 rest axes (stock kerrigan.m3): X=(0,-.35,.94) Y=(0,.94,.35) Z=(-1,0,0).
        model = _bone_model("Bone29", ((0.0, 0.0, -1.0), (-0.35, 0.94, 0.0), (0.94, 0.35, 0.0)))
        self.assertEqual(yaw_axis(model, "Bone29"), ("X", 1.0))
        self.assertEqual(pitch_axis(model, "Bone29"), ("Z", 1.0))

    def test_bake_reads_the_axes_from_the_rig(self) -> None:
        source = (SCRIPTS / "character_anim_assets.py").read_text(encoding="utf-8")
        self.assertIn("    nod_axis, pitch_sign = pitch_axis(model, head)\n", source)
        self.assertIn("    nod_axis, nod_sign = shared_pitch_axis(model, rig.pitch_bones)\n", source)
        self.assertIn("    head = make_head_groups(model, groups, rig.head_bone)\n", source)


class TorsoAxisTest(unittest.TestCase):
    """Operator 2026-11-22: Kerrigan's torso aim pitch turned on the wrong
    axis. The torso nods about its own left-right axis, read from the rig."""

    def test_tosh_torso_axis(self) -> None:
        # BoneSpine01 rest axes (stock tosh.m3): X=(0,0,1) Y=(-1,0,0) Z=(0,-1,0).
        model = _bone_model("BoneSpine01", ((0.0, -1.0, 0.0), (0.0, 0.0, -1.0), (1.0, 0.0, 0.0)))
        self.assertEqual(shared_pitch_axis(model, HEROES["tosh"].pitch_bones), ("Y", 1.0))

    def test_kerrigan_torso_axis(self) -> None:
        # Bone07 rest axes (stock kerrigan.m3): X=(0,-.13,.99) Y=(0,.99,.13) Z=(-1,0,0).
        model = _bone_model("Bone07", ((0.0, 0.0, -1.0), (-0.13, 0.99, 0.0), (0.99, 0.13, 0.0)))
        axis = shared_pitch_axis(model, HEROES["kerrigan"].pitch_bones)
        self.assertEqual(axis, ("Z", 1.0))
        # Negative: not Y, the axis copied from Tosh that rolled her sideways.
        self.assertNotEqual(axis[0], "Y")

    def test_bones_with_different_axes_are_refused(self) -> None:
        from types import SimpleNamespace as N

        one = _bone_model("A", ((0.0, -1.0, 0.0), (0.0, 0.0, -1.0), (1.0, 0.0, 0.0)))
        two = _bone_model("B", ((0.0, 0.0, -1.0), (-0.13, 0.99, 0.0), (0.99, 0.13, 0.0)))
        model = N(bones=one.bones + two.bones, absoluteInverseBoneRestPositions=one.absoluteInverseBoneRestPositions + two.absoluteInverseBoneRestPositions)
        with self.assertRaises(ValueError):
            shared_pitch_axis(model, ("A", "B"))


class AimPitchSourceTest(unittest.TestCase):
    def test_pitch_source_is_upper_only(self) -> None:
        self.assertEqual(HEROES["tosh"].aim_pose_clip, "Attack Arm Alternate")
        # Operator 2026-11-22: her aim pose is the Psi Blast cast, not talons.
        self.assertEqual(HEROES["kerrigan"].aim_pose_clip, "Spell Arm Alternate")


class AimDirectionsTest(unittest.TestCase):
    def test_eight_unique_directions(self) -> None:
        self.assertEqual(len(AIM_DIRECTIONS), 8)
        self.assertEqual(len({name for name, _, _ in AIM_DIRECTIONS}), 8)

    def test_twist_limit(self) -> None:
        for name, yaw, _ in AIM_DIRECTIONS:
            self.assertLessEqual(abs(yaw), 65.0, name)

    def test_side_twist(self) -> None:
        yaws = {name: yaw for name, yaw, _ in AIM_DIRECTIONS}
        self.assertEqual(yaws["Left"], 65.0)
        self.assertEqual(yaws["Right"], -65.0)

    def test_backpedal_directions(self) -> None:
        reverse = [name for name, _, reversed_motion in AIM_DIRECTIONS if reversed_motion]
        self.assertEqual(reverse, ["Back Left", "Back", "Back Right"])


APP = SCRIPTS.parent / "src" / "SCOBA.SC2Map" / "scripts" / "app"
BEHAVIOR_DATA = SCRIPTS.parent / "src" / "SCOBA.SC2Map" / "Base.SC2Data" / "GameData" / "BehaviorData.xml"


def app_text(*parts: str) -> str:
    return APP.joinpath(*parts).read_text(encoding="utf-8")


class SlowWalkTest(unittest.TestCase):
    """REQ-SLOW-WALK: data, constants, clip table, keys, and the profile agree."""

    def test_buff_is_thirty_percent_speed(self) -> None:
        # Operator 2026-11-22: 30 % (was 40 %).
        text = BEHAVIOR_DATA.read_text(encoding="utf-8")
        block = re.search(r'<CBehaviorBuff id="SCOBASlowWalk">(.*?)</CBehaviorBuff>', text, re.S)
        self.assertIsNotNone(block)
        multiplier = re.search(r'MoveSpeedMultiplier="([0-9.]+)"', block.group(1))
        self.assertEqual(float(multiplier.group(1)), 0.3)
        self.assertAlmostEqual(sum(slowwalk.SLOW_RATIO) / 2.0, 0.3)
        self.assertNotIn("<Duration", block.group(1))

    def test_lower_states(self) -> None:
        self.assertEqual(galaxy_const("c_ANIM_LOWER_WALK_SLOW"), slowwalk.LOWER_SLOW)
        self.assertEqual(galaxy_const("c_ANIM_LOWER_WALK_SLOW_BACK"), slowwalk.LOWER_SLOW_BACK)
        self.assertEqual(galaxy_const("c_ANIM_LOWER_COUNT"), 8)

    def test_clip_table_matches_the_bake(self) -> None:
        clips = sorted(clip.replace(",", " ") for _, clip in slow.CLIP_RE.findall(ANIMATION_AIM_GALAXY.read_text(encoding="utf-8")))
        self.assertEqual(clips, sorted(slow.PREFIX + name for name, _, _ in AIM_DIRECTIONS))

    def test_arm_states_and_clips(self) -> None:
        # R-SLOW-19: two upper states, their clips match the bake and the profile.
        self.assertEqual(galaxy_const("c_ANIM_UPPER_WALK_SLOW"), slowwalk.UPPER_SLOW)
        self.assertEqual(galaxy_const("c_ANIM_UPPER_WALK_SLOW_BACK"), slowwalk.UPPER_SLOW_BACK)
        # 13: the talons swing state follows them (operator 2026-11-23).
        self.assertEqual(galaxy_const("c_ANIM_UPPER_COUNT"), 13)
        arms = sorted(clip.replace(",", " ") for clip in slow.ARM_RE.findall(ANIMATION_AIM_GALAXY.read_text(encoding="utf-8")))
        self.assertEqual(arms, sorted((slow.ARM, slow.ARM_BACK)))
        self.assertEqual(sorted((slowwalk.ARM, slowwalk.ARM_BACK)), sorted(a.replace(" ", ",") for a in arms))
        fsm = app_text("systems", "animation_fsm.galaxy")
        self.assertIn("lv_upper = gf_SlowWalkUpperState(lp_player, lv_lower);", fsm)

    def test_slow_rate_factor(self) -> None:
        # Operator 2026-11-27: 25 % faster than 1.33 (2026-11-21), movement unchanged.
        self.assertEqual(slowwalk.slow_const("c_ANIM_SLOW_RATE"), 1.66)
        bracket = app_text("systems", "animation_bracket.galaxy")
        self.assertIn("return c_ANIM_SLOW_RATE * UnitGetPropertyFixed(lp_hero, c_unitPropMovementSpeed, c_unitPropCurrent) / c_ANIM_SLOW_STRIDE;", bracket)

    def test_speed_ramp_levels_are_linear(self) -> None:
        # Operator 2026-11-21 (R-SLOW-21): walk to slow walk over 1 s, 16 levels.
        self.assertEqual(slowwalk.slow_const("c_SLOW_WALK_RAMP"), 1.0)
        core = app_text("core", "slow_walk.galaxy")
        self.assertIn("const int c_SLOW_WALK_LEVELS = 16;", core)
        text = BEHAVIOR_DATA.read_text(encoding="utf-8")
        for k in range(1, 16):
            block = re.search(rf'<CBehaviorBuff id="SCOBASlowWalkRamp{k:02d}">(.*?)</CBehaviorBuff>', text, re.S)
            self.assertIsNotNone(block, k)
            value = float(re.search(r'MoveSpeedMultiplier="([0-9.]+)"', block.group(1)).group(1))
            self.assertAlmostEqual(value, 1.0 - 0.7 * k / 16.0, places=5)
            self.assertNotIn("<Duration", block.group(1))
        # Negative: no level 16 ramp buff; level 16 is SCOBASlowWalk itself.
        self.assertNotIn('id="SCOBASlowWalkRamp16"', text)
        self.assertEqual(slowwalk.RAMP_IN[-1], 0.3)
        self.assertEqual(slowwalk.RAMP_OUT[-1], 1.0)
        source = app_text("systems", "input.galaxy")
        self.assertIn('return lv_buff + "Ramp0" + IntToString(lp_level);', source)

    def test_kerrigan_speed_and_buff(self) -> None:
        # Operator 2026-11-23 (R-SLOW-22): walk 2.6, slow walk 1.3: her own
        # 0.5 buff and ramp 1 - 0.5 k / 16; Tosh's buff stays 0.3.
        units = (BEHAVIOR_DATA.parent / "UnitData.xml").read_text(encoding="utf-8")
        unit = re.search(r'<CUnit id="KerriganSCOBA" parent="Kerrigan">(.*?)</CUnit>', units, re.S)
        self.assertIsNotNone(unit)
        self.assertEqual(re.findall(r'<Speed value="([0-9.]+)"/>', unit.group(1)), ["2.6"])
        self.assertEqual(slowwalk.KERRIGAN_PROP1000, (2600, 1300))
        text = BEHAVIOR_DATA.read_text(encoding="utf-8")
        block = re.search(r'<CBehaviorBuff id="SCOBASlowWalkKerrigan">(.*?)</CBehaviorBuff>', text, re.S)
        self.assertIsNotNone(block)
        self.assertEqual(float(re.search(r'MoveSpeedMultiplier="([0-9.]+)"', block.group(1)).group(1)), 0.5)
        self.assertAlmostEqual(sum(slowwalk.KERRIGAN_SLOW_RATIO) / 2.0, 0.5)
        for k in range(1, 16):
            ramp = re.search(rf'<CBehaviorBuff id="SCOBASlowWalkKerriganRamp{k:02d}">(.*?)</CBehaviorBuff>', text, re.S)
            self.assertIsNotNone(ramp, k)
            value = float(re.search(r'MoveSpeedMultiplier="([0-9.]+)"', ramp.group(1)).group(1))
            self.assertAlmostEqual(value, 1.0 - 0.5 * k / 16.0, places=5)
            self.assertNotIn("<Duration", ramp.group(1))
        self.assertNotIn('id="SCOBASlowWalkKerriganRamp16"', text)
        self.assertEqual(slowwalk.KERRIGAN_RAMP_IN[-1], 0.5)
        self.assertEqual(slowwalk.KERRIGAN_RAMP_OUT[-1], 1.0)
        core = app_text("core", "slow_walk.galaxy")
        self.assertIn('const string c_SLOW_WALK_BUFF_KERRIGAN = "SCOBASlowWalkKerrigan";', core)
        source = app_text("systems", "input.galaxy")
        self.assertIn("return c_SLOW_WALK_BUFF_KERRIGAN;", source)
        self.assertIn("gf_SlowWalkLevelBuff(lv_hero, lv_level)", source)

    def test_slow_blend_is_three_times(self) -> None:
        # Operator 2026-11-21: into and out of the slow walk 3 x the 0.15 s blend.
        self.assertAlmostEqual(slowwalk.slow_const("c_ANIM_SLOW_BLEND"), 3 * 0.15)
        self.assertEqual(slowwalk.SLOW_BLEND_MS, 450)
        bracket = app_text("systems", "animation_bracket.galaxy")
        self.assertEqual(bracket.count("FixedToString(c_ANIM_SLOW_BLEND, 3)"), 2)
        self.assertIn("lv_blend = c_ANIM_SLOW_BLEND;", bracket)
        aim = app_text("systems", "animation_aim.galaxy")
        self.assertEqual(aim.count('"Walk,Slow,Arm", c_ANIM_SLOW_BLEND') + aim.count('"Walk,Slow,Arm,Back", c_ANIM_SLOW_BLEND'), 2)

    def test_slow_clips_are_tosh_only(self) -> None:
        self.assertEqual(slow.SLOW_HEROES, ("tosh",))
        config = app_text("systems", "animation_config.galaxy")
        self.assertRegex(config, r"if \(lv_profile == c_ANIM_HERO_TOSH\) \{\n\s+gf_AnimConfigAimSlow")

    def test_slow_key_triggers(self) -> None:
        # Shift slows, Z zooms (operator 2026-11-21).
        consts = app_text("core", "constants.galaxy")
        self.assertIn("const int gv_sLOWWALK = c_keyShift;", consts)
        self.assertIn("const int gv_zOOM = c_keyZ;", consts)
        text = app_text("systems", "input.galaxy")
        self.assertIn("TriggerAddEventKeyPressed(gt_SlowKeyDown, c_playerAny, gv_sLOWWALK, true,", text)
        self.assertIn("TriggerAddEventKeyPressed(gt_SlowKeyUp, c_playerAny, gv_sLOWWALK, false,", text)

    def test_alt_digit_keys_unchanged(self) -> None:
        # R-SLOW-7: hero switch and hall paint still require Alt.
        switch = app_text("systems", "hero_switch.galaxy")
        for name, key in (("Tosh", "1"), ("Kerrigan", "2"), ("Scv", "3"), ("Viking", "4")):
            self.assertIn(f"TriggerAddEventKeyPressed(gt_HeroSwitch{name}, 1, c_key{key}, true, c_keyModifierStateIgnore, c_keyModifierStateIgnore, c_keyModifierStateRequire);", switch)
        paint = app_text("systems", "hall_paint.galaxy")
        self.assertIn("c_key0, true, c_keyModifierStateIgnore, c_keyModifierStateIgnore, c_keyModifierStateRequire);", paint)

    def test_press_is_gated_release_is_not(self) -> None:
        scene = app_text("systems", "scene.galaxy")
        self.assertIn("return gt_SlowKeyDown;", scene)
        self.assertNotIn("return gt_SlowKeyUp;", scene)
        count = len(re.findall(r"if \(lp_i == \d+\) \{ return gt_", scene))
        self.assertEqual(f"const int c_SCENE_TRIGGERS = {count};" in app_text("core", "scene.galaxy"), True)

    def test_jump_blend_is_minimal(self) -> None:
        # R-SLOW-18: slow walk to regular walk to jump with a minimal blend.
        match = re.search(r"const fixed c_JUMP_BLEND = ([0-9.]+);", app_text("core", "jump.galaxy"))
        self.assertLessEqual(float(match.group(1)), 0.05)
        self.assertIn("gf_SlowWalkJumpPress(lp_player);", app_text("systems", "jump.galaxy"))

    def test_phase_gap_wraps(self) -> None:
        self.assertAlmostEqual(slow.phase_gap(0.99, 0.01), 0.02)
        self.assertAlmostEqual(slow.phase_gap(0.2, 0.5), 0.3)

    def test_profile_windows(self) -> None:
        self.assertEqual(slowwalk.SLOW_RATIO, (0.25, 0.35))
        self.assertEqual(set(slowwalk.CHECKS), {s for group in slowwalk.SECTIONS.values() for s in group})


if __name__ == "__main__":
    unittest.main()