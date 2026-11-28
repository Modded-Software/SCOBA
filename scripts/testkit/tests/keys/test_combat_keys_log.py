"""Host tests of the input log checks of `key_combo` (SPEC-POINT-AND-CLICK 5.8b)."""

from __future__ import annotations

import contextlib
import io
import unittest

from testkit.checks import Checks
from testkit.profiles.combat_parts import combat_keys_log as keys_log
from testkit.profiles.combat_parts import combat_keys_real as real

MARK = (
    "ms=58000 pos=120.00;118.50 travel=1.54 raw=10 keys=10 flags=10 held=0 strafe=1 aim=0 root=0 ticks=900 steps=140"
    " orders=1 order0=move@point,d29.80 hero=ToshSCOBA alive=1"
)
CODES = keys_log.GAME_CODES
NAMES = keys_log.GAME_NAMES


def edge_text(steps: tuple[tuple, ...] = real.SEQUENCE) -> str:
    """The edge log of a game that saw every key and button of the sequence."""
    edges = []
    ms = 40000
    for step in steps:
        ms += 60
        if step[0] in ("down", "up"):
            edge = step[0][0]
            if step[1] in NAMES:
                edges.append(f"{ms}{edge}{NAMES[step[1]]}")
            edges.append(f"{ms}{edge}k{CODES[step[1]]}")
        elif step[0] in ("press", "release"):
            edges.append(f"{ms}{'d' if step[0] == 'press' else 'u'}B{step[1]}")
    return " ".join(edges) + " "


def edge_values(**over) -> dict:
    """The edge log keys of a key_combo section in which the recorder behaves."""
    values = {"moveEdges": edge_text(), "marks0": 0, "marks1": 1, "seq0": 200, "seq1": 364, "markText": MARK}
    values.update(over)
    return values


def host_lines(steps: tuple[tuple, ...] = real.SEQUENCE) -> list[str]:
    """The host key log of a sequence that stayed in the game window."""
    lines = ["1000 start hz=250", "1004 focus id=0x3c00007 game=1", "1004 state down="]
    ms = 1004
    for step in steps:
        ms += 80
        if step[0] in ("down", "up"):
            lines.append(f"{ms} {step[0][0]} {step[1]}")
        elif step[0] in ("press", "release"):
            lines.append(f"{ms} {'d' if step[0] == 'press' else 'u'} B{step[1]}")
    return [*lines, f"{ms + 4} end reason=stop"]


def failed(values: dict) -> list[str]:
    checks = Checks({keys_log.SECTION: values})
    with contextlib.redirect_stdout(io.StringIO()):
        keys_log.check_edge_log(checks)
    return [str(r["section"]) for r in checks.results if r["status"] == "FAIL"]


class EdgeLogCheckTests(unittest.TestCase):
    def assert_fails(self, values: dict, name: str) -> None:
        got = failed(values)
        self.assertTrue(any(name in item for item in got), f"{name} not in {got}")

    def test_passing_section(self) -> None:
        self.assertEqual(failed(edge_values()), [])

    def test_empty_section_fails(self) -> None:
        # Negative: a run that wrote nothing proves nothing.
        self.assertGreaterEqual(len(failed({})), 6)

    def test_sent_counts(self) -> None:
        want = keys_log.sent_counts()
        self.assertEqual([want[name] for name in ("dW", "uW", "dS", "uS", "dA", "uA", "dD", "uD")], [4] * 8)
        self.assertEqual([want[name] for name in ("dk35", "uk35", "dk31", "uk31", "dk13", "uk13", "dk16", "uk16")], [4] * 8)
        self.assertEqual((want["dk25"], want["uk25"]), (1, 1))
        self.assertEqual([want[name] for name in ("dB1", "uB1", "dB2", "uB2", "dB3", "uB3")], [3, 3, 2, 2, 2, 2])

    def test_a_key_down_the_game_did_not_get(self) -> None:
        # Operator 2026-11-27: D is held and the game has no D down.
        text = edge_text().replace("dD ", "dX ", 1)
        self.assert_fails(edge_values(moveEdges=text), "four keys as sent")

    def test_any_key_trigger_missed_a_down(self) -> None:
        # The four-key trigger saw the D down, the any-key trigger did not.
        text = edge_text().replace("dk16 ", "", 1)
        self.assertEqual(failed(edge_values(moveEdges=text)), ["key_combo edge log: any-key edges as sent"])

    def test_any_key_trigger_saw_nothing(self) -> None:
        text = " ".join(edge for edge in edge_text().split() if "k" not in edge) + " "
        self.assert_fails(edge_values(moveEdges=text), "any-key edges as sent")

    def test_button_edge_lost(self) -> None:
        text = edge_text().replace("uB3 ", "", 1)
        self.assert_fails(edge_values(moveEdges=text), "button edges as sent")

    def test_a_key_the_host_did_not_send(self) -> None:
        # Negative. Run combat/20261127-165541: a NumLock tap (k81) with
        # every key event.
        for extra in ("59000dk0 ", "59000rk81*37from57812 "):
            self.assertEqual(failed(edge_values(moveEdges=edge_text() + extra)), ["key_combo edge log: no key the host did not send"])

    def test_a_tap_counts_as_a_down_and_an_up(self) -> None:
        # M down and up with no edge between is one taps entry.
        edges = [edge for edge in edge_text().split() if not edge.endswith("k25")]
        self.assertEqual(failed(edge_values(moveEdges=" ".join([*edges, "58812rk25*1from58750"]) + " ")), [])

    def test_no_mark_for_the_real_key(self) -> None:
        self.assert_fails(edge_values(marks1=0), "one mark by the real M")
        self.assert_fails(edge_values(marks1=2), "one mark by the real M")

    def test_mark_without_the_keys_down(self) -> None:
        self.assert_fails(edge_values(markText=MARK.replace("raw=10", "raw=0")), "mark has S and D down")

    def test_mark_without_travel(self) -> None:
        self.assert_fails(edge_values(markText=MARK.replace("travel=1.54", "travel=-1.00")), "mark has the travel")

    def test_mark_without_its_rows(self) -> None:
        self.assert_fails(edge_values(seq1=234), "mark wrote its rows and edges")

    def test_edge_counts(self) -> None:
        self.assertEqual(keys_log.edge_counts("100dW 100dk35 220dB1 300uk35 300uW junk "), {"dW": 1, "dk35": 1, "dB1": 1, "uk35": 1, "uW": 1})
        self.assertEqual(keys_log.edge_counts("400rk81*3from120 450dk81 "), {"dk81": 4, "uk81": 3})
        self.assertEqual(keys_log.edge_counts(None), {})


class HostLogCheckTests(unittest.TestCase):
    def assert_fails(self, lines: list[str], name: str) -> None:
        got = keys_log.check_host_log(lines)
        self.assertTrue(any(name in item for item in got), f"{name} not in {got}")

    def test_passing_log(self) -> None:
        self.assertEqual(keys_log.check_host_log(host_lines()), [])

    def test_empty_log_fails(self) -> None:
        # Negative: a log that wrote nothing proves nothing.
        self.assert_fails([], "the game window never had the focus")

    def test_key_the_x_server_did_not_hold(self) -> None:
        lines = [line for line in host_lines() if not line.endswith(" d m")]
        self.assert_fails(lines, "key and button edges as sent")

    def test_key_the_host_did_not_send(self) -> None:
        lines = [*host_lines(), "9000 d z", "9004 u z"]
        self.assert_fails(lines, "key and button edges as sent")

    def test_focus_left_the_game(self) -> None:
        lines = host_lines()
        lines.insert(8, "1500 focus id=0x5200003 game=0")
        self.assert_fails(lines, "the focus left the game window")

    def test_x_error(self) -> None:
        lines = [*host_lines(), "9000 xerror code=3"]
        self.assert_fails(lines, "X errors")


if __name__ == "__main__":
    unittest.main()
