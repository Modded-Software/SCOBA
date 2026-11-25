"""The skins of one owner in one dataset (SPEC-HD-TEXTURES 4.6, R-HD-130 to 136).

A skin is a name and a variant id per asset. A skin stands alone: it
names no other skin.
`original` names nothing and is not in the file: every texture shows its
original. `new` is New Skin, the one unsaved skin of an owner (R-HD-137).
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
NEW = "new"
NAME = re.compile(r"[A-Za-z0-9_-]{1,40}")
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
            f"a skin name is 1 to 40 letters, digits, '-' or '_'; got {name!r}"
        )
    if name.lower() == ORIGINAL_SKIN:
        raise SkinError(
            f"{name!r} is the Original skin: it names nothing and cannot be made, changed or removed"
        )
    if name.lower() == NEW and name != NEW:
        raise SkinError(f"{name!r} reads as New Skin; New Skin is {NEW!r}")
    return name


def check_saved(name: str) -> str:
    """A name a skin can be saved under: not New Skin's."""
    if check_name(name) == NEW:
        raise SkinError(f"{NEW!r} is New Skin; save it under a name of its own")
    return name


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


def offered(skins: dict[str, Skin], shows: dict[str, str]) -> dict[str, str] | None:
    """What the offered New Skin names (R-HD-137); None: none is offered.

    Offered when the owner holds no New Skin, shows a variant that is not
    the original, and no saved skin names exactly those variants.
    """
    look = _changed(shows)
    if NEW in skins or not look:
        return None
    if any(_changed(skin.textures) == look for skin in skins.values()):
        return None
    return look


def _changed(textures: dict[str, str]) -> dict[str, str]:
    """The textures that name a variant other than the original."""
    return {asset: one for asset, one in textures.items() if one != variants.ORIGINAL}


def made(
    skins: dict[str, Skin], name: str, textures: dict[str, str]
) -> dict[str, Skin]:
    """The skins with a new one naming `textures`. New Skin is refused while it is stored."""
    if check_name(name) == NEW and NEW in skins:
        raise SkinError(f"there is a skin {NEW!r} already; save or discard New Skin first")
    _taken(skins, name)
    return {**skins, name: Skin(name, dict(textures))}


def with_new(skins: dict[str, Skin], start: dict[str, str]) -> dict[str, Skin]:
    """The skins with New Skin stored: as it is, else naming `start` (R-HD-137)."""
    return skins if NEW in skins else made(skins, NEW, start)


def copied(skins: dict[str, Skin], source: str, name: str) -> dict[str, Skin]:
    """The skins with a new one naming what `source` names now (R-HD-133)."""
    _taken(skins, check_name(name))
    return {**skins, name: Skin(name, textures_of(skins, source))}


def renamed(skins: dict[str, Skin], name: str, new: str) -> dict[str, Skin]:
    if check_name(name) not in skins:
        raise SkinError(f"there is no skin {name!r}")
    _taken(skins, check_saved(new), but=name)
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
