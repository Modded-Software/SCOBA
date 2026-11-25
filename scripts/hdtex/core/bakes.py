"""The bakes of one dataset: what its package holds (SPEC-HD-TEXTURES 4.6, R-HD-140, R-HD-145).

An owner's bake is its skin as it was when baked: the name and the map
from asset to variant. A texture baked on its own (SC2: terrain) is one variant. Without a
file there is no bake (R-HD-22). Only this module writes the file.
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

from . import skins, variants
from .store import read_json, write_json

FORMAT = 1
FILE = "bakes.json"


class BakeError(ValueError):
    """A bake or a bake file is not valid."""


class Bake(NamedTuple):
    skin: str
    textures: dict[str, str]  # asset -> variant id


class Bakes(NamedTuple):
    owners: dict[str, Bake]
    textures: dict[
        str, str
    ]  # asset -> variant id of a texture baked on its own (SC2: terrain)


def _variant(value: object, where: str) -> str:
    try:
        variants.split(value)
    except variants.VariantError as error:
        raise BakeError(f"{where}: {error}") from error
    return str(value)


def parse(value: object) -> Bakes:
    if not isinstance(value, dict):
        raise BakeError("bakes: not an object")
    if unknown := sorted(set(value) - {"format", "owners", "textures"}):
        raise BakeError(f"{unknown[0]}: unknown key")
    if value.get("format") != FORMAT:
        raise BakeError(
            f"format: this tooling reads {FORMAT}, got {value.get('format')!r}"
        )
    if missing := sorted({"owners", "textures"} - set(value)):
        raise BakeError(f"{missing[0]}: missing")
    owners, textures = value["owners"], value["textures"]
    if not isinstance(owners, dict) or not isinstance(textures, dict):
        raise BakeError("owners and textures are objects")
    found: dict[str, Bake] = {}
    for owner, bake in owners.items():
        where = f"owners.{owner}"
        try:
            skins.check_owner(owner)
        except skins.SkinError as error:
            raise BakeError(f"{where}: {error}") from error
        if (
            not isinstance(bake, dict)
            or set(bake) != {"skin", "textures"}
            or not isinstance(bake["textures"], dict)
            or not isinstance(bake["skin"], str)
        ):
            raise BakeError(f"{where}: a bake holds skin and textures")
        found[owner] = Bake(
            bake["skin"],
            {
                asset: _variant(variant, f"{where}.textures.{asset}")
                for asset, variant in bake["textures"].items()
            },
        )
    return Bakes(
        found,
        {
            asset: _variant(variant, f"textures.{asset}")
            for asset, variant in textures.items()
        },
    )


def load(folder: Path) -> Bakes:
    path = folder / FILE
    if not path.is_file():
        return Bakes({}, {})
    try:
        return parse(read_json(path))
    except BakeError as error:
        raise BakeError(f"{path}: {error}") from error


def save(folder: Path, bakes: Bakes) -> None:
    path = folder / FILE
    if not bakes.owners and not bakes.textures:
        path.unlink(missing_ok=True)
        return
    write_json(path, {
        "format": FORMAT,
        "owners": {owner: {"skin": bake.skin, "textures": dict(sorted(bake.textures.items()))} for owner, bake in sorted(bakes.owners.items())},
        "textures": dict(sorted(bakes.textures.items())),
    })  # fmt: skip


def with_owner(bakes: Bakes, owner: str, bake: Bake | None) -> Bakes:
    """The bakes with an owner's bake set, or removed with None."""
    found = dict(bakes.owners)
    if bake is None:
        found.pop(skins.check_owner(owner), None)
    else:
        found[skins.check_owner(owner)] = bake
    return bakes._replace(owners=found)


def with_texture(bakes: Bakes, asset: str, variant: str | None) -> Bakes:
    found = dict(bakes.textures)
    if variant is None or variant == variants.ORIGINAL:
        found.pop(asset, None)
    else:
        found[asset] = _variant(variant, asset)
    return bakes._replace(textures=found)
