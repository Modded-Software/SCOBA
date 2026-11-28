"""Host key log (SPEC-POINT-AND-CLICK 5.8b).

What the X server holds down while the game window has the keyboard focus:
the game keys, the three mouse buttons and the focus window, read many
times a second. One line per change, with the clock time in ms:

    <ms> start hz=<n>
    <ms> focus id=<window> game=<0|1>
    <ms> state down=<names held when the game got the focus>
    <ms> d <name>          a key or button went down
    <ms> u <name>          it went up
    <ms> xerror code=<n>   an X request failed
    <ms> end reason=<why>

Keys and buttons are written only while the game window has the focus.
Outside it only the focus change is written.

The game's own edge log is in bank SCOBAMOVELOG
(systems/recorders/move_log_keys). A key this log holds down and the game
has no down for was lost between the X server and the script.

Run: make key-log (ARGS="--minutes n").
"""

from __future__ import annotations

import argparse
import ctypes
import re
import threading
import time
from pathlib import Path

import workpaths

# Log name -> X keysym names. The keys the map reads, no other key.
WATCH = {
    "w": ("w",),
    "a": ("a",),
    "s": ("s",),
    "d": ("d",),
    "shift": ("Shift_L", "Shift_R"),
    "ctrl": ("Control_L", "Control_R"),
    "alt": ("Alt_L", "Alt_R"),
    "space": ("space",),
    "z": ("z",),
    "e": ("e",),
    "c": ("c",),
    "m": ("m",),
    "enter": ("Return",),
    "escape": ("Escape",),
    "tab": ("Tab",),
}
# Mask bit of mouse button 1 in the X pointer state; 2 and 3 follow it.
BUTTON1_SHIFT = 8
HZ = 250
GAME_TITLE = "StarCraft II"
# Seconds a window's answer is kept: an id can go to a new window.
KNOWN_FOR_S = 2.0
# Parents to walk from the focus window to a game window.
TREE_DEPTH = 12

_FOCUS_LINE = re.compile(r"^(\d+) focus id=(0x[0-9a-f]+) game=([01])$")
_EDGE_LINE = re.compile(r"^(\d+) ([du]) (\S+)$")


def keys_down(keymap: bytes, codes: dict[str, tuple[int, ...]]) -> set[str]:
    """Names whose key is down in the 32 bytes XQueryKeymap gives."""
    return {name for name, group in codes.items() if any(keymap[code // 8] & (1 << (code % 8)) for code in group)}


def buttons_down(mask: int) -> set[str]:
    """B1, B2, B3 from the pointer state mask."""
    return {f"B{number}" for number in (1, 2, 3) if mask & (1 << (BUTTON1_SHIFT + number - 1))}


def is_game_title(title: str | None) -> bool:
    """The whole window title is the game's. A title that only holds it is not."""
    return title == GAME_TITLE


class KeyLog:
    """Turns readings into log lines."""

    def __init__(self) -> None:
        self.focus: int | None = None
        self.in_game = False
        self.down: frozenset[str] = frozenset()

    def step(self, ms: int, focus: int, in_game: bool, down: frozenset[str]) -> list[str]:
        lines = []
        if focus != self.focus or in_game != self.in_game:
            lines.append(f"{ms} focus id={focus:#x} game={int(in_game)}")
            if in_game:
                lines.append(f"{ms} state down={','.join(sorted(down))}")
        elif in_game:
            lines.extend(f"{ms} d {name}" for name in sorted(down - self.down))
            lines.extend(f"{ms} u {name}" for name in sorted(self.down - down))
        self.focus = focus
        self.in_game = in_game
        self.down = down if in_game else frozenset()
        return lines


def counts(lines: list[str]) -> dict[str, list[int]]:
    """[downs, ups] of each name in the log."""
    found: dict[str, list[int]] = {}
    for line in lines:
        match = _EDGE_LINE.match(line)
        if match:
            found.setdefault(match.group(3), [0, 0])[0 if match.group(2) == "d" else 1] += 1
    return found


def focus_changes(lines: list[str]) -> list[tuple[int, int, bool]]:
    """(ms, window, game window) of each focus line."""
    found = []
    for line in lines:
        match = _FOCUS_LINE.match(line)
        if match:
            found.append((int(match.group(1)), int(match.group(2), 16), match.group(3) == "1"))
    return found


_ERROR_HANDLER = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)


class XReader:
    """Reads the X server on its own connection."""

    def __init__(self) -> None:
        self.errors: list[str] = []
        self.x11 = ctypes.CDLL("libX11.so.6")
        x11 = self.x11
        x11.XOpenDisplay.restype = ctypes.c_void_p
        x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        x11.XStringToKeysym.restype = ctypes.c_ulong
        x11.XStringToKeysym.argtypes = [ctypes.c_char_p]
        x11.XKeysymToKeycode.restype = ctypes.c_ubyte
        x11.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        x11.XDefaultRootWindow.restype = ctypes.c_ulong
        x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
        x11.XQueryKeymap.argtypes = [ctypes.c_void_p, ctypes.c_char * 32]
        x11.XGetInputFocus.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_int)]
        pointer_args = [ctypes.POINTER(ctypes.c_ulong)] * 2 + [ctypes.POINTER(ctypes.c_int)] * 4 + [ctypes.POINTER(ctypes.c_uint)]
        x11.XQueryPointer.argtypes = [ctypes.c_void_p, ctypes.c_ulong, *pointer_args]
        tree_args = [ctypes.POINTER(ctypes.c_ulong)] * 2 + [ctypes.POINTER(ctypes.POINTER(ctypes.c_ulong)), ctypes.POINTER(ctypes.c_uint)]
        x11.XQueryTree.argtypes = [ctypes.c_void_p, ctypes.c_ulong, *tree_args]
        x11.XFree.argtypes = [ctypes.c_void_p]
        x11.XFetchName.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_void_p)]
        x11.XSetErrorHandler.argtypes = [_ERROR_HANDLER]
        x11.XSetErrorHandler.restype = ctypes.c_void_p
        # The stock handler ends the process. A window can close between two
        # requests: the error goes to the log, the read goes on.
        self._handler = _ERROR_HANDLER(self._on_error)
        x11.XSetErrorHandler(self._handler)
        self.display = x11.XOpenDisplay(None)
        if not self.display:
            raise RuntimeError("cannot open the X display")
        self.root = x11.XDefaultRootWindow(self.display)
        self.codes = {}
        for name, syms in WATCH.items():
            group = tuple(code for code in (x11.XKeysymToKeycode(self.display, x11.XStringToKeysym(sym.encode())) for sym in syms) if code)
            if not group:
                raise RuntimeError(f"no keycode for {name}")
            self.codes[name] = group
        self.known_at = 0.0
        self.known: dict[int, bool] = {}

    def _on_error(self, _display, event) -> int:
        # XErrorEvent: type, display, resourceid, serial, error_code.
        code = ctypes.cast(event, ctypes.POINTER(ctypes.c_ubyte))[32]
        self.errors.append(f"xerror code={code}")
        return 0

    def take_errors(self) -> list[str]:
        errors, self.errors = self.errors, []
        return errors

    def _title(self, window: int) -> str | None:
        name = ctypes.c_void_p(None)
        if not self.x11.XFetchName(self.display, window, ctypes.byref(name)) or not name.value:
            return None
        try:
            return ctypes.string_at(name.value).decode("utf-8", "replace")
        finally:
            self.x11.XFree(name)

    def _in_game(self, focus: int) -> bool:
        """The focus window or one of its parents has the game's title."""
        if focus in self.known:
            return self.known[focus]
        window = focus
        found = False
        for _ in range(TREE_DEPTH):
            # 0 is no focus, 1 is the pointer root: neither is a window.
            if window <= 1 or window == self.root:
                break
            if is_game_title(self._title(window)):
                found = True
                break
            root = ctypes.c_ulong(0)
            parent = ctypes.c_ulong(0)
            children = ctypes.POINTER(ctypes.c_ulong)()
            count = ctypes.c_uint(0)
            if not self.x11.XQueryTree(self.display, window, ctypes.byref(root), ctypes.byref(parent), ctypes.byref(children), ctypes.byref(count)):
                break
            if children:
                self.x11.XFree(children)
            window = int(parent.value)
        self.known[focus] = found
        return found

    def read(self) -> tuple[int, bool, frozenset[str]]:
        """(focus window, it is the game's, names down)."""
        now = time.monotonic()
        if now - self.known_at >= KNOWN_FOR_S:
            self.known = {}
            self.known_at = now
        focus = ctypes.c_ulong(0)
        revert = ctypes.c_int(0)
        self.x11.XGetInputFocus(self.display, ctypes.byref(focus), ctypes.byref(revert))
        keymap = (ctypes.c_char * 32)()
        self.x11.XQueryKeymap(self.display, keymap)
        ignored = [ctypes.c_ulong(0), ctypes.c_ulong(0), ctypes.c_int(0), ctypes.c_int(0), ctypes.c_int(0), ctypes.c_int(0)]
        mask = ctypes.c_uint(0)
        self.x11.XQueryPointer(self.display, self.root, *(ctypes.byref(item) for item in ignored), ctypes.byref(mask))
        down = keys_down(bytes(keymap), self.codes) | buttons_down(int(mask.value))
        return int(focus.value), self._in_game(int(focus.value)), frozenset(down)


def record(path: Path, stop: threading.Event, reader=None, hz: int = HZ, clock=time.time, sleep=time.sleep, deadline: float | None = None) -> str:
    """Writes the log until `stop` is set or `deadline` (clock seconds) passes."""
    reader = XReader() if reader is None else reader
    log = KeyLog()
    reason = "stop"
    with path.open("w", encoding="utf-8") as out:
        out.write(f"{int(clock() * 1000)} start hz={hz}\n")
        try:
            while not stop.is_set():
                if deadline is not None and clock() >= deadline:
                    reason = "time"
                    break
                focus, in_game, down = reader.read()
                ms = int(clock() * 1000)
                lines = [f"{ms} {error}" for error in reader.take_errors()]
                lines.extend(log.step(ms, focus, in_game, down))
                if lines:
                    out.write("\n".join(lines) + "\n")
                    out.flush()
                sleep(1.0 / hz)
        except BaseException as exc:
            reason = type(exc).__name__
            raise
        finally:
            out.write(f"{int(clock() * 1000)} end reason={reason}\n")
    return reason


class Recording:
    """The log in a thread, for the time of a test's input sequence."""

    def __init__(self, path: Path, reader=None) -> None:
        self.path = path
        self.reader = reader
        self.stop_event = threading.Event()
        self.failure: list[BaseException] = []
        self.thread = threading.Thread(target=self._run, name="host-keys", daemon=True)

    def _run(self) -> None:
        try:
            record(self.path, self.stop_event, reader=self.reader)
        except (RuntimeError, OSError) as exc:
            # stop() raises it in the caller's thread.
            self.failure.append(exc)

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> list[str]:
        """Ends the log and gives its lines. Raises what the thread raised."""
        self.stop_event.set()
        self.thread.join(10.0)
        if self.thread.is_alive():
            raise RuntimeError("the host key log did not stop")
        if self.failure:
            raise self.failure[0]
        lines = self.path.read_text(encoding="utf-8").splitlines()
        if not lines or not lines[-1].endswith(" end reason=stop"):
            raise RuntimeError(f"the host key log ended early: {lines[-1:]}")
        return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Host key log: game keys, mouse buttons and focus while the game window has the focus.")
    parser.add_argument("--minutes", type=float, default=120.0, help="stop after this many minutes (default 120)")
    args = parser.parse_args(argv)
    folder = workpaths.path("SC2_WORK") / "keylog"
    folder.mkdir(exist_ok=True)
    path = folder / (time.strftime("%Y%m%d-%H%M%S") + ".log")
    print(f"host key log: {path}", flush=True)
    print(f"stops after {args.minutes:g} minutes or Ctrl+C", flush=True)
    try:
        reason = record(path, threading.Event(), deadline=time.time() + args.minutes * 60.0)
    except KeyboardInterrupt:
        reason = "KeyboardInterrupt"
    print(f"host key log ended: {reason}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
