"""Host tests of the key and click race case `key_race` (R-PNC-57, SPEC 5.8b)."""

from __future__ import annotations

import contextlib
import io
import sys
import unittest
from pathlib import Path
from unittest import mock

from testkit.checks import Checks
from testkit.profiles import combat
from testkit.profiles.combat_parts import combat_keys_race as race
from testkit.profiles.combat_parts import combat_keys_real as real

# Key index in the harness counters: 0 W, 1 S, 2 A, 3 D.
INDEX = {"w": 0, "s": 1, "a": 2, "d": 3}
# Steps that pass time and send no edge: a sweep also moves the mouse.
WAITS = ("wait", "sweep")


def race_section(**over) -> dict:
    """The bank section of a run in which every key and click arrives."""
    values: dict = {"tpsOn": True, "armed": 1, "started": True, "tpsAfter": False, "repeats": 0, "looseUps": 0, "rawEnd": 0, "scriptEnd": 0, "edgeLog": ""}
    for key, (downs, ups) in race.sent_keys().items():
        values[f"downs{INDEX[key]}"] = downs
        values[f"ups{INDEX[key]}"] = ups
    values["btnLeft"] = race.sent_presses()[race.SHOT_BUTTON]
    values["btnRight"] = race.sent_presses()[race.AIM_BUTTON]
    values.update({"scriptOff": 0, "mapKeyEdges": 2 * 4 * race.ROUNDS, "mapAnyEdges": 900, "mapBtnEdges": 362, "rows": 620, "heldRows": 400, "path100": 5200, "turn10": 2400})
    values.update(over)
    return values


def race_lines() -> list[str]:
    """The host key log of the race, each edge at the time the host sent it."""
    lines = ["1000 start hz=250", "1004 focus id=0x3c00007 game=1", "1004 state down="]
    ms = 1004.0
    for step in race.RACE:
        if step[0] in WAITS:
            ms += step[1] * 1000
            continue
        _kind, name, down = real.step_edge(step)
        lines.append(f"{round(ms)} {'d' if down else 'u'} {name if isinstance(name, str) else f'B{name}'}")
    return [*lines, f"{round(ms) + 4} end reason=stop"]


def failed(section: dict) -> list[str]:
    checks = Checks({race.SECTION: section})
    with contextlib.redirect_stdout(io.StringIO()):
        race.check_race(checks)
    return [f"{r['section']} {r['tag']} {r['key']}".strip() for r in checks.results if r["status"] == "FAIL"]


def neighbours(steps: tuple[tuple, ...], index: int) -> tuple[tuple, float, tuple, float]:
    """(edge before, seconds to it, edge after, seconds to it) of a step."""
    before = index - 1
    wait_before = 0.0
    while steps[before][0] in WAITS:
        wait_before += steps[before][1]
        before -= 1
    after = index + 1
    wait_after = 0.0
    while steps[after][0] in WAITS:
        wait_after += steps[after][1]
        after += 1
    return steps[before], wait_before, steps[after], wait_after


class RaceSequenceTests(unittest.TestCase):
    def test_counts(self) -> None:
        self.assertEqual(race.sent_keys(), {key: [race.ROUNDS, race.ROUNDS] for key in ("d", "a", "w", "s")})
        self.assertEqual(race.sent_presses(), {race.SHOT_BUTTON: 3 * 4 * race.ROUNDS, race.AIM_BUTTON: 1})

    def test_gap_keys_go_down_between_a_button_up_and_a_button_down(self) -> None:
        # Operator's play 2026-11-27: 12 to 39 ms after the up, 0 to 18 ms
        # before the down.
        found = 0
        for index, step in enumerate(race.RACE):
            if step[0] == "kdown" and step[1] in race.GAP_KEYS:
                before, wait_before, after, wait_after = neighbours(race.RACE, index)
                self.assertEqual(before, ("bup", race.SHOT_BUTTON))
                self.assertEqual(after, ("bdown", race.SHOT_BUTTON))
                self.assertLessEqual(wait_before, 0.039)
                self.assertLessEqual(wait_after, 0.018)
                found += 1
        self.assertEqual(found, 2 * race.ROUNDS)

    def test_control_keys_go_down_inside_a_button_hold(self) -> None:
        found = 0
        for index, step in enumerate(race.RACE):
            if step[0] == "kdown" and step[1] in race.MID_KEYS:
                before, wait_before, after, wait_after = neighbours(race.RACE, index)
                self.assertEqual(before, ("bdown", race.SHOT_BUTTON))
                self.assertEqual(after, ("bup", race.SHOT_BUTTON))
                self.assertGreaterEqual(wait_before, 0.04)
                self.assertGreaterEqual(wait_after, 0.04)
                found += 1
        self.assertEqual(found, 2 * race.ROUNDS)

    def test_one_key_at_a_time_and_the_aim_button_around_all(self) -> None:
        down: set = set()
        for step in race.RACE:
            edge = real.step_edge(step)
            if edge is None:
                continue
            kind, name, is_down = edge
            if kind == "button" and name == race.AIM_BUTTON:
                continue
            # Every key and every click happens with the aim button held.
            self.assertEqual(race.RACE[0], ("bdown", race.AIM_BUTTON))
            if is_down:
                down.add((kind, name))
            else:
                down.remove((kind, name))
            self.assertLessEqual(sum(1 for item in down if item[0] == "key"), 1)
        self.assertEqual(down, set())
        edges = [step for step in race.RACE if real.step_edge(step) is not None]
        self.assertEqual(edges[-1], ("bup", race.AIM_BUTTON))
        # The host key log reads the X server every 4 ms: the sequence ends
        # with a wait, so the log holds the last up (run 20261127-193353).
        self.assertEqual(race.RACE[-1][0], "wait")
        self.assertGreaterEqual(race.RACE[-1][1], 0.1)

    def test_the_mouse_moves_through_every_round(self) -> None:
        # A player who aims moves the mouse while clicking and pressing keys.
        first = next(i for i, step in enumerate(race.RACE) if step == ("bdown", race.SHOT_BUTTON))
        last = max(i for i, step in enumerate(race.RACE) if step[0] == "kup")
        inside = race.RACE[first : last + 1]
        self.assertFalse([step for step in inside if step[0] == "wait"])
        sweeps = [step for step in inside if step[0] == "sweep"]
        self.assertGreater(len(sweeps), 6 * 4 * race.ROUNDS)
        # Both ways, so the camera does not spin.
        self.assertEqual({step[2] for step in sweeps}, {race.SWEEP_PX, -race.SWEEP_PX})
        self.assertLessEqual(abs(sum(step[2] for step in sweeps)), race.SWEEP_PX)

    def test_play_moves_the_mouse(self) -> None:
        driver = mock.Mock()
        driver.center_point.return_value = (640, 360)
        slept: list[float] = []
        real.play(driver, steps=(("sweep", 0.09, 2), ("sweep", 0.012, -2)), sleep=slept.append)
        # One nudge about every 4 ms, and the time of the step kept.
        self.assertEqual(driver.nudge.call_args_list, [mock.call(2, 0)] * 22 + [mock.call(-2, 0)] * 3)
        self.assertAlmostEqual(sum(slept), 0.102, places=6)
        # Negative: a sweep sends no key and no button.
        driver.key_edge.assert_not_called()
        driver.button_edge.assert_not_called()

    def test_play_sends_the_fast_edges(self) -> None:
        driver = mock.Mock()
        driver.center_point.return_value = (640, 360)
        banks = iter([None, {race.SECTION: {"armed": 1}}])
        race.play_race(lambda: next(banks), driver, sleep=lambda seconds: None, clock=lambda: 0.0)
        self.assertEqual(driver.key_edge.call_count, 2 * 4 * race.ROUNDS)
        self.assertEqual(driver.button_edge.call_count, 2 * (3 * 4 * race.ROUNDS + 1))
        self.assertGreater(driver.nudge.call_count, 1000)
        # Negative: none of the slow edges, which sleep 80 ms each.
        driver.key_down.assert_not_called()
        driver.button.assert_not_called()

    def test_no_input_when_the_harness_never_arms(self) -> None:
        driver = mock.Mock()
        ticks = iter(range(0, 1000, 10))
        with self.assertRaises(RuntimeError):
            race.play_race(dict, driver, sleep=lambda seconds: None, clock=lambda: float(next(ticks)))
        self.assertEqual(driver.method_calls, [])

    def test_error_leaves_nothing_down(self) -> None:
        driver = mock.Mock()
        driver.center_point.return_value = (640, 360)
        driver.focus_id.side_effect = [7] * 6 + [9]
        with self.assertRaisesRegex(RuntimeError, "keyboard focus left the game window"):
            real.play(driver, steps=race.RACE, sleep=lambda seconds: None)
        downs = [call for call in driver.method_calls if call[0] in ("key_edge", "button_edge") and call[1][1]]
        ups = [call for call in driver.method_calls if call[0] in ("key_edge", "button_edge") and not call[1][1]]
        # The aim button, D and the left button were down: all three go up.
        self.assertEqual(len(downs), 4)
        self.assertEqual(len(ups) + driver.key_up.call_count + driver.button.call_count, 4)
        driver.key_up.assert_called_once_with("d")


class RaceCheckTests(unittest.TestCase):
    def assert_fails(self, section: dict, name: str) -> None:
        got = failed(section)
        self.assertTrue(any(name in item for item in got), f"{name} not in {got}")

    def test_passing_section(self) -> None:
        self.assertEqual(failed(race_section()), [])

    def test_empty_section_fails(self) -> None:
        # Negative: a run that wrote nothing proves nothing.
        self.assertGreater(len(failed({})), 10)

    def test_key_down_lost_in_the_gap(self) -> None:
        # Operator's play 2026-11-27: D down between two clicks never came.
        self.assert_fails(race_section(downs3=race.ROUNDS - 1), "D down in the gap between two clicks")
        self.assert_fails(race_section(downs0=race.ROUNDS - 3), "W down in the gap between two clicks")

    def test_key_down_lost_inside_a_hold(self) -> None:
        self.assert_fails(race_section(downs2=race.ROUNDS - 1), "A down inside a click")

    def test_key_up_lost(self) -> None:
        self.assert_fails(race_section(ups3=race.ROUNDS - 1), "D ups as sent")

    def test_key_left_down(self) -> None:
        self.assert_fails(race_section(rawEnd=8), "rawEnd")
        self.assert_fails(race_section(scriptEnd=8), "scriptEnd")

    def test_click_lost(self) -> None:
        self.assert_fails(race_section(btnLeft=3), "left clicks as sent")
        self.assert_fails(race_section(btnRight=0), "one aim hold")

    def test_never_started(self) -> None:
        self.assert_fails(race_section(started=False), "started")

    def test_script_key_state_off_the_keys(self) -> None:
        self.assert_fails(race_section(scriptOff=3), "scriptOff")

    def test_map_trigger_missed_an_edge(self) -> None:
        self.assert_fails(race_section(mapKeyEdges=2 * 4 * race.ROUNDS - 2), "the map's key triggers got every edge")

    def test_hero_stands_with_a_key_down(self) -> None:
        # Operator 2026-11-27: a direction key held, the hero does not move.
        self.assert_fails(race_section(path100=300), "the hero walks with a key down")
        self.assert_fails(race_section(heldRows=0, path100=0), "the hero walks with a key down")

    def test_keys_never_down(self) -> None:
        self.assert_fails(race_section(heldRows=race.HELD_ROWS - 1), "keys down for their loops")

    def test_camera_did_not_turn(self) -> None:
        # The arrangement: the game got the mouse motion of the sweeps.
        self.assert_fails(race_section(turn10=race.TURN_LEAST10 - 1), "the camera turns with the mouse")


class RaceHostLogTests(unittest.TestCase):
    def findings(self, lines: list[str]) -> list[str]:
        with contextlib.redirect_stdout(io.StringIO()):
            return race.check_race_host(lines)

    def assert_fails(self, lines: list[str], name: str) -> None:
        got = self.findings(lines)
        self.assertTrue(any(name in item for item in got), f"{name} not in {got}")

    def test_passing_log(self) -> None:
        self.assertEqual(self.findings(race_lines()), [])

    def test_empty_log_fails(self) -> None:
        # Negative: a log that wrote nothing proves nothing.
        self.assert_fails([], "the game window never had the focus")
        self.assert_fails([], "gap keys down between a button up and a button down")

    def test_gap_times(self) -> None:
        gaps = race.gap_times(race_lines())
        self.assertEqual(len(gaps), 2 * race.ROUNDS)
        self.assertEqual(set(gaps), {("d", 12, 15), ("w", 12, 15)})

    def test_gap_key_outside_a_gap(self) -> None:
        # The X server held D down only after the next button down.
        lines = race_lines()
        index = next(i for i, line in enumerate(lines) if line.endswith(" d d"))
        lines[index], lines[index + 1] = lines[index + 1], lines[index]
        self.assertIn(("d", -1, -1), race.gap_times(lines))
        self.assert_fails(lines, "gap keys down between a button up and a button down")

    def test_gap_too_long(self) -> None:
        lines = race_lines()
        index = next(i for i, line in enumerate(lines) if line.endswith(" d d"))
        ms = int(lines[index].split()[0])
        lines[index - 1] = f"{ms - race.GAP_MOST_MS - 1} u B{race.SHOT_BUTTON}"
        self.assert_fails(lines, "gap keys down between a button up and a button down")

    def test_key_the_x_server_did_not_hold(self) -> None:
        lines = race_lines()
        lines.remove(next(line for line in lines if line.endswith(" d w")))
        self.assert_fails(lines, "key and button edges as sent")


class RaceProfileTests(unittest.TestCase):
    def ready(self, combo_error: Exception | None = None) -> tuple[mock.Mock, mock.Mock, mock.Mock]:
        driver = mock.Mock()
        ctx = mock.Mock(errors=[], run_dir=Path("/run"))
        with (
            mock.patch.dict(sys.modules, {"testkit.input_driver": driver}),
            mock.patch.object(combat, "host_keys") as host_keys,
            mock.patch.object(combat, "press_real_key"),
            mock.patch.object(combat, "play_combo", side_effect=combo_error),
            mock.patch.object(combat, "check_host_log", return_value=[]),
            mock.patch.object(combat, "play_race") as play,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            host_keys.Recording.return_value.stop.return_value = race_lines()
            if combo_error is None:
                combat.on_ready(ctx, {"key_real": {"waiting": 1}})
            else:
                with self.assertRaises(type(combo_error)):
                    combat.on_ready(ctx, {"key_real": {"waiting": 1}})
        return ctx, host_keys, play

    def test_race_runs_after_the_combo_with_its_own_host_log(self) -> None:
        ctx, host_keys, play = self.ready()
        play.assert_called_once_with(combat._read_test_bank, mock.ANY)
        self.assertEqual(host_keys.Recording.call_args_list, [mock.call(Path("/run") / "host_keys.log"), mock.call(Path("/run") / "host_keys_race.log")])
        self.assertEqual(host_keys.Recording.return_value.stop.call_count, 2)
        self.assertEqual(ctx.errors, [])

    def test_no_race_after_a_failed_combo(self) -> None:
        # Negative: no more input after the focus left the game window.
        _ctx, _host_keys, play = self.ready(combo_error=RuntimeError("focus"))
        play.assert_not_called()

    def test_no_input_unless_the_harness_waits(self) -> None:
        with mock.patch.dict(sys.modules, {"testkit.input_driver": None}), mock.patch.object(combat, "play_race") as play:
            combat.on_ready(None, {"meta": {"ready": 1}})
        play.assert_not_called()

    def test_clicks_a_run_must_count(self) -> None:
        clicks = real.sent_buttons() + 3 * 4 * race.ROUNDS + 1
        self.assertEqual(combat.expected_clicks("keys"), clicks)
        self.assertEqual(combat.expected_clicks("all"), clicks)
        # Negative: any click makes a run of another group invalid.
        self.assertEqual(combat.expected_clicks("single"), 0)

    def test_harness_file_is_in_the_map(self) -> None:
        spec = combat.map_spec()
        names = [path.name for path in spec.galaxy_files]
        self.assertLess(names.index("combat_keys_real.galaxy"), names.index("combat_keys_race.galaxy"))
        self.assertLess(names.index("combat_keys_race.galaxy"), names.index("combat.galaxy"))
        self.assertIn("scripts/test/combat/combat_keys_race", spec.galaxy_includes)
        self.assertEqual(len(spec.galaxy_files), len(spec.galaxy_includes))

    def test_checks_run_in_the_keys_group(self) -> None:
        checks = Checks({})
        with contextlib.redirect_stdout(io.StringIO()):
            combat.GROUP_CHECKS["keys"](checks)
        self.assertTrue(any(str(r["section"]).startswith(race.SECTION) for r in checks.results))


if __name__ == "__main__":
    unittest.main()
