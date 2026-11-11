from __future__ import annotations

import unittest

from character_anim_assets import AIM_DIRECTIONS


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