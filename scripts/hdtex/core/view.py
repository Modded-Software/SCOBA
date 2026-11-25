"""The state of a texture and of an owner as a reader shows them (SPEC-HD-TEXTURES 4.9), in the shapes of webviewer/src/shared/textures.ts.

The pipeline's rules decide every field here: which models and sizes may
be asked for, what a skin shows, whether the package holds a bake. A
reader only shows them. The state index keeps what this module works out.

Nothing here reads a dataset's files: a state comes from the texture's
description, what is known of its original, and the files of the store.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypedDict

from . import limits, progress, results, skins, variants
from .bakes import Bakes
from .interfaces import FAILED, Owner, Runner, Texture
from .results import Made, Original
from .store import GameStore

# What a state says of an open request. `pid` and `started` name its program, while it has not failed.
REQUEST_KEYS = ("state", "reason", "step", "steps", "planes", "pid", "started")


class VariantState(TypedDict):
    """One variant in a texture's state (TextureVariant in shared/textures.ts)."""

    id: str
    input: str
    title: str
    recipe: str
    models: list[str]
    size: int
    own: bool
    stale: bool
    numbers: list[limits.Band]
    problems: list[limits.Missed]
    accepted: bool
    path: str
    sha256: str


class ModelAsk(TypedDict):
    reason: str
    sizes: dict[str, str]  # size -> why it is refused; "" when it may be asked for


class InputAsk(TypedDict):
    """What a request on one input may ask for (TextureAsk in shared/textures.ts)."""

    input: str
    models: dict[str, ModelAsk]


def _variants(game: GameStore, texture: Texture, made: dict[str, Made]) -> list[VariantState]:
    found: list[VariantState] = []
    for recipe, one in sorted(made.items()):
        entry = one.entry
        numbers = limits.bands(entry["numbers"], texture.tiles)
        for size in sorted(one.sizes(), reverse=True):
            variant = variants.variant_id(recipe, size)
            found.append({
                "id": variant,
                "input": variants.input_of(variant),
                "title": variants.title(variant),
                "recipe": recipe,
                "models": entry["models"],
                "size": size,
                "own": one.own,
                "stale": one.stale,
                "numbers": numbers,
                "problems": list(one.missed),
                "accepted": one.accepted,
                "path": str(game.variant_file(texture.origin, recipe, size)),
                "sha256": entry["files"][str(size)]["sha256"],
            })  # fmt: skip
    return found


def _asks(
    texture: Texture, original: Original | None, made: dict[str, Made]
) -> list[InputAsk]:
    """For each input a request may take, each model with why it is refused, and the sizes it reaches (R-VIEW-116)."""
    if texture.role is None or original is None or original.unreadable:
        return []  # a request is refused with the reason (`reason`), or the texture was never asked for
    inputs = [variants.ORIGINAL] + [
        variants.variant_id(recipe, size)
        for recipe, one in sorted(made.items())
        if not one.stale
        for size in sorted(one.sizes(), reverse=True)
    ]
    found: list[InputAsk] = []
    for given in inputs:
        models: dict[str, ModelAsk] = {}
        for model in variants.MODELS:
            recipe = (
                model
                if given == variants.ORIGINAL
                else f"{given}{variants.JOIN}{model}"
            )
            reason = progress.refusal(texture, recipe, original.longest)
            sizes: dict[str, str] = {}
            if not reason:
                for size in variants.SIZES:
                    sizes[str(size)] = variants.size_refusal(
                        recipe, size, original.longest
                    )
                own = variants.own_size(variants.parse_recipe(recipe), original.longest)
                if own < variants.SIZES[0]:
                    sizes[str(own)] = ""
            models[model] = {"reason": reason, "sizes": sizes}
        found.append({"input": given, "models": models})
    return found


def texture_state(
    game: GameStore,
    texture: Texture,
    original: Original | None,
    baked: Bakes,
    record: dict | None,
    runner: Callable[[], Runner],
) -> dict:
    """The state of one texture of one dataset.

    `original`: None when nobody read it yet. Then the texture must have no
    variant: whether a variant is stale is a fact of the original.
    `baked` and `record`: the dataset's bakes and its package record.
    """
    if original is None and game.recipes(texture.origin):
        raise ValueError(
            f"{texture.asset} has variants and its original at {texture.origin} was not read"
        )
    made = {} if original is None else results.of(game, texture, original.sha256)
    open_requests = {}
    for recipe in progress.asked(game, texture.origin):
        # A request that is done leaves no state: None.
        state = progress.read(game, runner, texture.origin, recipe)
        if state is not None:
            open_requests[recipe] = {
                key: state[key] for key in REQUEST_KEYS if key in state
            }
    found = _variants(game, texture, made)
    bake = baked.textures.get(texture.asset)
    held = None if record is None else record["textures"].get(texture.asset)
    return {
        "asset": texture.asset,
        "kind": texture.kind,
        "users": list(texture.users),
        "tiles": texture.tiles,
        # False: its role or its size is not read yet, so `reason` and `asks` are empty. Asking for it by name reads them.
        "judged": texture.judged and (original is not None or texture.role is None),
        # Why it cannot be upscaled: its role was not found, or its original's header cannot be read.
        "reason": texture.reason if texture.role is None or original is None else original.unreadable,
        "colour": progress.has_colour(texture),
        "variants": found,
        "asks": _asks(texture, original, made) if texture.judged else [],
        "requests": open_requests,
        "bake": bake,
        "bakeProblem": results.refusal(made, bake) if bake else "",
        "packaged": _held(held, bake, found),
    }


def _held(held: dict | None, bake: str | None, found: list[VariantState]) -> dict | None:
    """What the package holds of a terrain texture, and whether it is the file the bake names."""
    if held is None:
        return None
    want = next((item["sha256"] for item in found if item["id"] == bake), None)
    return {
        "variant": held.get("variant"),
        "held": want is not None
        and held.get("sha256") == want
        and held.get("variant") == bake,
    }


def shown_now(owner: Owner, asset: str, baked: Bakes) -> str:
    """What an owner shows of one texture in the game now: its own bake, then the nearest bake below that names it, then the texture's own bake, then the original."""
    for name in (owner.id, *owner.below):
        bake = baked.owners.get(name)
        if bake is not None and asset in bake.textures:
            return bake.textures[asset]
    return baked.textures.get(asset, variants.ORIGINAL)


def owner_state(
    owner: Owner, found: dict[str, skins.Skin], baked: Bakes, record: dict | None
) -> dict:
    """The state of one owner: its skins with the offered New Skin, what it shows now, its bake (SPEC-VIEWER 17.2)."""
    below = {name: baked.owners.get(name) for name in owner.below}
    shows = {asset: shown_now(owner, asset, baked) for asset in owner.textures}
    listed = [
        {"name": skin.name, "textures": skin.textures, "stored": True}
        for skin in sorted(found.values())
    ]
    if (offer := skins.offered(found, shows)) is not None:
        listed.append({"name": skins.NEW, "textures": offer, "stored": False})
    bake = baked.owners.get(owner.id)
    held = None if record is None else record.get("owners", {}).get(owner.id)
    return {
        "owner": owner.id,
        "title": owner.title,
        "layer": owner.layer,
        "textures": list(owner.textures),
        "below": [
            {"owner": name, "bake": None if bake is None else bake.skin}
            for name, bake in below.items()
        ],
        "skins": listed,
        "shows": shows,
        "bake": None
        if bake is None
        else {"skin": bake.skin, "textures": bake.textures},
        "held": held is not None
        and bake is not None
        and held.get("textures") == bake.textures,
    }


def head() -> dict:
    """What holds for every texture of a dataset: the words a reader offers."""
    return {
        "sizes": list(variants.SIZES),
        "models": [
            {"id": model.id, "title": model.title, "note": model.note}
            for model in variants.MODELS.values()
        ],
        "limits": [
            {"limit": limit, "info": info} for limit, info in limits.INFO.items()
        ],
        "failed": FAILED,
    }
