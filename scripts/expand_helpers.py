"""Shared byte and grid helpers for the map expansion pipeline."""

from __future__ import annotations

import shutil
import struct
import subprocess
from pathlib import Path

import workpaths
from project_root import project_root

SCALE = 2
# Map audio (operator 2026-11-18): res/audio/*.wav goes to Assets\Sounds as
# Ogg Vorbis, the stock music format (and a tenth of the size). The encode is
# cached under SC2_OUT/audio (SPEC-PATHS) and redone when the wav is newer.
AUDIO_SRC = Path("res") / "audio"
AUDIO_DST = Path("Assets") / "Sounds"
AUDIO_CACHE = "audio"


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


def unpack_tile(tile: bytes) -> list[int]:
    cells = []
    for row in range(64):
        for col in range(32):
            b = tile[row * 32 + col]
            cells.append(b >> 4)
            cells.append(b & 0x0F)
    return cells


def pack_tile(cells: list[int]) -> bytes:
    out = bytearray(2048)
    for row in range(64):
        for col in range(32):
            a = cells[row * 64 + col * 2]
            b = cells[row * 64 + col * 2 + 1]
            out[row * 32 + col] = ((a & 0x0F) << 4) | (b & 0x0F)
    return bytes(out)


def expand_texture_masks(src: Path, dst: Path) -> None:
    data = read(src)
    magic, version, reserved, w, h = struct.unpack_from("<4sIIII", data, 0)
    assert magic == b"MASK" and version == 102 and w == 1024 and h == 1024
    old_tiles = 16
    new_tiles = 32
    tile_size = 2048
    layer_size = old_tiles * old_tiles * tile_size
    out = bytearray(64 + 8 * new_tiles * new_tiles * tile_size)
    out[:64] = data[:64]
    struct.pack_into("<4sIIII", out, 0, magic, version, reserved, 2048, 2048)
    write_pos = 64
    for layer in range(8):
        base = 64 + layer * layer_size
        for ty in range(new_tiles):
            for tx in range(new_tiles):
                old_tx = tx // 2
                old_ty = ty // 2
                old_tile = data[
                    base
                    + (old_ty * old_tiles + old_tx) * tile_size :
                    base
                    + (old_ty * old_tiles + old_tx + 1) * tile_size
                ]
                cells = unpack_tile(old_tile)
                dx = (tx % 2) * 32
                dy = (ty % 2) * 32
                scaled = [0] * (64 * 64)
                for y in range(64):
                    for x in range(64):
                        sx = dx + x // 2
                        sy = dy + y // 2
                        scaled[y * 64 + x] = cells[sy * 64 + sx]
                out[write_pos : write_pos + tile_size] = pack_tile(scaled)
                write_pos += tile_size
    write(dst, bytes(out))


def encode_ogg(wav: Path, ogg: Path) -> None:
    ogg.parent.mkdir(parents=True, exist_ok=True)
    command = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-map_metadata", "-1", "-c:a", "libvorbis", "-q:a", "6", "-ar", "44100", str(ogg)]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"ffmpeg failed on {wav}: {result.stderr.strip()}")


def import_audio(dst: Path, force: bool) -> None:
    """Every res/audio wav, as ogg, into the built map (SoundData names them)."""
    root = project_root()
    files = sorted((root / AUDIO_SRC).glob("*.wav"))
    if not files:
        raise SystemExit(f"no audio in {root / AUDIO_SRC}")
    (dst / AUDIO_DST).mkdir(parents=True, exist_ok=True)
    cache = workpaths.path("SC2_OUT") / AUDIO_CACHE
    for wav in files:
        ogg = cache / (wav.stem + ".ogg")
        if force or not ogg.is_file() or ogg.stat().st_mtime < wav.stat().st_mtime:
            encode_ogg(wav, ogg)
        shutil.copy2(ogg, dst / AUDIO_DST / ogg.name)
