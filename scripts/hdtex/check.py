"""Upscaled texture checks for scripts/validate-map.py.

The checks read the built map only. A map without upscaled textures passes:
the cache is optional. A map with some of them must be complete.
"""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from . import dds
from .models import HD_MODEL_DIR
from .sources import HD_DIR, HD_PREFIX, TERRAIN_FIELDS, terrain_texture_ids

MAX_TRAILER = 16


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def _is_power_of_two(value: int) -> bool:
    return value > 0 and value & (value - 1) == 0


def check_texture_file(path: Path) -> None:
    try:
        texture = dds.parse(path.read_bytes())
    except dds.DdsError as error:
        fail(f"upscaled texture {path.name}: {error}")
    if not (_is_power_of_two(texture.width) and _is_power_of_two(texture.height)):
        fail(f"upscaled texture {path.name}: size {texture.width}x{texture.height} is not a power of two")
    if len(texture.levels) != dds.full_mip_count(texture.width, texture.height):
        fail(f"upscaled texture {path.name}: mip chain has {len(texture.levels)} levels, not a full chain")
    if len(texture.trailer) > MAX_TRAILER:
        fail(f"upscaled texture {path.name}: {len(texture.trailer)} stray bytes after the last mip")


def _folder(map_dir: Path, game_path: str) -> Path:
    return map_dir.joinpath(*game_path.split("\\"))


def hd_model_files(map_dir: Path) -> dict[str, Path]:
    """Lower-case file name to path, for the patched models in the map."""
    folder = _folder(map_dir, HD_MODEL_DIR)
    return {path.name.lower(): path for path in folder.glob("*")} if folder.is_dir() else {}


def hd_references(map_dir: Path) -> set[str]:
    """Lower-case file names below HD_DIR that the map's catalogs or its patched models point at."""
    pattern = re.compile(r'value="' + re.escape(HD_DIR) + r'\\([^"\\]+)"', re.I)
    names: set[str] = set()
    for catalog in sorted((map_dir / "Base.SC2Data" / "GameData").glob("*.xml")):
        names.update(name.lower() for name in pattern.findall(catalog.read_text(encoding="utf-8", errors="replace")))
    # A model keeps its texture paths as plain text.
    in_model = re.compile(re.escape(HD_DIR.encode("ascii")) + rb"\\([^\\\x00]+\.dds)", re.I)
    for path in hd_model_files(map_dir).values():
        names.update(name.decode("ascii").lower() for name in in_model.findall(path.read_bytes()))
    return names


def check_model_overrides(map_dir: Path) -> None:
    """Every CModel that names a patched model has its files, and every patched file is named."""
    files = hd_model_files(map_dir)
    catalog = map_dir / "Base.SC2Data" / "GameData" / "ModelData.xml"
    prefix = HD_MODEL_DIR.lower() + "\\"
    named: set[str] = set()
    if catalog.is_file():
        for node in ET.parse(catalog).getroot().iter("CModel"):
            model = node.find("Model")
            value = (model.get("value") or "") if model is not None else ""
            if not value.lower().startswith(prefix):
                continue
            stem, _dot, extension = value.lower()[len(prefix) :].rpartition(".")
            own = {name for name in files if name == f"{stem}.{extension}" or re.fullmatch(re.escape(stem) + r"_\d\d\." + extension, name)}
            if not own:
                fail(f"model {node.get('id')} points at {value}, but the map has no such model file")
            named.update(own)
    for name in sorted(set(files) - named):
        fail(f"{HD_MODEL_DIR}\\{name} is in the map, but no model entry points at it")
    for path in files.values():
        if path.read_bytes()[:4] != b"43DM":
            fail(f"{HD_MODEL_DIR}\\{path.name} is not a model file")


def check_terrain_overrides(map_dir: Path) -> None:
    """A partly upscaled terrain mixes sharp and soft ground. All or nothing."""
    catalog = map_dir / "Base.SC2Data" / "GameData" / "TerrainTexData.xml"
    if not catalog.is_file():
        return
    prefix = HD_DIR.lower() + "\\"
    upscaled: set[tuple[str, str]] = set()
    for node in ET.parse(catalog).getroot().iter("CTerrainTex"):
        for child in node:
            if (child.get("value") or "").lower().startswith(prefix):
                upscaled.add((node.get("id", ""), child.tag))
    if not upscaled:
        return
    for entry in terrain_texture_ids(map_dir):
        for field, _role in TERRAIN_FIELDS:
            if (entry, field) not in upscaled:
                fail(f"terrain texture {entry} has no upscaled {field}, but other terrain textures do")


def check_hd_textures(map_dir: Path) -> None:
    folder = map_dir.joinpath(*HD_DIR.split("\\"))
    files = {path.name.lower(): path for path in folder.glob("*")} if folder.is_dir() else {}
    referenced = hd_references(map_dir)
    for name in sorted(referenced - set(files)):
        fail(f"a catalog points at {HD_DIR}\\{name}, but the file is not in the map")
    for name in sorted(set(files) - referenced):
        fail(f"{HD_DIR}\\{name} is in the map, but no catalog points at it")
    for name in sorted(files):
        if not name.startswith(HD_PREFIX):
            fail(f"{HD_DIR}\\{name} must start with {HD_PREFIX}: the game sizes a texture by its file name")
        check_texture_file(files[name])
    check_terrain_overrides(map_dir)
    check_model_overrides(map_dir)
