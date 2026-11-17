"""sc2-configure-window.py forces shadowmapsize=8192 in Variables.txt on every launch."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from project_root import project_root

SCRIPT = project_root() / "scripts" / "sc2-configure-window.py"


def run(docs: Path) -> subprocess.CompletedProcess[str]:
    # The script's output goes to the test log, where a failure shows why.
    env = dict(os.environ, SC2_DOCUMENTS=str(docs), SC2_WINDOW_WIDTH="1920", SC2_WINDOW_HEIGHT="1080")
    return subprocess.run([sys.executable, str(SCRIPT)], env=env, text=True)


class ConfigureTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.docs = Path(self.tmp.name)
        self.vars = self.docs / "Variables.txt"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def lines(self) -> list[str]:
        return self.vars.read_text(encoding="utf-8").splitlines()

    def test_replaces_the_old_value(self) -> None:
        self.vars.write_text("shadows=true\nshadowmapsize=4096\nsoftshadows=true\n", encoding="utf-8")
        self.assertEqual(run(self.docs).returncode, 0)
        lines = self.lines()
        self.assertEqual(lines.count("shadowmapsize=8192"), 1)
        self.assertNotIn("shadowmapsize=4096", lines)  # negative: the old value is gone
        self.assertIn("shadows=true", lines)  # other settings kept
        self.assertIn("softshadows=true", lines)

    def test_terrain_texture_size(self) -> None:
        self.vars.write_text("TerrainTextureLowResCacheSize=50\nTerrainTextureSize=768\n", encoding="utf-8")
        self.assertEqual(run(self.docs).returncode, 0)
        lines = self.lines()
        self.assertEqual([l for l in lines if l.startswith("TerrainTextureSize=")], ["TerrainTextureSize=2048"])
        self.assertIn("TerrainTextureLowResCacheSize=50", lines)  # negative: the similar key is untouched

    def test_adds_a_missing_value(self) -> None:
        self.vars.write_text("shadows=true\n", encoding="utf-8")
        self.assertEqual(run(self.docs).returncode, 0)
        self.assertEqual(self.lines().count("shadowmapsize=8192"), 1)

    def test_every_launch(self) -> None:
        self.vars.write_text("shadowmapsize=8192\n", encoding="utf-8")
        self.assertEqual(run(self.docs).returncode, 0)
        # The game's graphics menu writes it back; the next launch sets it again.
        self.vars.write_text(self.vars.read_text(encoding="utf-8").replace("=8192", "=2048"), encoding="utf-8")
        self.assertEqual(run(self.docs).returncode, 0)
        self.assertEqual([l for l in self.lines() if l.startswith("shadowmapsize=")], ["shadowmapsize=8192"])

    def test_missing_file_fails(self) -> None:
        self.assertNotEqual(run(self.docs).returncode, 0)

    def test_launch_stops_on_failure(self) -> None:
        launch = (project_root() / "scripts" / "launch-scoba.sh").read_text(encoding="utf-8")
        self.assertIn('fail "could not configure Variables.txt', launch)


if __name__ == "__main__":
    unittest.main()
