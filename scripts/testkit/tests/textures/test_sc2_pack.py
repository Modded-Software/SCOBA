"""StarCraft II package: what a bake writes into the map folder (R-HD-54, 101, 104, 143, 145)."""

from __future__ import annotations

from hdtex.core import package
from hdtex.core.interfaces import GameError
from hdtex.sc2 import check, game
from hdtex.sc2.packaged import HD_MODEL_DIR
from hdtex.sc2.sources import HD_DIR

from testkit.tests.textures.sc2_fixtures import (
    ASSETS,
    MAP_FILES,
    MODEL_LAYERS,
    SCOBA,
    TEXTURES,
    PackCase,
    layer,
    model_bytes,
    model_layers,
    objects,
)

T = TEXTURES
STORED = ASSETS + TEXTURES


class PackageTest(PackCase):
    def test_a_picked_terrain_texture_is_copied_and_every_field_that_names_it_is_set(
        self,
    ) -> None:
        self.pick_terrain()
        record = package.package(self.dataset(), self.map_dir)
        path = f"{HD_DIR}\\grass_normal_scoba_hd.dds"
        self.assertEqual(record["textures"][T + "grass_normal.dds"]["path"], path)
        kept = self.store.game(game.ID).variant_file(
            STORED + "grass_normal.dds", "fast", 256
        )
        self.assertEqual(self.map_file(path).read_bytes(), kept.read_bytes())
        self.assertEqual(
            self.value("TerrainTexData.xml", "CTerrainTex", "Grass", "Normalmap"), path
        )
        self.assertEqual(
            self.value("TerrainTexData.xml", "CTerrainTex", "Dirt", "Normalmap"), path
        )
        self.assertEqual(
            self.value("TerrainTexData.xml", "CTerrainTex", "Grass", "Texture"),
            f"{HD_DIR}\\grass_scoba_hd.dds",
        )
        self.assertEqual(
            self.value("TerrainTexData.xml", "CTerrainTex", "Dirt", "Texture"),
            f"{HD_DIR}\\Dirt_scoba_hd.dds",
            "the file name as the catalog spells it",
        )
        check.check(self.map_dir)

    def test_a_model_that_names_a_packaged_terrain_texture_gets_a_copy_that_names_the_same_file(
        self,
    ) -> None:
        self.pick_terrain()
        package.package(self.dataset(), self.map_dir)
        rock = [
            item["path"]
            for item in model_layers(
                self.map_file(f"{HD_MODEL_DIR}\\Rock.m3").read_bytes()
            )
        ]
        self.assertEqual(
            rock[-1],
            f"{HD_DIR}\\grass_scoba_hd.dds",
            "Rock names Grass.dds, which the terrain names too",
        )
        self.assertEqual(
            rock[:-1],
            [
                item["path"]
                for item in MODEL_LAYERS["assets\\doodads\\rock\\rock.m3"][:-1]
            ],
        )
        self.assertEqual(
            self.value("ModelData.xml", "CModel", "Rock", "Model"),
            f"{HD_MODEL_DIR}\\Rock.m3",
        )
        self.assertFalse(
            self.map_file(f"{HD_MODEL_DIR}\\Tree_00.m3").exists(),
            "Tree names no packaged texture",
        )

    def test_a_partly_upscaled_terrain_is_refused_before_a_file_is_written(
        self,
    ) -> None:
        self.pick(T + "grass.dds")
        self.pick(T + "grass_normal.dds")
        with self.assertRaises(GameError) as refused:
            package.package(self.dataset(), self.map_dir)
        self.assertIn("but not Dirt.Texture", str(refused.exception))
        self.assertNotIn("Grass", str(refused.exception))
        self.assertEqual(
            sorted(path.name for path in self.map_dir.iterdir()), MAP_FILES
        )

    def test_a_built_map_with_a_partly_upscaled_terrain_fails_the_check(self) -> None:
        self.pick_terrain()
        package.package(self.dataset(), self.map_dir)
        catalog = self.map_dir / "Base.SC2Data" / "GameData" / "TerrainTexData.xml"
        line = f'<Texture value="{HD_DIR}\\Dirt_scoba_hd.dds"/>'
        self.assertIn(line, catalog.read_text())
        catalog.write_text(catalog.read_text().replace(line, ""))
        self.map_file(f"{HD_DIR}\\Dirt_scoba_hd.dds").unlink()
        with self.assertRaises(GameError) as mixed:
            self.game.check(self.map_dir)
        self.assertIn(
            "terrain texture Dirt has no upscaled Texture", str(mixed.exception)
        )

    def test_a_terrain_texture_the_map_does_not_paint_with_may_be_upscaled_alone(
        self,
    ) -> None:
        self.pick(
            T + "tree_diffuse.dds"
        )  # the terrain entry Made names it; the map paints with Grass and Dirt
        record = package.package(self.dataset(), self.map_dir)
        self.assertEqual(sorted(record["textures"]), [T + "tree_diffuse.dds"])
        self.assertEqual(
            self.value("TerrainTexData.xml", "CTerrainTex", "Made", "Texture"),
            f"{HD_DIR}\\tree_diffuse_scoba_hd.dds",
        )

    def test_a_model_file_that_reads_a_flip_book_with_other_cells_keeps_the_original(
        self,
    ) -> None:
        cells = layer("Assets\\Textures\\cells.dds", flipbook=True, grid=(2, 2))
        self.casc.files[ASSETS + "assets\\doodads\\rock\\rock.m3"] = model_bytes(
            [cells]
        )
        self.casc.files[ASSETS + "assets\\doodads\\tree\\tree_00.m3"] = model_bytes(
            [cells]
        )
        self.casc.files[ASSETS + "assets\\doodads\\mist\\mist.m3"] = model_bytes(
            [layer("Assets\\Textures\\cells.dds")]
        )
        found = self.dataset().texture(T + "cells.dds")
        self.assertEqual(
            (found.grid, found.role, found.users),
            (
                (2, 2),
                "diffuse",
                ("assets\\doodads\\rock\\rock.m3", "assets\\doodads\\tree\\tree_00.m3"),
            ),
        )
        self.pick(T + "cells.dds")
        package.package(self.dataset(), self.map_dir)
        path = f"{HD_DIR}\\cells_scoba_hd_m.dds"
        self.assertEqual(
            [
                item["path"]
                for item in model_layers(
                    self.map_file(f"{HD_MODEL_DIR}\\Rock.m3").read_bytes()
                )
            ],
            [path],
        )
        self.assertEqual(
            [
                item["path"]
                for item in model_layers(
                    self.map_file(f"{HD_MODEL_DIR}\\Tree_00.m3").read_bytes()
                )
            ],
            [path],
        )
        self.assertFalse(
            self.map_file(f"{HD_MODEL_DIR}\\Mist.m3").exists(),
            "Mist reads it without cells",
        )
        self.assertIsNone(self.value("ModelData.xml", "CModel", "Mist", "Model"))

    def test_a_picked_model_texture_gets_a_copy_of_every_file_of_each_model_entry_that_names_it(
        self,
    ) -> None:
        self.pick(T + "tree_normal.dds")
        record = package.package(self.dataset(), self.map_dir)
        path = f"{HD_DIR}\\tree_normal_scoba_hd_m.dds"
        self.assertEqual(
            [(one["asset"], one["variant"], one["path"]) for one in record["files"]],
            [(T + "tree_normal.dds", "fast@256", path)],
        )
        self.assertEqual(
            record["textures"], {}, "a model texture is no bake of its own"
        )
        # A `CModel` finds its texture slots by the start of a file name (TextureDeclares Prefix): the start stays.
        self.assertTrue(path.rsplit("\\", 1)[-1].startswith("tree_normal"), path)
        self.assertFalse(
            path.rsplit("\\", 1)[-1].startswith("scoba_hd"),
            "negative: no mark in front of the name",
        )
        first = model_layers(self.map_file(f"{HD_MODEL_DIR}\\Tree_00.m3").read_bytes())
        self.assertEqual(
            [item["path"] for item in first],
            [
                "Assets\\Textures\\tree_diffuse.dds",
                path,
                "Assets\\Textures\\nowhere.dds",
            ],
        )
        second = model_layers(self.map_file(f"{HD_MODEL_DIR}\\Tree_01.m3").read_bytes())
        self.assertEqual(
            second,
            MODEL_LAYERS["assets\\doodads\\tree\\tree_01.m3"],
            "a variation that names no packaged texture is copied as it is",
        )
        self.assertEqual(
            self.value("ModelData.xml", "CModel", "Tree", "Model"),
            f"{HD_MODEL_DIR}\\Tree.m3",
        )
        self.assertIsNone(self.value("ModelData.xml", "CModel", "Rock", "Model"))
        self.assertFalse(self.map_file(f"{HD_MODEL_DIR}\\Rock.m3").exists())

    def test_a_model_the_map_does_not_show_gets_no_copy(self) -> None:
        (self.map_dir / "Objects").write_text(objects(("Tree",)))
        self.casc.files[ASSETS + "assets\\doodads\\mist\\mist.m3"] = model_bytes(
            [layer("Assets\\Textures\\tree_normal.dds", "normalLayer")]
        )
        self.pick(T + "tree_normal.dds")
        package.package(self.dataset(), self.map_dir)
        self.assertTrue(self.map_file(f"{HD_MODEL_DIR}\\Tree_00.m3").is_file())
        self.assertFalse(
            self.map_file(f"{HD_MODEL_DIR}\\Mist.m3").exists(),
            "Mist names the texture, but the map does not show it",
        )
        self.assertIsNone(self.value("ModelData.xml", "CModel", "Mist", "Model"))

    def test_a_packaged_map_lists_the_textures_it_listed_before(self) -> None:
        before = self.dataset().textures
        self.pick(T + "tree_normal.dds")
        self.pick_terrain()
        package.package(self.dataset(), self.map_dir)
        again = game.Sc2Game(self.casc, self.game.index)
        again.use(SCOBA, self.map_dir)
        self.assertEqual(
            {texture.asset: texture for texture in again.textures(SCOBA)}, before
        )

    def test_with_every_pick_the_original_nothing_is_written(self) -> None:
        self.assertEqual(package.package(self.dataset(), self.map_dir)["textures"], {})
        self.assertEqual(
            sorted(path.name for path in self.map_dir.iterdir()), MAP_FILES
        )

    def test_two_picked_textures_with_one_file_name_are_refused(self) -> None:
        self.casc.files[ASSETS + "assets\\other\\tree_normal.dds"] = self.casc.files[
            STORED + "tree_normal.dds"
        ]
        self.casc.files[ASSETS + "assets\\doodads\\mist\\mist.m3"] = model_bytes(
            [layer("Assets\\Other\\tree_normal.dds", "normalLayer")]
        )
        self.pick(T + "tree_normal.dds")
        self.pick("assets\\other\\tree_normal.dds")
        with self.assertRaises(GameError) as refused:
            package.package(self.dataset(), self.map_dir)
        self.assertIn("share the file name tree_normal.dds", str(refused.exception))

    def test_a_map_is_packaged_once(self) -> None:
        self.pick_terrain()
        package.package(self.dataset(), self.map_dir)
        with self.assertRaises(GameError) as twice:
            package.package(self.dataset(), self.map_dir)
        self.assertIn("packaged already", str(twice.exception))
