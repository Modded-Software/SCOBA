"""Variants of a texture, named by what made them (SPEC-HD-TEXTURES 4.1, 4.3).

A variant id is `original`, or its steps joined by `+`, first step first.
Each step is `model@size`: `pbrify@2048`, `pbrify@4096+seedvr2@4096`. The
size of a step that is not the last is the size the next step takes as
input. The size of the last step is the variant's own size.

The id without its last `@size` is the recipe: what the GPU makes. All
variants of one recipe come from one upscale and differ only in size.
"""

from __future__ import annotations

import re
from typing import NamedTuple

from .interfaces import Plane
from .store import kept_sizes

ORIGINAL = "original"
JOIN = "+"
AT = "@"
SIZES = (1024, 2048, 4096)
SCALE = 4
MAX_INPUT = 2048  # per side, of what the upscaler takes
MAX_OUTPUT = 4096  # per side, of what a step keeps
STEP = re.compile(r"([a-z0-9]+)(?:@([0-9]+))?")


class VariantError(ValueError):
    """The text names no variant or recipe, or the texture cannot have it."""


class Model(NamedTuple):
    id: str
    title: str
    colour_model: str  # the runner's model for colour planes
    data_model: str  # the runner's model for data planes
    invents: bool  # it adds detail the input does not hold
    note: str

    def model_for(self, plane: Plane) -> str:
        return self.colour_model if plane.colour else self.data_model


# The models are those of the runner. `pbrify` is the sharper one on colour
# but draws a crosshatch into masks and normal maps, so data gets `fast`
# (O-HD-10). `seedvr2` invents detail, so it gets colour only (R-HD-122).
MODELS = {
    "pbrify": Model(
        "pbrify",
        "PBRify",
        "pbrify",
        "fast",
        False,
        "sharp on colour; data planes get fast",
    ),
    "fast": Model("fast", "Fast", "fast", "fast", False, "soft; every plane"),
    "seedvr2": Model(
        "seedvr2",
        "SeedVR2",
        "seedvr2",
        "fast",
        True,
        "invents detail; colour only, data planes get fast",
    ),
}
DATA_MODEL = "fast"  # the one model of a texture without a colour plane


class Step(NamedTuple):
    model: Model
    size: int | None  # the size the next step takes; None for the last step of a recipe


def _model(name: str, text: str) -> Model:
    if name not in MODELS:
        raise VariantError(
            f"unknown model {name!r} in {text!r}; models: {', '.join(MODELS)}"
        )
    return MODELS[name]


def _size(value: str, text: str) -> int:
    size = int(value)
    if size < 1:
        raise VariantError(f"a size in {text!r} is a whole number of pixels")
    return size


def parse_recipe(recipe: object) -> tuple[Step, ...]:
    """The steps of a recipe: every step but the last has its size."""
    parts = recipe.split(JOIN) if isinstance(recipe, str) and recipe else []
    if not parts:
        raise VariantError(
            f"a recipe is model@size steps joined by {JOIN}, the last without a size; got {recipe!r}"
        )
    found = []
    for number, part in enumerate(parts, 1):
        match = STEP.fullmatch(part)
        last = number == len(parts)
        if match is None or (match.group(2) is None) != last:
            raise VariantError(
                f"step {number} of {recipe!r} is {part!r}; a step is model@size, the last one model alone"
            )
        found.append(
            Step(
                _model(match.group(1), recipe),
                None if last else _size(match.group(2), recipe),
            )
        )
    return tuple(found)


def split(variant: object) -> tuple[str, int]:
    """A variant id as recipe and size. The original is ("", 0)."""
    if variant == ORIGINAL:
        return "", 0
    if not isinstance(variant, str) or AT not in variant:
        raise VariantError(
            f"a variant is {ORIGINAL!r} or model@size steps joined by {JOIN}; got {variant!r}"
        )
    recipe, _, size = variant.rpartition(AT)
    if not size.isdigit():
        raise VariantError(f"a variant ends in @size; got {variant!r}")
    parse_recipe(recipe)
    return recipe, _size(size, variant)


def variant_id(recipe: str, size: int) -> str:
    return f"{recipe}{AT}{size}"


def join(input_variant: str, model: str, size: int) -> str:
    """The id of what `model` makes of `input_variant`, at `size`."""
    _model(model, model)
    split(input_variant)  # refuses what is no variant
    recipe = model if input_variant == ORIGINAL else f"{input_variant}{JOIN}{model}"
    return variant_id(recipe, size)


def input_of(variant: str) -> str:
    """The id of the variant a variant was made from: `original` for one step."""
    recipe, _ = split(variant)
    head, sep, _last = recipe.rpartition(JOIN)
    return head if sep else ORIGINAL


def prefixes(recipe: str) -> tuple[str, ...]:
    """The recipe after each of its steps: `a@1+b` gives `a`, `a@1+b`."""
    parts = recipe.split(JOIN)
    parse_recipe(recipe)
    return tuple(
        JOIN.join(parts[:count] + [parts[count].split(AT)[0]])
        for count in range(len(parts))
    )


def fitted(longest: int, limit: int) -> int:
    """The longest side a picture keeps when it is halved until no side is above `limit`."""
    while longest > limit:
        longest //= 2
    return longest


def passes(longest: int, colour: bool) -> bool:
    """A data plane that is already as large as a step may keep is passed on."""
    return not colour and longest >= MAX_OUTPUT


def after(longest: int, colour: bool) -> int:
    """The longest side of a plane after one step."""
    if passes(longest, colour):
        return fitted(longest, MAX_OUTPUT)
    return fitted(fitted(longest, MAX_INPUT) * SCALE, MAX_OUTPUT)


def own_size(steps: tuple[Step, ...], longest: int) -> int:
    """The own longest side of a recipe made from an original with that longest side."""
    for step in steps[:-1]:
        longest = min(after(longest, True), step.size or 0)
    return after(longest, True)


def model_refusal(recipe: str, colour: bool) -> str:
    """Why no texture of that kind can have the recipe, whatever its size. Empty: one can.

    `colour`: the texture has a colour plane. Without one, only `fast` is
    a model for it (R-HD-122, O-HD-10).
    """
    try:
        steps = parse_recipe(recipe)
    except VariantError as error:
        return str(error)
    if not colour and any(step.model.id != DATA_MODEL for step in steps):
        bad = next(step.model for step in steps if step.model.id != DATA_MODEL)
        return f"it has no colour plane, so {bad.id} is no model for it: {bad.note}; use {DATA_MODEL}"
    return ""


def refusal(recipe: str, longest: int, colour: bool) -> str:
    """Why a texture with that longest side cannot have the recipe. Empty: it can.

    The model check of model_refusal, then the steps against the size.
    `longest` is a read side; an unread size is model_refusal's case.
    """
    if longest <= 0:
        raise VariantError(f"a longest side is a positive number; got {longest}")
    if reason := model_refusal(recipe, colour):
        return reason
    steps = parse_recipe(recipe)
    for number, step in enumerate(steps[:-1], 1):
        own = after(longest, True)
        if step.size not in kept_sizes(own):
            return f"step {number} ({step.model.id}) is kept at {', '.join(map(str, kept_sizes(own)))}, not at {step.size}"
        longest = step.size or 0
    last = steps[-1].model
    if not last.invents and longest >= MAX_OUTPUT:
        return f"{last.id} on an input that already has a side of {longest} can add nothing"
    return ""


def size_refusal(recipe: str, size: int, longest: int) -> str:
    """Why a variant of the recipe cannot have `size`. Empty: it can (R-HD-123)."""
    own = own_size(parse_recipe(recipe), longest)
    if size not in kept_sizes(own):
        return f"{recipe} gives a side of {own} here, so it can be had at {', '.join(map(str, kept_sizes(own)))}, not at {size}"
    return ""


def title(variant: str) -> str:
    if variant == ORIGINAL:
        return "Original"
    recipe, size = split(variant)
    return (
        ", then ".join(
            f"{MODELS[step.split(AT)[0]].title}" for step in recipe.split(JOIN)
        )
        + f" at {size}"
    )
