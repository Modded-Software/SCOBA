"""The owners of a dataset: units, actors and model files, each with its textures (SPEC-HD-TEXTURES 5.1, R-HD-130).

- `model:<file>`: the model file a `CModel` entry names (its `Model`
  value), with its variations. Entries that name one file share it.
- `actor:<id>`: an actor of the dataset's catalogs (the game's and the
  map's own), with the model of its `Model` field and every model its
  lines in the map's own catalog link.
- `unit:<id>`: a unit of the dataset's catalogs. Its actor is the actor of
  that id, as the game's own data and `shown.py` have it.

The viewer's doodads are actors, its units units, its model files models.
Nothing here reads a texture file: the textures of a model file come from
the model index.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET

from ..core.interfaces import ACTOR, MODEL, UNIT, Owner
from . import modelindex, shown
from .catalog import CatalogError
from .packaged import GAMEDATA
from .sources import file_name, stored_name
from .storage import GAP_ACTORS, Storage

LOG = logging.getLogger(__name__)


def model_key(base: str) -> str:
    return f"{MODEL}:{stored_name(base)}"


def _actor_links(storage: Storage) -> dict[str, set[str]]:
    """Actor id -> the `CModel` ids its lines in the map's own catalog link (a death, a launch, a part)."""
    if storage.layer is None:
        return {}
    path = storage.layer / GAMEDATA / shown.ACTORS
    if not path.is_file():
        return {}
    found: dict[str, set[str]] = {}
    for node in ET.fromstring(path.read_text(encoding="utf-8-sig")):
        if node.tag.startswith("CActor") and node.get("id"):
            for line in node.iter():
                if line is not node:
                    found.setdefault(node.get("id", ""), set()).update(
                        value for name in shown.LINKS if (value := line.get(name))
                    )
    return found


def owners(
    storage: Storage, read: modelindex.Models, uses: dict[str, modelindex.Use]
) -> list[Owner]:
    """Every owner the dataset shows, top layer last."""
    files, layers = read
    by_entry: dict[str, str] = {}
    textures: dict[str, set[str]] = {}
    for file in files:
        key = model_key(file.base)
        by_entry[file.entry] = key
        textures.setdefault(key, set()).update(
            stored_name(layer.path) for layer in layers[file.origin]
        )
    models = {
        key: Owner(
            key,
            file_name(key.split(":", 1)[1]),
            MODEL,
            (),
            tuple(sorted(assets & uses.keys())),
        )
        for key, assets in sorted(textures.items())
    }
    found = list(models.values())
    actors = storage.catalog(shown.ACTORS)
    units = storage.catalog(shown.UNITS)
    links = _actor_links(storage)
    # Every unit and actor of the dataset's catalogs, the game's and the map's
    # own, is an owner, placed or not (operator 2026-11-25): the viewer lists
    # them all. Which models a bake must cover is another rule (R-HD-54).
    actor_ids = actors.ids("CActor")
    unit_ids = units.ids("CUnit")
    by_actor: dict[str, Owner] = {}
    unread: list[str] = []
    for actor in actor_ids:
        try:
            model = actors.field(actor, "Model")
        except CatalogError as error:
            # The game data breaks this actor (a parent it lacks, a token without a value).
            # It owns nothing; status lists it with the reason.
            unread.append(str(error))
            continue
        below = sorted(
            {
                by_entry[entry]
                for entry in [model, *links.get(actor, ())]
                if entry in by_entry
            }
        )
        if not below:
            continue
        assets = sorted({asset for key in below for asset in models[key].textures})
        by_actor[actor] = Owner(
            f"{ACTOR}:{actor}", actor, ACTOR, tuple(below), tuple(assets)
        )
    found += by_actor.values()
    # A unit shows the layers below it nearest first: its actor, then the actor's model files.
    found += [
        Owner(
            f"{UNIT}:{unit}",
            unit,
            UNIT,
            (by_actor[unit].id, *by_actor[unit].below),
            by_actor[unit].textures,
        )
        for unit in unit_ids
        if unit in by_actor
    ]
    storage.gaps[GAP_ACTORS] = tuple(unread)
    LOG.info(
        "%s: %d owners: %d model files, %d actors, %d units",
        storage.name, len(found), len(textures), len(by_actor), len(found) - len(textures) - len(by_actor),
    )  # fmt: skip
    return found
