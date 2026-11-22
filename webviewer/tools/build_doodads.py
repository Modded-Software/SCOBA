"""Build the doodad catalog for the web viewer from the game data stack.

A doodad is a CActorDoodad: a prop the map editor places (trees, rocks,
wreckage, cliff dressing, lights, weather). For every doodad: name, type,
the terrain sets that list it, model file and variation count, the editor
model of a doodad with nothing to show in game, and the data that changes
how it looks (scale, random scale range, animation speed, tint, rotation
rule, footprint).

Same data stack as build_catalog.py. Run through webviewer/scripts/catalog.sh.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from build_catalog import creation_sends, first_send, is_template, layer, layer_ids, map_arg, number, readable, stock, tint
from hitvolumes.resolve import Catalog, expand, vec3

VERSION = 1
# The CModel of a doodad that draws nothing in game (sound and weather
# emitters, blockers). Its EditorModel is what the map editor shows.
INVISIBLE = "Invisible"
NAME_KEY = "Actor/Name/"


def read_names(paths: list[Path]) -> dict[str, str]:
    """Actor/Name/<id> -> name, from the object strings. A later file wins."""
    names: dict[str, str] = {}
    for path in paths:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            if line.startswith(NAME_KEY) and "=" in line:
                key, value = line.split("=", 1)
                names[key[len(NAME_KEY) :]] = value.strip()
    return names


def values(catalog: Catalog, ident: str, name: str) -> list[str]:
    """Every value of a repeated field. The nearest entry along the parent
    chain that has the field decides; entries of one id add up."""
    for cur in catalog.chain(ident):
        found = [f.get("value") for el in catalog.entries[cur] for f in el.findall(name) if f.get("value")]
        if found:
            return list(dict.fromkeys(found))
    return []


def flag(catalog: Catalog, ident: str, name: str, index: str) -> bool | None:
    """<name index=... value=0|1/> along the parent chain; None when never set."""
    for cur in catalog.chain(ident):
        for el in reversed(catalog.entries[cur]):
            for f in el.findall(name):
                if f.get("index") == index and f.get("value") is not None:
                    return f.get("value") != "0"
    return None


def scale_range(text: str | None) -> list[float]:
    """RandomScaleRange "low,high"; missing is no random scale."""
    if not text:
        return [1.0, 1.0]
    parts = [float(p) for p in text.split(",")]
    if len(parts) != 2:
        raise ValueError(f"RandomScaleRange is not two values: {text!r}")
    return [min(parts), max(parts)]


def model_file(models: Catalog, model: str | None) -> str | None:
    if not model or model not in models.entries:
        return None
    path = models.field(model, "Model")
    return expand(path, models.tokens(model)) if path else None


def build(stock_dir: Path, map_dir: Path | None) -> dict:
    data = ("Base.SC2Data", "GameData")
    actors = Catalog(stock(stock_dir, "base.sc2data/gamedata/actordata.xml") + layer(map_dir, *data, "ActorData.xml"), ("CActorDoodad",))
    models = Catalog(stock(stock_dir, "base.sc2data/gamedata/modeldata.xml") + layer(map_dir, *data, "ModelData.xml"), ("CModel",))
    names = read_names(stock(stock_dir, "enus.sc2data/localizeddata/objectstrings.txt") + layer(map_dir, "enUS.SC2Data", "LocalizedData", "ObjectStrings.txt"))
    if not actors.entries:
        raise SystemExit(f"build_doodads: no doodad data under {stock_dir}")
    in_map = layer_ids(map_dir, "ActorData.xml", "CActorDoodad")

    skipped = {"template": 0, "no model": 0}
    records = []
    for ident in sorted(actors.entries):
        if is_template(actors, ident):
            skipped["template"] += 1
            continue
        tokens = actors.tokens(ident)
        model = expand(actors.field(ident, "Model") or ident, tokens)
        m3 = model_file(models, model)
        editor_model = actors.field(ident, "EditorModel")
        editor_model = expand(editor_model, tokens) if editor_model else None
        editor_m3 = model_file(models, editor_model)
        if m3 is None and editor_m3 is None:
            skipped["no model"] += 1
            continue
        categories = dict(part.split(":", 1) for part in (actors.field(ident, "EditorCategories") or "").split(",") if ":" in part)
        sends = creation_sends(actors, ident)
        event_scale = first_send(sends, "SetScale")
        time_scale = first_send(sends, "AnimSetTimeScale") or first_send(sends, "AnimSetTimeScaleGlobal")
        opacity = first_send(sends, "SetOpacity")
        has_model = m3 is not None
        records.append(
            {
                "id": ident,
                "name": names.get(ident) or readable(ident),
                "named": ident in names,
                "type": categories.get("DoodadType", "Props"),
                "tilesets": values(actors, ident, "TexSets"),
                "inMap": ident in in_map,
                "model": model,
                "m3": m3,
                "variationCount": int(number(models.field(model, "VariationCount"), 1.0)) if has_model else 1,
                "invisible": model == INVISIBLE or not has_model,
                "editorModel": editor_model,
                "editorM3": editor_m3,
                "actorScale": list(vec3(actors.field(ident, "Scale"))),
                "scaleRange": scale_range(actors.field(ident, "RandomScaleRange")),
                "modelScaleMin": list(vec3(models.field(model, "ScaleMin"))) if has_model else [1.0, 1.0, 1.0],
                "modelScaleMax": list(vec3(models.field(model, "ScaleMax"))) if has_model else [1.0, 1.0, 1.0],
                "eventScale": list(vec3(event_scale[0])) if event_scale else [1.0, 1.0, 1.0],
                "animSpeed": number(models.field(model, "AnimSpeed"), 1.0) if has_model else 1.0,
                "timeScale": number(time_scale[0], 1.0) if time_scale else 1.0,
                "radius": number(actors.field(ident, "Radius"), 0.5),
                "tint": tint(first_send(sends, "SetTintColor")),
                "opacity": number(opacity[0], 1.0) if opacity else None,
                "footprint": actors.field(ident, "Footprint"),
                "facing": number(actors.field(ident, "Facing"), 0.0),
                # The editor turns a new doodad to a random angle unless told not to.
                "autoRotate": not flag(actors, ident, "EditorFlags", "NoAutoRotate") and flag(actors, ident, "EditorFlags", "CanRotate") is not False,
                "footprintOnly": bool(flag(actors, ident, "DoodadFlags", "FootprintOnly")),
            }
        )

    types: dict[str, int] = {}
    for record in records:
        types[record["type"]] = types.get(record["type"], 0) + 1
    stats = {
        "doodads": len(records),
        "skipped": skipped,
        "named": sum(1 for r in records if r["named"]),
        "withVariations": sum(1 for r in records if r["variationCount"] > 1),
        "invisible": sum(1 for r in records if r["invisible"]),
        "inMap": sum(1 for r in records if r["inMap"]),
        "types": dict(sorted(types.items(), key=lambda kv: -kv[1])),
    }
    return {"version": VERSION, "stats": stats, "doodads": records}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stock", type=Path, required=True, help="folder with the extracted stock catalogs")
    parser.add_argument("--map", type=map_arg, required=True, help='the map layer: a folder shaped like an SC2Map, or "none"')
    parser.add_argument("--out", type=Path, required=True, help="folder for doodads.json")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    result = build(args.stock, args.map)
    target = args.out / "doodads.json"
    target.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    print(f"{target} {json.dumps(result['stats'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
