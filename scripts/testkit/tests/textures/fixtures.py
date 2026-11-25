"""Small textures and stand-in upscalers for the core's host tests. Nothing here touches a game or a GPU."""

from __future__ import annotations

import numpy as np
from hdtex.core import dds, registry
from hdtex.core.interfaces import Planes
from hdtex.core.steps import SCALE

SIZE = 64
TRAILER = b"_TAG"


def colour_rgba(seed: int = 1, width: int = SIZE, height: int = SIZE) -> np.ndarray:
    """A picture that tiles: waves over the whole side, a little noise, a dark mask in alpha."""
    rng = np.random.default_rng(seed)
    across = np.sin(np.arange(width) * (2 * np.pi / width))
    down = np.cos(np.arange(height) * (2 * np.pi / height))
    wave = down[:, None] * across[None, :]
    planes = [
        128 + 60 * np.roll(wave, shift, axis=1) for shift in (0, width // 4, width // 2)
    ]
    planes.append(48 + 40 * np.roll(wave, width // 8, axis=1))
    image = np.stack(planes, axis=2) + rng.normal(0, 2, (height, width, 4))
    return np.clip(np.rint(image), 0, 255).astype(np.uint8)


def noise_rgba(seed: int = 1, size: int = SIZE) -> np.ndarray:
    """A picture with nothing coarse in it: every pixel on its own."""
    return np.random.default_rng(seed).integers(0, 256, (size, size, 4), dtype=np.uint8)


def normal_rgba(width: int = SIZE, height: int = SIZE) -> np.ndarray:
    """A swizzled normal map: X in alpha, Y in green, red 255, blue 0."""
    rgba = np.zeros((height, width, 4), dtype=np.uint8)
    rgba[:, :, 0] = 255
    rgba[:, :, 1] = np.rint(
        (0.3 * np.cos(np.arange(height) * (2 * np.pi / height))[:, None] * 0.5 + 0.5)
        * 255
    )
    rgba[:, :, 3] = np.rint(
        (0.4 * np.sin(np.arange(width) * (2 * np.pi / width))[None, :] * 0.5 + 0.5)
        * 255
    )
    return rgba


def texture_file(
    role: str, rgba: np.ndarray, format: str = "DXT5", trailer: bytes = b""
) -> bytes:
    """A texture as a game stores it: the picture with a full mip chain."""
    layout = registry.ROLES.get(role)
    levels = layout.finish(layout.join(layout.split(rgba), None, True), rgba)
    codec = registry.CODECS.get(format)
    return dds.build(
        rgba.shape[1],
        rgba.shape[0],
        [codec.encode(level) for level in levels],
        trailer,
        format,
    )


def repeat(image: np.ndarray) -> np.ndarray:
    """Every pixel four times per side. The step across the edge stays, the steps inside shrink: a seam."""
    return image.repeat(SCALE, axis=0).repeat(SCALE, axis=1)


def smooth(image: np.ndarray) -> np.ndarray:
    """Four times per side with values between neighbours, around the edges too. It tiles as its input does."""
    values = image.astype(np.float32)
    for axis in (0, 1):
        share = (np.arange(SCALE, dtype=np.float32) + 0.5) / SCALE - 0.5
        before, after = np.roll(values, 1, axis=axis), np.roll(values, -1, axis=axis)
        parts = [
            values + (values - before) * part
            if part < 0
            else values + (after - values) * part
            for part in share
        ]
        shape = list(values.shape)
        shape[axis] *= SCALE
        values = np.stack(parts, axis=axis + 1).reshape(shape)
    return np.clip(np.rint(values), 0, 255).astype(np.uint8)


def invert(image: np.ndarray) -> np.ndarray:
    """Four times per side and every value turned around: another picture."""
    return 255 - smooth(image)


def planes_of(role: str, rgba: np.ndarray, enlarge=smooth) -> Planes:
    """The planes of a texture after one step of a stand-in upscaler."""
    return {
        name: enlarge(plane)
        for name, plane in registry.ROLES.get(role).split(rgba).items()
    }
