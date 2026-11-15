"""The upscaling variants: which model upscales which plane.

A variant is one set of upscaled textures. Each has its own cache folder, so
the variants exist side by side. The map build injects one of them, picked
by SC2_HD_TEXTURES.

The models are those of the arc-upscale tool:

    pbrify   stays close to the input
    fast     softer, invents nothing
    seedvr2  one-step diffusion, the most detail, invents detail
"""

from __future__ import annotations

import os
from typing import NamedTuple

ENV = "SC2_HD_TEXTURES"
OFF = "off"
DEFAULT = "upscale"


class VariantError(ValueError):
    """SC2_HD_TEXTURES names no variant."""


class Input(NamedTuple):
    """A plane's upscaler input taken from another variant's result, not the original."""

    variant: str  # its key; that variant must be built first
    shrink: int  # its 4x result is shrunk by this power of two before upscaling


class Variant(NamedTuple):
    key: str  # the cache folder, and the value of SC2_HD_TEXTURES
    title: str
    planes: dict[str, str]  # plane name to model
    textures: dict[str, str]  # "texture.plane" to model, the texture being the file name in lower case
    inputs: dict[str, Input] = {}  # plane name to input; planes not named read the original

    def model_for(self, plane: str, stem: str) -> str:
        return self.textures.get(f"{stem}.{plane}") or self.planes[plane]


class Choice(NamedTuple):
    key: str | None  # None: the map keeps the built-in textures
    asked: bool  # SC2_HD_TEXTURES is set, so a missing cache is an error


VARIANTS = {
    # pbrify draws a crosshatch pattern into smooth normal maps and masks.
    # fast does not, so those planes use it.
    #
    # On colour pbrify is the sharper one. On dark, low-contrast colour it
    # invents structure the original does not have: hatching on zerus_4, a
    # repainted look on zerus_8. Those two keep fast.
    "upscale": Variant(
        "upscale",
        "Upscale 4x",
        {"color": "pbrify", "alpha": "fast", "normal": "fast"},
        {"zerus_4.color": "fast", "zerus_8.color": "fast"},
    ),
    # seedvr2 invents detail, so it gets the colour only. The mask and the
    # normal map are data: they stay as in "upscale", and the two variants
    # differ in colour alone.
    #
    # From the 1024 original seedvr2 looked worse than "upscale" to the
    # operator: too little to work with. So its input is the "upscale"
    # colour shrunk to half, 2048 for the terrain. Its 4x result is shrunk
    # to the size of the other planes before the join.
    "generative": Variant(
        "generative",
        "Generative 4x",
        {"color": "seedvr2", "alpha": "fast", "normal": "fast"},
        {},
        {"color": Input("upscale", 2)},
    ),
}


def chosen() -> Choice:
    """The variant the map build injects, read from SC2_HD_TEXTURES."""
    value = os.environ.get(ENV, "").strip().lower()
    if not value:
        return Choice(DEFAULT, False)
    if value == OFF:
        return Choice(None, True)
    if value not in VARIANTS:
        raise VariantError(f"{ENV}={value} names no variant; use {', '.join(VARIANTS)}, or {OFF}")
    return Choice(value, True)
