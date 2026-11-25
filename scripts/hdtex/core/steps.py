"""One step on one plane: what goes to the upscaler, and what is kept of its output.

    prepare   the plane as the upscaler takes it, or nothing when it is passed on
    conclude  the step's plane, from the upscaler's output

A flip book gets a rim around each cell before the upscaler and loses it
after, so no cell takes pixels from another. The sizes a step keeps are
those of `variants` (SPEC-HD-TEXTURES 4.3).
"""

from __future__ import annotations

import numpy as np

from . import roles
from .flipbook import FLIP_MARGIN, explode, implode
from .variants import MAX_INPUT, MAX_OUTPUT, SCALE, after, fitted, passes

SINGLE = (1, 1)

__all__ = [
    "MAX_INPUT",
    "MAX_OUTPUT",
    "SCALE",
    "StepError",
    "after",
    "conclude",
    "fit",
    "fitted",
    "passes",
    "prepare",
    "side",
]


class StepError(ValueError):
    """A plane does not fit the step."""


def side(image: np.ndarray) -> int:
    return max(image.shape[:2])


def fit(image: np.ndarray, limit: int, colour: bool) -> np.ndarray:
    """The plane halved until no side is above `limit`. Colour is averaged in linear light."""
    while side(image) > limit:
        if image.shape[0] % 2 or image.shape[1] % 2:
            raise StepError(
                f"a plane of {image.shape[1]}x{image.shape[0]} cannot be halved"
            )
        image = roles.shrink_color(image, 2) if colour else roles.shrink_plain(image, 2)
    return image


def prepare(
    plane: np.ndarray, colour: bool, grid: tuple[int, int]
) -> np.ndarray | None:
    """The plane as the upscaler takes it. None: the step passes the plane on."""
    if passes(side(plane), colour):
        return None
    image = fit(plane, MAX_INPUT, colour)
    return explode(image, grid, FLIP_MARGIN) if tuple(grid) != SINGLE else image


def conclude(
    plane: np.ndarray, upscaled: np.ndarray | None, colour: bool, grid: tuple[int, int]
) -> np.ndarray:
    """The step's plane. `upscaled` is the upscaler's output for `prepare(plane)`, or None when that was None."""
    if upscaled is None:
        return fit(plane, MAX_OUTPUT, colour)
    image = (
        implode(upscaled, grid, FLIP_MARGIN * SCALE)
        if tuple(grid) != SINGLE
        else upscaled
    )
    given = fit(plane, MAX_INPUT, colour).shape[:2]
    if image.shape[:2] != (given[0] * SCALE, given[1] * SCALE):
        raise StepError(
            f"the upscaler gave {image.shape[1]}x{image.shape[0]} for an input of {given[1]}x{given[0]}, not {SCALE} times as much"
        )
    return fit(image, MAX_OUTPUT, colour)
