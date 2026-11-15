from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from testkit.logs import collect_new_logs, latest_script_error, report_logs, texture_warning_lines

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
