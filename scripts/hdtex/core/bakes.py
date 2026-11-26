"""The bakes of one dataset: what its package holds (SPEC-HD-TEXTURES 4.6, R-HD-140, R-HD-145).

An owner's bake is its skin as it was when baked: the name and the map
from asset to variant. A texture baked on its own (SC2: terrain) is one variant. Without a
file there is no bake (R-HD-22). Only this module writes the file.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

from . import skins, variants
from .interfaces import GameAdapter
from .store import read_json, write_json

FORMAT = 1
FILE = "bakes.json"


class BakeError(ValueError):
    """A bake or a bake file is not valid."""


def refuse(adapter: GameAdapter) -> None:
    """Refuse a bake, an unbake or a package of a game that bakes nothing, before any file is read or written (R-HD-115)."""
    if adapter.bakes:
        raise BakeError(f"{adapter.id}: {adapter.bakes}")


class Bake(NamedTuple):
    skin: str
    textures: dict[str, str]  # asset -> variant id


class Pins(NamedTuple):
    """The file each bake took (R-HD-160): the SHA-256 of the variant file, as its entry held it at the bake.
    `original` has none. A bake made before the pins has none either, and is not compared."""

    owners: dict[str, dict[str, str]]  # owner -> asset -> sha256
    textures: dict[str, str]  # asset -> sha256, of a texture baked on its own


NO_PINS = Pins({}, {})
SHA256 = re.compile(r"[0-9a-f]{64}")


class Bakes(NamedTuple):
    owners: dict[str, Bake]
    textures: dict[
        str, str
    ]  # asset -> variant id of a texture baked on its own (SC2: terrain)
    pins: Pins = NO_PINS


def _pins(value: object, owners: dict[str, Bake], textures: dict[str, str]) -> Pins:
    """The pins of a bake file. Each names a variant a bake of the file names."""
    if (
        not isinstance(value, dict)
        or set(value) != {"owners", "textures"}
        or not isinstance(value["owners"], dict)
        or not isinstance(value["textures"], dict)
    ):
        raise BakeError("pins: holds owners and textures")
    for owner, held in value["owners"].items():
        if owner not in owners or not isinstance(held, dict):
            raise BakeError(f"pins.owners.{owner}: no bake of that owner")
        named = owners[owner].textures
        for asset, pin in held.items():
            if named.get(asset, variants.ORIGINAL) == variants.ORIGINAL or not isinstance(pin, str) or not SHA256.fullmatch(pin):
                raise BakeError(f"pins.owners.{owner}.{asset}: a pin is the SHA-256 of a variant the bake names")
    for asset, pin in value["textures"].items():
        if asset not in textures or not isinstance(pin, str) or not SHA256.fullmatch(pin):
            raise BakeError(f"pins.textures.{asset}: a pin is the SHA-256 of a variant the bake names")
    return Pins({owner: dict(held) for owner, held in value["owners"].items() if held}, dict(value["textures"]))


def _variant(value: object, where: str) -> str:
    try:
        variants.split(value)
    except variants.VariantError as error:
        raise BakeError(f"{where}: {error}") from error
    return str(value)


def parse(value: object) -> Bakes:
    if not isinstance(value, dict):
        raise BakeError("bakes: not an object")
    if unknown := sorted(set(value) - {"format", "owners", "textures", "pins"}):
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
    alone = {
        asset: _variant(variant, f"textures.{asset}")
        for asset, variant in textures.items()
    }
    return Bakes(found, alone, _pins(value["pins"], found, alone) if "pins" in value else NO_PINS)


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
    pins = bakes.pins
    write_json(path, {
        "format": FORMAT,
        "owners": {owner: {"skin": bake.skin, "textures": dict(sorted(bake.textures.items()))} for owner, bake in sorted(bakes.owners.items())},
        "textures": dict(sorted(bakes.textures.items())),
        # A file that pins nothing is the file it was before the pins.
        **({"pins": {
            "owners": {owner: dict(sorted(held.items())) for owner, held in sorted(pins.owners.items())},
            "textures": dict(sorted(pins.textures.items())),
        }} if pins.owners or pins.textures else {}),
    })  # fmt: skip


def with_owner(bakes: Bakes, owner: str, bake: Bake | None, pins: dict[str, str] | None = None) -> Bakes:
    """The bakes with an owner's bake set, or removed with None.

    `pins`: the file of each variant the bake took (R-HD-160). None keeps
    the owner's pins: the bake's textures did not change (a rename).
    """
    found = dict(bakes.owners)
    held = dict(bakes.pins.owners)
    if bake is None:
        found.pop(skins.check_owner(owner), None)
        held.pop(owner, None)
    else:
        found[skins.check_owner(owner)] = bake
        if pins is not None:
            held.pop(owner, None)
            if pins:
                held[owner] = dict(pins)
    return bakes._replace(owners=found, pins=bakes.pins._replace(owners=held))


def with_texture(bakes: Bakes, asset: str, variant: str | None, pin: str | None = None) -> Bakes:
    """The bakes with a texture baked on its own, or unbaked with None. `pin`: the file the bake took."""
    found = dict(bakes.textures)
    held = dict(bakes.pins.textures)
    held.pop(asset, None)
    if variant is None or variant == variants.ORIGINAL:
        found.pop(asset, None)
    else:
        found[asset] = _variant(variant, asset)
        if pin is not None:
            held[asset] = pin
    return bakes._replace(textures=found, pins=bakes.pins._replace(textures=held))
