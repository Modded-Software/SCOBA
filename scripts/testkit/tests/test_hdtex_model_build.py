"""Host tests for the model texture source: which models and textures, and the cache build.

The storage, the upscaler, and the model reader are made for the test.
"""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
from unittest import mock

from hdtex import (
    dds,
    m3tex,
    models,
    pipeline,
)
from hdtex.sources import HD_DIR, SourceError

from testkit.tests.hdtex_fixtures import (
    SIZE,
)
from testkit.tests.hdtex_model_fixtures import (
    ASSETS,
    MODEL_CATALOG,
    MODEL_LAYERS,
    TEXTURES,
    FakeModels,
    ModelCasc,
    ModelCase,
    layer,
    write_model_map,
)


def flip_layers(grid_a, grid_b) -> dict:
    boom = "Assets\\Textures\\boom.dds"
    return {
        "assets\\doodads\\tree\\tree_01.m3": [{**layer(boom, flipbook=grid_a is not None), "grid": grid_a}],
        "assets\\doodads\\mist\\mist.m3": [{**layer(boom, flipbook=grid_b is not None), "grid": grid_b}],
    }


class ModelSourceTest(ModelCase):
    def test_placed_doodads_and_the_named_units_give_the_model_files(self) -> None:
        files = models.model_files(self.map_dir, ModelCasc(), self.folder)
        self.assertEqual(
            sorted(file.asset for file in files),
            [
                "Assets\\Buildings\\Terran\\CommandCenter\\CommandCenter.m3",
                "Assets\\Doodads\\Mist\\Mist.m3",
                "Assets\\Doodads\\Psi\\Psi.m3",
                "Assets\\Doodads\\Rock\\Rock.m3",
                "Assets\\Doodads\\Tree\\Tree_00.m3",
                "Assets\\Doodads\\Tree\\Tree_01.m3",
            ],
        )
        self.assertEqual({file.casc_path for file in files}, {ASSETS + path for path in MODEL_LAYERS})

    def test_a_doodad_the_game_does_not_know_is_an_error(self) -> None:
        write_model_map(self.map_dir, ("Tree", "Ghost"))
        with self.assertRaises(SourceError):
            models.model_files(self.map_dir, ModelCasc(), self.folder)

    def test_an_actor_of_the_map_names_its_model(self) -> None:
        write_model_map(self.map_dir, ("TreeFp1",))
        catalog = self.map_dir / "Base.SC2Data" / "GameData" / "ActorData.xml"
        catalog.parent.mkdir(parents=True)
        catalog.write_text('<Catalog><CActorDoodad id="TreeFp1" parent="Tree"><Model value="Tree"/></CActorDoodad></Catalog>')
        entries = models.model_entries(self.map_dir, ModelCasc(), self.folder)
        self.assertEqual(entries["Tree"], ["TreeFp1"])

    def test_each_texture_is_listed_once_with_its_role_and_a_name_of_its_own(self) -> None:
        refs = models.model_refs(self.map_dir, ModelCasc(), self.folder)
        self.assertEqual(
            {ref.asset: ref.role for ref in refs},
            {
                "assets\\textures\\tree_diffuse.dds": "diffuse",
                "assets\\textures\\tree_normal.dds": "normal",
                "assets\\textures\\rock_spec.dds": "data",
                "assets\\textures\\rock_normal.dds": "normal_red",
            },
        )
        for ref in refs:
            name = ref.asset.rsplit("\\", 1)[-1]
            self.assertEqual(ref.map_path, f"{HD_DIR}\\scoba_hd_m_{name}")
            self.assertEqual(ref.overrides, ())

    def test_what_is_left_alone_is_written_down_with_its_reason(self) -> None:
        models.model_refs(self.map_dir, ModelCasc(), self.folder)
        skipped = json.loads((self.folder / models.SKIPPED).read_text())
        self.assertEqual(sorted(skipped), ["assets\\textures\\boom.dds", "assets\\textures\\waves.dds"])
        self.assertIn("flip book", skipped["assets\\textures\\boom.dds"]["reason"])
        self.assertEqual(skipped["assets\\textures\\boom.dds"]["models"], ["Mist", "Tree"])

    def test_the_overrides_this_tooling_wrote_are_not_read_back(self) -> None:
        catalog = self.map_dir / MODEL_CATALOG
        catalog.parent.mkdir(parents=True)
        catalog.write_text(
            f'<Catalog>\n    <CModel id="Rock">\n        <Model value="{models.HD_MODEL_DIR}\\Rock.m3" />\n    </CModel>\n</Catalog>\n'
        )
        files = models.model_files(self.map_dir, ModelCasc(), self.folder)
        self.assertIn("Assets\\Doodads\\Rock\\Rock.m3", [file.asset for file in files])

    def own_model_catalog(self, files: tuple[str, ...]) -> str | None:
        """The Model of an entry only the map defines, after the tooling pointed it at a copy."""
        catalog = self.map_dir / MODEL_CATALOG
        catalog.parent.mkdir(parents=True, exist_ok=True)
        catalog.write_text(
            f'<Catalog>\n    <CModel id="Own">\n        <Model value="{models.HD_MODEL_DIR}\\Own.m3" />\n    </CModel>\n</Catalog>\n'
        )
        for place in files:
            path = self.map_dir.joinpath(*place.split("\\"))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("[]")
        return models.load_catalog("ModelData.xml", self.map_dir, ModelCasc(), self.folder).field("Own", "Model")

    def test_a_model_of_the_map_is_named_again_by_its_own_file(self) -> None:
        copy = f"{models.HD_MODEL_DIR}\\Own.m3"
        self.assertEqual(self.own_model_catalog(("Assets\\Deaths\\Own.m3", copy)), "Assets\\Deaths\\Own.m3")

    def test_a_copy_without_one_file_of_the_map_is_not_guessed(self) -> None:
        copy = f"{models.HD_MODEL_DIR}\\Own.m3"
        self.assertNotEqual(self.own_model_catalog((copy,)), copy)
        self.assertNotIn("Deaths", self.own_model_catalog(("Assets\\Deaths\\Own.m3", "Assets\\Other\\Own.m3", copy)) or "")


class ModelBuildTest(ModelCase):
    def test_textures_keep_their_format_and_stop_at_the_largest_size(self) -> None:
        manifest = self.build()
        self.assertEqual(len(manifest["textures"]), 4)
        for entry in manifest["textures"]:
            parsed = dds.parse((self.folder / entry["file"]).read_bytes())
            original = dds.parse(TEXTURES[entry["asset"].rsplit("\\", 1)[-1]])
            self.assertEqual(parsed.format, original.format)
            self.assertEqual(entry["format"], original.format)
            self.assertEqual((parsed.width, parsed.height), (SIZE * 2, SIZE * 2))
            self.assertEqual(len(parsed.levels), dds.full_mip_count(SIZE * 2, SIZE * 2))

    def test_every_file_of_a_model_with_an_upscaled_texture_is_copied(self) -> None:
        by_entry = {entry["entry"]: entry for entry in self.build()["models"]}
        self.assertEqual(sorted(by_entry), ["CommandCenter", "Mist", "PsiDecimator", "Rock", "Tree"])
        self.assertEqual([Path(file["file"]).name for file in by_entry["Tree"]["files"]], ["Tree_00.m3", "Tree_01.m3"])
        self.assertEqual(by_entry["Tree"]["map_base"], f"{models.HD_MODEL_DIR}\\Tree.m3")
        self.assertEqual(by_entry["PsiDecimator"]["map_base"], f"{models.HD_MODEL_DIR}\\Psi.m3")
        self.assertEqual(by_entry["Tree"]["actors"], ["Tree"])

    def test_a_model_without_an_upscaled_texture_is_not_copied(self) -> None:
        mist = next(entry for entry in self.build()["models"] if entry["entry"] == "Mist")
        self.assertEqual(mist["files"], [])
        self.assertIsNone(mist["map_base"])
        self.assertFalse((self.folder / "m3" / "Mist.m3").exists())

    def test_a_copy_names_the_upscaled_textures_and_leaves_the_others(self) -> None:
        self.build()
        tree = FakeModels.layers(FakeModels.load(self.folder / "m3" / "Tree_00.m3"))
        self.assertEqual(
            [item.path for item in tree],
            [f"{HD_DIR}\\scoba_hd_m_tree_diffuse.dds"] * 2 + [f"{HD_DIR}\\scoba_hd_m_tree_normal.dds"],
        )
        rock = FakeModels.layers(FakeModels.load(self.folder / "m3" / "Rock.m3"))
        self.assertEqual(rock[2].path, "Assets\\Textures\\waves.dds")
        # A path spelled with other case and slashes is found too.
        psi = FakeModels.layers(FakeModels.load(self.folder / "m3" / "Psi.m3"))
        self.assertEqual(psi[0].path, f"{HD_DIR}\\scoba_hd_m_rock_spec.dds")

    def test_a_copy_that_does_not_read_back_is_an_error(self) -> None:
        with mock.patch.object(FakeModels, "rewrite", staticmethod(lambda source, target, paths: target.parent.mkdir(parents=True, exist_ok=True) or target.write_bytes(Path(source).read_bytes()))):
            with self.assertRaises(m3tex.ModelError), contextlib.redirect_stdout(io.StringIO()):
                pipeline.build(models.SOURCE, self.map_dir, pipeline.Settings(max_size=SIZE * 2), casc=ModelCasc())

    def test_a_second_build_redoes_nothing(self) -> None:
        self.build()
        runs = len(self.upscaler.runs)
        stamps = {path: path.stat().st_mtime_ns for path in (self.folder / "m3").glob("*.m3")}
        self.build()
        self.assertEqual(len(self.upscaler.runs), runs)
        self.assertEqual(stamps, {path: path.stat().st_mtime_ns for path in (self.folder / "m3").glob("*.m3")})

    def test_the_manifest_lists_what_was_left_alone(self) -> None:
        self.assertEqual(sorted(self.build()["skipped"]), ["assets\\textures\\boom.dds", "assets\\textures\\waves.dds"])


class FlipBookBuildTest(ModelCase):
    BOOM = "assets\\textures\\boom.dds"

    def test_a_flip_book_is_upscaled_with_its_cells_apart(self) -> None:
        with mock.patch.dict(MODEL_LAYERS, flip_layers([2, 2], [2, 2])):
            manifest = self.build()
        entry = next(item for item in manifest["textures"] if item["asset"] == self.BOOM)
        self.assertEqual(entry["size"], [SIZE * 2, SIZE * 2])
        self.assertNotIn(self.BOOM, manifest["skipped"])
        (plane,) = self.folder.glob("planes/*/boom.color.png")
        grown = SIZE + 2 * pipeline.FLIP_MARGIN * 2
        self.assertEqual(pipeline.Image.open(plane).size, (grown, grown))
        (result,) = self.folder.glob("upscaled/*/boom.color.png")
        self.assertEqual(pipeline.Image.open(result).size, (grown * 4, grown * 4))

    def test_the_cells_come_out_as_the_picture_upscaled_cell_by_cell(self) -> None:
        # The test upscaler repeats pixels, so the rim changes nothing: the file equals the one without a flip book.
        with mock.patch.dict(MODEL_LAYERS, flip_layers([2, 2], [2, 2])):
            self.build()
        flip = (self.folder / "dds" / "scoba_hd_m_boom.dds").read_bytes()
        with mock.patch.dict(MODEL_LAYERS, flip_layers(None, None)):
            self.build()
        self.assertEqual((self.folder / "dds" / "scoba_hd_m_boom.dds").read_bytes(), flip)

    def test_models_that_disagree_on_the_cells_leave_the_flip_book(self) -> None:
        for grids in (([2, 2], [4, 4]), ([2, 2], None)):
            with mock.patch.dict(MODEL_LAYERS, flip_layers(*grids)):
                manifest = self.build()
            self.assertIn("flip book", manifest["skipped"][self.BOOM]["reason"], grids)
            self.assertNotIn(self.BOOM, [item["asset"] for item in manifest["textures"]])

    def test_a_texture_without_a_flip_book_keeps_its_stamp(self) -> None:
        ref = models.model_refs(self.map_dir, ModelCasc(), self.folder)[0]
        self.assertEqual(ref.grid, (1, 1))
        self.assertNotIn("grid", pipeline._ref_stamp(ref))
        self.assertIn("flip_margin", pipeline._ref_stamp(ref._replace(grid=(2, 2))))


class NamedEntryTest(ModelCase):
    def test_a_named_entry_is_followed_with_the_unit_it_belongs_to(self) -> None:
        write_model_map(self.map_dir, ("Tree",))
        with mock.patch.object(models, "MODEL_ENTRIES", {"Rock": "PsiDecimator"}):
            entries = models.model_entries(self.map_dir, ModelCasc(), self.folder)
            files = models.model_files(self.map_dir, ModelCasc(), self.folder)
        self.assertEqual(entries["Rock"], ["PsiDecimator"])
        self.assertIn("Assets\\Doodads\\Rock\\Rock.m3", [file.asset for file in files])

    def test_without_named_entries_only_what_stands_is_followed(self) -> None:
        write_model_map(self.map_dir, ("Tree",))
        self.assertNotIn("Rock", models.model_entries(self.map_dir, ModelCasc(), self.folder))
