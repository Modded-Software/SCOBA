"""Keep the coarse content of an upscaled image equal to its source.

Upscaler models drift: measured on the terrain set, colour came out up to
3.5 levels brighter and normals tilted by up to 3.7 levels. Seen from far
away the texture then no longer matches the original.

The fix works on cell averages. The source is averaged over cells of
LOW_CELL pixels, the result over the same areas, and the difference is
spread back over the result with bilinear weights. Detail inside a cell is
untouched, so compression noise of the source does not come back.
"""

from __future__ import annotations

import numpy as np

LOW_CELL = 32  # source pixels per cell side
PASSES = 2  # the bilinear spread smooths the difference, so one pass leaves a rest


def _grid(length: int) -> int:
    """Cells along one side. One cell, the plain mean, if the side does not divide."""
    return length // LOW_CELL if length >= LOW_CELL and length % LOW_CELL == 0 else 1


def cell_means(image: np.ndarray, rows: int, columns: int) -> np.ndarray:
    """Average an (H, W, C) image over a rows x columns grid of cells."""
    height, width, channels = image.shape
    cells = image.reshape(rows, height // rows, columns, width // columns, channels)
    return cells.mean(axis=(1, 3))


def _weights(cells: int, length: int, wrap: bool) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """For each pixel: the two nearest cell centres and the share of the second."""
    position = (np.arange(length, dtype=np.float32) + 0.5) * (cells / length) - 0.5
    low = np.floor(position).astype(np.int64)
    share = position - low
    high = low + 1
    if wrap:
        return low % cells, high % cells, share
    return np.clip(low, 0, cells - 1), np.clip(high, 0, cells - 1), share


def spread(field: np.ndarray, height: int, width: int, wrap: bool) -> np.ndarray:
    """Enlarge a grid of cell values to (height, width) with bilinear weights."""
    low, high, share = _weights(field.shape[0], height, wrap)
    rows = field[low] * (1.0 - share)[:, None, None] + field[high] * share[:, None, None]
    low, high, share = _weights(field.shape[1], width, wrap)
    return rows[:, low] * (1.0 - share)[None, :, None] + rows[:, high] * share[None, :, None]


def match(result: np.ndarray, source: np.ndarray, wrap: bool) -> np.ndarray:
    """Shift `result` so its cell averages equal those of `source`.

    Both are (H, W, C) float arrays in the same value domain. `result` is a
    whole multiple of `source` in size. `wrap` treats the image as tiling.
    """
    rows, columns = _grid(source.shape[0]), _grid(source.shape[1])
    target = cell_means(source, rows, columns)
    height, width = result.shape[:2]
    for _ in range(PASSES):
        difference = (target - cell_means(result, rows, columns)).astype(np.float32)
        result = result + spread(difference, height, width, wrap)
    return result
