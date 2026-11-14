from __future__ import annotations

import re
import unittest
from pathlib import Path

from character_anim_assets import (
    AIM_DIRECTIONS,
    AIM_PITCH_SOURCE,
    HEAD_TILT_GROUP,
    HEAD_TILT_MAX_DEG,
    HEAD_TILT_PRIORITY,
    HEAD_TILT_STEPS,
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

    def test_head_clips_sit_under_upper_body_clips(self) -> None:
        self.assertLess(HEAD_TILT_PRIORITY, 11)


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