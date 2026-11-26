"""The skins of one owner in one dataset (SPEC-HD-TEXTURES 4.6, R-HD-130 to 136).

A skin is a name and a variant id per asset. A skin stands alone: it
names no other skin.
`original` names nothing and is not in the file: every texture shows its
original. A skin made without a name is called New Skin 1, New Skin 2 and
so on (`next_new`, R-HD-137); it is stored and saved as any other.
One file per owner, in the dataset's folder of the store. Only this
module writes it.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

from . import variants
from .store import read_json, write_json

FORMAT = 1
FOLDER = "skins"
ORIGINAL_SKIN = "original"
NEW_PREFIX = "New Skin"
NUMBERED = re.compile(r"new skin ([0-9]+)")
# Words of letters, digits, '-' or '_', one space between them; 1 to 40 characters.
NAME = re.compile(r"(?=.{1,40}$)[A-Za-z0-9_-]+(?: [A-Za-z0-9_-]+)*")
OWNER = re.compile(r"(unit|actor|model):(.+)")


class SkinError(ValueError):
    """A skin change or a skin file is not valid."""


class Skin(NamedTuple):
    name: str
    textures: dict[str, str]  # asset -> variant id


def check_owner(owner: str) -> str:
    if not isinstance(owner, str) or not OWNER.fullmatch(owner):
        raise SkinError(
            f"an owner is unit:<id>, actor:<id> or model:<file>; got {owner!r}"
        )
    return owner


def check_name(name: str) -> str:
    if not isinstance(name, str) or not NAME.fullmatch(name):
        raise SkinError(
            f"a skin name is 1 to 40 letters, digits, '-' or '_', with one space between words; got {name!r}"
        )
    if name.lower() == ORIGINAL_SKIN:
        raise SkinError(
            f"{name!r} is the Original skin: it names nothing and cannot be made, changed or removed"
        )
    return name


def next_new(skins: dict[str, Skin]) -> str:
    """The name of the next skin made without one: New Skin N, N one above the highest in use (from 1)."""
    numbers = [int(found.group(1)) for name in skins if (found := NUMBERED.fullmatch(name.lower()))]
    return f"{NEW_PREFIX} {max(numbers, default=0) + 1}"


def _taken(skins: dict[str, Skin], name: str, but: str | None = None) -> None:
    """Refuse a name another skin of the owner holds; names are unique ignoring case (R-HD-138)."""
    for other in skins:
        if other != but and other.lower() == name.lower():
            raise SkinError(f"there is a skin {other!r} already")


def file_of(folder: Path, owner: str) -> Path:
    """The skin file of an owner: readable, and a hash of all of it."""
    kind, _, key = check_owner(owner).partition(":")
    tail = (
        re.sub(
            r"[^a-z0-9_.-]+", "_", key.lower().replace("/", "\\").rsplit("\\", 1)[-1]
        ).strip("._-")
        or kind
    )
    return (
        folder
        / FOLDER
        / f"{kind}-{tail[:60]}-{hashlib.sha256(owner.encode()).hexdigest()[:16]}.json"
    )


def _skin(name: str, value: object, where: str) -> Skin:
    if not isinstance(value, dict):
        raise SkinError(f"{where}: not an object")
    if unknown := sorted(set(value) - {"textures"}):
        raise SkinError(f"{where}.{unknown[0]}: unknown key")
    if "textures" not in value:
        raise SkinError(f"{where}.textures: missing")
    textures = value["textures"]
    if not isinstance(textures, dict):
        raise SkinError(f"{where}.textures: not an object")
    for asset, variant in textures.items():
        try:
            variants.split(variant)
        except variants.VariantError as error:
            raise SkinError(f"{where}.textures.{asset}: {error}") from error
    return Skin(check_name(name), dict(textures))


def load(folder: Path, owner: str) -> dict[str, Skin]:
    """The skins of an owner, by name. No file: none but Original."""
    path = file_of(folder, owner)
    if not path.is_file():
        return {}
    value = read_json(path)
    try:
        if (
            not isinstance(value, dict)
            or value.get("format") != FORMAT
            or value.get("owner") != owner
        ):
            raise SkinError(f"not a skin file of {owner} in format {FORMAT}")
        if unknown := sorted(set(value) - {"format", "owner", "skins"}):
            raise SkinError(f"{unknown[0]}: unknown key")
        if "skins" not in value:
            raise SkinError("skins: missing")
        found = value["skins"]
        if not isinstance(found, dict):
            raise SkinError("skins: not an object")
        loaded: dict[str, Skin] = {}
        for name, skin in found.items():
            _taken(loaded, name)
            loaded[name] = _skin(name, skin, f"skins.{name}")
        return loaded
    except SkinError as error:
        raise SkinError(f"{path}: {error}") from error


def save(folder: Path, owner: str, skins: dict[str, Skin]) -> None:
    path = file_of(folder, owner)
    if not skins:
        path.unlink(missing_ok=True)
        return
    write_json(path, {
        "format": FORMAT,
        "owner": owner,
        "skins": {name: {"textures": dict(sorted(skin.textures.items()))} for name, skin in sorted(skins.items())},
    })  # fmt: skip


def owners(folder: Path) -> list[str]:
    """Every owner with a skin file in a dataset's folder. A file that names no owner is refused."""
    found = []
    for path in sorted((folder / FOLDER).glob("*.json")):
        value = read_json(path)
        if not isinstance(value, dict) or not isinstance(value.get("owner"), str):
            raise SkinError(f"{path}: not a skin file: it names no owner")
        found.append(value["owner"])
    return found


def textures_of(skins: dict[str, Skin], name: str) -> dict[str, str]:
    """What a skin names. Original names nothing."""
    if name == ORIGINAL_SKIN:
        return {}
    if name not in skins:
        raise SkinError(
            f"there is no skin {name!r}; skins: {', '.join([ORIGINAL_SKIN, *sorted(skins)])}"
        )
    return dict(skins[name].textures)


def made(
    skins: dict[str, Skin], name: str, textures: dict[str, str]
) -> dict[str, Skin]:
    """The skins with a new one naming `textures`."""
    _taken(skins, check_name(name))
    return {**skins, name: Skin(name, dict(textures))}


def copied(skins: dict[str, Skin], source: str, name: str) -> dict[str, Skin]:
    """The skins with a new one naming what `source` names now (R-HD-133)."""
    return made(skins, name, textures_of(skins, source))


def renamed(skins: dict[str, Skin], name: str, new: str) -> dict[str, Skin]:
    if check_name(name) not in skins:
        raise SkinError(f"there is no skin {name!r}")
    _taken(skins, check_name(new), but=name)
    found = {key: skin for key, skin in skins.items() if key != name}
    found[new] = skins[name]._replace(name=new)
    return found


def deleted(skins: dict[str, Skin], name: str) -> dict[str, Skin]:
    """The skins without one. A baked skin is not deleted here: see skinbakes.delete (R-HD-136)."""
    if check_name(name) not in skins:
        raise SkinError(f"there is no skin {name!r}")
    return {key: skin for key, skin in skins.items() if key != name}


def with_texture(
    skins: dict[str, Skin],
    name: str,
    asset: str,
    variant: str | None,
    assets: set[str],
    refusal: Callable[[str, str], str],
) -> dict[str, Skin]:
    """The skins with one texture of one skin set, or cleared with None.

    `assets`: the textures of the owner (R-HD-135). `refusal(asset,
    variant)`: why the texture cannot name the variant; empty: it can.
    """
    if check_name(name) not in skins:
        raise SkinError(f"there is no skin {name!r}")
    textures = dict(skins[name].textures)
    if variant is None:
        textures.pop(asset, None)
    else:
        if asset not in assets:
            raise SkinError(f"{asset} is no texture of this owner")
        if reason := refusal(asset, variant):
            raise SkinError(f"{asset}: {reason}")
        textures[asset] = variant
    return {**skins, name: skins[name]._replace(textures=textures)}
