"""The `CModel` entries a map shows (R-HD-3, R-HD-54).

The game holds some 14000 model entries. A map shows few of them, and only
those get a copy when a texture of theirs is packaged. Which they are is
read from the map folder, never typed in:

- the doodads and units the map places (`Objects`);
- the units and actors of the map's own catalogs;
- the model entries the map's own catalog gives a model file.

A placed type, a unit and an actor are shown by the actor of that name.
That actor's model counts, and so does every model its entry in the map's
own catalog links: the model of a death, of a launch, of a part.

Not found: a unit the map only makes by script and that none of its own
catalogs names.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from .catalog import CatalogError
from .packaged import GAMEDATA, own_catalog
from .storage import GAP_SHOWN, Storage

OBJECTS = "Objects"
ACTORS = "ActorData.xml"
UNITS = "UnitData.xml"
MODELS = "ModelData.xml"
PLACED = re.compile(r'<Object(?:Doodad\b[^>]*\bType|Unit\b[^>]*\bUnitType)="([^"]+)"')
# Attributes of the lines inside an actor entry that name a `CModel`.
LINKS = ("Model", "ModelLink")

LOG = logging.getLogger(__name__)


def placed(map_dir: Path) -> set[str]:
    """The doodad and unit types the map places."""
    objects = map_dir / OBJECTS
    return (
        set(PLACED.findall(objects.read_text(encoding="utf-8", errors="replace")))
        if objects.is_file()
        else set()
    )


def own(catalog: Path, cls: str) -> tuple[set[str], set[str]]:
    """The ids of the entries of class `cls*` in one catalog file of the map, and the models their lines link."""
    if not catalog.is_file():
        return set(), set()
    ids: set[str] = set()
    linked: set[str] = set()
    for node in ET.fromstring(catalog.read_text(encoding="utf-8-sig")):
        if not node.tag.startswith(cls) or not node.get("id"):
            continue
        ids.add(node.get("id", ""))
        for line in node.iter():
            linked.update(line.get(name, "") for name in LINKS if line is not node)
    return ids, linked - {""}


def given_files(map_dir: Path) -> set[str]:
    """The ids of the `CModel` entries the map's own catalog gives a model file.

    The lines this tooling wrote there do not count: the build writes one
    for every entry it packages a copy of.
    """
    text = own_catalog(map_dir, MODELS)
    if text is None:
        return set()
    root = ET.fromstring(text)
    return {
        node.get("id", "")
        for node in root.iter("CModel")
        if node.get("id") and node.find("Model") is not None
    }


def entries(storage: Storage) -> frozenset[str] | None:
    """The ids of the `CModel` entries the dataset's layer shows. None: no layer, so every entry."""
    if storage.layer is None:
        return None
    on_map = placed(storage.layer)
    actors, linked = own(storage.layer / GAMEDATA / ACTORS, "CActor")
    units, _ = own(storage.layer / GAMEDATA / UNITS, "CUnit")
    given = given_files(storage.layer)
    catalog = storage.catalog(ACTORS)
    shown = linked | given
    nameless: list[str] = []
    for actor in sorted(on_map | actors | units):
        try:
            model = catalog.field(actor, "Model") if actor in catalog.entries else None
        except CatalogError as error:
            nameless.append(f"{actor}: {error}")
            continue
        if model:
            shown.add(model)
        else:
            nameless.append(f"{actor}: no actor with a model")
    storage.gaps[GAP_SHOWN] = tuple(nameless)
    LOG.info(
        "%s: the map shows %d model entries: it places %d types, its catalogs hold %d actors and %d units, link %d models and give %d entries a file; %d names have no model (first: %s)",
        storage.name, len(shown), len(on_map), len(actors), len(units), len(linked), len(given), len(nameless), nameless[:1],
    )  # fmt: skip
    return frozenset(shown)
