"""Names and files every part of the StarCraft II adapter shares: the packaged
texture folder, the archives a dependency loads, a map's terrain textures.
"""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from ..core.interfaces import GameError

HD_DIR = "Assets\\Textures\\scoba_hd"
# The game keeps a table of texture sizes per quality setting
# (texturereduction\texturereductionvalues.txt). Its key is the file name
# alone, without the folder. A file named like the original is matched to
# the original's entry and logged as "Texture DB does not match file info".
# The mark gives every packaged file a name the table does not hold. It
# stands at the end of the name. A `CModel` finds its texture slots by the
# start of a file name and by words inside it (`TextureDeclares` with
# `Prefix` and `TriggerOnSubstring`), so the start must stay as it was.
HD_MARK = "_scoba_hd"
# The mark of a texture only model files name. A terrain texture of the same name gets a file of its own.
MODEL_MARK = HD_MARK + "_m"
# Hex digits of a variant's hash in the name of a second variant of one texture (`tagged_mark`).
TAG = 6
# The end of a packaged file's stem: the mark, its model form, or the model form with a tag.
MARKED = re.compile(rf".*{re.escape(HD_MARK)}(?:_m|_[0-9a-f]{{{TAG}}}_m)?", re.DOTALL)

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


class SourceError(GameError):
    """The map's textures could not be resolved."""


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
            raise SourceError(
                f"unknown dependency {key}; add its archives to DEPENDENCY_ARCHIVES"
            )
        archives.extend(a for a in DEPENDENCY_ARCHIVES[key] if a not in archives)
    if not archives:
        raise SourceError("the map lists no dependencies")
    return tuple(archives)


TERRAIN_FILE = "t3Terrain.xml"


def terrain_texture_ids(map_dir: Path) -> list[str]:
    """Terrain texture entries the map paints with, in t3Terrain.xml order."""
    root = ET.parse(map_dir / TERRAIN_FILE).getroot()
    ids = [node.get("name", "") for node in root.iter("texture")]
    ids = list(dict.fromkeys(name for name in ids if name))
    if not ids:
        raise SourceError("t3Terrain.xml lists no terrain textures")
    return ids


def stored_name(asset: str) -> str:
    """An asset path as the storage spells it: lower case, backslashes."""
    return asset.replace("/", "\\").lower()


def file_name(asset: str) -> str:
    """The file name of an asset path, spelled as given."""
    return asset.replace("/", "\\").rsplit("\\", 1)[-1]


def marked_name(name: str, mark: str) -> str:
    """A file name with the mark before its extension."""
    stem, dot, extension = name.rpartition(".")
    if not stem or not dot:
        raise SourceError(f"{name}: a texture file name has a name and an extension")
    return f"{stem}{mark}.{extension}"


def tagged_mark(variant: str) -> str:
    """The mark of another variant of a texture than the one that keeps the plain name: a tag of its id, in the model form."""
    return f"{HD_MARK}_{hashlib.sha256(variant.encode()).hexdigest()[:TAG]}_m"


def is_marked(name: str) -> bool:
    """Does this file name carry a mark of a packaged texture? The three forms of SPEC-HD-TEXTURES 5.2, and no other."""
    return bool(MARKED.fullmatch(name.rpartition(".")[0].lower()))
