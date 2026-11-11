"""Game window input helpers for test profiles."""

from __future__ import annotations

import os
import re
import subprocess
import time

import input_inject


def window_geometry() -> tuple[int, int, int, int] | None:
    proc = subprocess.run(
        ["xwininfo", "-root", "-tree"],
        capture_output=True,
        text=True,
        env={**os.environ, "DISPLAY": os.environ.get("DISPLAY", ":0")},
    )
    if proc.returncode != 0:
        message = proc.stderr.strip()
        if not message:
            message = "xwininfo failed"
        raise RuntimeError(message)
    for line in proc.stdout.splitlines():
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
    proc = subprocess.run(
        ["xwininfo", "-root", "-tree"],
        capture_output=True,
        text=True,
        env={**os.environ, "DISPLAY": os.environ.get("DISPLAY", ":0")},
    )
    if proc.returncode != 0:
        message = proc.stderr.strip()
        if not message:
            message = "xwininfo failed"
        raise RuntimeError(message)
    for line in proc.stdout.splitlines():
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


def key(key: str, hold_ms: int) -> None:
    input_inject.key(key, hold_ms)