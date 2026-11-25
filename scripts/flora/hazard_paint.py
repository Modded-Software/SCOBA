"""Paint a lava ground texture on and around every placed hazard.

Operator 2026-11-16: one unused palette texture is replaced by a lava
texture and painted under the hazards, blended out over a few cells.
There is no Zerus lava terrain texture; the stock CharLavaCracks
(liberty.sc2mod, glowing cracks) is used. RedstoneLavaCracks showed no lava
(operator 2026-11-16). Its normal map fills red and blue with copies of Y;
hdtex.core.roles.normal_layout handles that layout.
Slot 7 (was the unpainted Zerus5) holds it. Under the paint the other
layers, except the lane dirt (see scaled_slots), are scaled by
(1 - lava weight): the first try left them at full weight and the lava
barely showed. The slot is set in
src t3Terrain.xml, because the HD texture build reads the source palette.
The build fails if the slot already holds paint.
"""

from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

from . import config
from .dirt import DIRT_NAME, TILE, layer, texture_slot

SLOT = 7
TEXTURE = "CharLavaCracks"
LAYERS = 8
FULL = 15  # mask weight of solid paint
CELLS = 256  # map cells per side (out/SCOBA256)


def disc_weights(size: int, hazards: list[tuple[float, float, float]], blend: float) -> np.ndarray:
    """Mask weights [row, col] (row 0 at y = 0): FULL inside each hazard's
    half size, dropping linearly to 0 over `blend` map cells beyond it."""
    k = size / CELLS  # mask cells per map cell
    centres = (np.arange(size) + 0.5) / k
    gx, gy = np.meshgrid(centres, centres)
    best = np.zeros((size, size))
    for x, y, half in hazards:
        d = np.hypot(gx - x, gy - y) - half
        best = np.maximum(best, np.clip(1.0 - d / blend, 0.0, 1.0))
    return np.rint(best * FULL).astype(np.uint8)


def write_layer(path: Path, slot: int, weights: np.ndarray) -> None:
    data = bytearray(path.read_bytes())
    _magic, _version, _reserved, w, h = struct.unpack_from("<4sIIII", data, 0)
    tiles_x, tiles_y = w // TILE, h // TILE
    tile_bytes = TILE * TILE // 2
    base = 64 + slot * tiles_x * tiles_y * tile_bytes
    nib = weights.reshape(tiles_y, TILE, tiles_x, TILE).transpose(0, 2, 1, 3).reshape(-1)
    packed = (nib[0::2] << 4) | nib[1::2]
    data[base : base + packed.size] = packed.astype(np.uint8).tobytes()
    path.write_bytes(bytes(data))


def paint_problems(map_dir: Path, hazards: list[tuple[str, float, float]]) -> list[str]:
    """Built-map check: the slot holds the lava texture and exactly the planned paint."""
    map_dir = Path(map_dir)
    problems = []
    xml = (map_dir / "t3Terrain.xml").read_text(encoding="utf-8")
    if f'<texture i="{SLOT}" name="{TEXTURE}"/>' not in xml:
        problems.append(f"texture slot {SLOT} is not {TEXTURE}")
    have = layer(map_dir, SLOT)
    rows = [(x, y, config.HAZARD_HALF[kind]) for kind, x, y in hazards]
    plan = disc_weights(have.shape[0], rows, config.HAZARD_PAINT_BLEND)
    if not np.array_equal(have, plan):
        problems.append(f"texture slot {SLOT} paint differs from the hazard plan")
    solid = plan == FULL
    for slot in scaled_slots(map_dir):
        if layer(map_dir, slot)[solid].any():
            problems.append(f"texture slot {slot} still shows under solid lava")
    return problems


def paint(map_dir: Path, hazards: list[tuple[str, float, float]]) -> int:
    """Returns the number of mask cells painted."""
    map_dir = Path(map_dir)
    current = layer(map_dir, SLOT)
    if current.any():
        raise ValueError(f"texture slot {SLOT} already has paint; pick an unused slot")
    rows = [(x, y, config.HAZARD_HALF[kind]) for kind, x, y in hazards]
    weights = disc_weights(current.shape[0], rows, config.HAZARD_PAINT_BLEND)
    # The palette slot is set in src t3Terrain.xml (the HD texture build reads
    # the source palette); a map without it is rejected here.
    xml = (map_dir / "t3Terrain.xml").read_text(encoding="utf-8")
    if f'<texture i="{SLOT}" name="{TEXTURE}"/>' not in xml:
        raise ValueError(f"t3Terrain.xml slot {SLOT} must be {TEXTURE} (set it in src/SCOBA.SC2Map)")
    masks = map_dir / "t3TextureMasks"
    for slot in scaled_slots(map_dir):
        write_layer(masks, slot, under_lava(layer(map_dir, slot), weights))
    write_layer(masks, SLOT, weights)
    return int((weights > 0).sum())


def scaled_slots(map_dir: Path) -> list[int]:
    """Layers scaled down under the lava: all but the lava and the lane dirt.

    The lane dirt layer defines the lanes (flora.dirt, lane gates read it), so
    it is never changed; the lava, the top layer, still draws over it.
    """
    keep = {SLOT}
    xml = (Path(map_dir) / "t3Terrain.xml").read_text(encoding="utf-8")
    if f'name="{DIRT_NAME}"' in xml:
        keep.add(texture_slot(map_dir, DIRT_NAME))
    return [slot for slot in range(LAYERS) if slot not in keep]


def under_lava(other: np.ndarray, lava: np.ndarray) -> np.ndarray:
    """Another layer's weights scaled down where the lava is painted."""
    keep = 1.0 - lava.astype(np.float64) / FULL
    return np.rint(other * keep).astype(np.uint8)
