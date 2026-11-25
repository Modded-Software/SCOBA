from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from testkit.logs import (
    collect_new_logs,
    latest_script_error,
    report_logs,
    texture_warning_lines,
)

# Lines as the game wrote them in "2026-11-15 03.44.06 Graphics.txt".
GRAPHICS_CLEAN = (
    "GFX  03:44:06.770 Hardware Depth Sampling: Available\n"
    "GFX  03:44:06.771 VRAM texture space: 2048MB\n"
    "GFX  03:44:08.256 D3D9 Device Reset from unknown returned e_errorKindGfx(0)\n"
)
TEXTURE_WARNING = (
    "GFX  03:44:13.888 WARNING: Texture DB does not match file info or file is corrupt "
    "for assets\\textures\\scoba_hd\\zerus_7.dds"
)


class TextureWarningTests(unittest.TestCase):
    def test_a_clean_graphics_log_has_no_texture_warning(self):
        self.assertEqual(texture_warning_lines(GRAPHICS_CLEAN), [])

    def test_a_texture_the_size_table_does_not_fit_is_found(self):
        self.assertEqual(texture_warning_lines(GRAPHICS_CLEAN + TEXTURE_WARNING + "\n"), [TEXTURE_WARNING])

    def test_a_new_graphics_log_with_a_warning_fails_the_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            logs = Path(tmp)
            (logs / "a Graphics.txt").write_text(GRAPHICS_CLEAN)
            self.assertEqual(collect_new_logs(logs, 0)["texture_warnings"], [])
            self.assertEqual(report_logs(logs, 0)[0], 0)
            (logs / "b Graphics.txt").write_text(GRAPHICS_CLEAN + TEXTURE_WARNING + "\n")
            found = collect_new_logs(logs, 0)["texture_warnings"]
            self.assertEqual(found, [f"b Graphics.txt: {TEXTURE_WARNING}"])
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(report_logs(logs, 0)[0], 1)

    def test_a_graphics_log_from_before_the_run_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            logs = Path(tmp)
            old = logs / "old Graphics.txt"
            old.write_text(TEXTURE_WARNING + "\n")
            later = old.stat().st_mtime + 10
            self.assertEqual(collect_new_logs(logs, later)["texture_warnings"], [])


class ActorAlertTests(unittest.TestCase):
    # As the game wrote it in podbirth/20261117-105245.
    SPHERE = "USER 1002 3.1 3.2 Scope[SCOBAHeroPod, Unit] Unable to create unit actor.  Creating fallback sphere unit.\n"
    BENIGN = "USER 1084 1.0 1.0 Scope[ToshSCOBAUnit, Unit] received invalid message CActorMsg[AbilMorph.Start].\n"

    def _failures(self, text: str) -> int:
        with tempfile.TemporaryDirectory() as tmp:
            logs = Path(tmp)
            (logs / "a Alerts.txt").write_text(text)
            with contextlib.redirect_stderr(io.StringIO()):
                return report_logs(logs, 0)[0]

    def test_fallback_sphere_fails_the_run(self):
        self.assertEqual(self._failures(self.SPHERE), 1)

    def test_other_actor_warning_does_not(self):
        self.assertEqual(self._failures(self.BENIGN), 0)

    # As the game wrote it in "2026-11-18 17.03.19 Alerts.txt": an event
    # with two IsStatus terms, dropped at load (no footfall dust).
    DROPPED = ('USER 0 0.000 0.063 CActorUnit[Goliath] Has event without a triggering message. '
               'Event[Terms "" Send "Create GoliathFootDust1"]\n')

    def test_dropped_actor_event_fails_the_run(self):
        self.assertEqual(self._failures(self.DROPPED), 1)

    # As the game wrote them in tps/20261124-185130: a packaged model copy
    # whose textures did not start as the `CModel` declares its slots.
    SLOTS = (
        "USER 0 0.000 0.063 Model Goliath; Texture expression for editor has non-existent slot.main\n",
        "USER 0 0.000 0.063 [143f    c] CActorUnit[Goliath] Model[Goliath]  m3[Goliath.m3]; No mapping for slot main.diffuse.\n",
        "USER 0 0.000 0.063 [143f    c] CActorUnit[Goliath] Goliath assets\\models\\scoba_hd\\goliath.m3; Could not find source texture with slot main.\n",
    )

    def test_each_line_of_a_texture_slot_that_is_not_there_fails_the_run(self):
        for line in self.SLOTS:
            self.assertEqual(self._failures(line), 1, line)
        self.assertEqual(self._failures(self.BENIGN + "".join(self.SLOTS)), 1)


class LogTests(unittest.TestCase):
    def test_latest_script_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            logs = Path(tmp)
            first = logs / "a ScriptError.txt"
            first.write_text("first")
            second = logs / "b ScriptError.txt"
            second.write_text("second")
            found = latest_script_error(logs, 0)
            self.assertIsNotNone(found)
        self.assertTrue(found.name.endswith("ScriptError.txt"))

    def test_no_script_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(latest_script_error(Path(tmp), 0))


if __name__ == "__main__":
    unittest.main()
