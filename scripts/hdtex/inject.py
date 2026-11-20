"""Put the upscaled textures of one cached variant into a built map folder.

Each texture is copied to its map path. Its catalog overrides make the
game load the copy in place of the built-in file.

A model texture has no catalog field. The cache holds a copy of each model
that names the upscaled textures. The copy goes into the map, and a CModel
override names it.

SC2_HD_TEXTURES picks the variant, or turns the step off. When it is not
set, the default variant is used and its cache is optional: without it the
map keeps the built-in textures and the build says so. A variant asked for
by name must have a cache.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

from . import models, variants
from .pipeline import MANIFEST, MANIFEST_FORMAT, file_sha256, variant_root
from .sources import terrain_texture_ids


class InjectError(RuntimeError):
    """The cache does not fit the map. Rebuild the cache or turn the step off."""


def build_hint(variant: str, source: str = "") -> str:
    named = f" --source {source}" if source else ""
    return f"run: uv run python scripts/hd_textures.py --variant {variant}{named} build"


def load_manifests(cache: Path) -> list[tuple[Path, dict]]:
    """The manifests of one variant's cache folder, one per source."""
    manifests = []
    for path in sorted(cache.glob(f"*/{MANIFEST}")):
        manifest = json.loads(path.read_text())
        if manifest.get("format") != MANIFEST_FORMAT:
            raise InjectError(f"{path} has manifest format {manifest.get('format')}; {build_hint(cache.name)}")
        if manifest.get("variant") != cache.name:
            raise InjectError(f"{path} holds variant {manifest.get('variant')}, not {cache.name}; {build_hint(cache.name)}")
        manifests.append((path.parent, manifest))
    return manifests


def missing_terrain_entries(map_dir: Path, manifest: dict) -> list[str]:
    """Terrain textures the map paints with that the cache does not cover."""
    covered = {
        override["entry"]
        for texture in manifest["textures"]
        for override in texture["overrides"]
        if override["element"] == "CTerrainTex"
    }
    return [entry for entry in terrain_texture_ids(map_dir) if entry not in covered]


def missing_model_actors(map_dir: Path, manifest: dict) -> list[str]:
    """Placed doodads and named units whose model the cache did not look at."""
    covered = {actor for entry in manifest.get("models", []) for actor in entry["actors"]}
    entries = {entry["entry"] for entry in manifest.get("models", [])}
    # The map build makes doodad actors of its own, with new names on every
    # change. Such an actor names its model in the map's catalog.
    own: dict[str, str] = {}
    catalog = map_dir / "Base.SC2Data" / "GameData" / "ActorData.xml"
    if catalog.is_file():
        for node in ET.parse(catalog).getroot():
            model = node.find("Model")
            if node.get("id") and model is not None and model.get("value"):
                own[node.get("id", "")] = model.get("value", "")
    wanted = [*models.doodad_types(map_dir), *models.MODEL_UNITS]
    return [actor for actor in wanted if actor not in covered and own.get(actor) not in entries]


def stale_models(map_dir: Path, manifest: dict) -> list[str]:
    """Cached model copies made from another file than the map now shows.

    The map build makes some models itself, at the game's path. A copy must
    come from that file as it is now.
    """
    stale = []
    for entry in manifest.get("models", []):
        for model in entry["files"]:
            own = models.map_model(map_dir, model["asset"])
            from_map = model["casc_path"].startswith(models.MAP_MARK)
            if own.is_file() != from_map or (from_map and file_sha256(own) != model["source_sha256"]):
                stale.append(model["asset"])
    return stale


def _map_file(map_dir: Path, map_path: str) -> Path:
    return map_dir.joinpath(*map_path.replace("/", "\\").split("\\"))


def _copy_texture(folder: Path, texture: dict, map_dir: Path, hint: str) -> None:
    source = folder / texture["file"]
    if not source.is_file():
        raise InjectError(f"{source} is missing; {hint}")
    if hashlib.sha256(source.read_bytes()).hexdigest() != texture["sha256"]:
        raise InjectError(f"{source} does not match its manifest; {hint}")
    target = _map_file(map_dir, texture["map_path"])
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def apply_overrides(catalog: Path, element: str, values: dict[tuple[str, str], str]) -> None:
    """Set `field` of entry `id` in a catalog file, creating what is missing."""
    if catalog.is_file():
        root = ET.parse(catalog).getroot()
    else:
        root = ET.Element("Catalog")
    for (entry, field), value in sorted(values.items()):
        node = next((n for n in root.iter(element) if n.get("id") == entry), None)
        if node is None:
            node = ET.SubElement(root, element, {"id": entry})
        child = node.find(field)
        if child is None:
            child = ET.SubElement(node, field)
        child.set("value", value)
    ET.indent(root, space="    ")
    catalog.parent.mkdir(parents=True, exist_ok=True)
    body = ET.tostring(root, encoding="unicode")
    catalog.write_text(f'<?xml version="1.0" encoding="us-ascii"?>\n{body}\n', encoding="ascii")


def variant_in_map(map_dir: Path) -> str | None:
    """The key of the cached variant whose files the map holds, or None."""
    for key in variants.VARIANTS:
        manifests = [manifest for _folder, manifest in load_manifests(variant_root(key))]
        textures = [texture for manifest in manifests for texture in manifest["textures"]]
        textures += [model for manifest in manifests for entry in manifest.get("models", []) for model in entry["files"]]
        files = [(_map_file(map_dir, texture["map_path"]), texture["sha256"]) for texture in textures]
        if files and all(path.is_file() and file_sha256(path) == sha256 for path, sha256 in files):
            return key
    return None


def apply_hd_textures(map_dir: Path) -> int:
    """Inject every cached source of the chosen variant into `map_dir`. Returns the number of textures."""
    off = f"{variants.ENV}={variants.OFF}"
    try:
        choice = variants.chosen()
    except variants.VariantError as error:
        raise InjectError(str(error)) from error
    if choice.key is None:
        print(f"hd textures: off by {off}, the map keeps the built-in textures")
        return 0
    cache, hint = variant_root(choice.key), build_hint(choice.key)
    manifests = load_manifests(cache)
    if not manifests:
        if choice.asked:
            raise InjectError(f"{variants.ENV}={choice.key}, but there is no cache at {cache}; {hint}")
        print(f"hd textures: no cache at {cache}, the map keeps the built-in textures; {hint}")
        return 0
    count = 0
    model_count = 0
    overrides: dict[tuple[str, str], dict[tuple[str, str], str]] = {}
    for folder, manifest in manifests:
        if manifest["source"] == "terrain":
            missing = missing_terrain_entries(map_dir, manifest)
            if missing:
                raise InjectError(f"the cache has no upscaled texture for {', '.join(missing)}; {hint}, or set {off}")
        if manifest["source"] == models.SOURCE:
            missing = missing_model_actors(map_dir, manifest)
            if missing:
                raise InjectError(f"the cache has not seen the models of {', '.join(missing)}; {build_hint(choice.key, models.SOURCE)}, or set {off}")
            if stale := stale_models(map_dir, manifest):
                raise InjectError(
                    f"the map's own model changed since the cache was built: {', '.join(stale)}; "
                    f"{build_hint(choice.key, models.SOURCE)}, or set {off}"
                )
            for entry in manifest["models"]:
                for model in entry["files"]:
                    _copy_texture(folder, model, map_dir, hint)
                    model_count += 1
                if entry["files"]:
                    overrides.setdefault(("ModelData.xml", "CModel"), {})[entry["entry"], "Model"] = entry["map_base"]
        for texture in manifest["textures"]:
            _copy_texture(folder, texture, map_dir, hint)
            count += 1
            for override in texture["overrides"]:
                key = (override["catalog_file"], override["element"])
                overrides.setdefault(key, {})[override["entry"], override["field"]] = texture["map_path"]
    for (catalog_file, element), values in sorted(overrides.items()):
        apply_overrides(map_dir / "Base.SC2Data" / "GameData" / catalog_file, element, values)
    print(f"hd textures: injected {count} textures, variant {variants.VARIANTS[choice.key].title}, from {cache}")
    if model_count:
        print(f"hd textures: injected {model_count} model files that name them")
    return count
