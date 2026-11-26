"""Package the bakes of a dataset: the baked files, through the game's adapter, and a record of them (R-HD-101 to 106).

The core decides what is packaged. The game decides where a file goes,
which entries it copies for an owner, and what makes the game load it.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import NamedTuple

from . import bakes, results, variants
from .dataset import Dataset
from .interfaces import OwnerBake, Packed
from .store import PACKAGE_RECORD as FILE
from .store import file_sha256, write_json

FORMAT = 2
FOLDER = "package"  # in a dataset's folder of the store: the package of a dataset no build packages
COMMAND = "scripts/hd_textures.py"

LOG = logging.getLogger(__name__)


class PackageError(RuntimeError):
    """Why the bakes cannot be packaged."""


class Plan(NamedTuple):
    files: list[Packed]  # every (asset, variant) a bake names, once
    owners: list[OwnerBake]
    textures: dict[str, str]  # asset -> variant of a texture baked on its own
    problems: list[
        str
    ]  # one per texture whose bake cannot be packaged, with the command that fixes it
    unused: list[str]  # owners and textures with a bake that the dataset does not use


def plan(dataset: Dataset) -> Plan:
    """What the bakes mean for the dataset. Nothing is written."""
    baked = dataset.baked
    where = f"--game {dataset.adapter.id} --dataset {dataset.name}"
    wanted: dict[
        tuple[str, str], tuple[str, str]
    ] = {}  # (asset, variant) -> who bakes it, and how to unbake that
    owners: list[OwnerBake] = []
    unused: list[str] = []
    for owner_id, bake in sorted(baked.owners.items()):
        owner = dataset.owners.get(owner_id)
        if owner is None:
            unused.append(owner_id)
            continue
        # `original` stays in the owner's bake: it hides the bake of the layer below (R-HD-131). It packages no file.
        named = {
            asset: variant
            for asset, variant in bake.textures.items()
            if asset in owner.textures
        }
        unused += [
            f"{owner_id}: {asset}"
            for asset in sorted(set(bake.textures) - set(owner.textures))
        ]
        owners.append(OwnerBake(owner, named))
        for asset, variant in named.items():
            if variant == variants.ORIGINAL:
                continue
            wanted.setdefault(
                (asset, variant),
                (f"{owner_id}, skin {bake.skin}", f"--owner {owner_id!r}"),
            )
    textures: dict[str, str] = {}
    for asset, variant in sorted(baked.textures.items()):
        if asset not in dataset.textures:
            unused.append(asset)
            continue
        textures[asset] = variant
        wanted.setdefault((asset, variant), ("its own bake", f"--asset {asset!r}"))
    # A variant is checked against its original. Those originals are taken out in one go.
    dataset.adapter.fetch(
        dataset.name,
        [
            dataset.textures[asset]
            for asset, _variant in wanted
            if asset in dataset.textures
        ],
    )
    files: list[Packed] = []
    problems: list[str] = []
    for (asset, variant), (who, unbake) in sorted(wanted.items()):
        if asset not in dataset.textures:
            problems.append(
                f"{asset}: {who} names it and the dataset does not list it; run: {COMMAND} index {where}"
            )
            continue
        texture = dataset.texture(asset)
        made = dataset.made(texture)
        recipe, size = variants.split(variant)
        if reason := results.refusal(made, variant):
            if recipe not in made or made[recipe].stale:
                fix = f"run: {COMMAND} request {where} --asset '{asset}' --variant {variant}"
            else:  # a variant with a problem is not made better by making it again
                fix = f"name another variant of it in the skin and bake again, or run: {COMMAND} unbake {where} {unbake}"
            problems.append(f"{asset} ({who}): {reason}; {fix}")
            continue
        entry = made[recipe].entry
        files.append(
            Packed(
                texture,
                variant,
                dataset.game.variant_file(texture.origin, recipe, size),
                entry["files"][str(size)]["sha256"],
            )
        )
    return Plan(files, owners, textures, problems, unused)


def package(dataset: Dataset, target: Path) -> dict:
    """Put what the bakes name into `target`, check it, and keep the record. Returns the record.

    A bake of a missing or stale variant, or of one with a problem that is
    not accepted, fails it, before anything is written (R-HD-102). A game
    that bakes nothing is refused first (R-HD-115).
    """
    bakes.refuse(dataset.adapter)
    planned = plan(dataset)
    if planned.problems:
        raise PackageError(
            f"{len(planned.problems)} baked textures of {dataset.name} cannot be packaged:\n"
            + "\n".join(planned.problems)
        )
    for item in planned.files:
        if not item.file.is_file() or file_sha256(item.file) != item.sha256:
            fix = f"request --game {dataset.adapter.id} --dataset {dataset.name} --asset '{item.texture.asset}' --variant {item.variant}"
            raise PackageError(
                f"{item.texture.asset}: {item.file} is not the file its entry names; remove its folder and run: {COMMAND} {fix}"
            )
    paths = dataset.adapter.package(
        dataset.name, planned.files, planned.owners, planned.textures, target
    )
    dataset.adapter.check(target)
    sha = {(item.texture.asset, item.variant): item.sha256 for item in planned.files}
    record = {
        "format": FORMAT,
        "files": [
            {
                "asset": asset,
                "variant": variant,
                "sha256": sha[asset, variant],
                "path": path,
            }
            for (asset, variant), path in sorted(paths.items())
        ],
        "owners": {
            bake.owner.id: {
                "skin": dataset.baked.owners[bake.owner.id].skin,
                "textures": dataset.baked.owners[bake.owner.id].textures,
            }
            for bake in planned.owners
        },
        "textures": {
            asset: {
                "variant": variant,
                "sha256": sha[asset, variant],
                "path": paths[asset, variant],
            }
            for asset, variant in planned.textures.items()
        },
        "unused": planned.unused,
    }
    write_json(dataset.folder / FILE, record)
    dataset.changed_all()
    LOG.info(
        "packaged %d files of %s for %d owners and %d textures into %s; %d bakes are unused",
        len(paths),
        dataset.name,
        len(planned.owners),
        len(planned.textures),
        target,
        len(planned.unused),
    )
    return record


def package_in_store(dataset: Dataset) -> dict:
    """Package a dataset no build packages, into its own folder of the store. What was there goes first."""
    bakes.refuse(dataset.adapter)
    target = dataset.folder / FOLDER
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    return package(dataset, target) | {"target": str(target)}


def record(dataset: Dataset) -> dict | None:
    """What the last package of the dataset held. None: it was never packaged."""
    return dataset.game.package_record(dataset.name)
