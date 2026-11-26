"""StarCraft: Ghost as a game of the texture pipeline (SPEC-HD-TEXTURES 6, R-HD-150 to R-HD-155).

One dataset, `build`: the extracted game build. It takes no layer. Its
textures are the texture files the materials of its models name; its
owners are each model file and each template with a model. It bakes
nothing yet: every bake, unbake and package is refused (R-HD-154).
"""

from __future__ import annotations

import struct
from pathlib import Path

from ..core import codecs as core_codecs
from ..core import dds, registry
from ..core.interfaces import ACTOR, MODEL, GameError, Owner, OwnerBake, Packed, Texture
from ..core.store import GameStore, store_root
from . import codecs
from .build import TEXTURE_FOLDERS, Build, BuildError, asset_of, settings
from .export import TEXTURE_KEYS, listing

ID = "ghost"
DATASET = "build"
KIND = "model"
MIN_SIDE = 32
NO_BAKE = "baking is not enabled for StarCraft: Ghost"
# Shaders the game does not draw (SPEC-VIEWER-GHOST 4.4); a texture only they name has no role.
HIDDEN = ("sky", "invis", "video")
# Keys whose file is a picture in light; `envmap` alone is data (SPEC-HD-TEXTURES 6.2).
COLOUR_KEYS = frozenset(TEXTURE_KEYS) - {"envmap"}
VOLUME = 0x200000  # DDSCAPS2_VOLUME
# Ghost's formats (R-HD-153): the core's DXT1 and DXT5, and DXT3 and RGBA32, which codecs registers.
FORMATS = (core_codecs.DXT1.id, codecs.DXT3.id, core_codecs.DXT5.id, codecs.RGBA32.id)


def hidden(shader: str) -> bool:
    return shader in HIDDEN or shader.startswith("constraint_")


def role_of(keys: frozenset[str], data: bytes) -> tuple[str | None, str]:
    """The role of a texture its materials name under `keys`, or the reason it has none, from its file (R-HD-153)."""
    try:
        info = dds.describe(data)
    except dds.DdsError as error:
        return None, str(error)
    if info.cube:
        return None, "cube map"
    if struct.unpack_from("<I", data, 112)[0] & VOLUME:
        return None, "volume texture"
    if info.format not in FORMATS:
        return None, f"format {info.format}"
    if min(info.width, info.height) < MIN_SIDE:
        return None, f"smaller than {MIN_SIDE} pixels"
    try:
        texture = dds.parse(data)
    except dds.DdsError as error:
        return None, str(error)
    rgba = texture.codec.decode(texture.level_bytes(0), texture.width, texture.height)
    if texture.format == "DXT1" and int(rgba[:, :, 3].min()) < 255:
        return None, "DXT1 with transparent pixels"
    return ("diffuse", "") if keys & COLOUR_KEYS else ("data", "")


class GhostGame:
    id = ID
    alone: frozenset[str] = frozenset()  # nothing is baked on its own
    bakes = NO_BAKE

    def __init__(self, build: Build | None = None, index: Path | None = None) -> None:
        """`build`, `index`: the build and the folder of this game's caches; found when first needed."""
        self._build, self._index = build, index
        self._listing: dict | None = None
        self._origins: dict[str, str] = {}
        self._textures: dict[str, Texture] = {}
        self._keys: dict[str, frozenset[str]] = {}

    @property
    def build(self) -> Build:
        if self._build is None:
            self._build = settings()
        return self._build

    @property
    def index(self) -> Path:
        if self._index is None:
            self._index = GameStore(store_root() / ID).index
        return self._index

    def _check(self, dataset: str) -> None:
        if dataset != DATASET:
            raise BuildError(f"{ID} has no dataset {dataset}; its one dataset is {DATASET}")

    def _listed(self) -> dict:
        if self._listing is None:
            self._listing, read = listing(self.build, self.index)
            folders = tuple(f"{folder}/".lower() for folder in TEXTURE_FOLDERS)
            for rel in read:
                if rel.lower().endswith(".dds") and rel.lower().startswith(folders):
                    self._origins.setdefault(asset_of(rel), rel)
            self._describe()
        return self._listing

    def _describe(self) -> None:
        """Every texture file the materials of the models name, with its users, materials and keys."""
        assert self._listing is not None
        materials = self._listing["materials"]
        repeats = self._listing["repeats"]
        found: dict[str, dict] = {}
        for model, names in sorted(self._listing["models"].items()):
            repeated = frozenset(repeats.get(model, ()))
            for name in names:
                material = materials.get(name, {"shader": "", "textures": {}})
                for key, rel in sorted(material["textures"].items()):
                    if rel is None:
                        continue
                    one = found.setdefault(asset_of(rel), {"rel": rel, "users": set(), "entries": set(), "keys": set(), "drawn": False, "tiles": False})
                    one["users"].add(asset_of(model))
                    one["entries"].add(name)
                    one["keys"].add(key)
                    one["drawn"] |= not hidden(material["shader"])
                    # It tiles when any model repeats it with any material that names it (export.repeating).
                    one["tiles"] |= name in repeated
        for asset, one in sorted(found.items()):
            origin = self._origins.get(asset, "")
            reason = (
                "not a DDS file" if not asset.endswith(".dds")
                else "not in the build" if not origin
                else "" if one["drawn"]
                else "only materials the game does not draw name it"
            )
            self._keys[asset] = frozenset(one["keys"])
            self._textures[asset] = Texture(asset, origin, KIND, None, reason, one["tiles"], (1, 1), tuple(sorted(one["users"])), judged=bool(reason), entries=tuple(sorted(one["entries"])))

    def use(self, dataset: str, layer: Path) -> None:
        raise BuildError(f"{ID} has one dataset, {DATASET}, the build GHOST_PATH names; it takes no folder")

    def datasets(self) -> tuple[str, ...]:
        return (DATASET,)

    def textures(self, dataset: str) -> list[Texture]:
        self._check(dataset)
        self._listed()
        return [self._textures[asset] for asset in sorted(self._textures)]

    def judge(self, dataset: str, texture: Texture) -> Texture:
        self._check(dataset)
        self._listed()
        role, reason = role_of(self._keys.get(texture.asset, frozenset()), self.original(dataset, texture).read_bytes())
        return texture._replace(role=role, reason=reason, judged=True)

    def original(self, dataset: str, texture: Texture) -> Path:
        self._check(dataset)
        if not texture.origin:
            raise BuildError(f"{texture.asset} is not in the build")
        return self.build.root / texture.origin

    def origins(self, dataset: str) -> dict[str, str]:
        self._check(dataset)
        self._listed()
        return dict(self._origins)

    def fetch(self, dataset: str, textures: list[Texture]) -> None:
        """The build is a folder: its files are at hand."""

    def owners(self, dataset: str) -> list[Owner]:
        self._check(dataset)
        listed = self._listed()
        assets = {asset: [] for asset in map(asset_of, listed["models"])}
        for texture in self._textures.values():
            for user in texture.users:
                assets[user].append(texture.asset)
        found = [Owner(f"{MODEL}:{model}", model.rsplit("\\", 1)[-1], MODEL, (), tuple(sorted(names))) for model, names in sorted(assets.items()) if names]
        for template in listed["templates"]:
            model = asset_of(template["model"])
            if assets[model]:
                found.append(Owner(f"{ACTOR}:{template['name']}", template["name"], ACTOR, (f"{MODEL}:{model}",), tuple(sorted(assets[model]))))
        return found

    def gaps(self, dataset: str) -> dict[str, list[str]]:
        self._check(dataset)
        listed = self._listed()
        missing = sorted({f"{name}: {key}" for name, one in listed["materials"].items() for key, rel in one["textures"].items() if rel is None})
        return {
            kind: lines
            for kind, lines in (
                ("model files NODExport refused", [f"{one['name']}: {one['error']}" for one in listed["refused"]]),
                ("materials found by no step", sorted(name for name, one in listed["materials"].items() if one["step"] == "none")),
                ("material texture files that are missing", missing),
            )
            if lines
        }

    def package(self, dataset: str, files: list[Packed], owners: list[OwnerBake], alone: dict[str, str], target: Path) -> dict[tuple[str, str], str]:
        raise GameError(f"{ID}: {NO_BAKE}")

    def check(self, target: Path) -> None:
        raise GameError(f"{ID}: {NO_BAKE}")


GAME = registry.GAMES.add(ID, GhostGame())
