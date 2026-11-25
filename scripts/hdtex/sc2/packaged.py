"""What the pack step writes into a map folder, and the map folder without it.

The pack step copies texture files and model files into two folders of
their own and sets catalog lines that name them. It notes what each line
replaced. Whoever asks what the map itself holds reads it through this
module: the texture pipeline, when it lists a dataset, and the hit volume
data, whose shapes do not depend on which textures are picked.

Nothing here is guessed. A catalog that names a packaged file without a
note of what stood there is refused.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from ..core.interfaces import GameError
from .sources import HD_DIR, stored_name

GAMEDATA = Path("Base.SC2Data") / "GameData"
# Model copies go here in the map. A `CModel` line names them.
HD_MODEL_DIR = "Assets\\Models\\scoba_hd"
FOLDERS = (stored_name(HD_DIR) + "\\", stored_name(HD_MODEL_DIR) + "\\")
# File in a packaged map: what its catalogs held before the pack step set its lines.
PRIOR = ".hd_prior"
FORMAT = 1

# (catalog file, element) -> (entry id, field) -> the packaged file or the made entry the field names.
Lines = dict[tuple[str, str], dict[tuple[str, str], str]]
# (catalog file, element) -> id of an entry the pack step makes -> its parent.
Made = dict[tuple[str, str], dict[str, str]]

PACKAGED_VALUE = re.compile(
    r'value="(?:'
    + "|".join(re.escape(folder) for folder in (HD_DIR, HD_MODEL_DIR))
    + r")\\",
    re.IGNORECASE,
)


class PackagedError(GameError):
    """A map folder whose packaged lines cannot be set or taken back."""


def is_packaged(asset: str) -> bool:
    """Is this asset path a file the pack step wrote?"""
    return stored_name(asset).startswith(FOLDERS)


def require_unpackaged(map_dir: Path) -> None:
    """A folder is packaged once: a second time would note the first one's lines as the map's own."""
    if (map_dir / PRIOR).exists():
        raise PackagedError(f"{map_dir} is packaged already; package a fresh folder")


def _entry(root: ET.Element, element: str, entry: str) -> ET.Element | None:
    return next(
        (node for node in root.findall(element) if node.get("id") == entry), None
    )


def name_files(map_dir: Path, lines: Lines, entries_made: Made | None = None) -> None:
    """Set the catalog fields that name packaged files or made entries, and note what each of them replaced.

    `entries_made`: entries to make, each with its parent. An entry or a
    catalog file that is missing is made. The note says so: it goes again
    with its lines when the map is read without them.
    """
    require_unpackaged(map_dir)
    entries_made = entries_made or {}
    new_ids = {entry for found in entries_made.values() for entry in found}
    prior: dict[str, dict | None] = {}
    for catalog in sorted({name for name, _element in [*lines, *entries_made]}):
        path = map_dir / GAMEDATA / catalog
        made = not path.is_file()
        root = ET.Element("Catalog") if made else ET.parse(path).getroot()
        replaced: dict[str, dict[str, dict[str, str | None] | None]] = {}
        for (name, element), parents in sorted(entries_made.items()):
            if name != catalog:
                continue
            for entry, parent in sorted(parents.items()):
                if _entry(root, element, entry) is not None:
                    raise PackagedError(
                        f"{catalog}: {element} {entry} is there already; the pack step makes it"
                    )
                ET.SubElement(root, element, {"id": entry, "parent": parent})
                replaced.setdefault(element, {})[entry] = None
        for (name, element), values in sorted(lines.items()):
            if name != catalog:
                continue
            entries = replaced.setdefault(element, {})
            for (entry, field), value in sorted(values.items()):
                if not is_packaged(value) and value not in new_ids:
                    raise PackagedError(
                        f"{catalog}: {entry}.{field} would name {value}, which is no packaged file and no entry the pack step makes"
                    )
                node = _entry(root, element, entry)
                if node is None:
                    node = ET.SubElement(root, element, {"id": entry})
                    entries[entry] = None
                child = node.find(field)
                if child is not None and child.get("value") is None:
                    raise PackagedError(
                        f"{catalog}: {entry}.{field} has no value to note"
                    )
                fields = entries.setdefault(entry, {})
                if fields is not None:
                    fields[field] = None if child is None else child.get("value")
                if child is None:
                    child = ET.SubElement(node, field)
                child.set("value", value)
        ET.indent(root, space="    ")
        path.parent.mkdir(parents=True, exist_ok=True)
        # Empty lines as the map's own catalogs spell them (`"/>`): the
        # build's checks read catalogs by text. ElementTree escapes `>` in
        # text and values, so `" />` stands only at the end of a line.
        body = ET.tostring(root, encoding="unicode").replace(" />", "/>")
        path.write_text(
            f'<?xml version="1.0" encoding="us-ascii"?>\n{body}\n', encoding="ascii"
        )
        prior[catalog] = None if made else replaced
    note = {"format": FORMAT, "catalogs": prior}
    (map_dir / PRIOR).write_text(
        json.dumps(note, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )


def noted(map_dir: Path) -> dict[str, dict | None]:
    """Catalog file -> what the pack step noted for it. Empty: the folder is not packaged."""
    path = map_dir / PRIOR
    if not path.is_file():
        return {}
    note = json.loads(path.read_text(encoding="utf-8"))
    if note.get("format") != FORMAT:
        raise PackagedError(
            f"{path} has the format {note.get('format')}, not {FORMAT}; build the map again"
        )
    return note["catalogs"]


def own_catalog(map_dir: Path, name: str) -> str | None:
    """One catalog file of the map as it was before the pack step. None: the map had no such file.

    The layout and the comments of a file the pack step wrote are not kept.
    A line that names a packaged file and is not in the note is refused.
    """
    path = map_dir / GAMEDATA / name
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8-sig")
    elements = noted(map_dir).get(name, {})
    if elements is None:
        return None
    if elements:
        root = ET.fromstring(text)
        for element, entries in elements.items():
            for entry, fields in entries.items():
                node = _entry(root, element, entry)
                if node is None:
                    raise PackagedError(
                        f"{path} has no {element} {entry}, which {PRIOR} lists; build the map again"
                    )
                if fields is None:
                    root.remove(node)
                    continue
                for field, value in fields.items():
                    child = node.find(field)
                    if child is None:
                        raise PackagedError(
                            f"{path}: {entry} has no {field}, which {PRIOR} lists; build the map again"
                        )
                    if value is None:
                        node.remove(child)
                    else:
                        child.set("value", value)
        text = ET.tostring(root, encoding="unicode")
    if PACKAGED_VALUE.search(text):
        raise PackagedError(
            f"{path} names a packaged file, but {PRIOR} does not say what stood there; build the map again"
        )
    return text
