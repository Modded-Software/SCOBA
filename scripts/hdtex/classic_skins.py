"""Show the classic ("Remastered") collection skins on the map's Terran and Zerg units.

The game swaps a skin in by model entry: a skin lists pairs of CModel ids,
From and To. A map cannot count on a player owning a skin, so this tool
writes the swap into the map's own ModelData.xml instead: every From entry
gets the fields of its To entry that differ, the model file first. The
From entry keeps its id, so the map's own changes to it stay (scale,
animation speed), and the tooling that follows unit to actor to model
(hit volumes, footprints, HD textures) finds the classic model.

The pairs come from the game's skin data. The result is written into
src/SCOBA.SC2Map and committed, so the build never reads the game install.

usage: cd scripts && uv run python -m hdtex.classic_skins [--list]
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import NamedTuple

from project_root import project_root

sys.path.insert(0, str(project_root() / "scripts"))

from hdtex.casc import Casc
from hdtex.catalog import TOKEN, Catalog, CatalogError
from hdtex.sources import map_archives

MAP = project_root() / "src" / "SCOBA.SC2Map"
MODEL_DATA = Path("Base.SC2Data") / "GameData" / "ModelData.xml"
GAMEDATA = "\\base.sc2data\\gamedata\\"

# Operator 2026-11-20: every Terran and Zerg unit that has a classic skin.
# CommandCenterRemastered: the hall keeps the leg footprint measured on the
# stock model (operator 2026-11-20: "pretty much the same 4 legs";
# footprints.config.HALL_FOOTPRINTS_ON).
SKINS = (
    "CommandCenterRemastered",
    "MarineRemastered",
    "SCVRemastered",
    "BattlecruiserRemastered",
    "HydraliskRemastered",
    "UltraliskRemastered",
    "DroneRemastered",
    "HatcheryRemastered",
)

# Fields that say how the collection shows a model, not how the game draws it.
IGNORED_FIELDS = frozenset({"EditorCategories"})
# A list field the From entry has and the To entry lacks is emptied. Only
# this one is known to matter: animations made for the other rig.
REMOVABLE = "RequiredAnims"
LIGHT_FIELD = "Lighting"
BEGIN = "    <!-- classic skins: written by scripts/classic_skins.py. Do not edit. -->"
END = "    <!-- classic skins: end -->"
LINE_MARK = " <!-- classic skins -->"


class SkinError(RuntimeError):
    """The skin data does not resolve to model files."""


class Swap(NamedTuple):
    """One model entry of the map and what it must show."""

    entry: str  # CModel id that keeps its name
    shows: str  # CModel id of the skin
    fields: tuple[tuple[str, str], ...]  # field values the entry takes over
    removed: tuple[str, ...]  # list fields the entry empties


def class_text(texts: list[str], cls: str) -> list[str]:
    """Each catalog text cut down to the entries of one class. Ids repeat across classes."""
    found = []
    for text in texts:
        parser = ET.XMLParser(target=ET.TreeBuilder(insert_pis=True))
        try:
            root = ET.fromstring(text, parser=parser)
        except ET.ParseError as error:
            print(f"classic skins: a catalog text is not XML and is left out: {error}", file=sys.stderr)
            continue
        kept = ET.Element("Catalog")
        kept.extend(node for node in root if node.tag == cls)
        if len(kept):
            found.append(ET.tostring(kept, encoding="unicode"))
    return found


def skin_pairs(texts: list[str], skins: Catalog, skin: str) -> dict[str, str]:
    """From -> To of every model replacement a skin makes. The skin's own lines win over its parents'."""
    lines: dict[str, list[tuple[str, str]]] = {}
    for text in texts:
        for node in ET.fromstring(text):
            if node.get("id"):
                lines.setdefault(node.get("id", ""), []).extend(
                    (item.get("From", ""), item.get("To", ""))
                    for item in node.findall("ReplacementArray")
                    if item.get("Catalog") == "Model"
                )
    chain: list[str] = []
    current: str | None = skin
    while current is not None:
        if current not in skins.entries:
            raise SkinError(f"skin {current} is not in the game data")
        chain.append(current)
        current = skins.entries[current].parent

    def fill(value: str) -> str:
        return TOKEN.sub(lambda match: skins.token(skin, match.group(1)), value)

    pairs: dict[str, str] = {}
    for entry in reversed(chain):
        for source, target in lines.get(entry, []):
            pairs[fill(source)] = fill(target)
    return pairs


def resolved(models: Catalog, entry: str) -> dict[str, str]:
    """Every plain field of a model entry, parents and tokens resolved."""
    chain = models.chain(entry)
    found = {}
    for name in sorted({name for item in chain for name in item.fields}):
        try:
            found[name] = models.field(entry, name) or ""
        except CatalogError:
            # A token nobody gives a value: the game data leaves the field open. Kept as written.
            found[name] = next(item.fields[name] for item in chain if name in item.fields)
    return found


def swap_for(models: Catalog, entry: str, shows: str, lights: frozenset[str]) -> Swap:
    old, new = resolved(models, entry), resolved(models, shows)
    if not new.get("Model"):
        raise SkinError(f"{shows} names no model file")
    changed = tuple(
        (name, value)
        for name, value in new.items()
        if old.get(name) != value
        and name not in IGNORED_FIELDS
        # The light of a model is named after the model by default. Most skins have none of their own.
        and (name != LIGHT_FIELD or value in lights)
    )
    if open_fields := [name for name, value in changed if TOKEN.search(value)]:
        raise SkinError(f"{shows}: {', '.join(open_fields)} holds a token without a value")
    gone = sorted(name for name in old if name not in new and name not in IGNORED_FIELDS)
    if unknown := [name for name in gone if name != REMOVABLE]:
        raise SkinError(f"{entry} has {', '.join(unknown)} and {shows} does not; this tool cannot unset a plain field")
    return Swap(entry, shows, changed, tuple(gone))


def swaps(
    skin_texts: list[str], model_texts: list[str], names: tuple[str, ...], lights: frozenset[str] = frozenset()
) -> tuple[list[Swap], list[str]]:
    """The swaps of the named skins, and the pairs left out because one side is not in the game data.

    `lights` are the CLight ids of the game. A pair whose entries differ in nothing is no swap.
    """
    skins, models = Catalog(skin_texts), Catalog(model_texts)
    found: dict[str, Swap] = {}
    left = []
    try:
        for skin in names:
            for entry, shows in sorted(skin_pairs(skin_texts, skins, skin).items()):
                if entry not in models.entries or shows not in models.entries:
                    left.append(f"{skin}: {entry} -> {shows}")
                    continue
                swap = swap_for(models, entry, shows, lights)
                if not swap.fields and not swap.removed:
                    continue
                if found.setdefault(entry, swap) != swap:
                    raise SkinError(f"two skins swap {entry}: {found[entry].shows} and {shows}")
    except CatalogError as error:
        raise SkinError(str(error)) from error
    return [found[entry] for entry in sorted(found)], left


def swap_lines(swap: Swap, mark: str = "") -> list[str]:
    lines = [f"        <!-- shows {swap.shows} -->{mark}"]
    lines.extend(f'        <{name} value="{value}"/>{mark}' for name, value in swap.fields)
    lines.extend(f'        <{name} index="0" removed="1"/>{mark}' for name in swap.removed)
    return lines


def stripped(text: str) -> str:
    """The catalog text without what this tool wrote: the marked block and the marked lines."""
    text = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END) + r"\r?\n", "", text, flags=re.DOTALL)
    return re.sub(r"[^\n]*" + re.escape(LINE_MARK) + r"\r?\n", "", text)


def merged(text: str, found: list[Swap]) -> str:
    """The catalog text with the swaps written in.

    An entry the map sets itself takes the lines into its own element: one
    id must not stand twice in a file. The other entries go into one marked
    block before the end. What an earlier run wrote is taken out first.
    """
    text = stripped(text)
    block = [BEGIN]
    for swap in found:
        opening = re.search(r'[ \t]*<CModel id="' + re.escape(swap.entry) + r'"[^>]*>\r?\n', text)
        if opening is None:
            block += [f'    <CModel id="{swap.entry}">', *swap_lines(swap), "    </CModel>"]
            continue
        if opening.group(0).rstrip().endswith("/>"):
            raise SkinError(f"{swap.entry}: the map's entry is an empty element; give it a body")
        lines = "".join(line + "\n" for line in swap_lines(swap, LINE_MARK))
        text = text[: opening.end()] + lines + text[opening.end() :]
    block.append(END)
    close = text.rfind("</Catalog>")
    if close < 0:
        raise SkinError("ModelData.xml has no </Catalog>")
    return text[:close] + "\n".join(block) + "\n" + text[close:]


def clashes(text: str, found: list[Swap]) -> list[str]:
    """Fields a swap sets that the map's own entry of the same id sets too."""
    own = stripped(text)
    problems = []
    for swap in found:
        for body in re.findall(r'<CModel id="' + re.escape(swap.entry) + r'"[^>]*>(.*?)</CModel>', own, re.DOTALL):
            for name in [name for name, _value in swap.fields] + list(swap.removed):
                if re.search(r"<" + re.escape(name) + r"\b", body):
                    problems.append(f"{swap.entry}: the map sets {name} itself")
    return problems


def game_texts(casc: Casc, map_dir: Path, work: Path) -> list[str]:
    """Every game data file of the archives the map loads, in load order."""
    archives = map_archives(map_dir)
    stored = [path for path in casc.find([".xml"]) if GAMEDATA in path]
    wanted = [path for archive in archives for path in sorted(stored) if path.startswith(archive + GAMEDATA)]
    extracted = casc.extract(wanted, work)
    return [extracted[path].read_text(encoding="utf-8-sig", errors="replace") for path in wanted]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="print the swaps and write nothing")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="classicskins-") as scratch:
        texts = game_texts(Casc(), MAP, Path(scratch))
    try:
        lights = frozenset(re.findall(r'<CLight id="([^"]+)"', "".join(class_text(texts, "CLight"))))
        found, left = swaps(class_text(texts, "CSkin"), class_text(texts, "CModel"), SKINS, lights)
        catalog = MAP / MODEL_DATA
        text = catalog.read_text(encoding="utf-8-sig")
        if problems := clashes(text, found):
            raise SkinError("; ".join(problems))
    except SkinError as error:
        print(f"classic skins: error: {error}", file=sys.stderr)
        return 1
    for swap in found:
        fields = ", ".join(f"{name}={value}" for name, value in swap.fields)
        print(f"{swap.entry} -> {swap.shows}: {fields}" + (f"; removes {', '.join(swap.removed)}" if swap.removed else ""))
    for line in left:
        print(f"left out, not in the game data: {line}")
    if not args.list:
        catalog.write_text(merged(text, found), encoding="utf-8")
        print(f"{catalog}: {len(found)} model entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
