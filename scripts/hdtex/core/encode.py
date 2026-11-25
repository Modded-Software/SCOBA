"""Join the planes of a result into a file of its original's layout, and measure it.

The file keeps the original's format and the bytes after its last mip. It
has a full mip chain. The same chain without its largest levels is the
result at a smaller size.
"""

from __future__ import annotations

import math
from typing import NamedTuple

import numpy as np

from . import dds, lowfreq, metrics
from .interfaces import Planes, Role
from .store import kept_sizes

ENCODER_VERSION = 1  # raise it when the same planes would give another file


class EncodeError(ValueError):
    """The planes do not make a texture of the original's layout."""


class Encoded(NamedTuple):
    format: str
    size: tuple[int, int]  # width, height at its own size
    mips: int
    source_size: tuple[int, int]
    files: dict[int, bytes]  # longest side to file
    numbers: dict


def read_texture(data: bytes) -> tuple[dds.Dds, np.ndarray]:
    """A texture file and its largest level as (H, W, 4) uint8."""
    texture = dds.parse(data)
    return texture, texture.codec.decode(
        texture.level_bytes(0), texture.width, texture.height
    )


def _level(levels: list[np.ndarray], width: int) -> np.ndarray:
    """The level of a chain that is `width` wide, or the largest one below it."""
    return next(level for level in levels if level.shape[1] <= width)


def _finite(value: float) -> float | None:
    return value if math.isfinite(value) else None


def measure(
    levels: list[np.ndarray],
    decoded: np.ndarray,
    source: np.ndarray,
    reference: list[np.ndarray],
) -> dict:
    """The numbers of `limits`. `decoded` is the largest level after the codec; `reference` the original's own chain."""
    width = levels[0].shape[1]
    shrunk = metrics.shrink(levels[0], width // source.shape[1])
    coarse = max(1, source.shape[1] // lowfreq.LOW_CELL)
    return {
        "encode_psnr": metrics.channel_psnr(levels[0], decoded),
        "fidelity_psnr": metrics.channel_psnr(shrunk, source),
        "fidelity_corr": metrics.channel_correlation(shrunk, source),
        "coarse_rmse": metrics.rmse(_level(levels, coarse), _level(reference, coarse)),
        "seam_source": _finite(metrics.seam_ratio(source)),
        "seam": _finite(metrics.seam_ratio(levels[0])),
    }


def encode(original: bytes, role: Role, planes: Planes) -> Encoded:
    """The result of `planes` for the texture file `original`, at every kept size."""
    source, source_rgba = read_texture(original)
    source_planes = role.split(source_rgba)
    # Every texture is joined as one that tiles: the upscaler made its edges match.
    levels = role.finish(role.join(planes, source_planes, True), source_rgba)
    reference = role.finish(role.join(source_planes, None, True), source_rgba)
    height, width = levels[0].shape[:2]
    if (
        width % source.width
        or height % source.height
        or width * source.height != height * source.width
    ):
        raise EncodeError(
            f"a result of {width}x{height} is not a whole multiple of the original's {source.width}x{source.height}"
        )
    codec = source.codec
    if codec.opaque:
        if int(source_rgba[:, :, 3].min()) < 255:
            raise EncodeError(
                f"the original is {source.format} with transparent pixels, which the encoder cannot write"
            )
        for level in levels:
            level[:, :, 3] = 255
    blobs = [codec.encode(level) for level in levels]
    files = {}
    for longest in kept_sizes(max(width, height)):
        skip = next(
            index
            for index, level in enumerate(levels)
            if max(level.shape[:2]) == longest
        )
        top = levels[skip]
        files[longest] = dds.build(
            top.shape[1], top.shape[0], blobs[skip:], source.trailer, source.format
        )
    numbers = measure(
        levels, codec.decode(blobs[0], width, height), source_rgba, reference
    )
    return Encoded(
        source.format,
        (width, height),
        len(levels),
        (source.width, source.height),
        files,
        numbers,
    )
