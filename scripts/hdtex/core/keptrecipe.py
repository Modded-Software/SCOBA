"""What a request takes from a kept recipe, and what it adds to one.

A kept recipe is never made again (R-HD-158). A step before the last is
the input as it is kept (R-HD-159). The last step gets the size asked for
beside its others, with no job (R-HD-123, R-HD-6).
"""

from __future__ import annotations

import hashlib
import logging

from . import dds, encode, results, variants
from .interfaces import Texture
from .progress import RequestError
from .roles import ROLES  # loading it registers the roles
from .store import GameStore, RecipeKept, SizeKept

LOG = logging.getLogger(__name__)


def holds(kept: dict, size: int) -> bool:
    """Whether a kept recipe has the file of `size`."""
    return str(size) in kept["files"]


def _checked(game: GameStore, texture: Texture, recipe: str, kept: dict, size: int, use: str) -> bytes:
    """The kept file of `size`, when it is the file its entry names."""
    path = game.variant_file(texture.origin, recipe, size)
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != kept["files"][str(size)]["sha256"]:
        raise RequestError(f"{path} is not the file its entry names; {use}")
    return data


def planes(game: GameStore, texture: Texture, recipe: str, kept: dict, size: int) -> dict:
    """The planes a kept recipe gives the next step (R-HD-159).

    Its kept planes, at its own size. One kept without planes is read from
    its file of `size`, checked against the entry: it is whole as a
    variant, and is not made again for its planes.
    """
    if kept["planes"]:
        return {name: game.get_plane(key) for name, key in kept["planes"].items()}
    given = variants.variant_id(recipe, size)
    if not holds(kept, size):
        raise RequestError(f"{given} is not kept, and its recipe holds no planes")
    data = _checked(game, texture, recipe, kept, size, f"{given} cannot be an input")
    LOG.info("%s: kept without planes; its file of %d is the input", given, size)
    return ROLES.get(texture.role or "").split(encode.read_texture(data)[1])


def input_refusal(made: dict[str, results.Made], recipe: str) -> str:
    """Why a kept step before the last cannot be the input its id names (R-HD-159). Empty: it can, or it is not
    kept and is made first."""
    found = variants.parse_recipe(recipe)
    for step, prefix in zip(found[:-1], variants.prefixes(recipe)[:-1], strict=True):
        kept = made.get(prefix)
        if kept is None:
            continue
        given = variants.variant_id(prefix, step.size or 0)
        if kept.stale:
            how = (
                "transfer the edit again"
                if step.edit
                else f"ask for {given} alone first: that makes a new variant of it, and a request then names that one"
            )
            return f"its input {given} is stale: {kept.why_stale}; {how}"
        if not kept.entry["planes"] and not holds(kept.entry, step.size or 0):
            sizes = ", ".join(map(str, kept.sizes()))
            return f"its input {given} is not kept; its recipe is kept at {sizes} and holds no planes"
    return ""


def keep(game: GameStore, texture: Texture, recipe: str, sha256: str, entry: dict, files: dict[int, bytes]) -> dict:
    """Keep what a step made. Returns the kept entry.

    Another program may have kept the recipe while this one made it: the
    store refuses the second write (`RecipeKept`). When the kept one serves
    this request, it is the result, and nothing of it is touched.
    """
    try:
        return game.write_recipe(texture.origin, recipe, entry, files)
    except RecipeKept:
        kept = game.entry(texture.origin, recipe)
        if kept is None or kept["original"]["sha256"] != sha256 or results.edges_off(kept, texture.tiles):
            raise
        LOG.info("%s: another request kept it meanwhile; that one is the result", recipe)
        return kept


def size_refusal(kept: dict, size: int) -> str:
    """Why a kept recipe that serves a request cannot get `size`. Empty: it holds it, or it can.

    With planes the size is encoded from them, by the encoder that made
    its other files. Without, it is cut from a larger kept file.
    """
    if holds(kept, size):
        return ""
    held = ", ".join(sorted(kept["files"], key=int))
    if kept["planes"]:
        if kept["encoder"] != encode.ENCODER_VERSION:
            return (
                f"it is not kept; its recipe is kept at {held} by encoder {kept['encoder']}, and this is encoder "
                f"{encode.ENCODER_VERSION}: its file would not be of the same mip chain"
            )
        return ""
    if not any(int(one) > size for one in kept["files"]):
        return f"it is not kept; its recipe is kept at {held} and holds no planes, so no larger size can be made of it"
    return ""


def _cut(game: GameStore, texture: Texture, recipe: str, kept: dict, size: int) -> bytes:
    """The file of `size` of a recipe kept without planes: the mip chain of its next larger file, from that level down."""
    given = variants.variant_id(recipe, size)
    larger = min(int(one) for one in kept["files"] if int(one) > size)
    whole = dds.parse(_checked(game, texture, recipe, kept, larger, f"{given} cannot be cut from it"))
    for skip, level in enumerate(whole.levels):
        if max(level.width, level.height) == size:
            levels = [whole.level_bytes(index) for index in range(skip, len(whole.levels))]
            return dds.build(level.width, level.height, levels, whole.trailer, whole.format)
    raise RequestError(f"the kept file of {larger} has no level with a longest side of {size}; {given} cannot be cut from it")


def with_size(game: GameStore, texture: Texture, kept: dict, size: int, original: bytes, reference: dict | None) -> dict:
    """The kept recipe with the file of `size` beside its others. Returns its entry.

    A request keeps the size it asks for (R-HD-123). One asked for later
    costs no job (R-HD-6), and changes no kept file and no mark (R-HD-158).
    """
    if holds(kept, size):
        return kept
    recipe = kept["recipe"]
    given = variants.variant_id(recipe, size)
    if reason := size_refusal(kept, size):
        raise RequestError(f"{given}: {reason}")
    if kept["planes"]:
        role = ROLES.get(texture.role or "")
        upscaled = {name: game.get_plane(key) for name, key in kept["planes"].items()}
        data = encode.encode(original, role, upscaled, reference, tiles=texture.tiles).file(size)
    else:
        data = _cut(game, texture, recipe, kept, size)
    LOG.info("%s: its recipe is kept; this size is added to it", given)
    try:
        return game.add_size(texture.origin, recipe, size, data)
    except SizeKept:
        now = game.entry(texture.origin, recipe)
        if now is None:
            raise
        LOG.info("%s: another request added it meanwhile; that one is the result", given)
        return now
