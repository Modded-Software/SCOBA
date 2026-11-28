"""Host tests of the real input case `key_combo` (R-PNC-57 to 59)."""

from __future__ import annotations

import contextlib
import io
import math
import sys
import unittest
from pathlib import Path
from unittest import mock

from testkit.checks import Checks
from testkit.profiles import combat
from testkit.profiles.combat_parts import combat_keys_real as real
from testkit.tests.keys.test_combat_keys_log import edge_values, host_lines

W, S, A, D = 1, 2, 4, 8
# Travel of one game loop of a walking hero.
STEP = 0.19


def part(keys: int, rows: int, turn: float = 0.0, aim: int = 0, travel: int | None = None) -> tuple:
    """`rows` game loops with `keys` down. `travel`: the keys the hero obeys."""
    return keys, rows, turn, aim, keys if travel is None else travel


def hold(first: int, second: int, *inside: tuple) -> tuple[tuple, ...]:
    """A pair as the host sends it: first key, both, first key, none."""
    return (part(first, 2), *inside, part(first, 2), part(0, 8))


def passing_parts() -> tuple[tuple, ...]:
    return (
        *hold(A, W, part(A | W, 25)),
        *hold(D, S, part(S | D, 25)),
        *hold(W, A, part(W | A, 8), part(W | A, 9, aim=1), part(W | A, 8)),
        *hold(S, D, part(S | D, 25)),
        *hold(W, A, part(W | A, 5), part(W | A, 15, turn=4.0), part(W | A, 5)),
        *hold(S, D, part(S | D, 5), part(S | D, 15, turn=-4.0), part(S | D, 5)),
        *hold(W, A, part(W | A, 8), part(W | A, 9, aim=1), part(W | A, 8)),
        *hold(S, D, part(S | D, 25)),
    )


def rows_of(parts: tuple[tuple, ...]) -> list[tuple[int, ...]]:
    """The rows the harness writes for a hero that walks as `travel` asks."""
    x = y = 100.0
    yaw = 90.0
    rows = []
    for keys, count, turn, aim, travel in parts:
        for _ in range(count):
            yaw += turn
            heading = real.key_heading(travel)
            if heading is not None:
                x += STEP * math.cos(math.radians(yaw + heading))
                y += STEP * math.sin(math.radians(yaw + heading))
            rows.append((keys, keys, keys, aim, 1 if keys else 0, round(x * 100), round(y * 100), round(yaw) % 360))
    return rows


def combo_section(rows: list[tuple[int, ...]] | None = None, **over) -> dict:
    """The bank section of a run in which every key behaves."""
    rows = rows_of(passing_parts()) if rows is None else rows
    downs, ups = real.sent_edges()
    values: dict = {"tpsOn": True, "started": True, "tpsAfter": False, "rows": len(rows), "looseUps": 0, "repeats": 0}
    values.update({"rawEnd": 0, "scriptEnd": 0, "clicks0": 0, "clicks1": real.sent_buttons(), "edgeLog": "", "cendMoveOrder": False})
    values.update({"stucks0": 2, "stucks1": 2, "keyOffs0": 4, "keyOffs1": 4, "btnLeft": 3, "btnMiddle": 2, "btnRight": 2})
    for index in range(4):
        values[f"downs{index}"] = downs[index]
        values[f"ups{index}"] = ups[index]
    chunks = [rows[start : start + 30] for start in range(0, len(rows), 30)]
    for index, chunk in enumerate(chunks):
        values[f"trace{index}"] = "".join(" ".join(str(value) for value in row) + ";" for row in chunk)
    values["chunks"] = len(chunks)
    values.update(edge_values())
    values.update(over)
    return values


def failed(section: dict) -> list[str]:
    """Names of the failed checks of a key_combo section."""
    checks = Checks({real.SECTION: section})
    with contextlib.redirect_stdout(io.StringIO()):
        real.check_combo(checks)
    return [f"{r['section']} {r['tag']} {r['key']}".strip() for r in checks.results if r["status"] == "FAIL"]


def swap(parts: tuple[tuple, ...], index: int, *new: tuple) -> tuple[tuple, ...]:
    return (*parts[:index], *new, *parts[index + 1 :])


class ComboCheckTests(unittest.TestCase):
    def assert_fails(self, section: dict, name: str) -> None:
        got = failed(section)
        self.assertTrue(any(name in item for item in got), f"{name} not in {got}")

    def test_passing_section(self) -> None:
        self.assertEqual(failed(combo_section()), [])

    def test_empty_section_fails(self) -> None:
        # Negative: a run that wrote nothing proves nothing.
        self.assertGreater(len(failed({})), 12)

    def test_key_up_the_host_did_not_send(self) -> None:
        section = combo_section()
        section["ups2"] += 1
        self.assert_fails(section, "key ups as sent")

    def test_key_down_not_seen(self) -> None:
        section = combo_section()
        section["downs0"] -= 1
        self.assert_fails(section, "key downs as sent")

    def test_key_left_down_at_the_end(self) -> None:
        self.assert_fails(combo_section(scriptEnd=4), "scriptEnd")
        self.assert_fails(combo_section(looseUps=1), "looseUps")

    def test_script_drops_a_key_that_is_down(self) -> None:
        # Operator 2026-11-27: A and W are down, the script holds W only.
        rows = [(k, W if k == (W | A) else sc, f, *rest) for k, sc, f, *rest in rows_of(passing_parts())]
        self.assert_fails(combo_section(rows), "script key state follows the keys")

    def test_direction_flag_dropped(self) -> None:
        rows = [(k, sc, W if k == (W | A) else f, *rest) for k, sc, f, *rest in rows_of(passing_parts())]
        self.assert_fails(combo_section(rows), "direction flags follow the keys")

    def test_two_keys_down_but_hero_walks_straight(self) -> None:
        # Operator 2026-11-27: no 45 degree travel with A and W held.
        parts = swap(passing_parts(), 1, part(A | W, 25, travel=W))
        got = failed(combo_section(rows_of(parts)))
        self.assertIn("key_combo no stretch off the heading of the keys", got)

    def test_every_pair_walks_straight(self) -> None:
        parts = tuple(part(k, n, t, a, W) if k == (W | A) else (k, n, t, a, tr) for k, n, t, a, tr in passing_parts())
        self.assert_fails(combo_section(rows_of(parts)), "W+A travels on the heading of both keys")

    def test_stall_with_keys_down(self) -> None:
        parts = swap(passing_parts(), 1, part(A | W, 10), part(A | W, 6, travel=0), part(A | W, 9))
        self.assert_fails(combo_section(rows_of(parts)), "no stall with a key down")

    def test_short_stall_is_not_a_finding(self) -> None:
        # Under 0.25 game seconds: the window is wider than one step.
        parts = swap(passing_parts(), 1, part(A | W, 10), part(A | W, real.RUN - 1, travel=0), part(A | W, 12))
        self.assertEqual(failed(combo_section(rows_of(parts))), [])

    def test_keys_never_held_together(self) -> None:
        parts = tuple(p for p in passing_parts() if p[0] != (S | D))
        self.assert_fails(combo_section(rows_of(parts)), "S+D held together")

    def test_no_aim_in_the_run(self) -> None:
        parts = tuple((k, n, t, 0, tr) for k, n, t, _a, tr in passing_parts())
        self.assert_fails(combo_section(rows_of(parts)), "aim with a key down")

    def test_camera_did_not_turn(self) -> None:
        parts = tuple((k, n, 0.0, a, tr) for k, n, _t, a, tr in passing_parts())
        self.assert_fails(combo_section(rows_of(parts)), "camera turned with a key down")

    def test_click_the_host_did_not_send(self) -> None:
        self.assert_fails(combo_section(clicks1=real.sent_buttons() + 1), "mouse buttons as sent")

    def test_recorder_missed_a_real_key(self) -> None:
        self.assert_fails(combo_section(keyOffs1=5), "recorder key state follows the real keys")

    def test_stuck_entry_with_the_keys_down(self) -> None:
        self.assert_fails(combo_section(stucks1=3), "no stuck entry with the keys down")

    def test_rows_lost(self) -> None:
        section = combo_section()
        section["rows"] += 30
        self.assert_fails(section, "trace complete")

    def test_move_order_left_after_the_release(self) -> None:
        self.assert_fails(combo_section(cendMoveOrder=True), "cend MoveOrder")

    def test_tps_not_on(self) -> None:
        self.assert_fails(combo_section(tpsOn=False), "tpsOn")


class ComboHeadingTests(unittest.TestCase):
    def test_key_heading(self) -> None:
        self.assertAlmostEqual(real.key_heading(W | A), 45.0)
        self.assertAlmostEqual(real.key_heading(S | D), -135.0)
        self.assertAlmostEqual(real.key_heading(A), 90.0)
        self.assertIsNone(real.key_heading(0))
        self.assertIsNone(real.key_heading(W | S))

    def test_rows_with_a_wrong_field_count_are_not_rows(self) -> None:
        self.assertEqual(real.trace_rows({"chunks": 1, "trace0": "1 1 1 0 1 100 100 90;5 5;"}), [(1, 1, 1, 0, 1, 100, 100, 90)])


class ComboSequenceTests(unittest.TestCase):
    def driver(self) -> mock.Mock:
        driver = mock.Mock()
        driver.center_point.return_value = (640, 360)
        return driver

    def test_every_key_and_button_goes_up(self) -> None:
        downs, ups = real.sent_edges()
        self.assertEqual(downs, ups)
        self.assertEqual(downs, [4, 4, 4, 4])
        presses = sum(1 for step in real.SEQUENCE if step[0] == "press")
        releases = sum(1 for step in real.SEQUENCE if step[0] == "release")
        self.assertEqual(presses, releases)
        self.assertEqual(real.sent_buttons(), 7)

    def test_mark_key_goes_down_with_two_keys_held(self) -> None:
        # Operator 2026-11-27: M is pressed while a direction key is held.
        down: set[str] = set()
        held_at_mark = None
        for step in real.SEQUENCE:
            if step == ("down", "m"):
                held_at_mark = set(down)
            if step[0] == "down":
                down.add(step[1])
            elif step[0] == "up":
                down.discard(step[1])
        self.assertEqual(held_at_mark, {"s", "d"})

    def test_no_opposite_keys_together(self) -> None:
        # The checks take the travel heading from the keys down.
        down: set[str] = set()
        for step in real.SEQUENCE:
            if step[0] == "down":
                down.add(step[1])
            elif step[0] == "up":
                down.discard(step[1])
            self.assertFalse({"w", "s"} <= down or {"a", "d"} <= down)

    def test_play_sends_the_sequence(self) -> None:
        driver = self.driver()
        real.play(driver, sleep=lambda seconds: None)
        self.assertEqual(driver.method_calls[0], mock.call.focus())
        # The 16 direction keys and the mark key M (5.8b).
        self.assertEqual(driver.key_down.call_count, 17)
        self.assertEqual(driver.key_up.call_count, 17)
        self.assertEqual(driver.key_down.call_args_list.count(mock.call("m")), 1)
        self.assertEqual(driver.button.call_count, 14)
        self.assertEqual(driver.nudge.call_count, 2 * real.TURN_STEPS)
        first = [call for call in driver.method_calls if call[0] in ("key_down", "key_up")][:2]
        self.assertEqual(first, [mock.call.key_down("a"), mock.call.key_down("w")])

    def test_error_leaves_no_key_down(self) -> None:
        driver = self.driver()
        driver.button.side_effect = [RuntimeError("no display"), None]
        with self.assertRaises(RuntimeError):
            real.play(driver, sleep=lambda seconds: None)
        self.assertEqual(driver.key_down.call_count, driver.key_up.call_count)
        self.assertEqual(driver.button.call_args_list[-1], mock.call(real.RIGHT_BUTTON, False))

    def test_focus_lost_stops_the_keys(self) -> None:
        # Negative: no key is typed into another window.
        driver = self.driver()
        driver.focus_id.side_effect = [7, 7, 7, 9]
        with self.assertRaisesRegex(RuntimeError, "keyboard focus left the game window"):
            real.play(driver, sleep=lambda seconds: None)
        self.assertEqual(driver.key_down.call_args_list, [mock.call("a"), mock.call("w")])
        self.assertEqual(driver.key_up.call_args_list, [mock.call("w"), mock.call("a")])
        driver.button.assert_not_called()

    def test_unknown_step(self) -> None:
        with self.assertRaises(ValueError):
            real.play(self.driver(), steps=(("jump", 1),), sleep=lambda seconds: None)

    def test_play_combo_waits_for_the_harness(self) -> None:
        driver = self.driver()
        banks = iter([None, {"key_real": {"waiting": 0}}, {real.SECTION: {"clicks0": 0}}])
        real.play_combo(lambda: next(banks), driver, sleep=lambda seconds: None, clock=lambda: 0.0)
        self.assertEqual(driver.key_down.call_count, 17)

    def test_no_input_when_the_harness_never_arms(self) -> None:
        # Negative: no key or click goes to the desktop.
        driver = self.driver()
        ticks = iter(range(0, 1000, 10))
        with self.assertRaises(RuntimeError):
            real.play_combo(dict, driver, sleep=lambda seconds: None, clock=lambda: float(next(ticks)))
        self.assertEqual(driver.method_calls, [])


class ComboProfileTests(unittest.TestCase):
    def test_no_input_unless_the_harness_waits(self) -> None:
        # Negative: another group sends nothing to the desktop.
        with mock.patch.dict(sys.modules, {"testkit.input_driver": None}), mock.patch.object(combat, "play_combo") as play:
            combat.on_ready(None, {"meta": {"ready": 1}})
            combat.on_ready(None, {"key_real": {"waiting": 0}})
        play.assert_not_called()

    def ready(self, lines: list[str], play_error: Exception | None = None) -> tuple[mock.Mock, mock.Mock, mock.Mock, mock.Mock]:
        """on_ready with the harness waiting; the host key log gives `lines`."""
        driver = mock.Mock()
        ctx = mock.Mock(errors=[], run_dir=Path("/run"))
        with (
            mock.patch.dict(sys.modules, {"testkit.input_driver": driver}),
            mock.patch.object(combat, "host_keys") as host_keys,
            mock.patch.object(combat, "press_real_key") as press,
            mock.patch.object(combat, "play_combo", side_effect=play_error) as play,
            # key_race follows key_combo (test_combat_keys_race).
            mock.patch.object(combat, "play_race"),
            mock.patch.object(combat, "check_race_host", return_value=[]),
        ):
            host_keys.Recording.return_value.stop.return_value = lines
            if play_error is None:
                combat.on_ready(ctx, {"key_real": {"waiting": 1}})
            else:
                with self.assertRaises(type(play_error)):
                    combat.on_ready(ctx, {"key_real": {"waiting": 1}})
        press.assert_called_once()
        play.assert_called_once_with(combat._read_test_bank, driver)
        return ctx, host_keys, driver, play

    def test_input_when_the_harness_waits(self) -> None:
        ctx, host_keys, _driver, _play = self.ready(host_lines())
        # The host key log runs for the sequence and lands in the run folder.
        self.assertEqual(host_keys.Recording.call_args_list[0], mock.call(Path("/run") / "host_keys.log"))
        # One log for key_combo, one for key_race: each started and stopped.
        self.assertEqual(host_keys.Recording.return_value.start.call_count, 2)
        self.assertEqual(host_keys.Recording.return_value.stop.call_count, 2)
        self.assertEqual(ctx.errors, [])

    def test_host_log_finding_fails_the_run(self) -> None:
        # Negative: a key the X server did not hold is a failure of the run.
        lines = [line for line in host_lines() if not line.endswith(" d m")]
        ctx, _host_keys, _driver, _play = self.ready(lines)
        self.assertTrue(any("key and button edges as sent" in error for error in ctx.errors), ctx.errors)

    def test_host_log_stops_when_the_sequence_fails(self) -> None:
        _ctx, host_keys, _driver, _play = self.ready(host_lines(), play_error=RuntimeError("focus"))
        host_keys.Recording.return_value.stop.assert_called_once()

    def test_harness_file_is_in_the_map(self) -> None:
        names = [path.name for path in combat.map_spec().galaxy_files]
        self.assertLess(names.index("combat_keys.galaxy"), names.index("combat_keys_real.galaxy"))
        self.assertLess(names.index("combat_keys_real.galaxy"), names.index("combat.galaxy"))
        self.assertIn("scripts/test/combat/combat_keys_real", combat.map_spec().galaxy_includes)


if __name__ == "__main__":
    unittest.main()
