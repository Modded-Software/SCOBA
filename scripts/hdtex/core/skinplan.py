"""What a skin upscale asks for (SPEC-HD-TEXTURES 4.6, R-HD-134).

For each texture of the owner: the input is what the source skin names,
else the original; the variant is the input joined with one model at one
size, `fast` for a texture without a colour plane (R-HD-122). A texture
that cannot have it keeps what the source names, with the reason.
"""

from __future__ import annotations

from collections.abc import Callable

from . import progress, variants
from .interfaces import Texture
from .results import Original


def plan(
    shows: dict[str, str],
    texture: Callable[[str], Texture],
    original: Callable[[Texture], Original],
    model: str,
    size: int,
) -> tuple[dict[str, str], dict[str, str]]:
    """The variants to name and request, and the textures kept with the reason.

    `shows`: asset -> what the source skin shows of it. `original`: what was
    read of a texture's original; one whose header cannot be read is kept.
    """
    named: dict[str, str] = {}
    kept: dict[str, str] = {}
    for asset, given in sorted(shows.items()):
        found = texture(asset)
        if found.role is None:
            kept[asset] = f"it cannot be upscaled: {found.reason}"
            continue
        chosen = model if progress.has_colour(found) else variants.DATA_MODEL
        variant = variants.join(given, chosen, size)
        recipe, _ = variants.split(variant)
        read = original(found)
        if read.unreadable:
            kept[asset] = read.unreadable
            continue
        most = read.longest
        if reason := progress.refusal(found, recipe, most) or variants.size_refusal(
            recipe, size, most
        ):
            kept[asset] = reason
            continue
        named[asset] = variant
    return named, kept
