"""A small StarCraft II for the host tests: a made storage, a made model reader, a map folder.

A test model file holds its layers in a form of its own (`model_bytes`).
Nothing here touches the game.
"""

from __future__ import annotations

import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import ClassVar
from unittest import mock

import numpy as np
from hdtex.core import progress, registry, requests, skins
from hdtex.core.dataset import Dataset
from hdtex.core.interfaces import MODEL
from hdtex.core.store import Store
from hdtex.sc2 import game, m3tex, modelindex, owned, pack
from hdtex.sc2.casc import CascError

from testkit.tests.textures.doubles import StandIn
from testkit.tests.textures.fixtures import SIZE, colour_rgba, normal_rgba, texture_file

ARCHIVE = "mods\\liberty.sc2mod\\"
ASSETS = ARCHIVE + "base.sc2assets\\"
GAMEDATA = ARCHIVE + "base.sc2data\\gamedata\\"
TEXTURES = "assets\\textures\\"

DOCUMENT_INFO = """<?xml version="1.0" encoding="utf-8"?>
<DocInfo><Dependencies><Value>bnet:Void Story (Campaign)/0.0/999,file:Campaigns/VoidStory.SC2Campaign</Value></Dependencies></DocInfo>
"""

TERRAIN_TEXTURES = """<Catalog>
<CTerrainTex default="1" id="Simple"><Texture value="Assets\\Textures\\##texId##.dds"/></CTerrainTex>
<CTerrainTex id="Grass"><Texture value="Assets\\Textures\\grass.dds"/><Normalmap value="Assets\\Textures\\grass_normal.dds"/></CTerrainTex>
<CTerrainTex id="Dirt"><Texture value="Assets\\Textures\\Dirt.dds"/><Normalmap value="Assets\\Textures\\grass_normal.dds"/></CTerrainTex>
<CTerrainTex id="Lost"><Texture value="Assets\\Textures\\lost.dds"/></CTerrainTex>
<CTerrainTex id="Made" parent="Simple" texId="tree_diffuse"/>
</Catalog>"""

TERRAIN_SETS = """<Catalog>
<CTerrain id="Meadow"><BlendTextures value="Grass"/><BlendTextures value="Dirt"/></CTerrain>
<CTerrain id="Field"><BlendTextures value="Dirt"/></CTerrain>
</Catalog>"""

MODELS = """<Catalog>
<CModel default="1"><Radius value="0.5"/></CModel>
<CModel default="1" id="Doodad"><Model value="Assets\\Doodads\\##id##\\##id##.m3"/></CModel>
<CModel id="Tree" parent="Doodad"><VariationCount value="2"/></CModel>
<CModel id="Rock" parent="Doodad"/>
<CModel id="Mist" parent="Doodad"/>
<CModel id="Ghost" parent="Doodad"/>
<CModel id="Nameless"/>
</Catalog>"""

# A doodad's actor shows the model of its own name. The unit Guard shows the model Rock.
ACTORS = """<Catalog>
<CActorDoodad default="1"><Model value="##id##"/></CActorDoodad>
<CActorDoodad id="Tree"/>
<CActorDoodad id="Rock"/>
<CActorDoodad id="Mist"/>
<CActorUnit id="Guard"><Model value="Rock"/></CActorUnit>
</Catalog>"""


def layer(
    path: str,
    slot: str = "diffuseLayer",
    material: str = "standardMaterials",
    flipbook: bool = False,
    grid: tuple[int, int] | None = None,
) -> dict:
    return {
        "material": material,
        "index": 0,
        "slot": slot,
        "path": path,
        "video": False,
        "flipbook": flipbook,
        "wrap": True,
        "grid": grid,
    }


MAGIC = b"43DM"


def model_bytes(layers: list[dict]) -> bytes:
    """A test model file: the magic of a model, then per layer its facts and its path, each ended by a zero byte.

    As in a real model, a texture path stands in the file as plain text.
    """
    parts = [MAGIC]
    for item in layers:
        facts = {key: value for key, value in item.items() if key != "path"}
        parts += [json.dumps(facts).encode(), b"\x00", item["path"].encode(), b"\x00"]
    return b"".join(parts)


def model_layers(data: bytes) -> list[dict]:
    """The layers of a test model file. ValueError when it is none."""
    if data[:4] != MAGIC:
        raise ValueError("no model magic")
    fields = data[4:].split(b"\x00")[:-1]
    if len(fields) % 2:
        raise ValueError("a layer without a path")
    return [
        {**json.loads(facts), "path": path.decode()}
        for facts, path in zip(fields[0::2], fields[1::2])
    ]


def free_red_normal() -> np.ndarray:
    rgba = normal_rgba()
    rgba[:, :, 0] = np.arange(SIZE, dtype=np.uint8)[None, :] * 3
    return rgba


# Model file -> its layers. Tree has two variations; only the first names a texture that can be upscaled.
MODEL_LAYERS = {
    "assets\\doodads\\tree\\tree_00.m3": [
        layer("Assets\\Textures\\tree_diffuse.dds"),
        layer("Assets\\Textures\\tree_normal.dds", "normalLayer"),
        layer("Assets\\Textures\\nowhere.dds"),
    ],
    "assets\\doodads\\tree\\tree_01.m3": [
        layer("Assets\\Textures\\boom.dds", flipbook=True)
    ],
    "assets\\doodads\\rock\\rock.m3": [
        layer("Assets\\Textures\\rock_spec.dds", "specularLayer"),
        layer("Assets\\Textures\\rock_normal.dds", "normalLayer"),
        layer("Assets\\Textures\\waves.dds", "normalLayer", "displacementMaterials"),
        layer("Assets/Textures/Grass.dds"),
    ],
    "assets\\doodads\\mist\\mist.m3": [
        layer("Assets\\Textures\\cells.dds", flipbook=True, grid=(2, 2))
    ],
}

STORED_TEXTURES = {
    "grass.dds": texture_file("diffuse", colour_rgba(1)),
    "grass_normal.dds": texture_file("normal", normal_rgba()),
    "dirt.dds": texture_file("diffuse", colour_rgba(2)),
    "tree_diffuse.dds": texture_file("diffuse", colour_rgba(3)),
    "tree_normal.dds": texture_file("normal", normal_rgba()),
    "rock_spec.dds": texture_file("data", colour_rgba(4), "DXT1"),
    "rock_normal.dds": texture_file("normal_red", free_red_normal()),
    "waves.dds": texture_file("normal", normal_rgba()),
    "boom.dds": texture_file("diffuse", colour_rgba(5)),
    "cells.dds": texture_file("diffuse", colour_rgba(6)),
}


class FakeCasc:
    """The game storage as a dict of path to bytes. It counts what is taken out."""

    def __init__(self) -> None:
        self.files = {
            GAMEDATA + "terraintexdata.xml": TERRAIN_TEXTURES.encode(),
            GAMEDATA + "terraindata.xml": TERRAIN_SETS.encode(),
            GAMEDATA + "modeldata.xml": MODELS.encode(),
            GAMEDATA + "actordata.xml": ACTORS.encode(),
            # A file of a campaign map inside an archive: no dataset loads it.
            ARCHIVE + "base.sc2maps\\maps\\one.sc2map\\assets\\textures\\lost.dds": b"",
        }
        for path, layers in MODEL_LAYERS.items():
            self.files[ASSETS + path] = model_bytes(layers)
        for name, data in STORED_TEXTURES.items():
            self.files[ASSETS + TEXTURES + name] = data
        self.taken: list[str] = []

    def find(self, suffixes: list[str]) -> list[str]:
        return sorted(
            path
            for path in self.files
            if path.endswith(tuple(suffix.lower() for suffix in suffixes))
        )

    def extract(
        self, paths: list[str], out_dir: Path, batch: int = 0, jobs: int = 1
    ) -> dict[str, Path]:
        found = {}
        for path in paths:
            if path not in self.files:
                raise CascError(f"not in the storage: {path}")
            target = out_dir / Path(*path.split("\\"))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(self.files[path])
            self.taken.append(path)
            found[path] = target
        return found


class FakeModels:
    """Stands in for the model reader: it reads test model files (`model_bytes`). It counts what it reads."""

    ModelError = m3tex.ModelError
    Layer = m3tex.Layer
    read: ClassVar[
        list[str]
    ] = []  # one list for the test that runs; `Sc2Case.setUp` empties it

    @classmethod
    def load(cls, path: Path):
        cls.read.append(Path(path).name)
        try:
            return model_layers(Path(path).read_bytes())
        except ValueError as error:
            raise m3tex.ModelError(f"{Path(path).name}: {error}") from error

    @staticmethod
    def layers(model) -> list[m3tex.Layer]:
        # JSON has no tuples: the cells of a flip book come back as a list.
        return [
            m3tex.Layer(
                **{**item, "grid": tuple(item["grid"]) if item.get("grid") else None}
            )
            for item in model
        ]

    @staticmethod
    def rewrite(source: Path, target: Path, paths: dict[str, str]) -> int:
        model = model_layers(Path(source).read_bytes())
        changed = 0
        for item in model:
            new = paths.get(item["path"].replace("/", "\\").lower())
            if new is not None:
                item["path"] = new
                changed += 1
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(model_bytes(model))
        return changed


PAINTED = ("Grass", "Dirt")  # the terrain textures the map paints with
PLACED = ("Tree", "Rock", "Mist")  # the doodads the map places
MAP_FILES = ["DocumentInfo", "Objects", "t3Terrain.xml"]  # what `write_map` writes


def objects(doodads: tuple[str, ...] = (), units: tuple[str, ...] = ()) -> str:
    """The file of a map that says what it places."""
    rows = [
        f'<ObjectDoodad Id="{index}" Position="1,1,0" Type="{name}"/>'
        for index, name in enumerate(doodads)
    ]
    rows += [
        f'<ObjectUnit Id="{index + 100}" Position="1,1,0" UnitType="{name}" Player="1"/>'
        for index, name in enumerate(units)
    ]
    return f"<PlacedObjects>{''.join(rows)}</PlacedObjects>"


def write_map(map_dir: Path) -> Path:
    map_dir.mkdir(parents=True, exist_ok=True)
    (map_dir / "DocumentInfo").write_text(DOCUMENT_INFO)
    (map_dir / "Objects").write_text(objects(PLACED))
    rows = "".join(
        f'<texture i="{index}" name="{name}"/>' for index, name in enumerate(PAINTED)
    )
    (map_dir / "t3Terrain.xml").write_text(
        f'<terrain><textureList num="64">{rows}<texture i="63" name=""/></textureList></terrain>'
    )
    return map_dir


class Sc2Case(unittest.TestCase):
    """A store, a made storage, a map folder, and the game registered over them for one test."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root / "store")
        self.casc = FakeCasc()
        self.map_dir = write_map(self.root / "map")
        self.game = game.Sc2Game(self.casc, self.store.game(game.ID).index)
        FakeModels.read = []
        for patch in (
            mock.patch.dict(registry.GAMES.items, {game.ID: self.game}),
            mock.patch.object(modelindex, "m3tex", FakeModels),
            mock.patch.object(pack, "m3tex", FakeModels),
            mock.patch.object(owned, "m3tex", FakeModels),
        ):
            patch.start()
            self.addCleanup(patch.stop)

    def map_file(self, game_path: str, data: bytes | None = None) -> Path:
        """A file of the map by its game path. With `data`, it is written."""
        path = self.map_dir.joinpath(*game_path.split("\\"))
        if data is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        return path


SCOBA = "scoba"
SKIN = "hd"
# Every file the terrain textures the map paints with name: Grass and Dirt, colour and normal map.
TERRAIN_FILES = ("grass.dds", "dirt.dds", "grass_normal.dds")


class PackCase(Sc2Case):
    """The map folder as the dataset `scoba`, with results made by a stand-in upscaler."""

    def setUp(self) -> None:
        super().setUp()
        self.runner = StandIn()

    def dataset(self) -> Dataset:
        return Dataset(self.store, game.ID, SCOBA, self.map_dir)

    def variant(self, asset: str) -> str:
        """The variant `pick` makes of a texture: pbrify where it has colour, else fast, at its own size."""
        texture = self.dataset().texture(asset)
        return f"{'pbrify' if progress.has_colour(texture) else 'fast'}@256"

    def pick(self, asset: str) -> None:
        """Make a variant of the texture and bake it: on its own for a terrain texture, else in skin hd of each model file that shows it."""
        found = self.dataset()
        texture = found.texture(asset)
        variant = self.variant(asset)
        requests.make(found, self.runner, texture, variant, wait=lambda _seconds: None)
        if texture.kind in found.adapter.alone:
            found.bake_texture(asset, variant)
            return
        for owner in found.owners.values():
            if owner.layer != MODEL or asset not in owner.textures:
                continue
            if SKIN not in found.skins_of(owner.id):
                found.change_skin(
                    owner.id, lambda now: skins.copied(now, skins.ORIGINAL_SKIN, SKIN)
                )
            found.set_texture(owner.id, SKIN, asset, variant)
            found.bake(owner.id, SKIN)

    def pick_terrain(self) -> None:
        """A pick for every file of the terrain textures the map paints with."""
        for name in TERRAIN_FILES:
            self.pick(TEXTURES + name)

    def value(self, catalog: str, element: str, entry: str, field: str) -> str | None:
        """A field of an entry in a catalog file of the map."""
        root = ET.parse(self.map_dir / "Base.SC2Data" / "GameData" / catalog).getroot()
        node = next(
            (item for item in root.iter(element) if item.get("id") == entry), None
        )
        return (
            None
            if node is None or node.find(field) is None
            else node.find(field).get("value")
        )
