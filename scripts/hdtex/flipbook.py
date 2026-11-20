"""Flip books: a texture whose picture is a grid of cells, one per frame.

A cell must not take pixels from the next cell when the texture is upscaled.
"""

from __future__ import annotations

import numpy as np

# A flip book is upscaled with its cells apart: each cell gets a rim of its
# own edge pixels, this many per side, so no cell reaches into the next.
FLIP_MARGIN = 16


def explode(image: np.ndarray, grid: tuple[int, int], margin: int) -> np.ndarray:
    """The picture with every cell of its (columns, rows) grid grown by `margin` edge pixels per side."""
    columns, rows = grid
    high, wide = image.shape[0] // rows, image.shape[1] // columns
    rim = ((margin, margin), (margin, margin)) + ((0, 0),) * (image.ndim - 2)
    return np.concatenate(
        [
            np.concatenate(
                [np.pad(image[r * high : (r + 1) * high, c * wide : (c + 1) * wide], rim, mode="edge") for c in range(columns)],
                axis=1,
            )
            for r in range(rows)
        ],
        axis=0,
    )


def implode(image: np.ndarray, grid: tuple[int, int], margin: int) -> np.ndarray:
    """`explode` undone: the rim of `margin` pixels cut from every cell."""
    columns, rows = grid
    high, wide = image.shape[0] // rows, image.shape[1] // columns
    return np.concatenate(
        [
            np.concatenate(
                [image[r * high + margin : (r + 1) * high - margin, c * wide + margin : (c + 1) * wide - margin] for c in range(columns)],
                axis=1,
            )
            for r in range(rows)
        ],
        axis=0,
    )
