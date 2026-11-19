"""Host tests for scripts/mapgen/player_slots.py (REQ-ROSTER seats and base owners)."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from mapgen import player_slots
from project_root import project_root

SRC = project_root() / "src" / "SCOBA.SC2Map"
ROSTER = SRC / "scripts" / "app" / "core" / "roster.galaxy"


class PlayerSlotsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.data = (SRC / "MapInfo").read_bytes()
        self.text = (SRC / "Attributes").read_text(encoding="utf-8").replace("\r\n", "\n")

    def test_source_records(self) -> None:
        records = player_slots.find_records(self.data)
        self.assertEqual([r.pid for r in records], list(range(16)))
        by_id = {r.pid: r for r in records}
        self.assertEqual(by_id[1].control, 1)
        self.assertEqual(by_id[2].control, 2)
        self.assertEqual(by_id[2].race, b"Terr")
        self.assertEqual(by_id[5].race, b"Zerg")
        for pid in range(9, 15):
            self.assertEqual((by_id[pid].control, by_id[pid].race), (3, b""), pid)

    def test_table(self) -> None:
        self.assertEqual(sorted(player_slots.BASE_OWNERS), [9, 10, 11, 12, 13, 14])
        want = player_slots.slots()
        self.assertEqual(sorted(want), [1, 2, 3, 4, 5, 6, 9, 10, 11, 12, 13, 14])
        for seat in (1, 2, 3):
            self.assertEqual((want[seat].control, want[seat].race, want[seat].locked), (1, "Terr", False))
        for seat in (4, 5, 6):
            self.assertEqual((want[seat].control, want[seat].race, want[seat].locked), (2, "Zerg", True))

    def test_patch_records(self) -> None:
        before = {r.pid: r for r in player_slots.find_records(self.data)}
        after = {r.pid: r for r in player_slots.find_records(player_slots.patch_mapinfo(self.data))}
        for pid, slot in player_slots.slots().items():
            self.assertEqual((after[pid].control, after[pid].race), (slot.control, slot.race.encode("ascii")), pid)
        for pid in (0, 7, 8, 15):
            self.assertEqual((after[pid].control, after[pid].race), (before[pid].control, before[pid].race), pid)

    def test_patch_keeps_tail(self) -> None:
        patched = player_slots.patch_mapinfo(self.data)
        tail = player_slots.find_records(self.data)[-1].end
        self.assertEqual(len(patched), len(self.data) + 6 * 4)
        self.assertEqual(patched[tail + 24 :], self.data[tail:])

    def test_patch_idempotent(self) -> None:
        patched = player_slots.patch_mapinfo(self.data)
        self.assertEqual(player_slots.patch_mapinfo(patched), patched)
        out = player_slots.patch_attributes(self.text)
        self.assertEqual(player_slots.patch_attributes(out), out)

    def test_attributes(self) -> None:
        out = player_slots.lobby(player_slots.patch_attributes(self.text))
        for pid, slot in player_slots.slots().items():
            self.assertEqual(out[pid], (slot.lobby, slot.locked), pid)
        for pid in (0, 7, 8):
            self.assertEqual(out[pid], player_slots.lobby(self.text)[pid], pid)

    def test_apply_and_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            map_dir = Path(tmp)
            shutil.copy2(SRC / "MapInfo", map_dir / "MapInfo")
            shutil.copy2(SRC / "Attributes", map_dir / "Attributes")
            self.assertTrue(player_slots.check(map_dir))
            player_slots.apply(map_dir)
            self.assertEqual(player_slots.check(map_dir), [])
            self.assertIn(b"\r\n", (map_dir / "Attributes").read_bytes())

    def test_script_agrees(self) -> None:
        self.assertEqual(player_slots.check_script(ROSTER.read_text(encoding="utf-8")), [])
        bad = ROSTER.read_text(encoding="utf-8").replace("if (lp_lane == 2) { return 11; }", "if (lp_lane == 2) { return 2; }")
        self.assertTrue(player_slots.check_script(bad))

    def test_script_owner_outside_table(self) -> None:
        good = ROSTER.read_text(encoding="utf-8")
        extra = good.replace("    if (lp_lane == 6) { return 14; }\n", "    if (lp_lane == 6) { return 14; }\n    if (lp_lane == 7) { return 7; }\n")
        self.assertIn("roster: owner 7 not in the table", player_slots.check_script(extra))
        fallback = good.replace("    return 0;\n}\n\n// Lane -> seat", "    return 9;\n}\n\n// Lane -> seat")
        self.assertIn("roster: gf_RosterOwner must end with one 'return 0;'", player_slots.check_script(fallback))


if __name__ == "__main__":
    unittest.main()
