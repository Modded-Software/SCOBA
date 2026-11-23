"""Host tests of the camera heights generator (R-TPS-90)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from hitvolumes import camera_heights as C
from project_root import project_root
from testkit.checks import Checks
from testkit.profiles import camheight

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
        # Tosh's camera height is pinned (operator 2026-11-21), not measured.
        self.assertEqual(C.heights(self.data()), {"Big": 2.0, "ToshSCOBA": C.CAMERA_HEIGHT["ToshSCOBA"]})

    def test_render_reference_and_calls(self) -> None:
        text = C.render(self.data())
        self.assertIn("const fixed c_CAM_HEIGHT_REFERENCE = 0.9305;", text)
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
            self.assertTrue(C.stale(out, {C.FILE: "x"}))
            (out / C.FILE).write_text("x", encoding="utf-8")
            self.assertEqual(C.stale(out, {C.FILE: "x"}), [])
            self.assertTrue(C.stale(out, {C.FILE: "y"}))
            # Negative: a chunk the generator no longer writes is reported.
            (out / C.CHUNK.format(9)).write_text("", encoding="utf-8")
            self.assertIn("not generated", "\n".join(C.stale(out, {C.FILE: "x"})))

    def test_chunks_stay_under_the_line_limit(self) -> None:
        units = {f"U{i:04d}": {"shapes": [{"k": "sphere", "c": [0, 0, 1], "r": 1.0}]} for i in range(1200)}
        units["ToshSCOBA"] = self.data()["units"]["ToshSCOBA"]
        files = C.render_files({"units": units})
        self.assertGreater(len(files), 2)
        for name, text in files.items():
            self.assertLess(text.count("\n"), 512, name)
        self.assertEqual(sum(t.count("gf_CamHeightType(") for t in files.values()), 1201)
        for i in range(1, len(files)):
            self.assertIn(f"gf_CamHeightLoad{i}();", files[C.FILE])


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

    def test_tosh_camera_kept_after_the_shrink(self) -> None:
        """Operator 2026-11-21: Tosh shrunk 10 %, his camera height is the old one."""
        data = C.load_json()
        measured = max(C.top(s) for s in data["units"]["ToshSCOBA"]["shapes"])
        self.assertAlmostEqual(data["units"]["ToshSCOBA"]["actorScale"][0], 0.675)
        self.assertAlmostEqual(measured, 0.9305 * 0.9, places=3)
        self.assertEqual(C.heights(data)["ToshSCOBA"], 0.9305)


if __name__ == "__main__":
    unittest.main()


# Run combat/20261123-144957, clamp_tps_sweep: the bounce once the pitch held.
BOUNCE = [5992] * 27 + [5156, 5253, 5433, 3750, 2812, 3277, 3250, 2906, 2250, 2324, 2503, 2640, 2250, 2328, 2484, 2625, 2250, 2328, 2488, 2625, 2250]
BOUNCE_CLEAR = [500] * 27 + [-73, -241, -430, -316, 51, -276, -261, -80, 252, 228, 133, 61, 252, 226, 141, 69, 252, 226, 141, 69, 252]
SWEEP_SAFE = [6000] * 28 + [3750, 3468, 3281, 3093] + [2906] * 16


def clamp_rows(**change) -> dict:
    """Every clamp case settled; `change` maps a section to replaced series."""
    data = {}
    for section in camheight.CLAMP_CASES:
        sweep = section.endswith("sweep")
        safe = SWEEP_SAFE if sweep else [6000] * 48
        dist = [6000] * 28 + [3750, 3468, 3281, 3093] + [2906] * 16 if sweep else [5992] * 48
        row = {"dist": dist, "safe": safe, "clear": [350] * 48, "pitches": [0] * 48, "desired1000": 6000}
        row.update(change.get(section, {}))
        data[section] = {k: " ".join(str(v) for v in val) if isinstance(val, list) else val for k, val in row.items()}
    return data


class ClampTests(unittest.TestCase):
    def test_settled_passes(self) -> None:
        checks = Checks(clamp_rows())
        camheight.check_camclamp(checks)
        self.assertEqual(checks.failures, 0)

    def test_the_bounce_fails(self) -> None:
        checks = Checks(clamp_rows(clamp_tps_sweep={"dist": BOUNCE, "clear": BOUNCE_CLEAR}))
        camheight.check_camclamp(checks)
        # Eye under the ground, reversals, not at the clamp.
        self.assertEqual(checks.failures, 3)

    def test_no_clamp_in_a_sweep_fails(self) -> None:
        checks = Checks(clamp_rows(clamp_pnc_sweep={"safe": [6000] * 48, "dist": [5992] * 48}))
        camheight.check_camclamp(checks)
        self.assertEqual(checks.failures, 1)

    def test_reversals_ignore_noise(self) -> None:
        self.assertEqual(camheight.reversals([100, 105, 100, 105]), 0)
        self.assertEqual(camheight.reversals([100, 200, 100, 200]), 2)
