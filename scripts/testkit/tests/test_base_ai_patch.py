"""Host tests for the map-init base AI switch patch (SPEC-BASE-AI 6)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from testkit.map_builder import BASE_AI_FILE, BASE_AI_OFF, BASE_AI_ON, patch_base_ai

ROOT = Path(__file__).resolve().parents[3]


def _root(tmp: str, text: str) -> tuple[Path, Path]:
    root = Path(tmp)
    path = root / BASE_AI_FILE
    path.parent.mkdir(parents=True)
    path.write_text(text, encoding="utf-8")
    return root, path


class BaseAiPatchTest(unittest.TestCase):
    def test_switch_turned_off(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, path = _root(tmp, f"// x\n{BASE_AI_ON}\n")
            patch_base_ai(root)
            text = path.read_text(encoding="utf-8")
            self.assertIn(BASE_AI_OFF, text)
            self.assertNotIn(BASE_AI_ON, text)

    def test_missing_switch_fails(self) -> None:
        # Negative case: a renamed constant must not pass silently.
        with tempfile.TemporaryDirectory() as tmp:
            root, _ = _root(tmp, "const bool c_BASE_AI_ON = true;\n")
            with self.assertRaises(SystemExit):
                patch_base_ai(root)

    def test_src_map_has_the_switch_on(self) -> None:
        text = (ROOT / "src" / "SCOBA.SC2Map" / BASE_AI_FILE).read_text(encoding="utf-8")
        self.assertEqual(text.count(BASE_AI_ON), 1)


if __name__ == "__main__":
    unittest.main()
