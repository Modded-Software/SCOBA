from __future__ import annotations

import unittest

from dump_m3_clip_metrics import frame_rows, map_models, model_type
from project_root import project_root

ROOT = project_root()
MAP = ROOT / "out" / "SCOBA256.SC2Map"


class ClipMetricsTests(unittest.TestCase):
    @unittest.skipUnless(MAP.is_dir(), "built map is absent")
    def test_models_have_frame_metrics(self) -> None:
        models = map_models(MAP)
        self.assertGreaterEqual(len(models), 2)
        types = {model_type(path) for path in models}
        self.assertIn("Tosh", types)
        self.assertIn("Kerrigan", types)

    @unittest.skipUnless(MAP.is_dir(), "built map is absent")
    def test_arbitrary_clip_frames(self) -> None:
        models = {model_type(path): path for path in map_models(MAP)}
        tosh = frame_rows(models["Tosh"])
        kerrigan = frame_rows(models["Kerrigan"])
        self.assertEqual(tosh["Stand Left"]["dur"], 1000)
        self.assertEqual(kerrigan["Walk"]["dur"], 1000)
        self.assertIn("Attack", tosh)
        self.assertIn("Attack Arm Alternate", tosh)
        self.assertIn("Spell Arm Alternate", tosh)
        self.assertIn("Stand Work", tosh)
        self.assertIn("Attack Arm Alternate", kerrigan)
        self.assertIn("Spell Arm Alternate", kerrigan)
        self.assertIn("Stand Work", kerrigan)
        self.assertGreater(tosh["Walk"]["fc"], 0)
        self.assertGreater(kerrigan["Stand"]["fc"], 0)
        self.assertNotEqual(tosh["Stand"]["fc"], kerrigan["Stand"]["fc"])

    @unittest.skipUnless(MAP.is_dir(), "built map is absent")
    def test_clip_name_uses_sequence_spelling(self) -> None:
        models = {model_type(path): path for path in map_models(MAP)}
        rows = frame_rows(models["Tosh"])
        self.assertIn("Stand Left", rows)
        self.assertNotIn("Stand,Left", rows)


if __name__ == "__main__":
    unittest.main()