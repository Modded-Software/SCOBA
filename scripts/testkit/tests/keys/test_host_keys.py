"""Host tests of the host key log (SPEC-POINT-AND-CLICK 5.8b)."""

from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from testkit import host_keys

GAME = 0x3C00007
OTHER = 0x5200003


def down(*names: str) -> frozenset[str]:
    return frozenset(names)


class FakeReader:
    """Readings in order; the last one repeats. Sets `stop` when they end."""

    def __init__(self, readings: list[tuple[int, bool, frozenset[str]]], stop: threading.Event) -> None:
        self.readings = list(readings)
        self.stop = stop
        self.errors: list[str] = []

    def read(self) -> tuple[int, bool, frozenset[str]]:
        if len(self.readings) == 1:
            self.stop.set()
            return self.readings[0]
        return self.readings.pop(0)

    def take_errors(self) -> list[str]:
        errors, self.errors = self.errors, []
        return errors


class KeyLogTests(unittest.TestCase):
    def test_edges_in_the_game_window(self) -> None:
        log = host_keys.KeyLog()
        self.assertEqual(log.step(100, GAME, True, down()), ["100 focus id=0x3c00007 game=1", "100 state down="])
        self.assertEqual(log.step(104, GAME, True, down("w")), ["104 d w"])
        self.assertEqual(log.step(108, GAME, True, down("w", "d", "B1")), ["108 d B1", "108 d d"])
        self.assertEqual(log.step(112, GAME, True, down("d", "B1")), ["112 u w"])
        # No change, no line.
        self.assertEqual(log.step(116, GAME, True, down("d", "B1")), [])

    def test_no_key_of_another_window_is_written(self) -> None:
        # Negative: what is typed outside the game stays out of the log.
        log = host_keys.KeyLog()
        self.assertEqual(log.step(100, OTHER, False, down("w", "shift")), ["100 focus id=0x5200003 game=0"])
        self.assertEqual(log.step(104, OTHER, False, down("a")), [])
        self.assertEqual(log.step(108, OTHER, False, down()), [])

    def test_focus_leaves_and_returns(self) -> None:
        log = host_keys.KeyLog()
        log.step(100, GAME, True, down())
        log.step(104, GAME, True, down("d"))
        self.assertEqual(log.step(108, OTHER, False, down("d")), ["108 focus id=0x5200003 game=0"])
        # D is still held when the game has the focus again: a state, no edge.
        self.assertEqual(log.step(112, GAME, True, down("d")), ["112 focus id=0x3c00007 game=1", "112 state down=d"])
        self.assertEqual(log.step(116, GAME, True, down()), ["116 u d"])

    def test_counts(self) -> None:
        lines = ["1 start hz=250", "2 focus id=0x1 game=1", "2 state down=", "3 d w", "4 d B1", "5 u w", "6 d w", "7 u B1", "8 u w", "9 end reason=stop"]
        self.assertEqual(host_keys.counts(lines), {"w": [2, 2], "B1": [1, 1]})
        self.assertEqual(host_keys.counts([]), {})

    def test_focus_lines(self) -> None:
        lines = ["2 focus id=0x1 game=1", "3 d w", "4 focus id=0x9 game=0", "5 focus id=0x1 game=1", "5 state down=w"]
        self.assertEqual(host_keys.focus_changes(lines), [(2, 0x1, True), (4, 0x9, False), (5, 0x1, True)])


class ReadingTests(unittest.TestCase):
    def test_keys_down(self) -> None:
        keymap = bytearray(32)
        for code in (25, 50, 62):
            keymap[code // 8] |= 1 << (code % 8)
        codes = {"w": (25,), "shift": (50, 62), "d": (40,), "m": (58,)}
        self.assertEqual(host_keys.keys_down(bytes(keymap), codes), {"w", "shift"})
        # Negative: a key that is no game key is no name in the log.
        keymap[30 // 8] |= 1 << (30 % 8)
        self.assertEqual(host_keys.keys_down(bytes(keymap), codes), {"w", "shift"})

    def test_buttons_down(self) -> None:
        self.assertEqual(host_keys.buttons_down(0), set())
        self.assertEqual(host_keys.buttons_down(1 << 8), {"B1"})
        self.assertEqual(host_keys.buttons_down((1 << 9) | (1 << 10) | 1), {"B2", "B3"})

    def test_game_title(self) -> None:
        self.assertTrue(host_keys.is_game_title("StarCraft II"))
        # Negative: a window that only has the name in its title is no game.
        self.assertFalse(host_keys.is_game_title("StarCraft II - notes.md"))
        self.assertFalse(host_keys.is_game_title("Battle.net"))
        self.assertFalse(host_keys.is_game_title(None))


class RecordTests(unittest.TestCase):
    def record(self, readings: list[tuple[int, bool, frozenset[str]]]) -> list[str]:
        stop = threading.Event()
        ticks = iter(range(1000, 100000, 4))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "keys.log"
            host_keys.record(path, stop, reader=FakeReader(readings, stop), clock=lambda: next(ticks) / 1000.0, sleep=lambda seconds: None)
            return path.read_text(encoding="utf-8").splitlines()

    def test_file_holds_the_edges(self) -> None:
        lines = self.record([(GAME, True, down()), (GAME, True, down("a")), (GAME, True, down("a", "w")), (GAME, True, down())])
        self.assertTrue(lines[0].endswith("start hz=250"))
        self.assertTrue(lines[-1].endswith("end reason=stop"))
        self.assertEqual(host_keys.counts(lines), {"a": [1, 1], "w": [1, 1]})

    def test_reader_errors_are_written(self) -> None:
        stop = threading.Event()
        reader = FakeReader([(GAME, True, down()), (GAME, True, down())], stop)
        reader.errors = ["xerror code=3"]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "keys.log"
            host_keys.record(path, stop, reader=reader, clock=lambda: 5.0, sleep=lambda seconds: None)
            lines = path.read_text(encoding="utf-8").splitlines()
        self.assertIn("5000 xerror code=3", lines)

    def test_recording_gives_its_lines(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            stop_at = threading.Event()
            reader = FakeReader([(GAME, True, down()), (GAME, True, down("m")), (GAME, True, down())], stop_at)
            recording = host_keys.Recording(Path(folder) / "keys.log", reader=reader)
            recording.start()
            stop_at.wait(5.0)
            lines = recording.stop()
        self.assertEqual(host_keys.counts(lines), {"m": [1, 1]})

    def test_recording_does_not_hide_an_early_end(self) -> None:
        class Odd:
            def read(self):
                raise ValueError("odd")

            def take_errors(self) -> list[str]:
                return []

        with tempfile.TemporaryDirectory() as folder:
            recording = host_keys.Recording(Path(folder) / "keys.log", reader=Odd())
            with mock.patch.object(threading, "excepthook"):
                recording.start()
                recording.thread.join(5.0)
            with self.assertRaisesRegex(RuntimeError, "ended early"):
                recording.stop()

    def test_recording_does_not_hide_a_failure(self) -> None:
        class Broken:
            def read(self):
                raise RuntimeError("no display")

            def take_errors(self) -> list[str]:
                return []

        with tempfile.TemporaryDirectory() as folder:
            recording = host_keys.Recording(Path(folder) / "keys.log", reader=Broken())
            recording.start()
            # The first read fails and ends the thread.
            recording.thread.join(5.0)
            with self.assertRaisesRegex(RuntimeError, "no display"):
                recording.stop()


if __name__ == "__main__":
    unittest.main()
