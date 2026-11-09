from __future__ import annotations

from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

from project_root import project_root


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


def disable_doodad_occlusion(map_dir: Path) -> list[str]:
    map_dir = Path(map_dir)
    model_path = map_dir / "Base.SC2Data" / "GameData" / "ModelData.xml"
    if not model_path.is_file():
        raise FileNotFoundError(model_path)

    ids = doodad_types(map_dir)
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
    return ids


def main(argv: list[str]) -> int:
    root = project_root()
    map_dir = Path(argv[1]) if len(argv) > 1 else root / "out" / "SCOBA256.SC2Map"
    ids = disable_doodad_occlusion(map_dir)
    print(f"occlusion disabled for {len(ids)} doodad types: {', '.join(ids)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
