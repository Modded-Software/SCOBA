"""Dirt texture on the sloped walls of the pools.

Operator, 2026-11-20: "remove rock waterfall features entirely, instead
paint the sloped walls of the pools with an upscaled rock texture"; then
"no switch to dirt replace with the dirt texture we use".

The texture is the lane dirt of the map's palette (t3Terrain.xml,
flora.dirt.DIRT_NAME). The HD texture build upscales every palette texture
(SPEC-HD-TEXTURES). The weight follows the slope of the carved ground: none
on flat ground, solid on a wall. The dirt layer only gains weight: paint it
already holds (the lanes) stays. Under the new paint the other layers are
scaled by (1 - weight), as flora.hazard_paint does for the lava.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from flora.dirt import layer, texture_slot
from flora.hazard_paint import FULL, LAYERS, under_lava, write_layer

from . import carve, config
from .sites import Site


def slope(ground: np.ndarray) -> np.ndarray:
    """Rise per cell at every vertex."""
    gy, gx = np.gradient(ground)
    return np.hypot(gx, gy)


def vertex_weights(ground: np.ndarray, sites: list[Site]) -> np.ndarray:
    """Paint weight 0..1 per vertex: the slope, at the pools only."""
    low, high = config.WALL_SLOPE
    weight = np.clip((slope(ground) - low) / (high - low), 0.0, 1.0)
    zone = np.zeros(ground.shape, dtype=bool)
    for site in sites:
        zone |= carve.inside(ground.shape, site.rect, config.WALL_MARGIN)
    return np.where(zone, weight, 0.0)


def mask_weights(vertex: np.ndarray, size: int) -> np.ndarray:
    """Vertex weights as mask weights 0..FULL, [row, col] with row 0 at y = 0."""
    cells = vertex.shape[0] - 1
    at = (np.arange(size) + 0.5) * cells / size  # mask cell centres, in map cells
    i = np.minimum(at.astype(int), cells - 1)
    f = at - i
    rows = vertex[i, :] * (1 - f)[:, None] + vertex[i + 1, :] * f[:, None]
    both = rows[:, i] * (1 - f)[None, :] + rows[:, i + 1] * f[None, :]
    return np.rint(both * FULL).astype(np.uint8)


def problems(map_dir: Path) -> list[str]:
    """What stops the paint, found before anything is written."""
    map_dir = Path(map_dir)
    if not (map_dir / "t3TextureMasks").is_file():
        return [f"no t3TextureMasks in {map_dir}"]
    try:
        texture_slot(map_dir, config.WALL_TEXTURE)
    except ValueError as error:
        return [f"{error} (the wall texture must be in the palette of src/SCOBA.SC2Map)"]
    return []


def apply(map_dir: Path, ground: np.ndarray, sites: list[Site]) -> int:
    """Paint the walls. Returns the number of mask cells that gained dirt."""
    map_dir = Path(map_dir)
    wrong = problems(map_dir)
    if wrong:
        raise ValueError("water features: " + "; ".join(wrong))
    slot = texture_slot(map_dir, config.WALL_TEXTURE)
    had = layer(map_dir, slot)
    weights = mask_weights(vertex_weights(ground, sites), had.shape[0])
    want = np.maximum(had, weights)  # the layer only gains: lane dirt stays
    gain = np.where(want > had, weights, 0).astype(np.uint8)  # nothing is scaled where the dirt was already as strong
    masks = map_dir / "t3TextureMasks"
    for other in range(LAYERS):
        if other != slot:
            write_layer(masks, other, under_lava(layer(map_dir, other), gain))
    write_layer(masks, slot, want)
    if not np.array_equal(layer(map_dir, slot), want):
        raise ValueError("water features: the wall paint read back differs from the plan")
    return int((want > had).sum())
