"""Host tests for scripts/input_gate_check.py (SPEC-ROSTER 3.4)."""

from __future__ import annotations

import unittest

import input_gate_check
from project_root import project_root

APP = project_root() / "src" / "SCOBA.SC2Map" / "scripts" / "app"


def source() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted(APP.rglob("*.galaxy")))


class InputGateTest(unittest.TestCase):
    def test_source_gated(self) -> None:
        self.assertEqual(input_gate_check.gated(source()), [])

    def test_missing_gate_fails(self) -> None:
        text = source().replace("    if (gf_InputHeld(EventPlayer())) {\n        return true;\n    }\n", "", 1)
        self.assertTrue(input_gate_check.gated(text))

    def test_disable_fails(self) -> None:
        self.assertTrue(input_gate_check.gated(source() + "\nvoid x () { TriggerEnable(gt_JumpKey, false); }\n"))


if __name__ == "__main__":
    unittest.main()
