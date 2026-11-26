"""StarCraft II as a game of the texture pipeline.

A dataset is the game's own data and, on top, an optional layer: a map
folder. `stock` has none. The caller names the layer of any other dataset
(`use`); this module finds none itself.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from ..core import codecs, dds, package, registry, roles
from ..core.bakes import BakeError
from ..core.dataset import Dataset, DatasetError
from ..core.interfaces import GameError, Owner, OwnerBake, Packed, Texture
from ..core.store import GameStore, Store, StoreError, store_root
from . import check, modelindex, owners, pack, terrain
from .casc import Casc
from .sources import SourceError
from .storage import Storage

ID = "sc2"
STOCK = "stock"
MAP_DATASET = "scoba"  # the dataset whose package target is the built map
MIN_SIDE = 32
NORMAL_SLOT = "normalLayer"
SURFACE_MATERIALS = "standardMaterials"
# Slots whose texture is a picture in light. Any other slot holds amounts.
COLOR_SLOTS = frozenset(
    {"diffuseLayer", "decalLayer", "emissiveLayer", "emissive2Layer"}
)
ABSENT = "not in the game storage"
# The core's formats. Another game's codec in the registry (DXT3, RGBA32) is not one of StarCraft II's (SPEC-HD-TEXTURES 5).
FORMATS = (codecs.DXT1.id, codecs.DXT5.id)

LOG = logging.getLogger(__name__)


def early_reason(use: modelindex.Use) -> str:
    """Why a model texture has no role, as far as its users say. Empty: its file must be read to know."""
    if use.origin is None:
        return ABSENT
    if not use.asset.endswith(".dds"):
        return "not a DDS file"
    if use.video:
        return "video layer"
    if use.grid is None:
        return "flip book: its cells are not known, or as many model files read it one way as another"
    return ""


def role_of(use: modelindex.Use, data: bytes) -> tuple[str | None, str]:
    """The role of a model texture, or the reason it has none, from its file."""
    try:
        info = dds.describe(data)
    except dds.DdsError as error:
        return None, str(error)
    if info.cube:
        return None, "cube map"
    if info.format not in FORMATS:
        return None, f"format {info.format}"
    if min(info.width, info.height) < MIN_SIDE:
        return None, f"smaller than {MIN_SIDE} pixels"
    if use.flipbook and use.grid is not None:
        columns, rows = use.grid
        if info.width % columns or info.height % rows:
            return (
                None,
                f"flip book: {columns}x{rows} cells do not divide {info.width}x{info.height}",
            )
        if min(info.width // columns, info.height // rows) < MIN_SIDE:
            return None, f"flip book: its cells are smaller than {MIN_SIDE} pixels"
    try:
        texture = dds.parse(data)
    except dds.DdsError as error:
        return None, str(error)
    rgba = texture.codec.decode(texture.level_bytes(0), texture.width, texture.height)
    if NORMAL_SLOT in use.slots:
        # Other materials bend the picture with their normal layer. Whether
        # that data is a unit vector is not known, so it is left alone.
        if other := sorted(set(use.materials) - {SURFACE_MATERIALS}):
            return None, f"normal slot of {', '.join(other)}"
        if len(use.slots) > 1:
            return None, f"slots that disagree: {', '.join(use.slots)}"
        try:
            roles.normal_layout(rgba)
        except roles.RoleError as error:
            return (
                ("normal_red", "")
                if roles.has_free_red(rgba)
                else (None, f"normal slot, but {error}")
            )
        return "normal", ""
    if texture.format == "DXT1" and int(rgba[:, :, 3].min()) < 255:
        return None, "DXT1 with transparent pixels"
    return ("diffuse", "") if COLOR_SLOTS.intersection(use.slots) else ("data", "")


class Sc2Game:
    id = ID
    alone = frozenset({pack.TERRAIN})  # kinds of texture baked on their own (R-HD-145)
    bakes = ""  # SC2 bakes (R-HD-115)

    def __init__(self, casc: Casc | None = None, index: Path | None = None) -> None:
        """`casc`, `index`: the game's storage and the folder of this game's caches; found when first needed."""
        self._casc, self._index = casc, index
        self.layers: dict[str, Path] = {}
        self._storages: dict[str, Storage] = {}
        self._files: dict[str, modelindex.Models] = {}
        self._models: dict[str, dict[str, modelindex.Use]] = {}
        self._owners: dict[str, list[Owner]] = {}

    @property
    def index(self) -> Path:
        if self._index is None:
            # The folder alone: reading the caches needs no store object.
            self._index = GameStore(store_root() / ID).index
        return self._index

    def use(self, dataset: str, layer: Path) -> None:
        if dataset == STOCK:
            raise SourceError(f"{STOCK} is the game's own data; it takes no folder")
        if self.layers.get(dataset, layer) != layer:
            raise SourceError(
                f"{dataset} has the folder {self.layers[dataset]} already, not {layer}"
            )
        self.layers[dataset] = layer

    def datasets(self) -> tuple[str, ...]:
        return (STOCK, *sorted(self.layers))

    def storage(self, dataset: str) -> Storage:
        if dataset not in self._storages:
            if dataset != STOCK and dataset not in self.layers:
                raise SourceError(
                    f"{ID} has no dataset {dataset}; name its map folder with --layer"
                )
            if self._casc is None:
                self._casc = Casc()
            self._storages[dataset] = Storage(
                dataset, self.layers.get(dataset), self._casc, self.index / "storage"
            )
        return self._storages[dataset]

    def model_files(self, dataset: str) -> modelindex.Models:
        """The dataset's model files and their layers, read once for its textures and its owners."""
        if dataset not in self._files:
            self._files[dataset] = modelindex.models(self.storage(dataset), self.index)
        return self._files[dataset]

    def model_uses(self, dataset: str) -> dict[str, modelindex.Use]:
        if dataset not in self._models:
            self._models[dataset] = {
                use.asset: use
                for use in modelindex.uses(self.storage(dataset), self.model_files(dataset))
            }
        return self._models[dataset]

    def textures(self, dataset: str) -> list[Texture]:
        storage = self.storage(dataset)
        found: dict[str, Texture] = {}
        for ground in terrain.uses(storage):
            if ground.origin is None:
                role, reason = None, ABSENT
            elif len(ground.roles) > 1:
                role, reason = (
                    None,
                    f"catalog fields that disagree: {', '.join(ground.roles)}",
                )
            elif not ground.asset.endswith(".dds"):
                role, reason = None, "not a DDS file"
            else:
                role, reason = ground.roles[0], ""
            entries = tuple(sorted({entry for entry, _field in ground.fields}))
            found[ground.asset] = Texture(
                ground.asset,
                ground.origin or "",
                pack.TERRAIN,
                role,
                reason,
                True,
                (1, 1),
                ground.sets,
                entries=entries,
            )
        shared = 0
        for use in self.model_uses(dataset).values():
            if use.asset in found:
                shared += 1  # the terrain names it too; it stays a terrain texture
                continue
            reason = early_reason(use)
            grid = use.grid if use.flipbook and use.grid else (1, 1)
            users = tuple(sorted({file.asset for file in use.files}))
            found[use.asset] = Texture(
                use.asset,
                use.origin or "",
                pack.MODEL,
                None,
                reason,
                use.repeats,  # tiles when a model shows it more than once (m3tex.repeating)
                grid,
                users,
                judged=bool(reason),
            )
        LOG.info(
            "%s: %d textures; %d of them are named by models and by the terrain",
            dataset,
            len(found),
            shared,
        )
        return [found[asset] for asset in sorted(found)]

    def judge(self, dataset: str, texture: Texture) -> Texture:
        use = self.model_uses(dataset)[texture.asset]
        role, reason = role_of(
            use, self.storage(dataset).file(texture.origin).read_bytes()
        )
        return texture._replace(role=role, reason=reason, judged=True)

    def original(self, dataset: str, texture: Texture) -> Path:
        if not texture.origin:
            raise SourceError(f"{texture.asset} is {ABSENT}")
        return self.storage(dataset).file(texture.origin)

    def origins(self, dataset: str) -> dict[str, str]:
        return self.storage(dataset).origins(".dds")

    def fetch(self, dataset: str, textures: list[Texture]) -> None:
        self.storage(dataset).fetch(
            texture.origin for texture in textures if texture.origin
        )

    def owners(self, dataset: str) -> list[Owner]:
        if dataset not in self._owners:
            self._owners[dataset] = owners.owners(
                self.storage(dataset), self.model_files(dataset), self.model_uses(dataset)
            )
        return self._owners[dataset]

    def gaps(self, dataset: str) -> dict[str, list[str]]:
        return {
            kind: list(lines)
            for kind, lines in sorted(self.storage(dataset).gaps.items())
        }

    def package(
        self,
        dataset: str,
        files: list[Packed],
        baked: list[OwnerBake],
        alone: dict[str, str],
        target: Path,
    ) -> dict[tuple[str, str], str]:
        return pack.package(
            self.storage(dataset),
            self.index,
            files,
            baked,
            alone,
            target,
            self.model_uses(dataset),
        )

    def check(self, target: Path) -> None:
        check.check(target)


GAME = registry.GAMES.add(ID, Sc2Game())


def package_map(map_dir: Path) -> None:
    """For the map build: put the bakes of the built map's dataset into its build folder (R-HD-101).

    A bake that cannot be packaged ends the build with the reason.
    """
    start = time.monotonic()
    try:
        record = package.package(Dataset(Store(), ID, MAP_DATASET, map_dir), map_dir)
    except (
        package.PackageError,
        GameError,
        DatasetError,
        StoreError,
        BakeError,
    ) as error:
        raise SystemExit(f"hd textures: {error}") from error
    print(
        f"hd textures: packaged {len(record['files'])} files of the dataset {MAP_DATASET} for {len(record['owners'])} owners and {len(record['textures'])} textures "
        f"in {time.monotonic() - start:.1f} s; {len(record['unused'])} bakes are unused"
    )
