"""Host tests of the WASD key checks (R-PNC-57 to 59, combat group `keys`)."""

from __future__ import annotations

import contextlib
import io
import sys
import unittest
from unittest import mock

from testkit.checks import Checks
from testkit.profiles import combat
from testkit.profiles.combat_parts import combat_keys
from testkit.tests.keys.test_combat_keys_race import race_section
from testkit.tests.keys.test_combat_keys_real import combo_section
from testkit.tests.keys.test_combat_keys_stuck import stuck_section

# Camera yaw 90: forward is +y, left is -x.
YAW = 90


def snap(bank: dict, section: str, tag: str, x10: int, y10: int, **values) -> None:
    row = {"HeroX10": x10, "HeroY10": y10, "CamYaw": YAW, "Root": 0, "MoveOrder": False, "HoldStrafe": False}
    row.update(values)
    for key, value in row.items():
        bank.setdefault(section, {})[tag + key] = value


def released(bank: dict, section: str, prefix: str, x10: int, y10: int, root: int = 1) -> None:
    snap(bank, section, prefix + "stop", x10, y10, Root=root)
    snap(bank, section, prefix + "end", x10, y10, Root=root)
    bank[section].update({"keysSent": 4, "keysRun": 4})


def passing() -> dict:
    """A bank of a run in which every key behaves as R-PNC-57 to 59 demand."""
    bank: dict = {}
    snap(bank, "key_hold", "t0000", 0, 0, Root=1)
    snap(bank, "key_hold", "tmove", 0, 30, MoveOrder=True)
    snap(bank, "key_hold", "tmore", 0, 60, MoveOrder=True)
    released(bank, "key_hold", "t", 0, 62)
    snap(bank, "key_retap", "t0000", 0, 15)
    snap(bank, "key_retap", "tmove", 0, 45, MoveOrder=True)
    released(bank, "key_retap", "t", 0, 47)
    for section, step in (("key_ws", (0, 1)), ("key_ad", (-1, 0))):
        snap(bank, section, "t0000", 0, 0, Root=1)
        snap(bank, section, "ta", 30 * step[0], 30 * step[1])
        snap(bank, section, "tb", 10 * step[0], 10 * step[1])
        snap(bank, section, "ta2", 30 * step[0], 30 * step[1])
        released(bank, section, "t", 32 * step[0], 32 * step[1])
    snap(bank, "key_order", "c0", 0, 0)
    snap(bank, "key_order", "c1", 0, -15, MoveOrder=True)
    snap(bank, "key_order", "c2", 0, 10, MoveOrder=True)
    released(bank, "key_order", "c", 0, 12, root=0)
    snap(bank, "key_order", "m0", 0, 0)
    snap(bank, "key_order", "m1", 0, 30, MoveOrder=True)
    released(bank, "key_order", "m", 0, 32, root=0)
    snap(bank, "key_order", "h0", 0, 15, MoveOrder=True)
    snap(bank, "key_order", "h1", 0, 45, MoveOrder=True)
    released(bank, "key_order", "h", 0, 47, root=0)
    bank["key_order"].update(
        {"clickBefore10": 0, "clickAfter10": 60, "m0OrderMode": True, "m1OrderMode": True, "h0OrderMode": True}
    )
    snap(bank, "key_scene", "t0000", 0, 0, Root=1)
    snap(bank, "key_scene", "thold", 0, 0, Root=1)
    snap(bank, "key_scene", "tfree", 0, 30, MoveOrder=True)
    released(bank, "key_scene", "t", 0, 32)
    snap(bank, "key_scene", "r0", 0, 0, Root=1)
    snap(bank, "key_scene", "r1", -20, 0, MoveOrder=True)
    for tag in ("r2", "r3", "r4"):
        snap(bank, "key_scene", tag, -22, 0, Root=1)
    released(bank, "key_scene", "r", -22, 0)
    bank["key_scene"].update({"held": True, "heldAfter": False})
    snap(bank, "key_strafe", "o0", 0, 0, HoldStrafe=True)
    snap(bank, "key_strafe", "o1", 0, 30, HoldStrafe=True, MoveOrder=True)
    released(bank, "key_strafe", "o", 0, 32)
    snap(bank, "key_strafe", "w0", 0, 0, HoldStrafe=True)
    snap(bank, "key_strafe", "w1", 0, 34, HoldStrafe=True, MoveOrder=True)
    released(bank, "key_strafe", "w", 0, 35)
    bank["key_strafe"].update({"reachOpen": "nnnnnnnnnnnyy", "reachWall": "nnnnnnnnnnnnn", "wallCount": 11, "wallOff10": 0})
    snap(bank, "key_real", "k0", 0, 0, Root=1)
    snap(bank, "key_real", "k1", 0, 30, MoveOrder=True)
    snap(bank, "key_real", "kstop", 0, 90, Root=1)
    snap(bank, "key_real", "kend", 0, 90, Root=1)
    bank["key_real"].update({"waiting": 0, "downSeen": True, "upSeen": True, "k1Forward": True, "k1InputHeld": False})
    snap(bank, "key_tps", "p0", 0, 0, HoldStrafe=True)
    snap(bank, "key_tps", "p1", 0, 30, HoldStrafe=True, MoveOrder=True)
    released(bank, "key_tps", "p", 0, 32)
    snap(bank, "key_tps", "q0", 0, 32, HoldStrafe=True)
    snap(bank, "key_tps", "q1", -30, 32, HoldStrafe=True, MoveOrder=True)
    released(bank, "key_tps", "q", -32, 32)
    bank["key_tps"].update({"tpsOn": True, "tpsAfter": False, "p1Forward": True, "p1InputHeld": False})
    bank["key_spot"] = {"found": True, "ring": 1, "dir": 2, "row": "18 " * 8, "anchorOpen": 0, "anchorRow": "0 " * 8}
    bank["key_combo"] = combo_section()
    bank["key_race"] = race_section()
    bank["key_stuck"] = stuck_section()
    return bank


def failed(bank: dict) -> list[str]:
    """Names of the failed checks of a bank."""
    checks = Checks(bank)
    with contextlib.redirect_stdout(io.StringIO()):
        combat_keys.check_keys(checks)
    return [f"{r['section']} {r['tag']} {r['key']}".strip() for r in checks.results if r["status"] == "FAIL"]


class KeyChecksTests(unittest.TestCase):
    def test_group_is_registered(self) -> None:
        self.assertIn("keys", combat.GROUPS)
        self.assertIs(combat.GROUP_CHECKS["keys"], combat_keys.check_keys)

    def test_passing_bank(self) -> None:
        self.assertEqual(failed(passing()), [])

    def test_empty_bank_fails(self) -> None:
        # Negative: a run that wrote nothing proves nothing.
        self.assertGreater(len(failed({})), 20)

    def assert_fails(self, bank: dict, name: str) -> None:
        got = failed(bank)
        self.assertTrue(any(name in item for item in got), f"{name} not in {got}")

    def test_key_down_but_hero_stands(self) -> None:
        bank = passing()
        snap(bank, "key_hold", "tmore", 0, 30, MoveOrder=True)
        self.assert_fails(bank, "key_hold tmove->tmore W keeps walking")

    def test_root_left_on_after_retap(self) -> None:
        bank = passing()
        snap(bank, "key_retap", "tmove", 0, 15, Root=1, MoveOrder=True)
        got = failed(bank)
        self.assertIn("key_retap t0000->tmove W walks on after the retap", got)
        self.assertIn("key_retap tmove Root", got)

    def test_travel_after_the_release(self) -> None:
        bank = passing()
        snap(bank, "key_hold", "tend", 0, 80, Root=1)
        self.assert_fails(bank, "key_hold tstop->tend no travel after the release")

    def test_last_key_does_not_win(self) -> None:
        bank = passing()
        snap(bank, "key_ws", "tb", 0, 30)
        self.assert_fails(bank, "key_ws ta->tb last key wins")

    def test_first_key_lost_after_the_release(self) -> None:
        bank = passing()
        snap(bank, "key_ad", "ta2", -10, 0)
        self.assert_fails(bank, "key_ad tb->ta2 first key walks again")

    def test_click_move_survives_the_key(self) -> None:
        bank = passing()
        bank["key_order"]["clickAfter10"] = 0
        self.assert_fails(bank, "key_order W replaces the click move in one loop")

    def test_key_dropped_in_order_mode(self) -> None:
        bank = passing()
        snap(bank, "key_order", "m1", 0, 0)
        self.assert_fails(bank, "key_order m0->m1 W walks in order mode")

    def test_travel_in_the_hold(self) -> None:
        bank = passing()
        snap(bank, "key_scene", "thold", 0, 30)
        self.assert_fails(bank, "key_scene t0000->thold no travel in the hold")

    def test_key_dropped_in_the_hold(self) -> None:
        bank = passing()
        snap(bank, "key_scene", "tfree", 0, 0)
        self.assert_fails(bank, "key_scene thold->tfree W walks when the hold ends")

    def test_release_dropped_in_the_hold(self) -> None:
        bank = passing()
        snap(bank, "key_scene", "r4", -52, 0)
        self.assert_fails(bank, "key_scene r3->r4 keys released in the hold")

    def test_no_step_at_the_block(self) -> None:
        bank = passing()
        snap(bank, "key_strafe", "w1", 0, 0, HoldStrafe=True)
        self.assert_fails(bank, "key_strafe w0->w1 W walks up to the block")

    def test_hero_enters_the_block(self) -> None:
        bank = passing()
        snap(bank, "key_strafe", "w1", 0, 60, HoldStrafe=True)
        self.assert_fails(bank, "key_strafe stops at the block")

    def test_block_not_arranged(self) -> None:
        bank = passing()
        bank["key_strafe"]["reachWall"] = "yynnnnnnnnnnn"
        self.assert_fails(bank, "key_strafe block covers every far point")

    def test_real_key_not_seen(self) -> None:
        bank = passing()
        bank["key_real"]["downSeen"] = False
        self.assert_fails(bank, "key_real  downSeen")

    def test_real_key_seen_but_hero_stands(self) -> None:
        bank = passing()
        snap(bank, "key_real", "k1", 0, 0)
        self.assert_fails(bank, "key_real k0->k1 a real W key walks")

    def test_real_key_release_not_seen(self) -> None:
        bank = passing()
        bank["key_real"]["upSeen"] = False
        self.assert_fails(bank, "key_real  upSeen")

    def test_no_real_key_unless_the_harness_waits(self) -> None:
        # Negative: no key goes to the desktop in another group or after the case.
        with mock.patch.dict(sys.modules, {"testkit.input_driver": None}):
            combat_keys.press_real_key({"meta": {"ready": 1}})
            combat_keys.press_real_key({"key_real": {"waiting": 0}})

    def test_real_key_down_then_up(self) -> None:
        driver = mock.Mock()
        with mock.patch.dict(sys.modules, {"testkit.input_driver": driver}), mock.patch.object(combat_keys.time, "sleep"):
            combat_keys.press_real_key({"key_real": {"waiting": 1}})
        names = [call[0] for call in driver.method_calls]
        self.assertEqual(names, ["focus", "key_down", "focus", "key_up"])
        driver.key_down.assert_called_once_with("w")
        driver.key_up.assert_called_once_with("w")

    def test_key_down_in_tps_but_hero_stands(self) -> None:
        bank = passing()
        snap(bank, "key_tps", "p1", 0, 0, HoldStrafe=True)
        self.assert_fails(bank, "key_tps p0->p1 W walks in TPS")

    def test_tps_not_on(self) -> None:
        # Negative: a walk outside TPS does not prove the TPS case.
        bank = passing()
        bank["key_tps"]["tpsOn"] = False
        self.assert_fails(bank, "key_tps  tpsOn")

    def test_no_free_ground(self) -> None:
        bank = passing()
        bank["key_spot"]["found"] = False
        self.assert_fails(bank, "key_spot  found")

    def test_key_call_did_not_run(self) -> None:
        bank = passing()
        bank["key_hold"]["keysRun"] = 3
        self.assert_fails(bank, "key_hold t every key call ran")


if __name__ == "__main__":
    unittest.main()
