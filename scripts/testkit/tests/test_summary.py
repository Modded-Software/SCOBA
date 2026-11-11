from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from testkit.summary import write_summary


class SummaryTests(unittest.TestCase):
    def test_summary_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            run_dir.mkdir()
            write_summary(
                run_dir,
                "aim",
                Path("out/map"),
                Path("bank"),
                0,
                [{"section": "case", "tag": "t0", "key": "value", "got": 1, "want": 1, "status": "PASS"}],
                {},
                [],
            )
            payload = json.loads((run_dir / "summary.json").read_text())
            self.assertEqual(payload["profile"], "aim")
            self.assertEqual(payload["failures"], 0)
            self.assertTrue((run_dir / "summary.txt").is_file())


if __name__ == "__main__":
    unittest.main()