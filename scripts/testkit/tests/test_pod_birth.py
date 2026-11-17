"""Hero pod Birth path: keys from the model, world transform, committed Galaxy data."""

from __future__ import annotations

import math
import unittest

from hitvolumes import pod_birth


class PodBirthTest(unittest.TestCase):
    def test_keys_match_the_model(self) -> None:
        self.assertTrue(pod_birth.MODEL.is_file(), f"model missing: {pod_birth.MODEL}")
        self.assertEqual(pod_birth.extract(), pod_birth.KEYS)
        self.assertEqual(pod_birth.extract_length(), pod_birth.LENGTH_MS)

    def test_committed_data_and_actor_scale(self) -> None:
        self.assertEqual(pod_birth.check(pod_birth.src_dir()), [])

    def test_check_flags_stale_data(self) -> None:
        good = pod_birth.KEYS
        try:
            pod_birth.KEYS = good[:-1]
            self.assertTrue(pod_birth.check(pod_birth.src_dir()))
        finally:
            pod_birth.KEYS = good

    def test_start_is_high_and_to_the_side(self) -> None:
        x, y, z = pod_birth.world(0, 0.0)
        self.assertAlmostEqual(z, 4.5 * 19.0215, places=3)
        # facing 0: model (MODEL_X * x, y) turns by 90 to world (-y, MODEL_X * x).
        self.assertAlmostEqual(x, -4.5 * 9.4498, places=3)
        self.assertAlmostEqual(y, 4.5 * -9.8702, places=3)

    def test_facing_turns_the_path(self) -> None:
        a = pod_birth.world(0, 0.0)
        b = pod_birth.world(0, 90.0)
        self.assertAlmostEqual(math.hypot(a[0], a[1]), math.hypot(b[0], b[1]), places=6)
        turn = (math.degrees(math.atan2(b[1], b[0])) - math.degrees(math.atan2(a[1], a[0]))) % 360.0
        self.assertAlmostEqual(turn, 90.0, places=4)

    def test_linear_between_keys(self) -> None:
        x0, y0, z0 = pod_birth.local(0)
        x1, y1, z1 = pod_birth.local(1600)
        xm, ym, zm = pod_birth.local(800)
        self.assertAlmostEqual(zm, (z0 + z1) / 2, places=6)
        self.assertAlmostEqual(xm, (x0 + x1) / 2, places=6)

    def test_lands_at_land_key(self) -> None:
        self.assertLessEqual(pod_birth.local(pod_birth.LAND_MS)[2], 0.0)
        # The root crosses 0 about 5 ms before the key (1.1443 to -0.0091).
        self.assertGreater(pod_birth.local(pod_birth.LAND_MS - 10)[2], 0.0)
        self.assertEqual(pod_birth.local(99999), pod_birth.KEYS[-1][1:])

    def test_travel_is_along_the_facing_offset(self) -> None:
        angle, pitch, horiz, z = pod_birth.travel()
        self.assertAlmostEqual(angle, 46.25, places=1)
        self.assertAlmostEqual(pitch, 54.3, places=1)
        self.assertAlmostEqual(horiz, 61.49, places=1)
        self.assertAlmostEqual(z, 85.64, places=1)
        # The pod flies along the camera yaw when facing = yaw - angle.
        for yaw in (0.0, 135.0, 225.0):
            sx, sy, _ = pod_birth.world(0, yaw - angle)
            diff = (math.degrees(math.atan2(-sy, -sx)) - yaw + 180.0) % 360.0 - 180.0
            self.assertAlmostEqual(diff, 0.0, places=1)

    def test_negative_fall_is_not_vertical(self) -> None:
        x, y, _ = pod_birth.world(0, 0.0)
        self.assertGreater(math.hypot(x, y), 50.0)


if __name__ == "__main__":
    unittest.main()
