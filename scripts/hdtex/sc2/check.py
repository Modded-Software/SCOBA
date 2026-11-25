"""Upscaled texture checks for scripts/validate-map.py.

The checks read the built map only. A map without upscaled textures passes.
A map with some of them must be complete: every file named, every named
file there, and every terrain texture the map paints with upscaled.
"""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from ..core import dds
from ..core.interfaces import GameError
from .packaged import GAMEDATA, HD_MODEL_DIR, PackagedError, own_catalog
from .sources import (
    HD_DIR,
    HD_MARK,
    TERRAIN_FIELDS,
    TERRAIN_FILE,
    is_marked,
    terrain_texture_ids,
)

MAX_TRAILER = 16


class CheckError(GameError):
    """What is wrong with the packaged textures of a map."""


def fail(message: str) -> None:
    raise CheckError(message)


def _is_power_of_two(value: int) -> bool:
    return value > 0 and value & (value - 1) == 0


def check_texture_file(path: Path) -> None:
    try:
        texture = dds.parse(path.read_bytes())
    except dds.DdsError as error:
        fail(f"upscaled texture {path.name}: {error}")
    if not (_is_power_of_two(texture.width) and _is_power_of_two(texture.height)):
        fail(
            f"upscaled texture {path.name}: size {texture.width}x{texture.height} is not a power of two"
        )
    if len(texture.levels) != dds.full_mip_count(texture.width, texture.height):
        fail(
            f"upscaled texture {path.name}: mip chain has {len(texture.levels)} levels, not a full chain"
        )
    if len(texture.trailer) > MAX_TRAILER:
        fail(
            f"upscaled texture {path.name}: {len(texture.trailer)} stray bytes after the last mip"
        )


def _folder(map_dir: Path, game_path: str) -> Path:
    return map_dir.joinpath(*game_path.split("\\"))


def hd_model_files(map_dir: Path) -> dict[str, Path]:
    """Lower-case game path below HD_MODEL_DIR to path, for the patched models in the map.

    A copy for one actor or unit lies in a folder of that owner's name, so
    two copies may share a file name (SPEC-HD-TEXTURES 5.2).
    """
    folder = _folder(map_dir, HD_MODEL_DIR)
    return (
        {
            "\\".join(path.relative_to(folder).parts).lower(): path
            for path in sorted(folder.rglob("*"))
            if path.is_file()
        }
        if folder.is_dir()
        else {}
    )


def hd_references(map_dir: Path) -> set[str]:
    """Lower-case file names below HD_DIR that the map's catalogs or its patched models point at."""
    pattern = re.compile(
        r'value="' + re.escape(HD_DIR) + r'\\([^"\\]+)"', re.IGNORECASE
    )
    names: set[str] = set()
    for catalog in sorted((map_dir / GAMEDATA).glob("*.xml")):
        names.update(
            name.lower()
            for name in pattern.findall(
                catalog.read_text(encoding="utf-8", errors="replace")
            )
        )
    # A model keeps its texture paths as plain text.
    in_model = re.compile(
        re.escape(HD_DIR.encode("ascii")) + rb"\\([^\\\x00]+\.dds)", re.IGNORECASE
    )
    for path in hd_model_files(map_dir).values():
        names.update(
            name.decode("ascii").lower() for name in in_model.findall(path.read_bytes())
        )
    return names


def check_model_overrides(map_dir: Path) -> None:
    """Every CModel that names a patched model has its files, and every patched file is named."""
    files = hd_model_files(map_dir)
    catalog = map_dir / GAMEDATA / "ModelData.xml"
    prefix = HD_MODEL_DIR.lower() + "\\"
    named: set[str] = set()
    if catalog.is_file():
        for node in ET.parse(catalog).getroot().iter("CModel"):
            model = node.find("Model")
            value = (model.get("value") or "") if model is not None else ""
            if not value.lower().startswith(prefix):
                continue
            stem, _dot, extension = value.lower()[len(prefix) :].rpartition(".")
            own = {
                name
                for name in files
                if name == f"{stem}.{extension}"
                or re.fullmatch(re.escape(stem) + r"_\d\d\." + extension, name)
            }
            if not own:
                fail(
                    f"model {node.get('id')} points at {value}, but the map has no such model file"
                )
            named.update(own)
    for name in sorted(set(files) - named):
        fail(f"{HD_MODEL_DIR}\\{name} is in the map, but no model entry points at it")
    for name, path in files.items():
        if path.read_bytes()[:4] != b"43DM":
            fail(f"{HD_MODEL_DIR}\\{name} is not a model file")


def mixed_terrain(
    map_dir: Path, upscaled: set[tuple[str, str]]
) -> list[tuple[str, str]]:
    """The (entry, field) of the terrain textures the map paints with that are not in `upscaled`, when some of them are.

    A partly upscaled terrain mixes sharp and soft ground: all or nothing
    (R-HD-104). A folder that is no map paints with nothing.
    """
    if not (map_dir / TERRAIN_FILE).is_file():
        return []
    painted = [
        (entry, field)
        for entry in terrain_texture_ids(map_dir)
        for field, _role in TERRAIN_FIELDS
    ]
    missing = [place for place in painted if place not in upscaled]
    return missing if len(missing) < len(painted) else []


def check_terrain_overrides(map_dir: Path) -> None:
    catalog = map_dir / GAMEDATA / "TerrainTexData.xml"
    if not catalog.is_file():
        return
    prefix = HD_DIR.lower() + "\\"
    upscaled: set[tuple[str, str]] = set()
    for node in ET.parse(catalog).getroot().iter("CTerrainTex"):
        for child in node:
            if (child.get("value") or "").lower().startswith(prefix):
                upscaled.add((node.get("id", ""), child.tag))
    for entry, field in mixed_terrain(map_dir, upscaled):
        fail(
            f"terrain texture {entry} has no upscaled {field}, but other terrain textures do"
        )


def check_note(map_dir: Path) -> None:
    """Every catalog reads back as it was before the pack step: each line that names a packaged file is noted."""
    try:
        for catalog in sorted((map_dir / GAMEDATA).glob("*.xml")):
            own_catalog(map_dir, catalog.name)
    except PackagedError as error:
        fail(str(error))


def check_hd_textures(map_dir: Path) -> None:
    """For scripts/validate-map.py: the first fault ends the program."""
    try:
        check(map_dir)
    except CheckError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1) from error


def check(map_dir: Path) -> None:
    """Raise CheckError when the packaged textures of the map are not sound."""
    folder = map_dir.joinpath(*HD_DIR.split("\\"))
    files = (
        {path.name.lower(): path for path in folder.glob("*")}
        if folder.is_dir()
        else {}
    )
    referenced = hd_references(map_dir)
    for name in sorted(referenced - set(files)):
        fail(f"a catalog points at {HD_DIR}\\{name}, but the file is not in the map")
    for name in sorted(set(files) - referenced):
        fail(f"{HD_DIR}\\{name} is in the map, but no catalog points at it")
    for name in sorted(files):
        if not is_marked(name):
            fail(
                f"{HD_DIR}\\{name} must end with {HD_MARK} or its model form before the extension: the game sizes a texture by its file name"
            )
        check_texture_file(files[name])
    check_terrain_overrides(map_dir)
    check_model_overrides(map_dir)
    check_note(map_dir)
