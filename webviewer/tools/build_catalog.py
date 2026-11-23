"""Build the unit catalog for the web viewer from the game data stack.

For every unit type: name, race, kind, actor, model file, icon, portrait,
and the data that changes how the unit looks (scale, animation speed, walk
speed, flying height, tint, opacity). Icons and portraits are converted to
PNG.

The stack is the stock data (hitvolumes.resolve.STACK) of a dataset, then
the dataset's map layer when it has one: a folder shaped like an SC2Map
(Base.SC2Data/GameData, enUS.SC2Data/LocalizedData, Assets). "--map none"
builds from the stock data alone. Datasets: webviewer/src/games/sc2/server/datasets.ts.
Stock catalogs must be extracted first; see webviewer/scripts/catalog.sh.

Run it through webviewer/scripts/catalog.sh. That script puts scripts/ and
scripts/hdtex/ on PYTHONPATH.
"""

from __future__ import annotations

import argparse
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from casc import Casc
from hitvolumes.resolve import STACK, Catalog, expand, vec3
from PIL import Image

RACES = {"Terr": "Terran", "Prot": "Protoss", "Zerg": "Zerg", "Neut": "Neutral"}
VERSION = 1
CHUNK = 80  # paths per stormex call


def stock(stock_dir: Path, tail: str) -> list[Path]:
    return [stock_dir / Path(*s.split("/")) / Path(*tail.split("/")) for s in STACK]


def map_arg(text: str) -> Path | None:
    """The --map argument: a folder, or "none" for a dataset with no map layer."""
    if text == "none":
        return None
    path = Path(text)
    if not path.is_dir():
        raise argparse.ArgumentTypeError(f"map layer is not a folder: {text}")
    return path


def layer(map_dir: Path | None, *parts: str) -> list[Path]:
    """The map layer's file, as the last entry of a stack; nothing without a map layer."""
    return [map_dir.joinpath(*parts)] if map_dir else []


def layer_ids(map_dir: Path | None, name: str, tag: str) -> set[str]:
    """Ids the map layer's own catalog file defines."""
    if not map_dir:
        return set()
    path = map_dir / "Base.SC2Data" / "GameData" / name
    if not path.is_file():
        return set()
    return {el.get("id") for el in ET.parse(path).getroot() if el.tag == tag and el.get("id")}


def read_strings(paths: list[Path]) -> dict[str, str]:
    """Unit/Name/<id> -> name. A later file wins."""
    names: dict[str, str] = {}
    for path in paths:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            if line.startswith("Unit/Name/") and "=" in line:
                key, value = line.split("=", 1)
                names[key[len("Unit/Name/") :]] = value.strip()
    return names


def readable(ident: str) -> str:
    """A name for a unit with no name string: split the id into words."""
    text = re.sub(r"[_]+", " ", ident)
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
    return re.sub(r"\s+", " ", text).strip() or ident


def is_template(catalog: Catalog, ident: str) -> bool:
    return any(el.get("default") == "1" for el in catalog.entries[ident])


def nested(catalog: Catalog, ident: str, outer: str, inner: str) -> str | None:
    """The value of <outer><inner value=.../></outer>, along the parent chain."""
    for cur in catalog.chain(ident):
        for el in reversed(catalog.entries[cur]):
            node = el.find(f"{outer}/{inner}")
            if node is not None and node.get("value"):
                return node.get("value")
    return None


def creation_sends(catalog: Catalog, ident: str) -> list[str]:
    """Messages the actor sends itself on creation, with no other condition. Nearest entry first."""
    out = []
    for cur in catalog.chain(ident):
        for el in reversed(catalog.entries[cur]):
            for on in el.findall("On"):
                if (on.get("Terms") or "").strip() == "ActorCreation" and not on.get("Target") and on.get("Send"):
                    out.append(on.get("Send").strip())
    return out


def first_send(sends: list[str], name: str) -> list[str] | None:
    for send in sends:
        parts = send.split()
        if parts and parts[0] == name and len(parts) > 1:
            return parts[1:]
    return None


def tint(args: list[str] | None) -> list[float] | None:
    """SetTintColor 255,128,0  or  SetTintColor {255,128,0 2.0}  ->  rgb factors."""
    if not args:
        return None
    text = " ".join(args).strip("{}")
    match = re.match(r"\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)(?:\s+([0-9.]+))?", text)
    if not match:
        return None
    hdr = float(match.group(4)) if match.group(4) else 1.0
    return [round(int(match.group(i)) / 255 * hdr, 4) for i in (1, 2, 3)]


def number(text: str | None, default: float) -> float:
    if text is None:
        return default
    try:
        return float(text.split(",")[0])
    except ValueError:
        return default


def asset_key(path: str) -> str:
    return path.replace("/", "\\").lower()


class Textures:
    """Find a texture by its in-model path: the map layer first, then the game storage."""

    def __init__(self, casc: Casc, map_dir: Path | None) -> None:
        self.casc = casc
        self.stored: dict[str, str] = {}
        for line in casc._run(["-I", r"\.(dds|tga|png)$", "-l"]).splitlines():
            path = line.strip()
            at = path.find("\\assets\\")
            if at < 0:
                continue
            key = path[at + 1 :]
            held = self.stored.get(key)
            if held is None or self.rank(path) < self.rank(held):
                self.stored[key] = path
        found = map_dir.rglob("*") if map_dir else []
        self.local = {p.relative_to(map_dir).as_posix().replace("/", "\\").lower(): p for p in found if p.suffix.lower() in (".dds", ".tga", ".png")}

    @staticmethod
    def rank(path: str) -> int:
        return 0 if "\\base.sc2assets\\" in path else 1

    def fetch(self, keys: set[str], work: Path) -> dict[str, Path]:
        """Where each texture is on disk. A file from the game storage is
        extracted into `work` once and found there afterwards (the storage
        only changes with a game patch: catalog.sh --extract empties `work`)."""
        found = {k: self.local[k] for k in keys if k in self.local}
        wanted = sorted({self.stored[k] for k in keys if k not in found and k in self.stored})
        files: dict[str, Path] = {}
        missing = []
        for path in wanted:
            held = work / Path(*path.split("\\"))
            if held.is_file():
                files[path] = held
            else:
                missing.append(path)
        for i in range(0, len(missing), CHUNK):
            files.update(self.casc.extract(missing[i : i + CHUNK], work))
        for k in keys:
            if k not in found and k in self.stored:
                found[k] = files[self.stored[k]]
        return found


def png_name(key: str) -> str:
    return re.sub(r"[^a-z0-9._-]+", "_", key.rsplit("\\", 1)[-1].rsplit(".", 1)[0]) + ".png"


def convert(source: Path, target: Path) -> None:
    """Write `source` as a PNG of at most 256 px. A PNG at least as new as its source is kept."""
    if target.is_file() and target.stat().st_mtime >= source.stat().st_mtime:
        return
    with Image.open(source) as image:
        image = image.convert("RGBA")
        if max(image.size) > 256:
            image.thumbnail((256, 256))
        image.save(target)


def build(stock_dir: Path, map_dir: Path | None, out: Path) -> dict:
    data = ("Base.SC2Data", "GameData")
    units = Catalog(stock(stock_dir, "base.sc2data/gamedata/unitdata.xml") + layer(map_dir, *data, "UnitData.xml"), ("CUnit",))
    actors = Catalog(stock(stock_dir, "base.sc2data/gamedata/actordata.xml") + layer(map_dir, *data, "ActorData.xml"), ("CActorUnit",))
    models = Catalog(stock(stock_dir, "base.sc2data/gamedata/modeldata.xml") + layer(map_dir, *data, "ModelData.xml"), ("CModel",))
    names = read_strings(stock(stock_dir, "enus.sc2data/localizeddata/gamestrings.txt") + layer(map_dir, "enUS.SC2Data", "LocalizedData", "GameStrings.txt"))
    if not units.entries:
        raise SystemExit(f"build_catalog: no unit data under {stock_dir}")
    map_units = layer_ids(map_dir, "UnitData.xml", "CUnit")

    # Unit -> actor: the actor named like the unit, else the first that names it.
    by_unit: dict[str, str] = {}
    actor_tokens: dict[str, dict[str, str]] = {}
    for ident in actors.entries:
        if is_template(actors, ident):
            continue
        tokens = actors.tokens(ident)
        tokens.setdefault("unitName", ident)
        actor_tokens[ident] = tokens
        by_unit.setdefault(tokens["unitName"], ident)
    for ident in actor_tokens:
        if ident in units.entries:
            by_unit[ident] = ident

    skipped = {"template": 0, "no actor": 0, "no model": 0}
    records = []
    for unit in sorted(units.entries):
        if is_template(units, unit):
            skipped["template"] += 1
            continue
        actor = by_unit.get(unit)
        if actor is None:
            skipped["no actor"] += 1
            continue
        tokens = actor_tokens[actor]
        model = expand(actors.field(actor, "Model") or unit, tokens)
        path = models.field(model, "Model")
        if path is None:
            skipped["no model"] += 1
            continue
        m3 = expand(path, models.tokens(model))

        def actor_text(name: str) -> str | None:
            value = actors.field(actor, name)
            return expand(value, tokens) if value else None

        sends = creation_sends(actors, actor)
        portrait_model = actor_text("PortraitModel")
        portrait = None
        if portrait_model and portrait_model in models.entries:
            image = models.field(portrait_model, "Image")
            portrait = expand(image, models.tokens(portrait_model)) if image else None
        icon = actor_text("UnitIcon") or actor_text("HeroIcon") or nested(actors, actor, "Wireframe", "Image")
        categories = dict(part.split(":", 1) for part in (units.field(unit, "EditorCategories") or "").split(",") if ":" in part)
        event_scale = first_send(sends, "SetScale")
        time_scale = first_send(sends, "AnimSetTimeScale") or first_send(sends, "AnimSetTimeScaleGlobal")
        opacity = first_send(sends, "SetOpacity")
        walk = actors.field(actor, "WalkAnimMoveSpeed")
        records.append(
            {
                "id": unit,
                "name": names.get(unit) or readable(unit),
                "named": unit in names,
                "race": RACES.get(units.field(unit, "Race") or "", "Neutral"),
                "kind": categories.get("ObjectType", "Other"),
                "family": categories.get("ObjectFamily", ""),
                "inMap": unit in map_units,
                "actor": actor,
                "model": model,
                "m3": m3,
                "iconSource": icon,
                "portraitSource": portrait,
                "actorScale": list(vec3(actors.field(actor, "Scale"))),
                "modelScaleMin": list(vec3(models.field(model, "ScaleMin"))),
                "modelScaleMax": list(vec3(models.field(model, "ScaleMax"))),
                "eventScale": list(vec3(event_scale[0])) if event_scale else [1.0, 1.0, 1.0],
                "animSpeed": number(models.field(model, "AnimSpeed"), 1.0),
                "timeScale": number(time_scale[0], 1.0) if time_scale else 1.0,
                "speed": number(units.field(unit, "Speed"), 0.0),
                "walkAnimMoveSpeed": number(walk, 0.0) if walk else None,
                "height": number(units.field(unit, "Height"), 0.0),
                "radius": number(units.field(unit, "Radius"), 0.5),
                "tint": tint(first_send(sends, "SetTintColor")),
                "opacity": number(opacity[0], 1.0) if opacity else None,
            }
        )

    # Icons and portraits.
    icon_dir = out / "icons"
    icon_dir.mkdir(parents=True, exist_ok=True)
    wanted = {asset_key(r[f]) for r in records for f in ("iconSource", "portraitSource") if r[f]}
    textures = Textures(Casc(), map_dir)
    files = textures.fetch(wanted, out / "raw")
    made: dict[str, str | None] = {}
    failed: dict[str, str] = {}
    for key in sorted(wanted):
        if key not in files:
            made[key] = None
            failed[key] = "not in the map or the game storage"
            continue
        name = png_name(key)
        try:
            convert(files[key], icon_dir / name)
        except (OSError, ValueError, NotImplementedError) as error:
            made[key] = None
            failed[key] = f"cannot convert: {error}"
            continue
        made[key] = name
    for record in records:
        record["icon"] = made.get(asset_key(record["iconSource"])) if record["iconSource"] else None
        record["portrait"] = made.get(asset_key(record["portraitSource"])) if record["portraitSource"] else None

    stats = {
        "units": len(records),
        "skipped": skipped,
        "withIcon": sum(1 for r in records if r["icon"]),
        "withPortrait": sum(1 for r in records if r["portrait"]),
        "named": sum(1 for r in records if r["named"]),
        "texturesWanted": len(wanted),
        "texturesFailed": len(failed),
    }
    return {"version": VERSION, "stats": stats, "failedTextures": failed, "units": records}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stock", type=Path, required=True, help="folder with the extracted stock catalogs")
    parser.add_argument("--map", type=map_arg, required=True, help='the map layer: a folder shaped like an SC2Map, or "none"')
    parser.add_argument("--out", type=Path, required=True, help="folder for units.json and icons/")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    result = build(args.stock, args.map, args.out)
    target = args.out / "units.json"
    target.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    print(f"{target} {json.dumps(result['stats'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
