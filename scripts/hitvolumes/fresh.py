"""Is scripts/data/hit_volumes.json still what the map's data gives?

hitvolumes.measure stays a separate step: it reads the game install, the
build does not. So measure stores, for each unit type, a key of the map's
own inputs to its volume, and validate-map recomputes the key from the map
alone:

- the map's CActorUnit entries on the recorded actor chain, and any map
  actor that would now claim the type (id, unitName, or a UnitBirth Create);
- the map's CModel entries on the recorded model chain;
- the bytes of each candidate m3 (model path, first variation) that lives
  in the map's own Assets.

An edit to any of them changes the key: "run hitvolumes.measure". So does a
map unit type the JSON lacks. XML comments and the layout of a file do not
count. Stock data is not re-read: a game patch needs a manual measure.

What the HD texture step packages does not count either: its model copies
and the lines that name them (hdtex.sc2.packaged). A copy has the shapes of
its original, so a volume does not depend on which textures are picked.
"""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path

from hdtex.sc2.packaged import is_packaged, own_catalog

from .resolve import ACTOR_TAGS, MAP_CATALOGS, birth_units
from .units import unit_types

GAMEDATA = Path("Base.SC2Data") / "GameData"


class MapInputs:
    """The map's actor and model entries, and its m3 files, read once."""

    def __init__(self, map_dir: Path) -> None:
        self.map_dir = map_dir
        # A unit or actor bake sets an actor's Model line (hdtex.sc2.owned): read the actors as before it too.
        self.actors = self._entries(own_catalog(map_dir, MAP_CATALOGS["actor"]), ACTOR_TAGS)
        self.models = self._entries(own_catalog(map_dir, MAP_CATALOGS["model"]), ("CModel",))
        self.claims: dict[str, list[str]] = {}
        for ident, texts in self.actors.items():
            for text in texts:
                el = ET.fromstring(text)
                names = [n for n in (el.get("unitName") or "").split(",") if n] + birth_units(el)
                for name in names:
                    self.claims.setdefault(name, []).append(ident)
        self._digests: dict[Path, bytes] = {}
        self.m3: dict[str, Path] = {}
        for p in map_dir.rglob("*.m3"):
            entry = p.relative_to(map_dir).as_posix().lower()
            if not is_packaged(entry):
                self.m3[entry] = p

    @staticmethod
    def _entries(text: str | None, tags: tuple[str, ...]) -> dict[str, list[str]]:
        """Id -> the text of each of its entries in one catalog, without comments and layout."""
        out: dict[str, list[str]] = {}
        if text is None:
            return out
        for el in ET.fromstring(text):
            if el.tag in tags and el.get("id"):
                el.tail = None
                for node in el.iter():
                    # Blank text between lines is layout: a step that writes the file again changes it.
                    if node.text is not None and not node.text.strip():
                        node.text = None
                    if node is not el and node.tail is not None and not node.tail.strip():
                        node.tail = None
                out.setdefault(el.get("id"), []).append(ET.tostring(el, encoding="unicode"))
        return out

    def map_m3(self, entry: str) -> Path | None:
        return self.m3.get(entry.replace("\\", "/").lower())

    def key(self, unit: str, rec: dict) -> str:
        """sha256 of the map's inputs to one measured unit record."""
        h = hashlib.sha256()
        actors = list(rec.get("actors", []))
        claimed = sorted(set(([unit] if unit in self.actors else []) + self.claims.get(unit, [])))
        for ident in actors + ["|claims|"] + claimed:
            h.update(f"A:{ident}\n".encode())
            for text in self.actors.get(ident, []):
                h.update(text.encode())
        for ident in rec.get("models", []):
            h.update(f"M:{ident}\n".encode())
            for text in self.models.get(ident, []):
                h.update(text.encode())
        for entry in rec.get("files") or ([rec["m3"]] if rec.get("m3") else []):
            path = self.map_m3(entry)
            if path is not None:
                h.update(f"F:{entry.lower()}\n".encode())
                h.update(self.digest(path))
        return h.hexdigest()

    def digest(self, path: Path) -> bytes:
        if path not in self._digests:
            self._digests[path] = hashlib.sha256(path.read_bytes()).digest()
        return self._digests[path]


def problems(map_dir: Path, data: dict, harness_dir: Path) -> list[str]:
    """Stale or missing unit types of the JSON against this map."""
    inputs = MapInputs(map_dir)
    units = data["units"]
    out = []
    for name in unit_types(map_dir, harness_dir):
        if name not in units:
            out.append(f"hit volumes: unit type {name} is not measured; run hitvolumes.measure")
    for name, rec in sorted(units.items()):
        if "inputs" not in rec:
            out.append(f"hit volumes: {name} has no input key; run hitvolumes.measure")
        elif inputs.key(name, rec) != rec["inputs"]:
            out.append(f"hit volumes: {name} changed in the map since it was measured; run hitvolumes.measure")
    return out
