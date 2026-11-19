"""Host tests for scripts/hitvolumes/drop_path_check.py (R-DROP-11)."""

from __future__ import annotations

import unittest

from hitvolumes import drop_path_check as D
from project_root import project_root

APP = project_root() / "src" / "SCOBA.SC2Map" / "scripts" / "app"


class DropPathTest(unittest.TestCase):
    def setUp(self) -> None:
        self.files = D.app_files(APP)

    def with_added(self, rel: str, code: str) -> dict[str, str]:
        files = dict(self.files)
        files[rel] = files.get(rel, "") + "\n" + code + "\n"
        return files

    def test_source_passes(self) -> None:
        self.assertEqual(D.problems(self.files), [])

    def test_intro_drop_code_fails(self) -> None:
        # Negative cases: drop code back in the intro.
        for code in ("void x () { gf_HeroDropFall(1); }", "void x () { CameraSetValue(1, c_cameraValueFieldOfView, c_DROP_ZOOM_FOV0, 0.0, 0.0, 0.0); }", "void x () { gv_dropPod[1] = null; }", "void x () { gf_HeroDropSide(null, 0.0); }"):
            self.assertTrue(D.problems(self.with_added("systems/intro_flow.galaxy", code)), code)

    def test_old_path_fails(self) -> None:
        self.assertTrue(D.problems(self.with_added("systems/spawns.galaxy", "void x () { gf_HeroDropStart(1, null); }")))
        self.assertTrue(D.problems(self.with_added("data/intro_shots.galaxy", "const int c_INTRO_ROW_ZOOM = 9;")))

    def test_scene_writer_elsewhere_fails(self) -> None:
        self.assertTrue(D.problems(self.with_added("systems/hero_drop.galaxy", "void x () { CinematicMode(PlayerGroupAll(), true, 0.0); }")))
        self.assertTrue(D.problems(self.with_added("systems/roster.galaxy", "void x () { gv_inputHeld[1] = false; }")))

    def test_other_go_caller_fails(self) -> None:
        self.assertTrue(D.problems(self.with_added("systems/xp.galaxy", "void x () { gf_HeroDropGo(1, null, null); }")))

    def test_missing_go_call_fails(self) -> None:
        files = dict(self.files)
        files["systems/spawns.galaxy"] = files["systems/spawns.galaxy"].replace("gf_HeroDropGo(", "gf_Nothing(")
        self.assertTrue(D.problems(files))

    def test_comments_ignored(self) -> None:
        self.assertEqual(D.problems(self.with_added("systems/intro_flow.galaxy", "// gf_HeroDropStart, c_INTRO_ROW_ZOOM")), [])


if __name__ == "__main__":
    unittest.main()
