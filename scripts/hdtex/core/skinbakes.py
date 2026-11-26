"""Skin changes that touch a bake (SPEC-HD-TEXTURES 4.6, R-HD-136, R-HD-138).

A bake names the skin it was made from. So a rename of a baked skin
renames it in the bake too, and a baked skin cannot be deleted. The
bake's textures never change here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from . import bakes, skins

if TYPE_CHECKING:
    from .dataset import Dataset


def _baked_as(dataset: Dataset, owner: str, name: str) -> bakes.Bake | None:
    """The owner's bake when it names skin `name`; else None."""
    bake = dataset.baked.owners.get(owner)
    return bake if bake is not None and bake.skin == name else None


def rename(dataset: Dataset, owner: str, name: str, new: str) -> dict[str, skins.Skin]:
    """Rename a skin. A bake of it then names `new`.

    The rename is checked first, then the bake is written, then the skins: the owner's state, which the
    viewer may read meanwhile, holds the new name in its skins and its bake at once.
    """
    bake = _baked_as(dataset, owner, name)
    skins.renamed(dataset.skins_of(owner), name, new)  # a refusal writes nothing
    if bake is not None:
        bakes.save(
            dataset.folder,
            bakes.with_owner(dataset.baked, owner, bake._replace(skin=new)),
        )
    found = dataset.change_skin(owner, lambda now: skins.renamed(now, name, new))
    if bake is not None:
        dataset.owner_changed(owner, below=True)
        # The bake's line in each texture's `namedBy` holds the skin's name (R-HD-156).
        dataset.names_changed(bake.textures)
    return found


def delete(dataset: Dataset, owner: str, name: str) -> dict[str, skins.Skin]:
    """Delete a skin. A baked skin is refused, and nothing changes."""
    if _baked_as(dataset, owner, name) is not None:
        raise skins.SkinError(
            f"skin {name!r} is baked; unbake it or bake another skin first"
        )
    return dataset.change_skin(owner, lambda now: skins.deleted(now, name))
