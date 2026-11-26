"""The removal of one variant of a texture (R-HD-146, SPEC-HD-TEXTURES 4.8).

A variant is one size of a recipe. Its file goes, and its size leaves the
recipe's entry; the last size takes the recipe's folder with it. What still
needs the variant refuses its removal: a bake of any dataset of the game,
a skin of another dataset, a recipe made from it, an open request of its
recipe, an edit session on it. Variants live by origin, so every dataset
that shares the origin loses it; their skins and bakes are read too.

A skin of this dataset does not refuse it (operator 2026-11-26: only the
variant picked now is kept, and the page refuses that one). Each skin of
this dataset that names it names the original for that texture after.
"""

from __future__ import annotations

import shutil

from . import bakes, edits, progress, skins, variants
from .dataset import Dataset
from .interfaces import FAILED, Texture
from .store import ENTRY, write_json


class RemovalError(ValueError):
    """Why a variant cannot be removed."""


def _named_in(dataset: Dataset, asset: str, variant: str) -> list[str]:
    """Each bake, in any dataset of the game, and each skin of another dataset, that names `variant` for `asset`."""
    found = []
    root = dataset.game.root / "datasets"
    for folder in sorted(root.iterdir()) if root.is_dir() else []:
        if not folder.is_dir():
            continue
        baked = bakes.load(folder)
        if baked.textures.get(asset) == variant:
            found.append(f"the bake of {asset} in {folder.name}")
        for owner, bake in sorted(baked.owners.items()):
            if bake.textures.get(asset) == variant:
                found.append(f"the bake of {owner} (skin {bake.skin}) in {folder.name}")
        if folder.name == dataset.name:
            continue  # this dataset's skins let it go (_release)
        for owner in skins.owners(folder):
            for name, skin in sorted(skins.load(folder, owner).items()):
                if skin.textures.get(asset) == variant:
                    found.append(f"skin {name} of {owner} in {folder.name}")
    return found


def _release(dataset: Dataset, asset: str, variant: str) -> None:
    """Each skin of this dataset that names `variant` for `asset` names the original for it from now on."""
    for owner in skins.owners(dataset.folder):
        held = skins.load(dataset.folder, owner)
        if not any(skin.textures.get(asset) == variant for skin in held.values()):
            continue
        dataset.change_skin(owner, lambda found: {
            name: skin._replace(textures={key: one for key, one in skin.textures.items() if not (key == asset and one == variant)})
            for name, skin in found.items()
        })  # fmt: skip


def refusal(dataset: Dataset, texture: Texture, variant: str) -> str:
    """Why `variant` of this texture cannot be removed. Empty: it can."""
    if variant == variants.ORIGINAL:
        return "the original is the game's file; it is not removed"
    recipe, size = variants.split(variant)
    made = dataset.made(texture)
    if recipe not in made or str(size) not in made[recipe].entry["files"]:
        return f"{texture.asset} has no variant {variant}"
    game = dataset.game
    state = progress.read(game, dataset.runner, texture.origin, recipe)
    if state is not None and state["state"] != FAILED:
        return f"a request of {recipe} is {state['state']}; wait until it is done"
    built = [
        one
        for one in sorted(set(game.recipes(texture.origin)) | set(progress.asked(game, texture.origin)))
        if one.startswith(variant + variants.JOIN)
    ]
    if built:
        return f"{', '.join(built)} {'is' if len(built) == 1 else 'are'} made from it; remove {'that' if len(built) == 1 else 'those'} first"
    if (edits.session_dir(game, edits.session_id(texture.origin, variant)) / edits.SESSION).is_file():
        return "an edit session is open on it; discard it first"
    if named := _named_in(dataset, texture.asset, variant):
        return "it is named by " + "; ".join(named)
    return ""


def remove(dataset: Dataset, texture: Texture, variant: str) -> None:
    """Remove one variant of a texture, or refuse with the reason. Every dataset with its origin sees it gone."""
    if reason := refusal(dataset, texture, variant):
        raise RemovalError(f"{texture.asset}, {variant}: {reason}")
    # The skins first: no skin names a variant that is gone.
    _release(dataset, texture.asset, variant)
    recipe, size = variants.split(variant)
    game = dataset.game
    folder = game.recipe_dir(texture.origin, recipe)
    entry = game.entry(texture.origin, recipe)
    if entry is None:
        raise RemovalError(f"{texture.asset}, {variant}: its entry went while it was removed")
    files = {key: value for key, value in entry["files"].items() if key != str(size)}
    if files:
        # The entry first: a reader never sees a size whose file is gone.
        write_json(folder / ENTRY, {**entry, "files": files})
        game.variant_file(texture.origin, recipe, size).unlink()
    else:
        game.drop_recipe(texture.origin, recipe)
        # A failed request keeps its note and its log; else the folder goes.
        if not (folder / progress.FILE).is_file():
            shutil.rmtree(folder)
    dataset.changed(texture)
