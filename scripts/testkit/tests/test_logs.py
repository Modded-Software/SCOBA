from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from testkit.logs import latest_script_error


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
