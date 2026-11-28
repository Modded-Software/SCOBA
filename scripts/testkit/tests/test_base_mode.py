"""Host tests for the base AI lane mode (R-BASE-37, scripts/mapgen/base_mode.py)."""

from __future__ import annotations

import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mapgen import base_mode as M

from testkit.profiles import baseai_env

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src" / "SCOBA.SC2Map"
SOURCE = (SRC / M.MODE_FILE).read_text(encoding="utf-8")


def _root(tmp: str, text: str) -> tuple[Path, Path]:
    root = Path(tmp)
    path = root / M.MODE_FILE
    path.parent.mkdir(parents=True)
    path.write_text(text, encoding="utf-8")
    return root, path


class BaseModeTest(unittest.TestCase):
    def test_source_default_is_middle(self) -> None:
        self.assertEqual(M.check_script(SOURCE), [])
        self.assertIn(M.mode_line("middle"), SOURCE)
        self.assertEqual(M.DEFAULT, "middle")

    def test_source_values_match(self) -> None:
        for mode, name in M.MODES.items():
            self.assertIn(f"const int {name} = {M.MODE_VALUES[mode]};", SOURCE)

    def test_roster_middle_lanes_match(self) -> None:
        roster = (SRC / "scripts" / "app" / "core" / "roster.galaxy").read_text(encoding="utf-8")
        body = re.search(r"bool gf_RosterIsMiddle \(int lp_lane\) \{\n(.*?)\n\}", roster, re.DOTALL).group(1)
        self.assertEqual(tuple(int(n) for n in re.findall(r"lp_lane == (\d+)", body)), M.MIDDLE_LANES)

    def test_lanes_with_base(self) -> None:
        self.assertEqual(M.lanes_with_base("middle"), (1, 4))
        self.assertEqual(M.lanes_with_base("3v3"), (1, 2, 3, 4, 5, 6))
        with self.assertRaises(ValueError):
            M.lanes_with_base("2v2")

    def test_patch_swaps_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, path = _root(tmp, SOURCE)
            M.patch_mode(root, "3v3")
            text = path.read_text(encoding="utf-8")
            self.assertIn(M.mode_line("3v3"), text)
            self.assertNotIn(M.mode_line("middle"), text)
            self.assertEqual(M.check_script(text), [])
            # Nothing else changed.
            self.assertEqual(text.replace(M.mode_line("3v3"), M.mode_line("middle")), SOURCE)

    def test_patch_refuses_unknown_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, path = _root(tmp, SOURCE)
            with self.assertRaises(ValueError):
                M.patch_mode(root, "2v2")
            self.assertEqual(path.read_text(encoding="utf-8"), SOURCE)

    def test_check_refuses_missing_double_and_unknown(self) -> None:
        line = M.mode_line("middle")
        self.assertTrue(M.check_script(SOURCE.replace(line, "")))
        self.assertTrue(M.check_script(SOURCE + "\n" + line + "\n"))
        self.assertTrue(M.check_script(SOURCE.replace(line, "const int c_BASE_AI_MODE = 2;")))

    def test_patch_refuses_bad_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, _ = _root(tmp, SOURCE.replace(M.mode_line("middle"), ""))
            with self.assertRaises(SystemExit):
                M.patch_mode(root, "3v3")

    def test_env_switch(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SC2_BA_MODE", None)
            self.assertIsNone(baseai_env.base_mode())
        with mock.patch.dict(os.environ, {"SC2_BA_MODE": "3v3"}):
            self.assertEqual(baseai_env.base_mode(), "3v3")
        with mock.patch.dict(os.environ, {"SC2_BA_MODE": "all"}), self.assertRaises(SystemExit):
            baseai_env.base_mode()


if __name__ == "__main__":
    unittest.main()
