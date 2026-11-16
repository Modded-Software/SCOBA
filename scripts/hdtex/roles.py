"""What the channels of a texture mean, and how to upscale them.

A role splits an RGBA texture into planes. Each plane is a plain image the
upscaler can handle. After upscaling, the role joins the planes into an RGBA
mip chain again, in the layout the game expects.

    diffuse  RGB colour and a specular mask in alpha
    normal   tangent-space normal, stored as X in alpha and Y in green

A new texture kind, such as a doodad emissive map, is a new entry in ROLES.
"""

from __future__ import annotations

from typing import Callable, NamedTuple

import numpy as np

from . import lowfreq

# The game's own mips are averaged in linear light with this gamma. Measured
# on its terrain files: byte averaging misses their small levels by twice
# the error of this curve.
GAMMA = 2.2

# The game stores red as 255 and blue as 0 in its swizzled normal maps.
NORMAL_RED = 255
NORMAL_BLUE = 0
NORMAL_TOLERANCE = 8

Planes = dict[str, np.ndarray]


class RoleError(ValueError):
    """The texture does not have the layout its role expects."""


class Plane(NamedTuple):
    name: str  # variants.py names the upscaler model of each plane


class Role(NamedTuple):
    """`join(planes, source, wrap)` builds the mip chain, largest level first.

    `source` holds the planes of the original texture. With it, the coarse
    content of the result is matched to the original. `wrap` says the
    texture tiles.
    """

    name: str
    planes: tuple[Plane, ...]
    split: Callable[[np.ndarray], Planes]
    join: Callable[[Planes, Planes | None, bool], list[np.ndarray]]


def _halve(image: np.ndarray) -> np.ndarray:
    """2x2 box filter. Sizes are powers of two, so no row is left over."""
    height, width = image.shape[:2]
    rows = image.reshape(max(1, height // 2), min(2, height), width, -1).mean(axis=1)
    return rows.reshape(rows.shape[0], max(1, width // 2), min(2, width), -1).mean(axis=2)


def _chain(top: np.ndarray, fix: Callable[[np.ndarray], np.ndarray]) -> list[np.ndarray]:
    """Mip chain down to 1x1. `fix` repairs each level after averaging."""
    levels = [top]
    while max(levels[-1].shape[:2]) > 1:
        levels.append(fix(_halve(levels[-1])))
    return levels


def shrink_color(image: np.ndarray, factor: int) -> np.ndarray:
    """Shrink an 8-bit RGB image by a power of two, averaging in linear light."""
    if factor < 1 or factor & (factor - 1):
        raise RoleError(f"shrink factor must be a power of two, got {factor}")
    linear = (image.astype(np.float32) / 255.0) ** GAMMA
    while factor > 1:
        linear = _halve(linear)
        factor //= 2
    return _to_byte(np.clip(linear, 0.0, 1.0) ** (1.0 / GAMMA))


def _to_byte(value: np.ndarray) -> np.ndarray:
    return np.clip(np.rint(value * 255.0), 0, 255).astype(np.uint8)


def _grey(plane: np.ndarray) -> np.ndarray:
    """The upscaler returns grey planes as RGB. Average them back to one channel."""
    return plane if plane.ndim == 2 else plane.mean(axis=2)


def split_diffuse(rgba: np.ndarray) -> Planes:
    return {"color": rgba[:, :, :3].copy(), "alpha": rgba[:, :, 3].copy()}


def _linear_diffuse(planes: Planes) -> np.ndarray:
    """Colour in linear light and the mask as it is, as one (H, W, 4) float image."""
    color = (planes["color"].astype(np.float32) / 255.0) ** GAMMA
    alpha = _grey(planes["alpha"]).astype(np.float32) / 255.0
    if color.shape[:2] != alpha.shape[:2]:
        raise RoleError(f"colour is {color.shape[:2]}, alpha is {alpha.shape[:2]}")
    return np.concatenate([color, alpha[:, :, None]], axis=2)


def join_diffuse(planes: Planes, source: Planes | None = None, wrap: bool = True) -> list[np.ndarray]:
    top = _linear_diffuse(planes)
    if source is not None:
        top = np.clip(lowfreq.match(top, _linear_diffuse(source), wrap), 0.0, 1.0)
    out = []
    for level in _chain(top, lambda level: level):
        color = np.clip(level[:, :, :3], 0.0, 1.0) ** (1.0 / GAMMA)
        out.append(_to_byte(np.concatenate([color, level[:, :, 3:]], axis=2)))
    return out


def _unit(vectors: np.ndarray) -> np.ndarray:
    length = np.linalg.norm(vectors, axis=2, keepdims=True)
    flat = np.array([0.0, 0.0, 1.0], dtype=vectors.dtype)
    return np.where(length > 1e-6, vectors / np.maximum(length, 1e-6), flat)


def _vectors(planes: Planes) -> np.ndarray:
    return _unit(planes["normal"].astype(np.float32) / 255.0 * 2.0 - 1.0)


# Swizzled normal maps carry X in alpha and Y in green; the game reads only
# those two. Red and blue hold one of two fillers:
#   "fixed": red 255, blue 0 (the Zerus maps);
#   "copy":  red and blue equal, both a copy of Y (CharLavaCracks: R == B
#            exactly, correlation with green 0.998).
COPY_MIN_CORR = 0.95


def normal_layout(rgba: np.ndarray) -> str:
    red, green, blue = (rgba[:, :, c].astype(int) for c in range(3))
    if np.abs(red - NORMAL_RED).max() <= NORMAL_TOLERANCE and np.abs(blue - NORMAL_BLUE).max() <= NORMAL_TOLERANCE:
        return "fixed"
    if np.abs(red - blue).max() <= NORMAL_TOLERANCE and red.std() > 0 and green.std() > 0:
        if np.corrcoef(red.ravel(), green.ravel())[0, 1] >= COPY_MIN_CORR:
            return "copy"
    raise RoleError(
        "not a swizzled normal map: red/blue must be 255/0 or both a copy of green, "
        f"got red {red.min()}..{red.max()}, blue {blue.min()}..{blue.max()}"
    )


def split_normal(rgba: np.ndarray) -> Planes:
    """Rebuild Z, so the upscaler sees an ordinary blue-ish normal map."""
    normal_layout(rgba)
    x = rgba[:, :, 3].astype(np.float32) / 255.0 * 2.0 - 1.0
    y = rgba[:, :, 1].astype(np.float32) / 255.0 * 2.0 - 1.0
    z = np.sqrt(np.clip(1.0 - x * x - y * y, 0.0, 1.0))
    return {"normal": _to_byte(np.stack([x, y, z], axis=2) * 0.5 + 0.5)}


def match_layout(levels: list[np.ndarray], layout: str) -> list[np.ndarray]:
    """join_normal writes the "fixed" filler; "copy" maps get Y in red and blue again."""
    if layout == "fixed":
        return levels
    out = []
    for level in levels:
        level = level.copy()
        level[:, :, 0] = level[:, :, 1]
        level[:, :, 2] = level[:, :, 1]
        out.append(level)
    return out


def join_normal(planes: Planes, source: Planes | None = None, wrap: bool = True) -> list[np.ndarray]:
    """Every level is unit length again before it is packed."""
    vectors = _vectors(planes)
    if source is not None:
        vectors = _unit(lowfreq.match(vectors, _vectors(source), wrap))
    out = []
    for level in _chain(vectors, _unit):
        rgba = np.empty(level.shape[:2] + (4,), dtype=np.uint8)
        rgba[:, :, 0] = NORMAL_RED
        rgba[:, :, 1] = _to_byte(level[:, :, 1] * 0.5 + 0.5)
        rgba[:, :, 2] = NORMAL_BLUE
        rgba[:, :, 3] = _to_byte(level[:, :, 0] * 0.5 + 0.5)
        out.append(rgba)
    return out


ROLES = {
    "diffuse": Role("diffuse", (Plane("color"), Plane("alpha")), split_diffuse, join_diffuse),
    "normal": Role("normal", (Plane("normal"),), split_normal, join_normal),
}


def limit_size(levels: list[np.ndarray], max_size: int) -> list[np.ndarray]:
    """Drop the largest levels until the top one fits `max_size`."""
    if max_size < 1:
        raise ValueError(f"max_size must be at least 1, got {max_size}")
    while len(levels) > 1 and max(levels[0].shape[:2]) > max_size:
        levels = levels[1:]
    return levels
