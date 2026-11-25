"""Bakes on a unit or an actor: copies that change that owner only (SPEC-HD-TEXTURES 5.2, R-HD-141, R-HD-142).

An actor shows its model by its `Model` field, a `CModel` id. For an actor
whose bake makes that model show other textures than the model layer:

- each file of the `CModel` is copied to `Assets\\Models\\scoba_hd\\<actor>\\`,
  naming what the actor shows;
- a new `CModel` `<entry>_hd_<actor>` is made, with the old entry as its
  parent, and its `Model` naming the copy;
- the actor's `Model` names the new entry.

A unit's actor is the actor of the unit's id (`owners.py`). So a unit's
bake is a bake of that actor, over the actor's own bake.

Not covered: models the actor names in its event lines (death, portrait).
They keep the model layer. Not known in the game: E-1 and E-2 of the
specification.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import NamedTuple

from ..core.interfaces import ACTOR, UNIT, OwnerBake
from . import m3tex, modelindex, packaged, shown
from .catalog import CatalogError
from .owners import model_key
from .packaged import HD_MODEL_DIR
from .sources import SourceError, file_name, stored_name
from .storage import Storage

LOG = logging.getLogger(__name__)
SUFFIX = "_hd_"


class Made(NamedTuple):
    values: dict[tuple[str, str], str]  # (new CModel id, "Model") -> the copy
    lines: packaged.Lines  # the actors' Model lines
    entries: packaged.Made  # the entries made, each with its parent


def _wanted(owners: list[OwnerBake]) -> dict[str, dict[str, str]]:
    """Actor id -> asset -> variant: the actor's bake, then its unit's over it."""
    found: dict[str, dict[str, str]] = {}
    for layer in (ACTOR, UNIT):
        for bake in owners:
            if bake.owner.layer == layer:
                found.setdefault(bake.owner.id.split(":", 1)[1], {}).update(
                    bake.textures
                )
    return found


def _shows(
    origin: str,
    assets: list[str],
    layers: list[dict[str, str]],
    paths: dict[tuple[str, str], str],
    apart: set[tuple[str, str]],
) -> dict[str, str]:
    """Asset -> packaged path, for each texture of a file whose nearest layer names a packaged variant.

    `layers`: asset -> variant, nearest first. A layer that names a texture
    decides it, `original` too. A file that reads a texture with other cells
    keeps its original (R-HD-56).
    """
    found = {}
    for asset in assets:
        variant = next((layer[asset] for layer in layers if layer.get(asset)), None)
        if variant and (asset, variant) in paths and (origin, asset) not in apart:
            found[asset] = paths[asset, variant]
    return found


def package(
    storage: Storage,
    index: Path,
    owners: list[OwnerBake],
    paths: dict[tuple[str, str], str],
    models: dict[str, dict[str, str]],
    alone: dict[str, str],
    target: Path,
    uses: dict[str, modelindex.Use],
) -> Made:
    """Copies and entries for every unit and actor bake. Nothing is made for an actor whose bake changes nothing."""
    made = Made({}, {}, {})
    wanted = _wanted(owners)
    if not wanted:
        return made
    actors = storage.catalog(shown.ACTORS)
    files = modelindex.model_files(storage)
    layers = modelindex.layers(storage, files, index)
    by_entry: dict[str, list[modelindex.ModelFile]] = {}
    for file in files:
        by_entry.setdefault(file.entry, []).append(file)
    apart = {(file.origin, asset) for asset, use in uses.items() for file in use.others}
    for actor, textures in sorted(wanted.items()):
        try:
            entry = actors.field(actor, "Model")
            cls = actors.entries[actor].cls
        except (CatalogError, KeyError) as error:
            raise SourceError(
                f"actor {actor} has no model entry to copy: {error}"
            ) from error
        if not entry or entry not in by_entry:
            raise SourceError(
                f"actor {actor} shows {entry!r}, which names no model file of the dataset"
            )
        below = models.get(model_key(by_entry[entry][0].base), {})
        changed = False
        for file in by_entry[entry]:
            assets = sorted({stored_name(layer.path) for layer in layers[file.origin]})
            shows = _shows(file.origin, assets, [textures, below, alone], paths, apart)
            # What the model layer shows, over every texture of the file: a
            # bake that names `original` where the model shows a variant
            # changes the file too.
            plain = _shows(file.origin, assets, [below, alone], paths, apart)
            changed = changed or shows != plain
            copy = target.joinpath(*f"{HD_MODEL_DIR}\\{actor}\\{file.name}".split("\\"))
            copy.parent.mkdir(parents=True, exist_ok=True)
            m3tex.rewrite(storage.file(file.origin), copy, shows)
            expected = [
                layer._replace(path=shows.get(stored_name(layer.path), layer.path))
                for layer in layers[file.origin]
            ]
            if m3tex.layers(m3tex.load(copy)) != expected:
                copy.unlink()
                raise m3tex.ModelError(
                    f"{actor}: the copy of {file.name} does not read back with the new texture paths"
                )
        if not changed:
            for file in by_entry[entry]:
                target.joinpath(
                    *f"{HD_MODEL_DIR}\\{actor}\\{file.name}".split("\\")
                ).unlink()
            LOG.info(
                "%s: the bake of %s shows what its model shows; nothing is copied for it",
                storage.name,
                actor,
            )
            continue
        new = f"{entry}{SUFFIX}{actor}"
        made.entries.setdefault((modelindex.CATALOG, "CModel"), {})[new] = entry
        made.values[new, "Model"] = (
            f"{HD_MODEL_DIR}\\{actor}\\{file_name(by_entry[entry][0].base)}"
        )
        made.lines.setdefault((shown.ACTORS, cls), {})[actor, "Model"] = new
        LOG.info("%s: actor %s shows the new model entry %s", storage.name, actor, new)
    return made
