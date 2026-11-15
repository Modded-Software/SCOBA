"""Painted lane dirt ("Zerus Dirt Medium") from the map's terrain texture masks.

t3TextureMasks: a 64-byte header ("MASK", version 102, width, height in
mask cells), then 8 layers. Each layer is tiles of 64 x 64 four-bit values,
row-major tiles, two values per byte (high nibble first). Layer i is the
weight of texture slot i of t3Terrain.xml.
"""

from __future__ import annotations

import re
import struct
from pathlib import Path

import numpy as np

DIRT_NAME = "Zerus1"  # editor name "Zerus Dirt Medium" (swarm.sc2mod GameStrings)
DIRT_MIN = 8  # mask weight (0-15) at which a cell counts as dirt
TILE = 64


def texture_slot(map_dir: Path, name: str) -> int:
    xml = (map_dir / "t3Terrain.xml").read_text(encoding="utf-8")
    match = re.search(r'<texture i="(\d+)" name="' + re.escape(name) + '"/>', xml)
    if match is None:
        raise ValueError(f"t3Terrain.xml has no texture {name}")
    return int(match.group(1))


def layer(map_dir: Path, slot: int) -> np.ndarray:
    """Mask weights 0-15 of one texture slot, [row, col] with row 0 at y = 0."""
    data = (map_dir / "t3TextureMasks").read_bytes()
    magic, version, _reserved, w, h = struct.unpack_from("<4sIIII", data, 0)
    if magic != b"MASK" or version != 102:
        raise ValueError(f"t3TextureMasks: unexpected header {magic!r} {version}")
    tiles_x, tiles_y = w // TILE, h // TILE
    tile_bytes = TILE * TILE // 2
    base = 64 + slot * tiles_x * tiles_y * tile_bytes
    raw = np.frombuffer(data, dtype=np.uint8, count=tiles_x * tiles_y * tile_bytes, offset=base)
    nib = np.empty(raw.size * 2, dtype=np.uint8)
    nib[0::2] = raw >> 4
    nib[1::2] = raw & 0x0F
    tiles = nib.reshape(tiles_y, tiles_x, TILE, TILE)
    return tiles.transpose(0, 2, 1, 3).reshape(h, w)


def dirt_cells(map_dir: Path, n: int) -> np.ndarray:
    """Per map cell [y, x]: True where the dirt texture dominates."""
    weights = layer(map_dir, texture_slot(map_dir, DIRT_NAME))
    k = weights.shape[0] // n
    return weights.reshape(n, k, n, k).mean(axis=(1, 3)) >= DIRT_MIN
