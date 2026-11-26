"""The textures the model files of a dataset name (R-HD-3).

The files are those of the `CModel` entries the dataset shows, with
variations: every entry of the game's catalogs, or with a map folder as
layer those the map shows (`shown.py`). No list of units or models is typed
in.

Reading a model file takes time, so what each file names is kept in one
index file. A file of the game's storage is kept by its path there: it does
not change. A file of a dataset's own layer is kept by its hash.
"""

from __future__ import annotations

import logging
import os
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import NamedTuple

from ..core.store import file_sha256, read_json, write_json
from . import m3tex, shown
from .catalog import CatalogError
from .sources import SourceError, file_name, stored_name
from .storage import GAP_FILES, GAP_MODELS, OWN, Storage

FORMAT = 3  # 3: each layer's `moves`, `spans` and `triangles` (m3tex.layers)
FILE = "model-layers.json"
CATALOG = shown.MODELS
PARALLEL_FROM = (
    64  # fewer files than this are read in this process: starting others takes longer
)
PROGRESS = 500  # files between two lines of the log
SINGLE = (1, 1)

LOG = logging.getLogger(__name__)


class ModelFile(NamedTuple):
    entry: str  # CModel id
    asset: str  # game path of this file, as the storage spells it
    origin: str
    base: str  # the entry's Model value; variations share it
    name: str  # the file name as the catalog spells it


class Use(NamedTuple):
    """One texture and the model files that read it with the same cells.

    Model files may read one texture with different flip book cells. A
    result has one set of cells. So the cells most files use hold, and a
    file that reads the texture another way keeps the original (R-HD-56).
    """

    asset: str  # as the storage spells it
    origin: str | None  # None: the dataset cannot show the file
    slots: tuple[str, ...]  # of `files`
    materials: tuple[str, ...]  # material lists of `files`, such as standardMaterials
    files: tuple[
        ModelFile, ...
    ]  # the files that read it with `grid`; all of them when `grid` is None
    video: bool
    flipbook: bool
    # (columns, rows) most files read it with; a layer without a flip book counts as (1, 1).
    # None: no file reads it with known cells, or as many files read it one way as another.
    grid: tuple[int, int] | None
    others: tuple[ModelFile, ...] = ()  # the files that read it with other cells
    repeats: bool = False  # it tiles: `repeating` of the layers of `files`


def variation_assets(base: str, count: int) -> list[str]:
    """`Dir\\Name.m3` with N variations is `Dir\\Name_00.m3` to `Dir\\Name_<N-1>.m3`."""
    stem, dot, extension = base.rpartition(".")
    if not dot:
        raise SourceError(f"model path without an extension: {base}")
    return [f"{stem}_{index:02d}.{extension}" for index in range(count)]


def model_files(storage: Storage, shown_only: bool = False) -> list[ModelFile]:
    """Every model file of the dataset's `CModel` entries, as far as the dataset holds the file.

    Every entry has owners and textures, placed or not (operator
    2026-11-25). `shown_only`: only the entries the map shows, for what a
    bake must cover in the map (R-HD-54, the package).
    """
    catalog = storage.catalog(CATALOG)
    wanted = shown.entries(storage) if shown_only else None
    every = catalog.ids("CModel")
    files: list[ModelFile] = []
    unnamed: list[str] = []
    absent: list[str] = []
    for entry in (
        every if wanted is None else [entry for entry in every if entry in wanted]
    ):
        try:
            base = catalog.field(entry, "Model") or ""
            count = int(catalog.field(entry, "VariationCount") or 0)
            assets = variation_assets(base, count) if count else [base]
        except (CatalogError, SourceError, ValueError) as error:
            unnamed.append(f"{entry}: {error}")
            continue
        if not base:
            unnamed.append(f"{entry}: no Model")
            continue
        for asset in assets:
            origin = storage.origin(asset)
            if origin is None:
                absent.append(asset)
            else:
                files.append(
                    ModelFile(entry, stored_name(asset), origin, base, file_name(asset))
                )
    if wanted is None:  # the gaps of every entry; the shown subset is a part of them
        storage.gaps[GAP_MODELS] = tuple(unnamed)
        storage.gaps[GAP_FILES] = tuple(absent)
    LOG.info(
        "%s: %d model files of %d CModel entries, of %d in the game; %d entries name no file (first: %s); %d named files are not there (first: %s)",
        storage.name, len(files), len(every) if wanted is None else len(wanted.intersection(every)), len(every), len(unnamed), unnamed[:1], len(absent), absent[:1],
    )  # fmt: skip
    return files


def read_layers(path: str) -> dict:
    """What one model file names, as plain values. A file that cannot be read gives its error."""
    try:
        found = m3tex.layers(m3tex.load(Path(path)))
    except m3tex.ModelError as error:
        return {"error": str(error)}
    return {"layers": [layer._asdict() for layer in found]}


def _layer(item: dict) -> m3tex.Layer:
    return m3tex.Layer(
        **{**item, "grid": tuple(item["grid"]) if item.get("grid") else None}
    )


def layers(
    storage: Storage, files: list[ModelFile], index: Path
) -> dict[str, list[m3tex.Layer]]:
    """Origin -> the layers of that model file. A file that cannot be read has none, and the log names it."""
    path = index / FILE
    kept = read_json(path) if path.is_file() else {}
    known: dict[str, dict] = (
        kept.get("files", {})
        if isinstance(kept, dict) and kept.get("format") == FORMAT
        else {}
    )
    storage.fetch(file.origin for file in files)
    paths = {file.origin: storage.file(file.origin) for file in files}
    keys = {
        origin: f"sha256:{file_sha256(found)}" if origin.startswith(OWN) else origin
        for origin, found in paths.items()
    }
    unread = sorted(origin for origin, key in keys.items() if key not in known)
    if unread:
        start = time.monotonic()
        wanted = [str(paths[origin]) for origin in unread]
        if len(unread) < PARALLEL_FROM:
            read = [read_layers(found) for found in wanted]
        else:
            read = []
            with ProcessPoolExecutor(max_workers=os.cpu_count() or 1) as pool:
                for found in pool.map(read_layers, wanted, chunksize=16):
                    read.append(found)
                    if len(read) % PROGRESS == 0:
                        LOG.info(
                            "%s: read %d of %d model files in %.0f s",
                            storage.name,
                            len(read),
                            len(unread),
                            time.monotonic() - start,
                        )
        known.update({keys[origin]: found for origin, found in zip(unread, read)})
        write_json(path, {"format": FORMAT, "files": known})
        LOG.info(
            "%s: read %d model files in %.1f s; %s now holds %d",
            storage.name,
            len(unread),
            time.monotonic() - start,
            path,
            len(known),
        )
    broken = sorted(origin for origin, key in keys.items() if "error" in known[key])
    if broken:
        LOG.info(
            "%s: %d model files cannot be read (first: %s: %s)",
            storage.name,
            len(broken),
            broken[0],
            known[keys[broken[0]]]["error"],
        )
    return {
        origin: [_layer(item) for item in known[key].get("layers", [])]
        for origin, key in keys.items()
    }


def cells(
    items: list[tuple[ModelFile, m3tex.Layer]],
) -> tuple[tuple[int, int] | None, set[ModelFile]]:
    """The cells most model files read a texture with, and those files. None and every file: no such cells.

    A file whose layers read it with different cells, or with a flip book of
    unknown cells, agrees with nobody and counts for nothing.
    """
    read: dict[ModelFile, set[tuple[int, int] | None]] = {}
    for file, layer in items:
        read.setdefault(file, set()).add(layer.grid if layer.flipbook else SINGLE)
    votes = Counter(
        next(iter(grids))
        for grids in read.values()
        if len(grids) == 1 and None not in grids
    )
    ranked = votes.most_common(2)
    if not ranked or (len(ranked) == 2 and ranked[0][1] == ranked[1][1]):
        return None, set(read)
    return ranked[0][0], {
        file for file, grids in read.items() if grids == {ranked[0][0]}
    }


def repeating(layers: list[m3tex.Layer]) -> bool:
    """Whether a texture tiles: a layer that names it tiles or scrolls (m3tex.moves), or at least
    m3tex.TILE_SHARE of the triangles drawn with it span a whole-number line of their coordinates."""
    triangles = sum(layer.triangles for layer in layers)
    spans = sum(layer.spans for layer in layers)
    return any(layer.moves for layer in layers) or (triangles > 0 and spans >= m3tex.TILE_SHARE * triangles)


class Models(NamedTuple):
    """The model files of a dataset and what each names: read once, for its textures and its owners."""

    files: list[ModelFile]
    layers: dict[str, list[m3tex.Layer]]


def models(storage: Storage, index: Path) -> Models:
    files = model_files(storage)
    return Models(files, layers(storage, files, index))


def uses(storage: Storage, read: Models) -> list[Use]:
    """Every texture a model file of the dataset names, in asset order."""
    found = read.layers
    grouped: dict[str, list[tuple[ModelFile, m3tex.Layer]]] = {}
    for file in read.files:
        for layer in found[file.origin]:
            grouped.setdefault(stored_name(layer.path), []).append((file, layer))
    listed = []
    apart = 0
    for asset, items in sorted(grouped.items()):
        grid, agreed = cells(items)
        mine = [layer for file, layer in items if file in agreed]
        others = {file for file, _layer in items} - agreed
        apart += bool(others)
        listed.append(
            Use(
                asset,
                storage.origin(asset),
                tuple(sorted({layer.slot for layer in mine})),
                tuple(sorted({layer.material for layer in mine})),
                tuple(sorted(agreed)),
                any(layer.video for layer in mine),
                any(layer.flipbook for layer in mine),
                grid,
                tuple(sorted(others)),
                repeating(mine),
            )
        )
    LOG.info(
        "%s: %d textures named by model files; %d of them are read with other cells by some files, which keep the original",
        storage.name,
        len(listed),
        apart,
    )
    return listed
