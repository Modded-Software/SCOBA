"""Which textures the map uses, and where the game keeps them.

A source lists `TextureRef`s for one kind of content. Only terrain exists
today. A doodad source would be one more function in SOURCES. Its refs
need overrides too: a file that shadows the original by path keeps the
original's name, and the game then sizes it by the original's table entry
(see HD_PREFIX).
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Callable, NamedTuple

from .casc import Casc

HD_DIR = "Assets\\Textures\\scoba_hd"
# The game keeps a table of texture sizes per quality setting
# (texturereduction\texturereductionvalues.txt). Its key is the file name
# alone, without the folder. A file named like the original is matched to
# the original's entry and logged as "Texture DB does not match file info".
# The prefix gives every upscaled file a name the table does not hold.
HD_PREFIX = "scoba_hd_"

# Archives a dependency loads, first to last. A later archive wins. The game
# ships no dependency list for its own archives, so the order is fixed here.
DEPENDENCY_ARCHIVES = {
    "campaigns/voidstory.sc2campaign": (
        "mods\\core.sc2mod",
        "mods\\liberty.sc2mod",
        "mods\\swarm.sc2mod",
        "mods\\void.sc2mod",
        "campaigns\\liberty.sc2campaign",
        "campaigns\\swarm.sc2campaign",
        "campaigns\\void.sc2campaign",
        "campaigns\\libertystory.sc2campaign",
        "campaigns\\swarmstory.sc2campaign",
        "campaigns\\voidstory.sc2campaign",
    ),
}

# Catalog field of a terrain texture entry, and the role of the file it names.
TERRAIN_FIELDS = (("Texture", "diffuse"), ("Normalmap", "normal"))


class SourceError(RuntimeError):
    """The map's textures could not be resolved."""


class Override(NamedTuple):
    """A catalog field that must point at the new file."""

    catalog_file: str  # file below Base.SC2Data/GameData
    element: str
    entry: str
    field: str


class TextureRef(NamedTuple):
    asset: str  # game path, as the catalog spells it
    role: str
    casc_path: str
    map_path: str  # where the upscaled file goes in the map
    overrides: tuple[Override, ...]
    # (columns, rows) of a flip book. Its cells are upscaled apart from each other.
    grid: tuple[int, int] = (1, 1)


def map_archives(map_dir: Path) -> tuple[str, ...]:
    """Game archives the map depends on, in load order."""
    root = ET.parse(map_dir / "DocumentInfo").getroot()
    archives: list[str] = []
    for value in root.iter("Value"):
        match = re.search(r"file:([^,]+)", value.text or "")
        if not match:
            raise SourceError(f"dependency without a file: {value.text!r}")
        key = match.group(1).strip().replace("\\", "/").lower()
        if key not in DEPENDENCY_ARCHIVES:
            raise SourceError(f"unknown dependency {key}; add its archives to DEPENDENCY_ARCHIVES")
        archives.extend(a for a in DEPENDENCY_ARCHIVES[key] if a not in archives)
    if not archives:
        raise SourceError("the map lists no dependencies")
    return tuple(archives)


def terrain_texture_ids(map_dir: Path) -> list[str]:
    """Terrain texture entries the map paints with, in t3Terrain.xml order."""
    root = ET.parse(map_dir / "t3Terrain.xml").getroot()
    ids = [node.get("name", "") for node in root.iter("texture")]
    ids = list(dict.fromkeys(name for name in ids if name))
    if not ids:
        raise SourceError("t3Terrain.xml lists no terrain textures")
    return ids


def catalog_fields(catalogs: list[str], element: str) -> dict[str, dict[str, str]]:
    """Field values per entry id, from catalog XML texts in load order.

    Entries with a parent, and values built from `##` tokens, are left out
    of the result for that field. A caller that needs one gets a clear error.
    """
    entries: dict[str, dict[str, str]] = {}
    for text in catalogs:
        for node in ET.fromstring(text).iter(element):
            entry = node.get("id")
            if not entry or node.get("default") == "1":
                continue
            fields = entries.setdefault(entry, {})
            if node.get("parent"):
                fields["__parent__"] = node.get("parent", "")
            for child in node:
                value = child.get("value")
                if value is not None:
                    fields[child.tag] = value
    return entries


def stored_name(asset: str) -> str:
    """An asset path as the storage spells it: lower case, backslashes."""
    return asset.replace("/", "\\").lower()


def _archive_of(casc_path: str, asset: str, archives: tuple[str, ...]) -> int:
    """Load position of the archive that holds `asset` at `casc_path`, or -1.

    An archive keeps assets at its root or in one `*.sc2assets` folder. A
    deeper match is a campaign map inside the archive, which the map does
    not load.
    """
    asset = stored_name(asset)
    for index, archive in enumerate(archives):
        if not casc_path.startswith(archive + "\\"):
            continue
        rest = casc_path[len(archive) + 1 :]
        if rest == asset:
            return index
        folder, _, tail = rest.partition("\\")
        if tail == asset and folder.endswith(".sc2assets"):
            return index
    return -1


def locate(asset: str, candidates: list[str], archives: tuple[str, ...]) -> str:
    """The stored file an asset path resolves to: the one in the last-loaded archive."""
    ranked = sorted((_archive_of(path, asset, archives), path) for path in candidates)
    ranked = [item for item in ranked if item[0] >= 0]
    if not ranked:
        raise SourceError(f"{asset} is not in any archive the map depends on")
    return ranked[-1][1]


def terrain_refs(map_dir: Path, casc: Casc, work_dir: Path) -> list[TextureRef]:
    archives = map_archives(map_dir)
    wanted = terrain_texture_ids(map_dir)
    catalog_tail = "\\base.sc2data\\gamedata\\terraintexdata.xml"
    present = set(casc.find([catalog_tail]))
    stored = [archive + catalog_tail for archive in archives if archive + catalog_tail in present]
    extracted = casc.extract(stored, work_dir / "catalogs")
    texts = [extracted[path].read_text(encoding="utf-8-sig") for path in stored]
    own = map_dir / "Base.SC2Data" / "GameData" / "TerrainTexData.xml"
    if own.is_file():
        texts.append(own.read_text(encoding="utf-8-sig"))
    entries = catalog_fields(texts, "CTerrainTex")

    assets: dict[str, tuple[str, list[Override]]] = {}
    for entry in wanted:
        fields = entries.get(entry)
        if fields is None:
            raise SourceError(f"terrain texture {entry} is not in any catalog the map loads")
        for field, role in TERRAIN_FIELDS:
            value = fields.get(field)
            if value is None or "##" in value:
                raise SourceError(
                    f"terrain texture {entry} has no plain {field} value "
                    f"(parent {fields.get('__parent__', 'none')}); template values are not supported"
                )
            if value.lower().startswith(HD_DIR.lower() + "\\"):
                raise SourceError(f"{entry}.{field} already points at an upscaled file: {value}")
            known_role, overrides = assets.setdefault(value, (role, []))
            if known_role != role:
                raise SourceError(f"{value} is used as both {known_role} and {role}")
            overrides.append(Override("TerrainTexData.xml", "CTerrainTex", entry, field))

    candidates = casc.find(["\\" + stored_name(asset) for asset in assets])
    refs = []
    names: dict[str, str] = {}
    for asset, (role, overrides) in assets.items():
        name = asset.replace("/", "\\").rsplit("\\", 1)[-1]
        if names.setdefault(name.lower(), asset) != asset:
            raise SourceError(f"{asset} and {names[name.lower()]} share the file name {name}")
        refs.append(
            TextureRef(
                asset, role, locate(asset, candidates, archives), f"{HD_DIR}\\{HD_PREFIX}{name}", tuple(overrides)
            )
        )
    return refs


def model_refs(map_dir: Path, casc: Casc, work_dir: Path) -> list[TextureRef]:
    from .models import model_refs as resolve  # models.py builds on this module

    return resolve(map_dir, casc, work_dir)


SOURCES: dict[str, Callable[[Path, Casc, Path], list[TextureRef]]] = {
    "terrain": terrain_refs,
    "models": model_refs,
}
