from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from testkit.animlog import write_animlog


class AnimLogTests(unittest.TestCase):
    def test_writes_timestamped_frames_and_report(self) -> None:
        data = {
            "frames": {
                "p1_100_2": "ms=100 seq=2 up=1 lo=2 uc=1 lc=2 hold=0 intent=1 fwd=1 back=0 left=0 right=0 x=10 y=20 facing=90 orders=1 ucount=1 lcount=1 resets=0",
                "p1_50_1": "ms=50 seq=1 up=1 lo=1 uc=1 lc=1 hold=0 intent=0 fwd=0 back=0 left=0 right=0 x=10 y=20 facing=90 orders=0 ucount=0 lcount=0 resets=0",
            },
            "events": {
                "p1_100_3": "ms=100 kind=lower_start clip=Walk flags=1 ustate=1 lstate=2 ucount=1 lcount=1 resets=0",
            },
        }
        with tempfile.TemporaryDirectory() as folder:
            run_dir = Path(folder)
            write_animlog(run_dir, data)
            frames = (run_dir / "animlog.tsv").read_text(encoding="utf-8").splitlines()
            events = (run_dir / "animevents.tsv").read_text(encoding="utf-8").splitlines()
            report = (run_dir / "animreport.txt").read_text(encoding="utf-8")
            self.assertIn("player\tms\tseq", frames[0])
            self.assertEqual(frames[1].split("\t")[1], "50")
            self.assertEqual(frames[2].split("\t")[1], "100")
            self.assertIn("kind\tclip", events[0])
            self.assertIn("lower_changes=1", report)
            self.assertIn("lower_starts=1", report)

    def test_skips_empty_sections(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            run_dir = Path(folder)
            write_animlog(run_dir, {})
            self.assertFalse((run_dir / "animlog.tsv").exists())
            self.assertFalse((run_dir / "animreport.txt").exists())


if __name__ == "__main__":
    unittest.main()