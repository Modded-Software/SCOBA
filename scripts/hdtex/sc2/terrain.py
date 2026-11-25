"""The terrain textures of a dataset: every `CTerrainTex` of its catalogs (R-HD-3).

An entry names a colour file and a normal map. The terrain sets
(`CTerrain`) that blend an entry are its users.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from typing import NamedTuple

from .catalog import CatalogError
from .sources import TERRAIN_FIELDS, file_name, stored_name
from .storage import GAP_TERRAIN, Storage

TEXTURES = "TerrainTexData.xml"
SETS = "TerrainData.xml"
ELEMENT = "CTerrainTex"

LOG = logging.getLogger(__name__)


class Use(NamedTuple):
    """One terrain texture file and everything that names it."""

    asset: str  # as the storage spells it
    origin: str | None  # None: the dataset cannot show the file
    roles: tuple[str, ...]  # more than one: entries disagree on what the file is
    fields: tuple[
        tuple[str, str], ...
    ]  # (entry, field) of each catalog field that names it
    sets: tuple[str, ...]  # the terrain sets that blend one of those entries
    name: str  # the file name as the first of `fields` spells it


def sets_by_entry(texts: list[str]) -> dict[str, set[str]]:
    """Terrain texture entry -> the terrain sets that blend it, from catalog texts."""
    found: dict[str, set[str]] = {}
    for text in texts:
        for node in ET.fromstring(text).iter("CTerrain"):
            for blend in node.iter("BlendTextures"):
                if node.get("id") and blend.get("value"):
                    found.setdefault(blend.get("value", ""), set()).add(
                        node.get("id", "")
                    )
    return found


def uses(storage: Storage) -> list[Use]:
    """Every file a terrain texture entry of the dataset names, in asset order."""
    catalog = storage.catalog(TEXTURES)
    sets = sets_by_entry(storage.catalog_texts(SETS))
    grouped: dict[str, list[tuple[str, str, str, str]]] = {}
    unnamed: list[str] = []
    for entry in catalog.ids(ELEMENT):
        for field, role in TERRAIN_FIELDS:
            try:
                value = catalog.field(entry, field)
            except CatalogError as error:
                unnamed.append(f"{entry}.{field}: {error}")
                continue
            if value:
                grouped.setdefault(stored_name(value), []).append(
                    (entry, field, role, file_name(value))
                )
    storage.gaps[GAP_TERRAIN] = tuple(unnamed)
    LOG.info(
        "%s: %d terrain texture files of %d entries; %d fields have no value (first: %s)",
        storage.name,
        len(grouped),
        len(catalog.ids(ELEMENT)),
        len(unnamed),
        unnamed[:1],
    )
    return [
        Use(
            asset,
            storage.origin(asset),
            tuple(sorted({role for _entry, _field, role, _name in named})),
            tuple(sorted((entry, field) for entry, field, _role, _name in named)),
            tuple(
                sorted(
                    set().union(
                        *(
                            sets.get(entry, set())
                            for entry, _field, _role, _name in named
                        )
                    )
                )
            ),
            min(named)[3],
        )
        for asset, named in sorted(grouped.items())
    ]
