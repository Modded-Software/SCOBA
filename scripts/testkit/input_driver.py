"""Game window input helpers for test profiles."""

from __future__ import annotations

import ctypes
import os
import re
import subprocess
import time

import input_inject

input_inject.xt.XTestFakeRelativeMotionEvent.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_ulong]
input_inject.x11.XGetInputFocus.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_int)]


def _window_tree() -> list[str]:
    """The lines of the X window tree. A failed xwininfo raises with its message."""
    try:
        proc = subprocess.run(
            ["xwininfo", "-root", "-tree"],
            capture_output=True,
            text=True,
            check=True,
            env={**os.environ, "DISPLAY": os.environ.get("DISPLAY", ":0")},
        )
    except subprocess.CalledProcessError as error:
        message = error.stderr.strip()
        if not message:
            message = f"xwininfo failed with exit code {error.returncode}"
        raise RuntimeError(message) from error
    return proc.stdout.splitlines()


def window_geometry() -> tuple[int, int, int, int] | None:
    for line in _window_tree():
        if "StarCraft II" not in line:
            continue
        match = re.search(r"(\d+)x(\d+)\+(-?\d+)\+(-?\d+)", line)
        if match:
            w, h, x, y = (int(v) for v in match.groups())
            return x, y, w, h
    return None


def center_point() -> tuple[int, int]:
    geometry = window_geometry()
    if geometry is None:
        raise RuntimeError("StarCraft II window not found")
    x, y, w, h = geometry
    return x + w // 2, y + h // 2


def focus() -> None:
    for line in _window_tree():
        if "StarCraft II" not in line:
            continue
        wid = int(line.split()[0], 16)
        input_inject.focus(wid)
        return
    raise RuntimeError("StarCraft II window not found")


def click(x: int, y: int) -> None:
    input_inject.click(x, y)


def rclick(x: int, y: int) -> None:
    input_inject.rclick(x, y)


def rclick_fast(x: int, y: int) -> None:
    input_inject.rclick_fast(x, y)





def ldrag(x1: int, y1: int, x2: int, y2: int) -> None:
    input_inject.ldrag(x1, y1, x2, y2)


def rdrag(x1: int, y1: int, x2: int, y2: int) -> None:
    input_inject.rdrag(x1, y1, x2, y2)


def rhold(x: int, y: int, hold_ms: int) -> None:
    input_inject.rhold(x, y, hold_ms)


def focus_id() -> int:
    """The X window that holds the keyboard focus now."""
    window = ctypes.c_ulong(0)
    revert = ctypes.c_int(0)
    input_inject.x11.XGetInputFocus(input_inject.d, ctypes.byref(window), ctypes.byref(revert))
    return int(window.value)


def move(x: int, y: int) -> None:
    input_inject.move(x, y)


def button(number: int, down: bool) -> None:
    """One mouse button edge: 1 left, 2 middle, 3 right."""
    input_inject.button(number, down)


def nudge(dx: int, dy: int) -> None:
    """Relative pointer motion: what mouse look reads in relative mouse mode."""
    input_inject.xt.XTestFakeRelativeMotionEvent(input_inject.d, dx, dy, 0)
    input_inject.x11.XFlush(input_inject.d)


def rpress() -> None:
    input_inject.button(3, True)


def rrelease() -> None:
    input_inject.button(3, False)


def key_down(key: str) -> None:
    kc = input_inject.x11.XKeysymToKeycode(
        input_inject.d, input_inject.x11.XStringToKeysym(key.encode())
    )
    input_inject.xt.XTestFakeKeyEvent(input_inject.d, kc, 1, 0)
    input_inject.x11.XFlush(input_inject.d)
    time.sleep(0.08)


def key_up(key: str) -> None:
    kc = input_inject.x11.XKeysymToKeycode(
        input_inject.d, input_inject.x11.XStringToKeysym(key.encode())
    )
    input_inject.xt.XTestFakeKeyEvent(input_inject.d, kc, 0, 0)
    input_inject.x11.XFlush(input_inject.d)
    time.sleep(0.08)


def key_edge(key: str, down: bool) -> None:
    """One key edge, sent at once: the caller keeps the time between edges."""
    kc = input_inject.x11.XKeysymToKeycode(
        input_inject.d, input_inject.x11.XStringToKeysym(key.encode())
    )
    input_inject.xt.XTestFakeKeyEvent(input_inject.d, kc, 1 if down else 0, 0)
    input_inject.x11.XFlush(input_inject.d)


def button_edge(number: int, down: bool) -> None:
    """One mouse button edge, sent at once: 1 left, 2 middle, 3 right."""
    input_inject.xt.XTestFakeButtonEvent(input_inject.d, number, 1 if down else 0, 0)
    input_inject.x11.XFlush(input_inject.d)


def key(key: str, hold_ms: int) -> None:
    input_inject.key(key, hold_ms)