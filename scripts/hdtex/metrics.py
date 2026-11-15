"""Numbers that say whether a converted texture can be trusted."""

from __future__ import annotations

import math

import numpy as np


def psnr(a: np.ndarray, b: np.ndarray) -> float:
    """Peak signal-to-noise ratio of two uint8 arrays, in dB. 99 means identical."""
    error = ((a.astype(np.float64) - b.astype(np.float64)) ** 2).mean()
    return 99.0 if error == 0 else round(10 * math.log10(255.0 * 255.0 / error), 2)


def channel_psnr(a: np.ndarray, b: np.ndarray) -> list[float]:
    return [psnr(a[:, :, channel], b[:, :, channel]) for channel in range(a.shape[2])]


def channel_correlation(a: np.ndarray, b: np.ndarray) -> list[float | None]:
    """Pearson correlation per channel. None for a channel that is constant in either image.

    Near 1 means the same picture. Near 0 means unrelated content, such as
    two channels swapped. Negative means the channel is inverted.
    """
    out: list[float | None] = []
    for channel in range(a.shape[2]):
        left = a[:, :, channel].astype(np.float64).ravel()
        right = b[:, :, channel].astype(np.float64).ravel()
        if left.std() == 0 or right.std() == 0:
            out.append(None)
        else:
            out.append(round(float(np.corrcoef(left, right)[0, 1]), 3))
    return out


def rmse(a: np.ndarray, b: np.ndarray) -> float:
    """Root mean square difference of two uint8 arrays, in levels."""
    return round(float(np.sqrt(((a.astype(np.float64) - b.astype(np.float64)) ** 2).mean())), 3)


def shrink(image: np.ndarray, factor: int) -> np.ndarray:
    """Box-average an (H, W, C) uint8 image down by an integer factor."""
    height, width, channels = image.shape
    blocks = image.reshape(height // factor, factor, width // factor, factor, channels)
    return np.rint(blocks.astype(np.float64).mean(axis=(1, 3))).astype(np.uint8)


def seam_ratio(image: np.ndarray) -> float:
    """Step across the wrap-around edges, relative to the step between inner neighbours.

    About 1 means the texture tiles as smoothly as it continues inside.
    Well above 1 means a visible seam where two tiles meet.
    """
    pixels = image.astype(np.float64)
    inner = (np.abs(np.diff(pixels, axis=0)).mean() + np.abs(np.diff(pixels, axis=1)).mean()) / 2
    edge = (np.abs(pixels[0] - pixels[-1]).mean() + np.abs(pixels[:, 0] - pixels[:, -1]).mean()) / 2
    return round(edge / inner, 3) if inner > 0 else (1.0 if edge == 0 else float("inf"))
