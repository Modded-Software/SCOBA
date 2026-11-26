"""What a skin upscale asks for (SPEC-HD-TEXTURES 4.6, R-HD-134).

For each texture of the owner: the input is what the source skin names,
else the original; the variant is the input joined with one model at one
factor of its input's side, `fast` for a texture without a colour plane
(R-HD-122). A texture
that cannot have it keeps what the source names, with the reason.
"""

from __future__ import annotations

from collections.abc import Callable

from . import progress, skins, variants
from .interfaces import Texture
from .results import Original


def plan(
    shows: dict[str, str],
    texture: Callable[[str], Texture],
    original: Callable[[Texture], Original],
    model: str,
    factor: int,
    cap: int,
) -> tuple[dict[str, str], dict[str, str]]:
    """The variants to name and request, and the textures kept with the reason.

    `shows`: asset -> what the source skin shows of it. `original`: what was
    read of a texture's original; one whose header cannot be read is kept.
    Each variant is `factor` times its input's side, at most `cap`.
    """
    named: dict[str, str] = {}
    kept: dict[str, str] = {}
    for asset, given in sorted(shows.items()):
        found = texture(asset)
        if found.role is None:
            kept[asset] = f"it cannot be upscaled: {found.reason}"
            continue
        chosen = model if progress.has_colour(found) else variants.DATA_MODEL
        recipe = variants.extended(given, chosen)
        read = original(found)
        if read.unreadable:
            kept[asset] = read.unreadable
            continue
        most = read.longest
        if reason := progress.refusal(found, recipe, most):
            kept[asset] = reason
            continue
        side, reason = variants.factor_side(recipe, factor, most, cap)
        if reason:
            kept[asset] = reason
            continue
        named[asset] = variants.variant_id(recipe, side)
    return named, kept


def refuse_empty(owner: str, factor: int, named: dict[str, str], kept: dict[str, str]) -> None:
    """An upscale that names no variant makes no skin: it is refused with each texture's reason (no empty New Skin)."""
    if named:
        return
    why = "; ".join(f"{asset}: {reason}" for asset, reason in sorted(kept.items()))
    raise skins.SkinError(
        f"{owner}: {factor}x asks for no texture, so no skin is made ({why or 'it has no texture'})"
    )
