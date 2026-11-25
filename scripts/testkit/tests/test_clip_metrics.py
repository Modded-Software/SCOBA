from __future__ import annotations

import unittest

import workpaths
from m3dump.dump_m3_clip_metrics import frame_rows, map_models, model_type
from project_root import project_root

from testkit.tests.built_map import needs_built

ROOT = project_root()


def map_path():
    return workpaths.path("SC2_BUILT_MAP")


class ClipMetricsTests(unittest.TestCase):
    @needs_built()
    def test_models_have_frame_metrics(self) -> None:
        models = map_models(map_path())
        self.assertGreaterEqual(len(models), 2)
        types = {model_type(path) for path in models}
        self.assertIn("Tosh", types)
        self.assertIn("Kerrigan", types)

    @needs_built()
    def test_arbitrary_clip_frames(self) -> None:
        models = {model_type(path): path for path in map_models(map_path())}
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

    @needs_built()
    def test_clip_name_uses_sequence_spelling(self) -> None:
        models = {model_type(path): path for path in map_models(map_path())}
        rows = frame_rows(models["Tosh"])
        self.assertIn("Stand Left", rows)
        self.assertNotIn("Stand,Left", rows)


if __name__ == "__main__":
    unittest.main()