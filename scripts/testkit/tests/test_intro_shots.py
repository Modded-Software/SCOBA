"""Host tests on the intro shot table (SPEC-INTRO 4.1)."""

from __future__ import annotations

import math
import unittest

from hitvolumes import intro_shots as S
from flora import terrain as terrain_mod
from project_root import project_root

BUILT = project_root() / "out" / "SCOBA256.SC2Map"
SAMPLES = 41
CLEARANCE = 0.5
# Largest slope of each easing, d(eased)/du.
SLOPE = {"E": 1.5, "Z": 1.5, "L": 1.0, "S": 0.0, "A": 1 / (1 - S.ARC_RAMP), "O": 3.0}


def us() -> list[float]:
    return [k / (SAMPLES - 1) for k in range(SAMPLES)]


class TableTest(unittest.TestCase):
    def test_src_file_is_the_generated_table(self) -> None:
        have = S.src_path().read_text(encoding="utf-8").replace("\r\n", "\n")
        self.assertEqual(have, S.galaxy())

    def test_check_reports_a_stale_table(self) -> None:
        # Negative case: a hand edit is caught.
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / S.DATA_FILE
            path.parent.mkdir(parents=True)
            path.write_text(S.galaxy().replace("12.0000", "13.0000", 1), encoding="utf-8")
            self.assertEqual(len(S.check(Path(tmp))), 1)
            path.write_text(S.galaxy(), encoding="utf-8")
            self.assertEqual(S.check(Path(tmp)), [])

    def test_lengths(self) -> None:
        self.assertAlmostEqual(S.LOOP_LENGTH, 72.0)  # S7 7 s, S8 7 s (operator 2026-11-18)
        for shot in S.SHOTS:
            self.assertGreaterEqual(shot.length, 3.0, shot.name)

    def test_dof_in_s2_only(self) -> None:
        self.assertEqual([s.name for s in S.SHOTS if s.dof], ["S2 Line"])

    def test_dolly_zoom_keeps_the_subject_size(self) -> None:
        s8 = next(s for s in S.SHOTS if s.ease == "Z")
        k = S.dolly_k()
        for u in us():
            p = S.sample(s8, u)
            self.assertAlmostEqual(p.dist * math.tan(math.radians(p.fov / 2)), k, delta=k * 0.001)
        self.assertAlmostEqual(S.sample(s8, 0).dist, 42.0, places=3)  # 3x (operator 2026-11-17)
        self.assertAlmostEqual(S.sample(s8, 1).dist, 138.3, delta=0.15)
        # Negative case: a plain distance lerp breaks the invariant.
        lerped = s8.dist0 + (s8.dist1 - s8.dist0) * 0.5
        self.assertGreater(abs(lerped * math.tan(math.radians(S.sample(s8, 0.5).fov / 2)) - k), 0.01 * k)

    def test_easings_run_from_0_to_1(self) -> None:
        for code in ("E", "L", "A", "O", "Z"):
            self.assertAlmostEqual(S.ease(code, 0.0), 0.0, places=9, msg=code)
            self.assertAlmostEqual(S.ease(code, 1.0), 1.0, places=9, msg=code)
            prev = 0.0
            for u in us():
                e = S.ease(code, u)
                self.assertGreaterEqual(e, prev - 1e-12, code)  # monotonic
                prev = e
        self.assertEqual(S.ease("S", 0.7), 0.0)
        # Negative case: the crash easing left the table (core/hero_drop).
        with self.assertRaises(ValueError):
            S.ease("C", 0.5)

    def test_arc_is_continuous(self) -> None:
        r = S.ARC_RAMP
        for edge in (r, 1 - r):
            self.assertAlmostEqual(S.ease("A", edge - 1e-9), S.ease("A", edge + 1e-9), places=6)

    def test_no_jump_inside_a_shot(self) -> None:
        # SCRIPT-INTRO P14: one sample step never exceeds the eased step.
        for shot in S.SHOTS:
            for odd in (False, True):
                ps = [S.sample(shot, u, odd) for u in us()]
                for name in ("yaw", "pitch", "dist", "fov"):
                    span = abs(getattr(ps[-1], name) - getattr(ps[0], name))
                    if shot.ease == "Z" and name == "dist":
                        span = abs(ps[-1].dist - ps[0].dist) * 2.0  # 1/tan is steeper at the long end
                    bound = SLOPE[shot.ease] * span / (SAMPLES - 1) + 1e-6
                    for a, b in zip(ps, ps[1:]):
                        self.assertLessEqual(abs(getattr(b, name) - getattr(a, name)), bound, f"{shot.name} {name}")

    def test_targets_and_eyes_in_bounds(self) -> None:
        for shot in S.SHOTS:
            for odd in (False, True):
                for u in us():
                    p = S.sample(shot, u, odd)
                    self.assertTrue(0 <= p.x <= S.BOUNDS and 0 <= p.y <= S.BOUNDS, f"{shot.name} target")
                    ex, ey, _ = S.eye(p.x, p.y, 0.0, p.yaw, p.pitch, p.dist)
                    self.assertTrue(0 <= ex <= 256 and 0 <= ey <= 256, f"{shot.name} eye ({ex:.1f}, {ey:.1f})")

    def test_variants(self) -> None:
        s2 = next(s for s in S.SHOTS if s.variant == S.VAR_TARGET)
        self.assertEqual(S.sample(s2, 0, True)[:2], S.sample(s2, 1, False)[:2])
        s6 = next(s for s in S.SHOTS if s.variant == S.VAR_YAW)
        self.assertEqual(S.sample(s6, 0, True).yaw, s6.yaw1)
        # Negative case: a shot without variant plays the same on odd passes.
        s1 = S.SHOTS[0]
        self.assertEqual(S.sample(s1, 0.3, True), S.sample(s1, 0.3, False))

    def test_galaxy_rows(self) -> None:
        text = S.galaxy()
        self.assertIn(f"const int c_INTRO_SHOTS = {len(S.SHOTS)};", text)
        self.assertIn(f"gv_introRow_dof[{len(S.SHOTS) - 1}] = false;", text)
        self.assertIn("gv_introRow_dof[1] = true;", text)
        self.assertIn("gv_introRow_ease[8] = c_INTRO_EASE_Z;", text)
        # Negative case: no row past the shots (the zoom row is gone).
        self.assertNotIn(f"gv_introRow_dof[{len(S.SHOTS)}]", text)


class IntroPatchTest(unittest.TestCase):
    """SPEC-INTRO 3.11: the intro is off in every profile map but intro."""

    def _root(self, tmp: str, text: str):
        from pathlib import Path

        from testkit.map_builder import INTRO_FILE

        root = Path(tmp)
        (root / INTRO_FILE).parent.mkdir(parents=True)
        (root / INTRO_FILE).write_text(text, encoding="utf-8")
        return root, root / INTRO_FILE

    def test_off_for_other_profiles_on_for_intro(self) -> None:
        import tempfile

        from testkit.map_builder import INTRO_OFF, INTRO_ON, patch_intro

        for profile, want in (("herodrop", INTRO_OFF), ("combat", INTRO_OFF), ("intro", INTRO_ON)):
            with tempfile.TemporaryDirectory() as tmp:
                root, path = self._root(tmp, f"// x\n{INTRO_ON}\n")
                patch_intro(root, profile)
                self.assertIn(want, path.read_text(encoding="utf-8"), profile)

    def test_missing_switch_fails(self) -> None:
        # Negative case: a renamed constant must not pass silently.
        import tempfile

        from testkit.map_builder import patch_intro

        with tempfile.TemporaryDirectory() as tmp:
            root, _ = self._root(tmp, "const bool c_INTRO_ON = true;\n")
            with self.assertRaises(SystemExit):
                patch_intro(root, "combat")

    def test_src_map_has_the_switch_on(self) -> None:
        from testkit.map_builder import INTRO_FILE, INTRO_ON

        text = (project_root() / "src" / "SCOBA.SC2Map" / INTRO_FILE).read_text(encoding="utf-8")
        self.assertEqual(text.count(INTRO_ON), 1)


@unittest.skipUnless((BUILT / "t3HeightMap").is_file(), "needs the built map (scripts/playtest.sh build)")
class TerrainTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.t = terrain_mod.load(BUILT)

    def ground(self, x: float, y: float) -> float:
        return terrain_mod.ground_z(self.t, x, y)

    def surface(self, x: float, y: float) -> float:
        g = self.ground(x, y)
        i, j = int(min(max(y, 0), 255)), int(min(max(x, 0), 255))
        return max(g, self.t.water_level) if self.t.depth[i, j] > 0 else g

    def clearance(self, shot: S.Shot, odd: bool, at: tuple[float, float] | None = None) -> float:
        worst = 1e9
        for u in us():
            p = S.sample(shot, u, odd)
            x, y = at if at else (p.x, p.y)
            z = self.ground(x, y) + p.z
            ex, ey, ez = S.eye(x, y, z, p.yaw, p.pitch, p.dist)
            worst = min(worst, ez - self.surface(ex, ey))
        return worst

    def test_absolute_heights_hold_on_the_survey_ground(self) -> None:
        # S1 and S2 are specified at absolute heights (SPEC-INTRO 3.4). The
        # table stores offsets from the survey ground; this pins the sum.
        for shot in S.SHOTS:
            if shot.name not in S.ABSOLUTE:
                continue
            want0, want1 = S.ABSOLUTE[shot.name]
            self.assertAlmostEqual(self.ground(shot.x0, shot.y0) + shot.z0, want0, delta=0.1, msg=shot.name)
            self.assertAlmostEqual(self.ground(shot.x1, shot.y1) + shot.z1, want1, delta=0.1, msg=shot.name)

    def test_absolute_check_catches_a_wrong_offset(self) -> None:
        # Negative case: the old absolute z used as an offset is off by the ground.
        s2 = next(s for s in S.SHOTS if s.name.startswith("S2"))
        # The absolute z used as an offset lands off by the ground under it.
        want = S.ABSOLUTE[s2.name][0]
        self.assertGreater(abs(self.ground(s2.x0, s2.y0) + want - want), 0.1)

    def test_s1_eye_at_the_brakk_looking_at_the_bc(self) -> None:
        s1 = next(s for s in S.SHOTS if s.name.startswith("S1"))
        for x, y, z, yaw, pitch, d in ((s1.x0, s1.y0, s1.z0, s1.yaw0, s1.pitch0, s1.dist0), (s1.x1, s1.y1, s1.z1, s1.yaw1, s1.pitch1, s1.dist1)):
            ex, ey, _ = S.eye(x, y, z, yaw, pitch, d)
            self.assertLess(math.hypot(ex - S.BRAKK[0], ey - S.BRAKK[1]), 0.5)
            to_bc = math.degrees(math.atan2(S.BC[1] - ey, S.BC[0] - ex))
            self.assertLess(abs((yaw - to_bc + 180) % 360 - 180), 1.0)

    def test_water_level(self) -> None:
        self.assertAlmostEqual(self.t.water_level, S.WATER, places=2)

    def test_eye_clears_ground_and_water(self) -> None:
        for shot in S.SHOTS:
            for odd in (False, True):
                self.assertGreaterEqual(self.clearance(shot, odd), CLEARANCE, f"{shot.name} odd={odd}")

    def test_clearance_catches_a_shot_in_the_ground(self) -> None:
        # Negative case: S7 looking up steeply from far away puts the eye under the ground.
        s7 = next(s for s in S.SHOTS if s.name.startswith("S7"))
        bad = s7._replace(pitch0=-60, pitch1=-60, z0=0.5, z1=0.5, dist0=30, dist1=30)
        self.assertLess(self.clearance(bad, False), CLEARANCE)

    def test_s4_eye_at_the_operator_point(self) -> None:
        # Eye exactly at (193.5, 164.5, 10.2), looking at the Hybrid (2026-11-18).
        s4 = next(s for s in S.SHOTS if s.name.startswith("S4"))
        bx, by = S.S4_EYE
        self.assertAlmostEqual(self.ground(s4.x0, s4.y0), S.S4_GROUND, delta=0.05)
        ez = S.S4_EYE_Z
        tz = self.ground(s4.x0, s4.y0) + s4.z0
        dx, dy = s4.x0 - bx, s4.y0 - by
        flat = math.hypot(dx, dy)
        self.assertAlmostEqual(s4.yaw0, math.degrees(math.atan2(dy, dx)), delta=0.5)
        self.assertAlmostEqual(s4.pitch0, math.degrees(math.atan2(ez - tz, flat)), delta=0.5)
        self.assertAlmostEqual(s4.dist0, math.hypot(flat, ez - tz), delta=0.5)


if __name__ == "__main__":
    unittest.main()
