from __future__ import annotations

import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

from project_root import project_root

# Models whose Occlusion resolves to Show, or to nothing (the engine
# default; Kerrigan sets none and shows a silhouette), in the map's
# dependencies: an occluded unit with such a model draws a silhouette.
# Hide and None stay. Written by
# `doodad_occlusion.py --refresh` from the game storage.
SILHOUETTE_JSON = Path("scripts") / "data" / "silhouette_models.json"
DEPENDENCY = "campaigns/voidstory.sc2campaign"


def doodad_types(map_dir: Path) -> list[str]:
    found: set[str] = set()
    objects = map_dir / "Objects"
    if objects.is_file():
        text = objects.read_text(encoding="utf-8", errors="replace")
        found.update(re.findall(r'<ObjectDoodad\b[^>]*\bType="([^"]+)"', text))
    actors = map_dir / "Base.SC2Data" / "GameData" / "ActorData.xml"
    if actors.is_file():
        text = actors.read_text(encoding="utf-8", errors="replace")
        found.update(re.findall(r'<CActorDoodad\b[^>]*\bid="([^"]+)"', text))
    return sorted(found)


def _set_none(map_dir: Path, ids: list[str]) -> None:
    model_path = map_dir / "Base.SC2Data" / "GameData" / "ModelData.xml"
    if not model_path.is_file():
        raise FileNotFoundError(model_path)
    tree = ET.parse(model_path)
    root = tree.getroot()
    by_id = {e.get("id"): e for e in root.findall("CModel") if e.get("id")}

    for model_id in ids:
        entry = by_id.get(model_id)
        if entry is None:
            entry = ET.SubElement(root, "CModel", {"id": model_id})
            by_id[model_id] = entry
        for old in entry.findall("Occlusion"):
            entry.remove(old)
        ET.SubElement(entry, "Occlusion", {"value": "None"})

    ET.indent(tree, space="    ")
    tree.write(model_path, encoding="utf-8", xml_declaration=True)


def disable_doodad_occlusion(map_dir: Path) -> list[str]:
    map_dir = Path(map_dir)
    ids = doodad_types(map_dir)
    _set_none(map_dir, ids)
    return ids


def resolve_show(entries: list[tuple[str, str | None, str | None]]) -> list[str]:
    """Ids whose Occlusion, through the parent chain, is Show or unset.

    entries: (id, parent, occlusion) in load order; a later entry of the
    same id overrides the fields it sets.
    """
    parent: dict[str, str] = {}
    own: dict[str, str] = {}
    for model_id, link, value in entries:
        if link is not None:
            parent[model_id] = link
        if value is not None:
            own[model_id] = value
    ids = set(parent) | set(own)

    def value_of(model_id: str) -> str | None:
        seen: set[str] = set()
        while model_id not in seen:
            seen.add(model_id)
            if model_id in own:
                return own[model_id]
            if model_id not in parent:
                return None
            model_id = parent[model_id]
        return None

    return sorted(i for i in ids if value_of(i) in ("Show", None))


def catalog_entries(paths: list[Path]) -> list[tuple[str, str | None, str | None]]:
    out = []
    for path in paths:
        for entry in ET.parse(path).getroot().iter("CModel"):
            model_id = entry.get("id")
            if not model_id:
                continue
            occlusion = entry.find("Occlusion")
            out.append((model_id, entry.get("parent"), None if occlusion is None else occlusion.get("value")))
    return out


def refresh(work: Path) -> list[str]:
    """Read every dependency ModelData.xml from the game storage; write the JSON."""
    from hdtex.casc import Casc
    from hdtex.sources import DEPENDENCY_ARCHIVES

    casc = Casc()
    names = [a + "\\base.sc2data\\gamedata\\modeldata.xml" for a in DEPENDENCY_ARCHIVES[DEPENDENCY]]
    present = set(casc.find(["modeldata.xml"]))
    stored = [n for n in names if n in present]
    files = casc.extract(stored, work)
    ids = resolve_show(catalog_entries([files[n] for n in stored]))
    (project_root() / SILHOUETTE_JSON).write_text(json.dumps({"archives": stored, "models": ids}, indent=1) + "\n", encoding="utf-8")
    return ids


def disable_unit_silhouettes(map_dir: Path) -> list[str]:
    """No unit silhouette behind buildings (operator 2026-11-18): Occlusion None
    on every model that resolves to Show or unset, in the dependencies and the map."""
    map_dir = Path(map_dir)
    stock = json.loads((project_root() / SILHOUETTE_JSON).read_text(encoding="utf-8"))["models"]
    model_path = map_dir / "Base.SC2Data" / "GameData" / "ModelData.xml"
    shown = set(stock)
    own = catalog_entries([model_path])
    stock_entries = [(i, None, "Show") for i in stock]
    ids = sorted(set(resolve_show(stock_entries + own)) | shown)
    _set_none(map_dir, ids)
    return ids


def main(argv: list[str]) -> int:
    root = project_root()
    if len(argv) > 1 and argv[1] == "--refresh":
        ids = refresh(Path(argv[2]) if len(argv) > 2 else Path("/tmp/opencode/modeldata"))
        print(f"{len(ids)} silhouette models written to {SILHOUETTE_JSON}")
        return 0
    map_dir = Path(argv[1]) if len(argv) > 1 else root / "out" / "SCOBA256.SC2Map"
    ids = disable_doodad_occlusion(map_dir)
    print(f"occlusion disabled for {len(ids)} doodad types: {', '.join(ids)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
