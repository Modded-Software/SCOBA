"""Put baked texture files into a map folder, with what makes the game load them (SPEC-HD-TEXTURES 5.2).

What a model file shows, per texture, is decided by layer: the bake of the
unit, then of the actor, then of the model file, then the texture's own
bake, then the original. A texture baked on its own is named by a catalog
field (terrain): the field is set to the packaged file. A model file that
shows a packaged texture is copied, the copy names the packaged file, and
the `CModel` that shows it is pointed at the copy (`owned.py` for a unit
or an actor). All files of such a `CModel` are copied, because its
variations share one base path.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from ..core.interfaces import MODEL, OwnerBake, Packed
from . import m3tex, modelindex, owned, packaged, terrain
from .check import hd_references, mixed_terrain
from .owners import model_key
from .packaged import HD_MODEL_DIR
from .sources import (
    HD_DIR,
    HD_MARK,
    MODEL_MARK,
    SourceError,
    file_name,
    marked_name,
    stored_name,
    tagged_mark,
)
from .storage import Storage

TERRAIN = "terrain"
MODEL_KIND = "model"
MARKS = {TERRAIN: HD_MARK, MODEL_KIND: MODEL_MARK}

LOG = logging.getLogger(__name__)

Key = tuple[str, str]  # (asset, variant)


def map_file(map_dir: Path, map_path: str) -> Path:
    return map_dir.joinpath(*map_path.replace("/", "\\").split("\\"))


def packaged_paths(
    files: list[Packed], first: dict[str, str], spelled: dict[str, str]
) -> dict[Key, str]:
    """(asset, variant) -> the path its packaged file gets in the map. Two files must not get one path.

    `first`: asset -> the variant that keeps the plain marked name; another
    variant of that texture gets a tag of its id. `spelled`: asset -> its
    file name as a catalog spells it. Other build steps and data files name
    packaged files that way. A texture only model files name keeps the
    storage's spelling.
    """
    paths: dict[Key, str] = {}
    owners: dict[str, Key] = {}
    for item in sorted(
        files,
        key=lambda one: (
            one.texture.asset,
            one.variant != first.get(one.texture.asset),
            one.variant,
        ),
    ):
        asset = item.texture.asset
        if item.texture.kind not in MARKS:
            raise SourceError(
                f"{asset}: no rule packages a texture of kind {item.texture.kind}"
            )
        name = spelled.get(asset) or file_name(asset)
        mark = MARKS[item.texture.kind]
        if first.setdefault(asset, item.variant) != item.variant:
            mark = tagged_mark(item.variant)
        path = f"{HD_DIR}\\{marked_name(name, mark)}"
        if owners.setdefault(path.lower(), (asset, item.variant)) != (
            asset,
            item.variant,
        ):
            raise SourceError(
                f"{asset} and {owners[path.lower()][0]} share the file name {name}; one of them must keep its original"
            )
        paths[asset, item.variant] = path
    return paths


def _model_bakes(owners: list[OwnerBake]) -> dict[str, dict[str, str]]:
    """Model owner id -> asset -> variant, for the bakes of model files."""
    return {
        bake.owner.id: bake.textures for bake in owners if bake.owner.layer == MODEL
    }


def _copy(
    storage: Storage,
    origin: str,
    name: str,
    copy: Path,
    wanted: dict[str, str],
    layers: list[m3tex.Layer],
) -> None:
    """Write one model file copy that names `wanted` (asset -> packaged path), and read it back."""
    m3tex.rewrite(storage.file(origin), copy, wanted)
    # The copy is read again. It must name the new textures, and its layers must be the same otherwise.
    expected = [
        layer._replace(path=wanted.get(stored_name(layer.path), layer.path))
        for layer in layers
    ]
    if m3tex.layers(m3tex.load(copy)) != expected:
        copy.unlink()
        raise m3tex.ModelError(
            f"{name}: the written copy does not read back with the new texture paths"
        )


def _copy_models(
    storage: Storage,
    index: Path,
    paths: dict[Key, str],
    models: dict[str, dict[str, str]],
    alone: dict[str, str],
    target: Path,
    uses: dict[str, modelindex.Use],
) -> dict[tuple[str, str], str]:
    """Copy every model file of every `CModel` whose files show a packaged texture. Returns the Model value of each such entry.

    A file shows, per texture, its model file's bake, else the texture's own
    bake. A file that reads a texture with other flip book cells than its
    variant has keeps the original of it (R-HD-56).
    """
    # Only the models the map shows get a copy (R-HD-54).
    files = modelindex.model_files(storage, shown_only=True)
    layers = modelindex.layers(storage, files, index)
    apart = {(file.origin, asset) for asset, use in uses.items() for file in use.others}
    shows: dict[str, dict[str, str]] = {}
    for file in files:
        named = models.get(model_key(file.base), {})
        assets = {stored_name(layer.path) for layer in layers[file.origin]}
        wanted = {}
        for asset in sorted(assets):
            variant = named.get(asset) or alone.get(asset)
            if (
                variant
                and (asset, variant) in paths
                and (file.origin, asset) not in apart
            ):
                wanted[asset] = paths[asset, variant]
        shows[file.origin] = wanted
    if apart:
        LOG.info(
            "%s: %d model files keep the original of a packaged texture: they read it with other cells (first: %s reads %s)",
            storage.name, len({origin for origin, _asset in apart}), *min(apart),
        )  # fmt: skip
    touched = {file.entry for file in files if shows[file.origin]}
    owners: dict[str, str] = {}
    names: dict[str, str] = {}
    values: dict[tuple[str, str], str] = {}
    for file in files:
        if file.entry not in touched:
            continue
        # The copy keeps the file name as the catalog spells it: other build steps and data files name it so.
        name = names.setdefault(file.origin, file.name)
        if owners.setdefault(name.lower(), file.origin) != file.origin:
            raise SourceError(
                f"the model files {file.origin} and {owners[name.lower()]} share the name {name}; their textures cannot both be packaged"
            )
        copy = map_file(target, f"{HD_MODEL_DIR}\\{name}")
        if not copy.is_file():  # several entries may show one file
            _copy(
                storage,
                file.origin,
                name,
                copy,
                shows[file.origin],
                layers[file.origin],
            )
        values[file.entry, "Model"] = f"{HD_MODEL_DIR}\\{file_name(file.base)}"
    return values


def package(
    storage: Storage,
    index: Path,
    files: list[Packed],
    owners: list[OwnerBake],
    alone: dict[str, str],
    target: Path,
    uses: dict[str, modelindex.Use],
) -> dict[Key, str]:
    """Copy the baked files into the map folder `target` and name them there. Returns (asset, variant) -> path in the map.

    `alone`: asset -> variant of each texture baked on its own (terrain).
    `uses`: the dataset's model textures by asset, with the files that read each.
    A folder is packaged once (packaged.require_unpackaged).
    """
    packaged.require_unpackaged(target)
    in_terrain = {
        asset
        for asset in alone
        if any(
            item.texture.asset == asset and item.texture.kind == TERRAIN
            for item in files
        )
    }
    ground = {use.asset: use for use in terrain.uses(storage)} if in_terrain else {}
    paths = packaged_paths(
        files, dict(alone), {asset: ground[asset].name for asset in in_terrain}
    )
    if not paths:
        LOG.info(
            "%s: no bake names a variant; nothing is copied into %s",
            storage.name,
            target,
        )
        return {}
    # Found here before a file is written; `check` finds the same in a built map.
    upscaled = {place for asset in in_terrain for place in ground[asset].fields}
    if (
        mixed := mixed_terrain(storage.layer, upscaled)
        if storage.layer is not None
        else []
    ):
        raise SourceError(
            f"the bakes of {storage.name} upscale some terrain textures the map paints with, but not {', '.join(f'{entry}.{field}' for entry, field in mixed)}: "
            "sharp and soft ground would lie side by side. Bake a variant of each, or unbake all of them"
        )
    lines: packaged.Lines = {}
    for asset in sorted(in_terrain):
        for entry, field in ground[asset].fields:
            lines.setdefault((terrain.TEXTURES, terrain.ELEMENT), {})[entry, field] = (
                paths[asset, alone[asset]]
            )
    models = _model_bakes(owners)
    # A model file may name a terrain texture too (zerus_4 on ZerusWaterfall): its copy names the same packaged file.
    values = _copy_models(storage, index, paths, models, alone, target, uses)
    made = owned.package(
        storage,
        index,
        [bake for bake in owners if bake.owner.layer != MODEL],
        paths,
        models,
        alone,
        target,
        uses,
    )
    values.update(made.values)
    if values:
        lines[modelindex.CATALOG, "CModel"] = values
    for key, found in made.lines.items():
        lines.setdefault(key, {}).update(found)
    packaged.name_files(target, lines, made.entries)
    # A variant goes in when a catalog line or a model copy names it. One that
    # only a hidden layer names (an actor's bake under its unit's original) stays out.
    named = hd_references(target)
    shown = {
        key: path
        for key, path in paths.items()
        if path.rsplit("\\", 1)[-1].lower() in named
    }
    for item in files:
        key = (item.texture.asset, item.variant)
        if key not in shown:
            LOG.info(
                "%s: %s %s is baked and nothing shows it; it is not packaged",
                storage.name,
                *key,
            )
            continue
        copy = map_file(target, shown[key])
        copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(item.file, copy)
    LOG.info(
        "%s: %d files and %d model entries packaged into %s",
        storage.name,
        len(shown),
        len(values),
        target,
    )
    return shown
