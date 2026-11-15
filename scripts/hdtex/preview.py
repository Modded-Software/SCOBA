"""Comparison sheets for judging upscaled textures by eye.

One PNG per texture. Each plane is one row with four tiles:

    source | result | source at the seam | result at the seam

The source is enlarged with a plain filter to the size of the result. The
result is decoded from the finished DDS, so it shows what the game gets.
A seam tile is centred on the corner where four copies of the texture
meet. A cross there is a tiling seam. A cross in both seam tiles comes
from the original file.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from . import roles
from .pipeline import read_texture

CROP = 192  # result pixels per tile side
ZOOM = 2
GAP = 8
TILES = 4


def stretch(plane: np.ndarray, low: int, high: int) -> np.ndarray:
    """Spread a narrow grey range over black to white, so a dark mask is readable."""
    scaled = (plane.astype(np.float32) - low) * (255.0 / max(1, high - low))
    return np.clip(np.rint(scaled), 0, 255).astype(np.uint8)


def _tile(plane: np.ndarray, top: int, left: int) -> Image.Image:
    crop = plane[top : top + CROP, left : left + CROP]
    return Image.fromarray(crop).convert("RGB").resize((CROP * ZOOM, CROP * ZOOM), Image.NEAREST)


def sheet(role_name: str, source_rgba: np.ndarray, result_rgba: np.ndarray) -> Image.Image:
    role = roles.ROLES[role_name]
    source_planes = role.split(source_rgba)
    result_planes = role.split(result_rgba)
    side = CROP * ZOOM
    out = Image.new("RGB", (TILES * (side + GAP) - GAP, len(role.planes) * (side + GAP) - GAP), "white")
    height, width = result_rgba.shape[:2]
    top, left = (height - CROP) // 3, (width - CROP) // 3
    seam_top, seam_left = (height - CROP) // 2, (width - CROP) // 2
    for row, plane in enumerate(role.planes):
        source, result = source_planes[plane.name], result_planes[plane.name]
        if source.ndim == 2:
            low, high = int(source.min()), int(source.max())
            source, result = stretch(source, low, high), stretch(result, low, high)
        enlarged = np.asarray(Image.fromarray(source).resize((width, height), Image.BICUBIC))
        tiles = (
            _tile(enlarged, top, left),
            _tile(result, top, left),
            _tile(np.roll(enlarged, (height // 2, width // 2), axis=(0, 1)), seam_top, seam_left),
            _tile(np.roll(result, (height // 2, width // 2), axis=(0, 1)), seam_top, seam_left),
        )
        for column, tile in enumerate(tiles):
            out.paste(tile, (column * (side + GAP), row * (side + GAP)))
    return out


def write_sheets(folder: Path, manifest: dict) -> list[Path]:
    """Write one sheet per texture of a cached source. Returns the files."""
    target = folder / "preview"
    target.mkdir(parents=True, exist_ok=True)
    written = []
    for texture in manifest["textures"]:
        _source, source_rgba = read_texture(folder / "original" / Path(*texture["casc_path"].split("\\")))
        _result, result_rgba = read_texture(folder / texture["file"])
        path = target / (Path(texture["file"]).stem + ".png")
        sheet(texture["role"], source_rgba, result_rgba).save(path)
        written.append(path)
    return written
