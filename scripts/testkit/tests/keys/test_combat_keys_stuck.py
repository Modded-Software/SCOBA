"""Host tests of the stuck recorder checks (SPEC-POINT-AND-CLICK 5.8b)."""

from __future__ import annotations

import contextlib
import io
import unittest

from testkit.checks import Checks
from testkit.profiles import combat
from testkit.profiles.combat_parts import combat_keys_stuck as stuck

ENTRY = (
    "ms=41000 pos=100.00;118.50 travel=0.00 raw=1 keys=1 flags=1 held=0 strafe=0 aim=0 root=0 ticks=900 steps=140"
    " orders=1 order0=move@point,d0.50 hero=ToshSCOBA alive=1 facing=90 camYaw=90 speed=3.10 mouseFwd=0 scene=0 tps=0"
    " orderMode=0 free=0 mright=0 rorbit=0 lorbit=0 rotUnit=0 rotCam=0 stand=1 moveSup=0 turnSup=0 stun=1 hidden=0"
    " jump=0 hasTarget=0 order1=none order2=none path=here:1,cliff1.0,heading90,d0.5:11,d2.0:11,d6.0:11"
    " behaviors=SCOBAChaseStand*1, near="
)

# Counters at the tags a to j: (Stucks, Frees, KeyOffs, Seq, Ticks, Steps,
# KeyEdges, AnyEdges, BtnEdges). The tags in the order of the scenario:
# a b c d e f, i j, g h.
KEYS = ("Stucks", "Frees", "KeyOffs", "Seq", "Ticks", "Steps", "KeyEdges", "AnyEdges", "BtnEdges")
COUNTS = {
    "a": (2, 1, 5, 380, 600, 100, 40, 76, 14),
    "b": (2, 1, 5, 380, 616, 100, 40, 76, 14),
    "c": (2, 1, 5, 380, 640, 124, 41, 76, 14),
    "d": (3, 1, 5, 418, 664, 148, 41, 76, 14),
    "e": (3, 1, 5, 418, 680, 164, 41, 76, 14),
    "f": (3, 2, 5, 419, 704, 188, 41, 76, 14),
    "i": (3, 2, 5, 419, 710, 188, 42, 76, 14),
    "j": (3, 2, 5, 419, 758, 236, 45, 76, 14),
    "g": (3, 2, 5, 419, 760, 236, 46, 76, 14),
    "h": (3, 2, 6, 420, 768, 244, 46, 76, 14),
}
# Hero position x10 at the snapshots, camera yaw 90: forward is +y.
SNAPS = {"f0": (1000, 1000), "f1": (1000, 1045), "s1": (1000, 1046), "s2": (1000, 1080)}


def stuck_section(**over) -> dict:
    """The bank section of a run in which the recorder behaves."""
    values: dict = {"stuckText": ENTRY}
    for tag, row in COUNTS.items():
        for key, value in zip(KEYS, row, strict=True):
            values[tag + key] = value
    for tag, (x10, y10) in SNAPS.items():
        values[tag + "HeroX10"] = x10
        values[tag + "HeroY10"] = y10
    values.update(over)
    return values


def failed(section: dict) -> list[str]:
    checks = Checks({stuck.SECTION: section})
    with contextlib.redirect_stdout(io.StringIO()):
        stuck.check_stuck(checks)
    return [str(r["section"]) for r in checks.results if r["status"] == "FAIL"]


class StuckCheckTests(unittest.TestCase):
    def assert_fails(self, section: dict, name: str) -> None:
        got = failed(section)
        self.assertTrue(any(name in item for item in got), f"{name} not in {got}")

    def test_passing_section(self) -> None:
        self.assertEqual(failed(stuck_section()), [])

    def test_empty_section_fails(self) -> None:
        # Negative: a run that wrote nothing proves nothing.
        self.assertGreater(len(failed({})), 20)

    def test_entry_for_a_stand_with_no_key(self) -> None:
        self.assert_fails(stuck_section(bStucks=3), "no entry for a stand with no key")

    def test_entry_for_a_walk(self) -> None:
        self.assert_fails(stuck_section(cStucks=3), "no entry for a walk")

    def test_no_entry_when_the_hero_stands_on_a_key(self) -> None:
        self.assert_fails(stuck_section(dStucks=2), "one stuck entry")

    def test_an_entry_each_loop(self) -> None:
        self.assert_fails(stuck_section(eStucks=9), "no second entry while it stands")

    def test_hero_was_not_held(self) -> None:
        # Negative: an entry while the hero walked on proves nothing.
        self.assert_fails(stuck_section(s1HeroY10=1090), "the stunned hero stands")

    def test_entry_does_not_name_the_stun(self) -> None:
        self.assert_fails(stuck_section(stuckText=ENTRY.replace("stun=1", "stun=0")), "stuck entry stun")

    def test_entry_lacks_the_orders(self) -> None:
        self.assert_fails(stuck_section(stuckText=ENTRY.replace("order0=", "o=")), "stuck entry has order0")

    def test_script_did_not_step(self) -> None:
        self.assert_fails(stuck_section(dSteps=124), "the script kept stepping: Steps")

    def test_rows_before_not_written(self) -> None:
        self.assert_fails(stuck_section(dSeq=381), "entry, its rows and its edges written")

    def test_edges_not_written_with_the_entry(self) -> None:
        # The entry and its 32 rows, no `edges` entry.
        self.assert_fails(stuck_section(dSeq=413), "entry, its rows and its edges written")

    def test_key_edge_not_in_the_edge_log(self) -> None:
        self.assert_fails(stuck_section(cKeyEdges=40), "W down is one key edge")

    def test_key_edge_while_the_key_stays_down(self) -> None:
        self.assert_fails(stuck_section(dKeyEdges=42), "no key edge while W stays down")

    def test_real_input_in_a_script_only_section(self) -> None:
        # Negative: the any-key and button triggers hear real input only.
        self.assert_fails(stuck_section(hAnyEdges=77), "no any-key edge from script keys")
        self.assert_fails(stuck_section(hBtnEdges=15), "no button edge from script keys")

    def test_no_free_entry(self) -> None:
        self.assert_fails(stuck_section(fFrees=1), "one free entry")

    def test_hero_stays_after_the_stun(self) -> None:
        self.assert_fails(stuck_section(s2HeroY10=1046), "walks when the stun ends")

    def test_keys_entry_while_both_agree(self) -> None:
        self.assert_fails(stuck_section(dKeyOffs=6), "no keys entry while both agree")

    def test_no_keys_entry_for_a_script_only_key(self) -> None:
        self.assert_fails(stuck_section(hKeyOffs=5), "one keys entry")

    def test_entry_for_a_turn_around(self) -> None:
        self.assert_fails(stuck_section(jStucks=4), "no entry for a turn-around")

    def test_entry_fields(self) -> None:
        fields = stuck.entry_fields(ENTRY)
        self.assertEqual(fields["order0"], "move@point,d0.50")
        self.assertEqual(fields["near"], "")
        self.assertEqual(stuck.entry_fields(None), {})

    def test_harness_file_is_in_the_map(self) -> None:
        names = [path.name for path in combat.map_spec().galaxy_files]
        self.assertLess(names.index("combat_keys.galaxy"), names.index("combat_keys_stuck.galaxy"))
        self.assertLess(names.index("combat_keys_stuck.galaxy"), names.index("combat.galaxy"))
        self.assertIn("scripts/test/combat/combat_keys_stuck", combat.map_spec().galaxy_includes)


if __name__ == "__main__":
    unittest.main()
