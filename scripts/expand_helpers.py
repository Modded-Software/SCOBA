"""Shared byte and grid helpers for the map expansion pipeline."""

from __future__ import annotations

from pathlib import Path

SCALE = 2


def read(path: Path) -> bytes:
    return path.read_bytes()


def write(path: Path, data: bytes) -> None:
    path.write_bytes(data)


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def upsample_grid(values: list[float], old_n: int, new_n: int) -> list[float]:
    out = [0.0] * (new_n * new_n)
    for y in range(new_n):
        oy = y / 2.0
        y0 = min(int(oy), old_n - 1)
        y1 = min(y0 + 1, old_n - 1)
        ty = oy - y0
        for x in range(new_n):
            ox = x / 2.0
            x0 = min(int(ox), old_n - 1)
            x1 = min(x0 + 1, old_n - 1)
            tx = ox - x0
            v0 = lerp(values[y0 * old_n + x0], values[y0 * old_n + x1], tx)
            v1 = lerp(values[y1 * old_n + x0], values[y1 * old_n + x1], tx)
            out[y * new_n + x] = lerp(v0, v1, ty)
    return out


def clone_cells(data: bytes, old_w: int, old_h: int, stride: int) -> bytes:
    out = bytearray(old_w * SCALE * old_h * SCALE * stride)
    new_w = old_w * SCALE
    for y in range(old_h * SCALE):
        sy = y // SCALE
        for x in range(old_w * SCALE):
            sx = x // SCALE
            src = (sy * old_w + sx) * stride
            dst = (y * new_w + x) * stride
            out[dst : dst + stride] = data[src : src + stride]
    return bytes(out)