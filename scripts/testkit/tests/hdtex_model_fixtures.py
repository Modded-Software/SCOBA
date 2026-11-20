"""What the model texture tests share: a made storage, a made model reader, a temp map and cache.

A test model file is a JSON list of layers.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
from hdtex import (
    check,
    dds,
    inject,
    m3tex,
    models,
    pipeline,
    roles,
    variants,
)
from project_root import project_root

from testkit.tests.hdtex_fixtures import (
    DOCUMENT_INFO,
    SIZE,
    FakeCasc,
    FakeUpscaler,
    diffuse_rgba,
    normal_rgba,
)

BUILT_MAP = project_root() / "out" / "SCOBA256.SC2Map"
ASSETS = "mods\\liberty.sc2mod\\base.sc2assets\\"
GAMEDATA = "mods\\liberty.sc2mod\\base.sc2data\\gamedata\\"
MODEL_CATALOG = Path("Base.SC2Data") / "GameData" / "ModelData.xml"

ACTORS = """<Catalog>
<CActorModel default="1"><Model value="##id##"/></CActorModel>
<CActorDoodad default="1"><Radius value="0.5"/></CActorDoodad>
<CActorUnit default="1" id="GenericUnit"><?token id="unitName" value="Bogus"?><Model value="##unitName##"/></CActorUnit>
<CActorDoodad id="Tree"/>
<CActorDoodad id="Rock"/>
<CActorDoodad id="Mist"/>
<CActorUnit id="CommandCenter" parent="GenericUnit" unitName="CommandCenter"/>
<CActorUnit id="PsiDecimator" parent="GenericUnit" unitName="PsiDecimator"/>
</Catalog>"""

MODELS = """<Catalog>
<CModel default="1"><Radius value="0.5"/></CModel>
<CModel default="1" id="Doodad"><Model value="Assets\\Doodads\\##id##\\##id##.m3"/></CModel>
<CModel default="1" id="Building"><?token id="Race" value="Neutral"?><Model value="Assets\\Buildings\\##Race##\\##id##\\##id##.m3"/></CModel>
<CModel id="Tree" parent="Doodad"><VariationCount value="2"/></CModel>
<CModel id="Rock" parent="Doodad"/>
<CModel id="Mist" parent="Doodad"/>
<CModel id="CommandCenter" parent="Building" Race="Terran"/>
<CModel id="PsiDecimator" parent="Building"><Model value="Assets\\Doodads\\Psi\\Psi.m3"/></CModel>
</Catalog>"""


def layer(path: str, slot: str = "diffuseLayer", material: str = "standardMaterials", flipbook: bool = False) -> dict:
    return {"material": material, "index": 0, "slot": slot, "path": path, "video": False, "flipbook": flipbook, "wrap": True}


def free_red_normal() -> np.ndarray:
    rgba = normal_rgba()
    rgba[:, :, 0] = np.arange(SIZE, dtype=np.uint8)[None, :] * 3
    return rgba


def texture(role: str, rgba: np.ndarray, format: str = "DXT5") -> bytes:
    levels = roles.ROLES[role].join(roles.ROLES[role].split(rgba), None, True)
    codec = dds.CODECS[format]
    return dds.build(SIZE, SIZE, [codec.encode(level) for level in levels], b"", format)


# Model file -> its layers. Tree has two variations; the second names no texture that is upscaled.
MODEL_LAYERS = {
    "assets\\doodads\\tree\\tree_00.m3": [
        layer("Assets\\Textures\\tree_diffuse.dds"),
        layer("Assets\\Textures\\tree_diffuse.dds", "specularLayer"),
        layer("Assets\\Textures\\tree_normal.dds", "normalLayer"),
    ],
    "assets\\doodads\\tree\\tree_01.m3": [layer("Assets\\Textures\\boom.dds", flipbook=True)],
    "assets\\doodads\\rock\\rock.m3": [
        layer("Assets\\Textures\\rock_spec.dds", "specularLayer"),
        layer("Assets\\Textures\\rock_normal.dds", "normalLayer"),
        layer("Assets\\Textures\\waves.dds", "normalLayer", "displacementMaterials"),
    ],
    "assets\\doodads\\mist\\mist.m3": [layer("Assets\\Textures\\boom.dds", flipbook=True)],
    "assets\\buildings\\terran\\commandcenter\\commandcenter.m3": [layer("Assets\\Textures\\tree_diffuse.dds")],
    "assets\\doodads\\psi\\psi.m3": [layer("assets/textures/Rock_Spec.dds", "specularLayer")],
}

TEXTURES = {
    "tree_diffuse.dds": texture("diffuse", diffuse_rgba(1)),
    "tree_normal.dds": texture("normal", normal_rgba()),
    "rock_spec.dds": texture("data", diffuse_rgba(2), "DXT1"),
    "rock_normal.dds": texture("normal_red", free_red_normal()),
    "waves.dds": texture("normal", normal_rgba()),
    "boom.dds": texture("diffuse", diffuse_rgba(3)),
}


class ModelCasc(FakeCasc):
    def __init__(self) -> None:
        self.files = {GAMEDATA + "actordata.xml": ACTORS.encode(), GAMEDATA + "modeldata.xml": MODELS.encode()}
        for path, layers in MODEL_LAYERS.items():
            self.files[ASSETS + path] = json.dumps(layers).encode()
        for name, data in TEXTURES.items():
            self.files[ASSETS + "assets\\textures\\" + name] = data


class FakeModels:
    """Stands in for the model reader: a model file is a JSON list of layers."""

    ModelError = m3tex.ModelError
    Layer = m3tex.Layer

    @staticmethod
    def load(path: Path):
        return json.loads(Path(path).read_text())

    @staticmethod
    def layers(model) -> list[m3tex.Layer]:
        # JSON has no tuples: the cells of a flip book come back as a list.
        return [m3tex.Layer(**{**item, "grid": tuple(item["grid"]) if item.get("grid") else None}) for item in model]

    @staticmethod
    def rewrite(source: Path, target: Path, paths: dict[str, str]) -> int:
        model = json.loads(Path(source).read_text())
        changed = 0
        for item in model:
            new = paths.get(item["path"].replace("/", "\\").lower())
            if new is not None:
                item["path"] = new
                changed += 1
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(model))
        return changed


def write_model_map(map_dir: Path, doodads: tuple[str, ...] = ("Tree", "Rock", "Mist")) -> Path:
    map_dir.mkdir(parents=True, exist_ok=True)
    (map_dir / "DocumentInfo").write_text(DOCUMENT_INFO.format(dependency="Campaigns/VoidStory.SC2Campaign"))
    rows = "".join(f'<ObjectDoodad Id="{index}" Type="{name}"/>' for index, name in enumerate(doodads))
    (map_dir / "Objects").write_text(f"<PlacedObjects>{rows}</PlacedObjects>")
    (map_dir / "t3Terrain.xml").write_text('<terrain><textureList num="1"><texture i="0" name="Zerus1"/></textureList></terrain>')
    return map_dir


class ModelCase(unittest.TestCase):
    """A temp map and a temp cache, with the storage, the upscaler, and the model reader faked."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.map_dir = write_model_map(root / "map")
        self.cache = root / "cache"
        self.folder = self.cache / variants.DEFAULT / models.SOURCE
        self.upscaler = FakeUpscaler()
        patches = (
            mock.patch.dict(os.environ, {"SC2_HDTEX_CACHE": str(self.cache)}),
            mock.patch.object(pipeline.upscaler, "run", self.upscaler),
            mock.patch.object(pipeline.upscaler, "version", lambda: "tool-1"),
            mock.patch.object(pipeline, "m3tex", FakeModels),
            mock.patch.object(models, "m3tex", FakeModels),
            # The units of the test storage, not those of the real map.
            mock.patch.object(models, "MODEL_UNITS", ("CommandCenter", "PsiDecimator")),
            mock.patch.object(models, "MODEL_ENTRIES", {}),
        )
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        os.environ.pop(variants.ENV, None)

    def build(self) -> dict:
        with contextlib.redirect_stdout(io.StringIO()):
            path = pipeline.build(models.SOURCE, self.map_dir, pipeline.Settings(max_size=SIZE * 2), casc=ModelCasc())
        return json.loads(path.read_text())

    def inject(self) -> int:
        with contextlib.redirect_stdout(io.StringIO()) as self.output:
            return inject.apply_hd_textures(self.map_dir)

    def map_file(self, game_path: str) -> Path:
        return self.map_dir.joinpath(*game_path.split("\\"))

    def check_fails(self, word: str) -> None:
        errors = io.StringIO()
        with contextlib.redirect_stderr(errors), self.assertRaises(SystemExit):
            check.check_hd_textures(self.map_dir)
        self.assertIn(word, errors.getvalue())
