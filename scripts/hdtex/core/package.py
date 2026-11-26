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
    # (asset, variant) -> everyone who bakes it, each with how to unbake that (R-HD-157),
    # how to bake it again, and the file the bake took (its pin, R-HD-160; None: it has none)
    wanted: dict[tuple[str, str], list[tuple[str, str, str, str | None]]] = {}
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
            # Quoted as it is, not by repr: that doubles each backslash of a model path, and the command names no owner.
            wanted.setdefault((asset, variant), []).append((
                f"{owner_id}, skin {bake.skin}",
                f"--owner '{owner_id}'",
                f"--owner '{owner_id}' --skin '{bake.skin}'",
                baked.pins.owners.get(owner_id, {}).get(asset),
            ))
    textures: dict[str, str] = {}
    for asset, variant in sorted(baked.textures.items()):
        if asset not in dataset.textures:
            unused.append(asset)
            continue
        textures[asset] = variant
        wanted.setdefault((asset, variant), []).append((
            "its own bake",
            f"--asset '{asset}'",
            f"--asset '{asset}' --variant {variant}",
            baked.pins.textures.get(asset),
        ))
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
    for (asset, variant), bakers in sorted(wanted.items()):
        # Everyone who bakes it, with their number and the command that unbakes each (R-HD-157).
        named = "\n".join(
            [f"  baked by {len(bakers)} owner{'' if len(bakers) == 1 else 's'}:"]
            + [f"    {who}: {COMMAND} unbake {where} {unbake}" for who, unbake, _again, _pin in bakers]
        )
        if asset not in dataset.textures:
            problems.append(
                f"{asset}: {variant} is baked and the dataset does not list the texture; run: {COMMAND} index {where}\n{named}"
            )
            continue
        texture = dataset.texture(asset)
        made = dataset.made(texture)
        recipe, size = variants.split(variant)
        if reason := results.refusal(made, variant):
            if recipe not in made or made[recipe].stale:
                fix = f"run: {COMMAND} request {where} --asset '{asset}' --variant {variant}"
            else:  # a variant with a problem is not made better by making it again
                fix = "name another variant of it in each skin and bake again, or unbake"
            problems.append(f"{asset}: {reason}; {fix}\n{named}")
            continue
        entry = made[recipe].entry
        # A bake pins the file it took. The id alone does not say that the file is still that one (R-HD-160).
        now = entry["files"][str(size)]["sha256"]
        off = [(who, again) for who, _unbake, again, pin in bakers if pin is not None and pin != now]
        if off:
            problems.append(
                f"{asset}: {variant} is not the file {len(off)} bake{'' if len(off) == 1 else 's'} took: "
                "its file has another hash now; bake again to take it as it is, or name another variant\n"
                + "\n".join(f"    {who}: {COMMAND} bake {where} {again}" for who, again in off)
            )
            continue
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
