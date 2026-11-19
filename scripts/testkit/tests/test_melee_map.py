"""Host tests for scripts/mapgen/melee_map.py and the melee rules of REQ-BASE-AI 3.5."""

from __future__ import annotations

import re
import shutil
import struct
import tempfile
import unittest
from pathlib import Path

from mapgen import melee_map
from mapgen import player_slots
from project_root import project_root

SRC = project_root() / "src" / "SCOBA.SC2Map"
APP = SRC / "scripts" / "app"


def _galaxy() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted(APP.rglob("*.galaxy")))


class MeleeMapTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        for name in ("MapInfo", "Objects", "Regions", "Attributes"):
            shutil.copy2(SRC / name, self.tmp / name)
        player_slots.apply(self.tmp)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp)

    def test_apply_then_check_passes(self) -> None:
        melee_map.apply(self.tmp)
        self.assertEqual(melee_map.check(self.tmp), [])

    def test_one_start_per_owner_at_its_spawn(self) -> None:
        melee_map.apply(self.tmp)
        objects = (self.tmp / "Objects").read_text(encoding="utf-8")
        points = re.findall(r'<ObjectPoint Id="(\d+)" Position="([^"]+)"[^>]*Type="StartLoc"', objects)
        owners = sorted(player_slots.BASE_OWNERS)
        self.assertEqual(sorted(int(i) for i, _ in points), [melee_map.start_id(o) for o in owners])
        centres = melee_map.region_centres((self.tmp / "Regions").read_text(encoding="utf-8"))
        for lane, (_seat, owner, _race) in player_slots.LANES.items():
            x, y = centres[melee_map.LANE_REGION[lane]]
            at = dict(points)[str(melee_map.start_id(owner))].split(",")
            self.assertLessEqual(abs(float(at[0]) - x), 0.5)
            self.assertLessEqual(abs(float(at[1]) - y), 0.5)

    def test_records_point_at_start_ids_only_for_owners(self) -> None:
        melee_map.apply(self.tmp)
        data = (self.tmp / "MapInfo").read_bytes()
        for record in player_slots.find_records(data):
            got = struct.unpack_from("<I", data, melee_map._start_at(data, record))[0]
            want = melee_map.start_id(record.pid) if record.pid in player_slots.BASE_OWNERS else 0
            self.assertEqual(got, want, f"player {record.pid}")

    def test_record_sizes_unchanged(self) -> None:
        before = (self.tmp / "MapInfo").read_bytes()
        melee_map.apply(self.tmp)
        self.assertEqual(len((self.tmp / "MapInfo").read_bytes()), len(before))

    def test_check_finds_missing_start(self) -> None:
        # Negative: the unpatched map fails the check.
        errors = melee_map.check(self.tmp)
        self.assertTrue(any("start locations: 0" in e for e in errors), errors)

    def test_apply_twice_fails(self) -> None:
        melee_map.apply(self.tmp)
        with self.assertRaises(SystemExit):
            melee_map.apply(self.tmp)

    def test_source_depots_two_per_terran_owner(self) -> None:
        objects = (SRC / "Objects").read_text(encoding="utf-8")
        owners = re.findall(r'UnitType="SupplyDepot" Player="(\d+)"', objects)
        self.assertEqual(sorted(owners), ["11", "11", "12", "12", "9", "9"])
        self.assertNotIn("7", owners)


class MeleeScriptTest(unittest.TestCase):
    def test_stock_start_and_no_driver(self) -> None:
        text = _galaxy()
        self.assertIn("AIMeleeStart(lp_player);", text)
        # R-BASE-27: no copy of the stock body.
        self.assertNotIn("AIDeclareTown(", text)
        # R-BASE-28: the stock AI expands and attacks on its own.
        self.assertNotIn("AIExpand(", text)
        self.assertNotIn("AISetAttackState(", text)
        self.assertIn("PlayerStartLocation(lv_owner)", text)


if __name__ == "__main__":
    unittest.main()
