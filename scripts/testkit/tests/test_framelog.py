from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from testkit.framelog import analyze, parse_section, write_framelog


def frame(
    ms: int,
    seq: int,
    x: int,
    y: int,
    a0: str,
    a4: str,
    uframe: int = 0,
    lframe: int = 0,
) -> str:
    return (
        f"ms={ms} seq={seq} up=1 lo=1 uclip=Stand lclip=Stand,Left"
        f" uq=ok lq=ok uframe={uframe} uframes=81 lframe={lframe} lframes=81"
        f" x={x} y={y} a0={a0} a4={a4}"
    )


class FrameLogTests(unittest.TestCase):
    def test_parse_section(self) -> None:
        records = parse_section({"p1_7": frame(100, 7, 1, 2, "3,4,5", "0,0,0")})
        self.assertEqual(records[0]["player"], 1)
        self.assertEqual(records[0]["ms"], 100)
        self.assertEqual(records[0]["seq"], 7)
        self.assertEqual(records[0]["uclip"], "Stand")
        self.assertEqual(records[0]["a0"], "3,4,5")

    def test_order_by_sample_index(self) -> None:
        data = {
            "config": {"hero": "Tosh", "a4": "Ref_Center"},
            "frames": {
                "p1_9": frame(900, 9, 0, 0, "0,0,0", "0,0,0", lframe=5),
                "p1_2": frame(200, 2, 0, 0, "0,0,0", "0,0,0", lframe=1),
            },
            "events": {},
        }
        records = parse_section(data["frames"])
        records.sort(key=lambda item: int(item["seq"]))
        counts = analyze(records, [], data["config"])
        self.assertEqual(counts["frame_advance"], 1)
        self.assertNotIn("clock", counts)

    def test_write_files(self) -> None:
        data = {
            "config": {"hero": "Tosh", "a4": "Ref_Center"},
            "frames": {"p1_1": frame(100, 1, 0, 0, "0,0,0", "0,0,0")},
            "events": {},
        }
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            write_framelog(run_dir, data)
            self.assertTrue((run_dir / "framelog.tsv").is_file())
            self.assertTrue((run_dir / "framelog.jsonl").is_file())
            self.assertTrue((run_dir / "frameprobe.txt").is_file())

    def test_slide_and_gap(self) -> None:
        data = {
            "config": {"hero": "Tosh", "a4": "Ref_Center"},
            "frames": {
                "p1_1": frame(100, 1, 0, 0, "0,0,0", "0,0,0"),
                "p1_2": frame(700, 2, 20, 0, "0,0,0", "0,0,0"),
            },
            "events": {},
        }
        records = parse_section(data["frames"])
        counts = analyze(records, [], data["config"])
        self.assertEqual(counts["slide"], 1)
        self.assertEqual(counts["gap"], 1)

    def test_spike_and_teleport(self) -> None:
        data = {
            "config": {"hero": "Tosh", "a4": "Ref_Center"},
            "frames": {
                "p1_1": frame(100, 1, 0, 0, "0,0,0", "0,0,0"),
                "p1_2": frame(200, 2, 100, 0, "200,0,0", "0,0,0"),
            },
            "events": {},
        }
        records = parse_section(data["frames"])
        counts = analyze(records, [], data["config"])
        self.assertEqual(counts["spike"], 1)
        self.assertEqual(counts["teleport"], 1)

    def test_frame_wrap(self) -> None:
        data = {
            "config": {"hero": "Tosh", "a4": "Ref_Center"},
            "frames": {
                "p1_1": frame(100, 1, 0, 0, "0,0,0", "0,0,0", lframe=80),
                "p1_2": frame(200, 2, 0, 0, "0,0,0", "0,0,0", lframe=0),
            },
            "events": {},
        }
        records = parse_section(data["frames"])
        counts = analyze(records, [], data["config"])
        self.assertEqual(counts["frame_wrap"], 1)

    def test_churn(self) -> None:
        frames = {
            "p1_1": frame(100, 1, 0, 0, "0,0,0", "0,0,0"),
            "p1_2": frame(1100, 2, 0, 0, "0,0,0", "0,0,0"),
        }
        events = {
            f"p1_{index}_1": f"ms={index} seq={index} kind=lower_start clip=Walk flags=0 up=2 lo=1"
            for index in range(20)
        }
        records = parse_section(frames)
        parsed_events = parse_section(events)
        counts = analyze(records, parsed_events, {"hero": "Tosh"})
        self.assertEqual(counts["churn"], 1)


if __name__ == "__main__":
    unittest.main()