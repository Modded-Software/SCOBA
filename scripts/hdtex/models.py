"""Which models the map shows for its doodads and for the named units.

    placed doodad or unit -> actor -> model entry -> model files -> layers

The doodads are read from the built map: the map build places most of
them. The units are named in MODEL_UNITS. Only the model an actor shows
while it stands is followed. Death models, missiles, and attachments are
not, but for the entries named in MODEL_ENTRIES.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import NamedTuple

from . import dds, m3tex, roles
from .casc import Casc
from .catalog import Catalog, CatalogError
from .sources import HD_DIR, HD_PREFIX, SourceError, TextureRef, locate, map_archives, stored_name

# Units whose models are upscaled. Operator 2026-11-19: a proof of concept
# with the Command Center and the psi destroyer. 2026-11-20: the shackled
# ultralisk, both forms of the Viking, and the Overlord as well. The vista
# overlord (SCOBAVistaOverlord) shows the model of the Overlord.
# Then the Mengsk battlecruiser the map places (MengskBC) and the sensor tower.
# Then the Hellion and the Goliath.
MODEL_UNITS = ("CommandCenter", "PsiDecimator", "HybridUltraliskShackled", "VikingAssault", "VikingFighter", "Overlord", "MengskBC", "SensorTower", "Hellion", "Goliath")

# Model entries that are upscaled by name, with the unit each belongs to.
# Operator 2026-11-20: the explosions of the death of the Mengsk battlecruiser.
MODEL_ENTRIES = {"BattlecruiserLokiDeathSlow": "MengskBC"}

GAMEDATA = "\\base.sc2data\\gamedata\\"

# Patched model files go here in the map. A CModel override names them.
HD_MODEL_DIR = "Assets\\Models\\scoba_hd"
# A terrain texture can also sit on a model (zerus_4 on ZerusWaterfall). The
# two sources make their own file of it, so the names must differ.
MODEL_PREFIX = HD_PREFIX + "m_"
# Operator 2026-11-19: 2048 per side is plenty for a model texture.
MODEL_MAX_SIZE = 2048
MIN_SIDE = 32
SKIPPED = "skipped.json"
SOURCE = "models"  # the name of this source in sources.SOURCES

# The map build makes some models itself and puts them at the game's path
# (VikingAssault.m3 with footstep events). Such a file is the one to copy.
MAP_MARK = "map:"

NORMAL_SLOT = "normalLayer"
SURFACE_MATERIALS = "standardMaterials"
# Slots whose texture is a picture in light. The other slots hold amounts.
COLOR_SLOTS = frozenset({"diffuseLayer", "decalLayer", "emissiveLayer", "emissive2Layer"})


class ModelFile(NamedTuple):
    entry: str  # CModel id
    asset: str  # game path of this file, as the engine builds it
    casc_path: str  # where the game keeps it, or MAP_MARK and its path in the map
    base: str  # the entry's Model value; variations share it
    actors: tuple[str, ...]


class ModelLayer(NamedTuple):
    model: ModelFile
    layer: m3tex.Layer


def doodad_types(map_dir: Path) -> list[str]:
    """Doodad actor ids the map places, in name order."""
    text = (map_dir / "Objects").read_text(encoding="utf-8", errors="replace")
    return sorted(set(re.findall(r'<ObjectDoodad\b[^>]*\bType="([^"]+)"', text)))


def _own_models(map_dir: Path) -> dict[str, list[str]]:
    """File name in lower case -> the map paths of the models the map ships itself, the patched copies left out."""
    found: dict[str, list[str]] = {}
    for path in sorted(map_dir.rglob("*.m3")):
        place = "\\".join(path.relative_to(map_dir).parts)
        if not place.lower().startswith(HD_MODEL_DIR.lower() + "\\"):
            found.setdefault(path.name.lower(), []).append(place)
    return found


def _drop_hd_overrides(text: str, map_dir: Path) -> str:
    """The map's own catalog without the lines this tooling wrote into it.

    The stock catalogs name a stock model again once the line is gone. A
    model the map ships itself is named by the map's catalog alone, and the
    line took the place of that. Such a line gets the map's own file back:
    the copy keeps the file name, and one file of the map has it.
    """
    own = _own_models(map_dir)

    def restore(match: re.Match[str]) -> str:
        places = own.get(match.group(2).lower(), [])
        return f"{match.group(1)}{places[0]}{match.group(3)}" if len(places) == 1 else match.group(0)

    text = re.sub(r'(<Model value=")' + re.escape(HD_MODEL_DIR) + r'\\([^"\\]+)("\s*/>)', restore, text, flags=re.IGNORECASE)
    folders = "|".join(re.escape(folder) for folder in (HD_DIR, HD_MODEL_DIR))
    pattern = re.compile(r'[ \t]*<\w+ value="(?:' + folders + r')\\[^"]*"\s*/>\r?\n?', re.I)
    return pattern.sub("", text)


def load_catalog(name: str, map_dir: Path, casc: Casc, work: Path) -> Catalog:
    """One catalog file from every archive the map loads, then from the map."""
    archives = map_archives(map_dir)
    tail = GAMEDATA + name.lower()
    present = set(casc.find([tail]))
    stored = [archive + tail for archive in archives if archive + tail in present]
    extracted = casc.extract(stored, work / "catalogs")
    texts = [extracted[path].read_text(encoding="utf-8-sig") for path in stored]
    own = map_dir / "Base.SC2Data" / "GameData" / name
    if own.is_file():
        texts.append(_drop_hd_overrides(own.read_text(encoding="utf-8-sig"), map_dir))
    return Catalog(texts)


def variation_assets(base: str, count: int) -> list[str]:
    """`Dir\\Name.m3` with N variations is `Dir\\Name_00.m3` to `Dir\\Name_<N-1>.m3`."""
    stem, dot, extension = base.rpartition(".")
    if not dot:
        raise SourceError(f"model path without an extension: {base}")
    return [f"{stem}_{index:02d}.{extension}" for index in range(count)]


def model_entries(map_dir: Path, casc: Casc, work: Path) -> dict[str, list[str]]:
    """CModel id -> the actors that show it."""
    actors = load_catalog("ActorData.xml", map_dir, casc, work)
    wanted: dict[str, list[str]] = {}
    try:
        for unit in MODEL_UNITS:
            if actors.token(unit, "unitName") != unit:
                raise SourceError(f"actor {unit} is not the actor of unit {unit}")
        for actor in [*doodad_types(map_dir), *MODEL_UNITS]:
            wanted.setdefault(actors.need(actor, "Model"), []).append(actor)
    except CatalogError as error:
        raise SourceError(str(error)) from error
    for entry, unit in MODEL_ENTRIES.items():
        wanted.setdefault(entry, []).append(unit)
    return wanted


def model_files(map_dir: Path, casc: Casc, work: Path) -> list[ModelFile]:
    """Every model file of the wanted entries, with where the game keeps it."""
    archives = map_archives(map_dir)
    wanted = model_entries(map_dir, casc, work)
    catalog = load_catalog("ModelData.xml", map_dir, casc, work)
    plans: list[tuple[str, str, list[str]]] = []
    try:
        for entry in sorted(wanted):
            base = catalog.need(entry, "Model")
            count = int(catalog.field(entry, "VariationCount") or 0)
            plans.append((entry, base, variation_assets(base, count) if count else [base]))
    except CatalogError as error:
        raise SourceError(str(error)) from error
    every = [asset for _entry, _base, assets in plans for asset in assets]
    candidates = casc.find(["\\" + stored_name(asset) for asset in every if not map_model(map_dir, asset).is_file()])
    files = []
    for entry, base, assets in plans:
        for asset in assets:
            if map_model(map_dir, asset).is_file():
                path = MAP_MARK + asset.replace("/", "\\")
            else:
                path = locate(asset, candidates, archives)
            files.append(ModelFile(entry, asset, path, base, tuple(wanted[entry])))
    return files


def map_model(map_dir: Path, asset: str) -> Path:
    """Where the map would keep a model of its own for a game path."""
    return map_dir.joinpath(*asset.replace("/", "\\").split("\\"))


def fetch(files: list[ModelFile], map_dir: Path, casc: Casc, work: Path) -> dict[str, Path]:
    """The file of each model, by `casc_path`: extracted from the game, or the map's own."""
    stored = sorted({file.casc_path for file in files if not file.casc_path.startswith(MAP_MARK)})
    found = dict(casc.extract(stored, work / "models"))
    for file in files:
        if file.casc_path.startswith(MAP_MARK):
            found[file.casc_path] = map_model(map_dir, file.casc_path[len(MAP_MARK) :])
    return found


class Use(NamedTuple):
    """One texture and everything that names it."""

    asset: str  # lower case, backslashes
    casc_path: str | None  # None: the storage does not hold it
    slots: tuple[str, ...]
    materials: tuple[str, ...]  # material lists, such as standardMaterials
    entries: tuple[str, ...]  # CModel ids
    video: bool
    flipbook: bool
    wrap: bool
    # (columns, rows) every layer agrees on; a layer without a flip book counts as (1, 1). None: they differ, or a flip book has no known cells.
    grid: tuple[int, int] | None = None


class Verdict(NamedTuple):
    role: str | None  # None: the texture is left as it is
    reason: str  # why it is left; empty when it has a role


def texture_uses(layers: list[ModelLayer], map_dir: Path, casc: Casc) -> list[Use]:
    archives = map_archives(map_dir)
    grouped: dict[str, list[ModelLayer]] = {}
    for item in layers:
        grouped.setdefault(stored_name(item.layer.path), []).append(item)
    candidates = casc.find(["\\" + asset for asset in grouped])
    uses = []
    for asset, items in sorted(grouped.items()):
        grids = {item.layer.grid if item.layer.flipbook else (1, 1) for item in items}
        try:
            path: str | None = locate(asset, candidates, archives)
        except SourceError:
            path = None
        uses.append(
            Use(
                asset,
                path,
                tuple(sorted({item.layer.slot for item in items})),
                tuple(sorted({item.layer.material for item in items})),
                tuple(sorted({item.model.entry for item in items})),
                any(item.layer.video for item in items),
                any(item.layer.flipbook for item in items),
                all(item.layer.wrap for item in items),
                next(iter(grids)) if len(grids) == 1 else None,
            )
        )
    return uses


def judge(use: Use, data: bytes | None) -> Verdict:
    """The role of a texture, or the reason it is not upscaled. `data` is the file, if the storage has it."""
    if use.casc_path is None or data is None:
        return Verdict(None, "not in the game storage")
    if not use.asset.endswith(".dds"):
        return Verdict(None, "not a DDS file")
    if use.video:
        return Verdict(None, "video layer")
    if use.flipbook and use.grid is None:
        return Verdict(None, "flip book: the size of its cells is not known")
    info = dds.describe(data)
    if info.cube:
        return Verdict(None, "cube map")
    if info.format not in dds.CODECS:
        return Verdict(None, f"format {info.format}")
    if min(info.width, info.height) < MIN_SIDE:
        return Verdict(None, f"smaller than {MIN_SIDE} pixels")
    if max(info.width, info.height) >= MODEL_MAX_SIZE:
        return Verdict(None, f"already {MODEL_MAX_SIZE} pixels or more")
    if use.flipbook and use.grid is not None:
        columns, rows = use.grid
        if info.width % columns or info.height % rows:
            return Verdict(None, f"flip book: {columns}x{rows} cells do not divide {info.width}x{info.height}")
        if min(info.width // columns, info.height // rows) < MIN_SIDE:
            return Verdict(None, f"flip book: its cells are smaller than {MIN_SIDE} pixels")
    try:
        texture = dds.parse(data)
    except dds.DdsError as error:
        return Verdict(None, str(error))
    rgba = texture.codec.decode(texture.level_bytes(0), texture.width, texture.height)
    if NORMAL_SLOT in use.slots:
        # Other materials bend the picture with their normal layer. Whether
        # that data is a unit vector is not known, so it is left alone.
        if other := sorted(set(use.materials) - {SURFACE_MATERIALS}):
            return Verdict(None, f"normal slot of {', '.join(other)}")
        try:
            roles.normal_layout(rgba)
        except roles.RoleError as error:
            if roles.has_free_red(rgba):
                return Verdict("normal_red", "")
            return Verdict(None, f"normal slot, but {error}")
        return Verdict("normal", "")
    if texture.format == "DXT1" and int(rgba[:, :, 3].min()) < 255:
        return Verdict(None, "DXT1 with transparent pixels")
    if COLOR_SLOTS.intersection(use.slots):
        return Verdict("diffuse", "")
    return Verdict("data", "")


def hd_texture_path(asset: str) -> str:
    return f"{HD_DIR}\\{MODEL_PREFIX}{asset.rsplit(chr(92), 1)[-1]}"


def judged(map_dir: Path, casc: Casc, work: Path) -> list[tuple[Use, Verdict]]:
    """Every texture of the wanted models with its verdict."""
    files = model_files(map_dir, casc, work)
    uses = texture_uses(model_layers(files, map_dir, casc, work), map_dir, casc)
    extracted = casc.extract(sorted({use.casc_path for use in uses if use.casc_path}), work / "original")
    found = []
    for use in uses:
        data = extracted[use.casc_path].read_bytes() if use.casc_path else None
        found.append((use, judge(use, data)))
    return found


def model_refs(map_dir: Path, casc: Casc, work: Path) -> list[TextureRef]:
    """The textures of the wanted models that can be upscaled. The others are listed in SKIPPED."""
    refs = []
    skipped = {}
    names: dict[str, str] = {}
    for use, verdict in judged(map_dir, casc, work):
        if verdict.role is None or use.casc_path is None:
            skipped[use.asset] = {"reason": verdict.reason, "slots": list(use.slots), "models": list(use.entries)}
            continue
        name = use.asset.rsplit("\\", 1)[-1]
        if names.setdefault(name, use.asset) != use.asset:
            raise SourceError(f"{use.asset} and {names[name]} share the file name {name}")
        grid = use.grid if use.flipbook and use.grid else (1, 1)
        refs.append(TextureRef(use.asset, verdict.role, use.casc_path, hd_texture_path(use.asset), (), grid))
    work.mkdir(parents=True, exist_ok=True)
    (work / SKIPPED).write_text(json.dumps(skipped, indent=2, sort_keys=True) + "\n")
    return refs


def model_layers(files: list[ModelFile], map_dir: Path, casc: Casc, work: Path) -> list[ModelLayer]:
    """Every layer of every model file that names a texture."""
    extracted = fetch(files, map_dir, casc, work)
    found = []
    for file in files:
        try:
            model = m3tex.load(extracted[file.casc_path])
        except m3tex.ModelError as error:
            raise SourceError(f"model {file.entry}: {error}") from error
        found.extend(ModelLayer(file, layer) for layer in m3tex.layers(model))
    return found
