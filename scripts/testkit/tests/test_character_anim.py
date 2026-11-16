from __future__ import annotations

import re
import unittest
from pathlib import Path

from character_anim_assets import AIM_DIRECTIONS, AIM_PITCH_SOURCE
from character_anim_assets import (
    HEAD_TILT_GROUP,
    HEAD_TILT_MAX_DEG,
    HEAD_TILT_PRIORITY,
    HEAD_TILT_STEPS,
    HEAD_YAW_MAX_DEG,
    HEAD_YAW_STEPS,
)
from testkit.profiles import tps

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

    def test_head_yaw_step_is_fine(self) -> None:
        self.assertLessEqual(2.0 * HEAD_YAW_MAX_DEG / (HEAD_YAW_STEPS - 1), 5.0)
        # Clip numbers are two-digit animation tokens.
        self.assertLessEqual(HEAD_YAW_STEPS * HEAD_TILT_STEPS, 99)


class AimPitchSourceTest(unittest.TestCase):
    def test_pitch_source_is_upper_only(self) -> None:
        self.assertEqual(AIM_PITCH_SOURCE, "Attack Arm Alternate")


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


if __name__ == "__main__":
    unittest.main()