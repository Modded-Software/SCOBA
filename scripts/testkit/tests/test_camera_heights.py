"""Host tests of the camera heights generator (R-TPS-90)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from hitvolumes import camera_heights as C
from project_root import project_root

BOX_AXES = [[1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, 1.0, 0.0]]


class TopTests(unittest.TestCase):
    def test_sphere(self) -> None:
        self.assertAlmostEqual(C.top({"k": "sphere", "c": [0, 0, 1.0], "r": 0.5}), 1.5)

    def test_capsule_takes_higher_end(self) -> None:
        self.assertAlmostEqual(C.top({"k": "capsule", "a": [0, 0, 0.2], "b": [0, 0, 1.0], "r": 0.3}), 1.3)

    def test_box_uses_vertical_extent(self) -> None:
        # The second axis is vertical, half size 0.4.
        shape = {"k": "box", "c": [0, 0, 1.0], "u": BOX_AXES, "h": [2.0, 0.4, 3.0]}
        self.assertAlmostEqual(C.top(shape), 1.4)

    def test_unknown_kind(self) -> None:
        with self.assertRaises(ValueError):
            C.top({"k": "cone"})


class HeightsTests(unittest.TestCase):
    def data(self) -> dict:
        return {
            "units": {
                "ToshSCOBA": {"shapes": [{"k": "sphere", "c": [0, 0, 0.5], "r": 0.5}]},
                "Big": {"shapes": [{"k": "sphere", "c": [0, 0, 1.5], "r": 0.5}]},
                "Empty": {"shapes": []},
                "Below": {"shapes": [{"k": "sphere", "c": [0, 0, -2.0], "r": 0.5}]},
            }
        }

    def test_max_top_per_type(self) -> None:
        self.assertEqual(C.heights(self.data()), {"Big": 2.0, "ToshSCOBA": 1.0})

    def test_render_reference_and_calls(self) -> None:
        text = C.render(self.data())
        self.assertIn("const fixed c_CAM_HEIGHT_REFERENCE = 1.0000;", text)
        self.assertIn('gf_CamHeightType("Big", 2.0000);', text)
        # Negative: types without shapes or below ground get no entry.
        self.assertNotIn('"Empty"', text)
        self.assertNotIn('"Below"', text)

    def test_missing_reference_fails(self) -> None:
        with self.assertRaises(ValueError):
            C.render({"units": {"Big": self.data()["units"]["Big"]}})

    def test_stale_detects_difference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            self.assertTrue(C.stale(out, "x"))
            (out / C.FILE).write_text("x", encoding="utf-8")
            self.assertEqual(C.stale(out, "x"), [])
            self.assertTrue(C.stale(out, "y"))


class ScaleTests(unittest.TestCase):
    DATA = {"units": {"Big": {"actor": "BigActor", "actorScale": [1.0, 1.0, 1.0], "shapes": []}}}

    def test_stale_scale_fails(self) -> None:
        problems = C.scale_problems(self.DATA, {"BigActor": (3.0, 3.0, 3.0)})
        self.assertEqual(len(problems), 1)
        self.assertIn("Big", problems[0])

    def test_matching_or_unknown_scale_passes(self) -> None:
        self.assertEqual(C.scale_problems(self.DATA, {"BigActor": (1.0, 1.0, 1.0)}), [])
        self.assertEqual(C.scale_problems(self.DATA, {}), [])

    def test_missing_body_fails(self) -> None:
        self.assertEqual(len(C.missing_bodies({"units": {}})), len(C.BODIES))


class CommittedTests(unittest.TestCase):
    def test_committed_file_matches_json(self) -> None:
        self.assertEqual(C.check_map(project_root() / "src" / "SCOBA.SC2Map"), [])

    def test_hero_heights(self) -> None:
        table = C.heights(C.load_json())
        self.assertIn("ToshSCOBA", table)
        self.assertIn("KerriganSCOBA", table)
        self.assertGreater(table["KerriganSCOBA"], table["ToshSCOBA"])
        # The landed hero Viking (actor Scale 3) stands far above Tosh.
        self.assertGreater(table["SCOBAVikingHeroAssault"], 3.0 * table["ToshSCOBA"])
        self.assertEqual(C.missing_bodies(C.load_json()), [])


if __name__ == "__main__":
    unittest.main()
