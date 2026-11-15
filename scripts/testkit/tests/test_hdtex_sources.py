from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import hd_textures
from hdtex import pipeline, roles, sources, variants
from hdtex.sources import DEPENDENCY_ARCHIVES, HD_DIR, HD_PREFIX, SourceError
from testkit.tests.hdtex_fixtures import DOCUMENT_INFO, TEXTURE_FOLDER, FakeCasc, write_map

ARCHIVES = DEPENDENCY_ARCHIVES["campaigns/voidstory.sc2campaign"]


class MapFilesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.map_dir = write_map(Path(self.temp.name) / "map", ("Zerus7", "Zerus6", "Zerus7"))

    def test_texture_ids_keep_order_and_drop_repeats_and_empty_slots(self) -> None:
        self.assertEqual(sources.terrain_texture_ids(self.map_dir), ["Zerus7", "Zerus6"])

    def test_a_map_without_textures_is_an_error(self) -> None:
        write_map(self.map_dir, ())
        with self.assertRaises(SourceError):
            sources.terrain_texture_ids(self.map_dir)

    def test_archives_come_in_load_order(self) -> None:
        archives = sources.map_archives(self.map_dir)
        self.assertEqual(archives, ARCHIVES)
        self.assertLess(archives.index("mods\\liberty.sc2mod"), archives.index("mods\\swarm.sc2mod"))

    def test_an_unknown_dependency_is_an_error(self) -> None:
        (self.map_dir / "DocumentInfo").write_text(DOCUMENT_INFO.format(dependency="Mods/Other.SC2Mod"))
        with self.assertRaises(SourceError):
            sources.map_archives(self.map_dir)


class CatalogTest(unittest.TestCase):
    def test_a_later_catalog_wins(self) -> None:
        first = '<Catalog><CTerrainTex id="A"><Texture value="one.dds"/><Normalmap value="n.dds"/></CTerrainTex></Catalog>'
        second = '<Catalog><CTerrainTex id="A"><Texture value="two.dds"/></CTerrainTex></Catalog>'
        fields = sources.catalog_fields([first, second], "CTerrainTex")
        self.assertEqual(fields["A"], {"Texture": "two.dds", "Normalmap": "n.dds"})

    def test_the_default_entry_is_left_out_and_a_parent_is_recorded(self) -> None:
        text = (
            '<Catalog><CTerrainTex default="1" id="Base"><Texture value="x.dds"/></CTerrainTex>'
            '<CTerrainTex id="B" parent="A"/><CModel id="C"><Texture value="m.dds"/></CModel></Catalog>'
        )
        fields = sources.catalog_fields([text], "CTerrainTex")
        self.assertEqual(fields, {"B": {"__parent__": "A"}})


class LocateTest(unittest.TestCase):
    asset = "Assets\\Textures\\Zerus_1.dds"

    def test_the_last_loaded_archive_wins(self) -> None:
        liberty = f"{TEXTURE_FOLDER}zerus_1.dds"
        void = "mods\\void.sc2mod\\base.sc2assets\\assets\\textures\\zerus_1.dds"
        self.assertEqual(sources.locate(self.asset, [void, liberty], ARCHIVES), void)
        self.assertEqual(sources.locate(self.asset, [liberty], ARCHIVES), liberty)

    def test_a_file_at_the_archive_root_counts(self) -> None:
        root = "mods\\swarm.sc2mod\\assets\\textures\\zerus_1.dds"
        self.assertEqual(sources.locate(self.asset, [root], ARCHIVES), root)

    def test_a_campaign_map_inside_an_archive_does_not_count(self) -> None:
        nested = "campaigns\\voidstory.sc2campaign\\base.sc2maps\\maps\\a.sc2map\\assets\\textures\\zerus_1.dds"
        with self.assertRaises(SourceError):
            sources.locate(self.asset, [nested], ARCHIVES)

    def test_an_archive_the_map_does_not_load_does_not_count(self) -> None:
        other = "mods\\novastoryassets.sc2mod\\base.sc2assets\\assets\\textures\\zerus_1.dds"
        with self.assertRaises(SourceError):
            sources.locate(self.asset, [other], ARCHIVES)


class TerrainRefsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.map_dir = write_map(Path(self.temp.name) / "map")
        self.work = Path(self.temp.name) / "work"

    def refs(self, casc: FakeCasc | None = None):
        return sources.terrain_refs(self.map_dir, casc or FakeCasc(), self.work)

    def test_each_texture_gives_a_diffuse_and_a_normal_ref(self) -> None:
        refs = self.refs()
        self.assertEqual(
            [(ref.asset, ref.role) for ref in refs],
            [
                ("Assets\\Textures\\Zerus_2.dds", "diffuse"),
                ("Assets\\Textures\\Zerus_2Normal.dds", "normal"),
                ("Assets\\Textures\\Zerus_1.dds", "diffuse"),
                ("Assets\\Textures\\Zerus_1Normal.dds", "normal"),
            ],
        )
        first = refs[0]
        self.assertEqual(first.casc_path, f"{TEXTURE_FOLDER}zerus_2.dds")
        self.assertEqual(first.map_path, f"{HD_DIR}\\{HD_PREFIX}Zerus_2.dds")
        self.assertEqual(
            [(o.catalog_file, o.element, o.entry, o.field) for o in first.overrides],
            [("TerrainTexData.xml", "CTerrainTex", "Zerus2", "Texture")],
        )
        self.assertEqual(pipeline.stem_of(refs[1]), "zerus_2normal")

    def test_no_upscaled_file_reuses_a_game_file_name(self) -> None:
        # The game's texture size table is keyed by file name alone.
        refs = self.refs()
        game_names = {ref.casc_path.rsplit("\\", 1)[-1] for ref in refs}
        for ref in refs:
            name = ref.map_path.rsplit("\\", 1)[-1]
            self.assertTrue(name.startswith(HD_PREFIX), name)
            self.assertNotIn(name.lower(), game_names)

    def test_the_maps_own_catalog_is_read_last(self) -> None:
        catalog = self.map_dir / "Base.SC2Data" / "GameData" / "TerrainTexData.xml"
        catalog.parent.mkdir(parents=True)
        catalog.write_text(
            '<Catalog><CTerrainTex id="Zerus1"><Texture value="Assets\\Textures\\Zerus_2.dds"/></CTerrainTex></Catalog>'
        )
        refs = self.refs()
        shared = next(ref for ref in refs if ref.asset == "Assets\\Textures\\Zerus_2.dds")
        self.assertEqual([o.entry for o in shared.overrides], ["Zerus2", "Zerus1"])
        self.assertNotIn("Assets\\Textures\\Zerus_1.dds", [ref.asset for ref in refs])

    def test_a_texture_the_game_does_not_know_is_an_error(self) -> None:
        write_map(self.map_dir, ("Zerus1", "Zerus9"))
        with self.assertRaises(SourceError):
            self.refs()

    def test_a_template_value_is_an_error(self) -> None:
        casc = FakeCasc()
        path = next(path for path in casc.files if path.endswith("terraintexdata.xml"))
        casc.files[path] = casc.files[path].replace(b"Assets\\Textures\\Zerus_1.dds", b"Assets\\Textures\\##id##.dds")
        with self.assertRaises(SourceError):
            self.refs(casc)

    def test_a_map_that_already_points_at_upscaled_files_is_an_error(self) -> None:
        catalog = self.map_dir / "Base.SC2Data" / "GameData" / "TerrainTexData.xml"
        catalog.parent.mkdir(parents=True)
        catalog.write_text(
            f'<Catalog><CTerrainTex id="Zerus1"><Texture value="{HD_DIR}\\Zerus_1.dds"/></CTerrainTex></Catalog>'
        )
        with self.assertRaises(SourceError):
            self.refs()

    def test_a_file_missing_from_the_storage_is_an_error(self) -> None:
        casc = FakeCasc()
        del casc.files[f"{TEXTURE_FOLDER}zerus_1normal.dds"]
        with self.assertRaises(SourceError):
            self.refs(casc)


class ModelChoiceTest(unittest.TestCase):
    color = roles.Plane("color")

    def test_the_plane_default_applies_to_a_plain_texture(self) -> None:
        self.assertEqual(pipeline.Settings().model_for(self.color, "zerus_1"), "pbrify")

    def test_the_texture_default_beats_the_plane_default(self) -> None:
        self.assertEqual(variants.VARIANTS["upscale"].textures["zerus_4.color"], "fast")
        self.assertEqual(pipeline.Settings().model_for(self.color, "zerus_4"), "fast")

    def test_the_variant_sets_the_defaults(self) -> None:
        generative = pipeline.Settings(variant="generative")
        self.assertEqual(generative.model_for(self.color, "zerus_1"), "seedvr2")
        self.assertEqual(generative.model_for(self.color, "zerus_4"), "seedvr2")
        self.assertEqual(generative.model_for(roles.Plane("alpha"), "zerus_1"), "fast")
        self.assertEqual(generative.model_for(roles.Plane("normal"), "zerus_1normal"), "fast")
        asked = pipeline.Settings(variant="generative", models=(("color", "other"),))
        self.assertEqual(asked.model_for(self.color, "zerus_1"), "other")

    def test_the_variants_have_their_titles(self) -> None:
        self.assertEqual({key: variant.title for key, variant in variants.VARIANTS.items()}, {"upscale": "Upscale 4x", "generative": "Generative 4x"})
        self.assertEqual({key: variant.key for key, variant in variants.VARIANTS.items()}, {"upscale": "upscale", "generative": "generative"})

    def test_the_flag_names_a_variant_or_off(self) -> None:
        cases = {None: ("upscale", False), "": ("upscale", False), "upscale": ("upscale", True), "Generative": ("generative", True), "off": (None, True)}
        for value, wanted in cases.items():
            env = {} if value is None else {variants.ENV: value}
            with mock.patch.dict(os.environ, env):
                if value is None:
                    os.environ.pop(variants.ENV, None)
                self.assertEqual(tuple(variants.chosen()), wanted, value)
        for value in ("1", "seedvr2", "upscale 4x"):
            with mock.patch.dict(os.environ, {variants.ENV: value}), self.assertRaises(variants.VariantError, msg=value):
                variants.chosen()

    def test_an_asked_plane_beats_the_texture_default(self) -> None:
        settings = pipeline.Settings(models=(("color", "other"),))
        self.assertEqual(settings.model_for(self.color, "zerus_4"), "other")
        self.assertEqual(settings.model_for(self.color, "zerus_1"), "other")

    def test_an_asked_texture_beats_an_asked_plane(self) -> None:
        settings = pipeline.Settings(models=(("color", "other"), ("zerus_1.color", "third")))
        self.assertEqual(settings.model_for(self.color, "zerus_1"), "third")
        self.assertEqual(settings.model_for(self.color, "zerus_2"), "other")

    def test_unknown_keys_are_reported(self) -> None:
        known = {"zerus_1.color", "zerus_1.alpha"}
        settings = pipeline.Settings(models=(("color", "a"), ("zerus_1.alpha", "b"), ("zerus_9.color", "c")))
        self.assertEqual(settings.unknown_models(known), ["zerus_9.color"])
        self.assertEqual(pipeline.Settings(models=(("normal", "a"),)).unknown_models(known), ["normal"])


class CommandLineTest(unittest.TestCase):
    def texture(self, **changes) -> dict:
        entry = {
            "file": "dds/missing.dds",
            "sha256": "",
            "encode_psnr": [40.0, 40.0, 40.0, 99.0],
            "fidelity_corr": [0.9, 0.9, 0.9, None],
            "coarse_rmse": 0.5,
            "seam": 1.2,
            "seam_source": 1.0,
        }
        entry.update(changes)
        return entry

    def problems(self, **changes) -> list[str]:
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "dds" / "t.dds"
            target.parent.mkdir()
            target.write_bytes(b"texture")
            entry = self.texture(file="dds/t.dds", sha256=pipeline.file_sha256(target))
            entry.update(changes)
            return hd_textures.texture_problems(Path(folder), entry)

    def test_models_parse_per_plane_and_per_texture(self) -> None:
        pairs = hd_textures.parse_models(["color=fast", "Zerus_4.color=pbrify"])
        self.assertEqual(pairs, (("color", "fast"), ("zerus_4.color", "pbrify")))

    def test_bad_models_are_rejected(self) -> None:
        for value in ("bogus=fast", "color=", "color", "zerus_4.bogus=fast"):
            with self.assertRaises(SystemExit, msg=value):
                hd_textures.parse_models([value])

    def test_a_good_texture_has_no_problems(self) -> None:
        self.assertEqual(self.problems(), [])

    def test_a_missing_file_is_a_problem(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(hd_textures.texture_problems(Path(folder), self.texture()), ["file is missing"])

    def test_each_limit_is_checked(self) -> None:
        cases = {
            "hash": {"sha256": "0"},
            "PSNR": {"encode_psnr": [40.0, hd_textures.MIN_ENCODE_PSNR - 0.1, 40.0, 99.0]},
            "correlation": {"fidelity_corr": [0.9, hd_textures.MIN_FIDELITY_CORR - 0.01, 0.9, None]},
            "coarse": {"coarse_rmse": hd_textures.MAX_COARSE_RMSE + 0.01},
            "seam": {"seam": hd_textures.MAX_SEAM_GROWTH + 0.01},
        }
        for word, change in cases.items():
            problems = self.problems(**change)
            self.assertEqual(len(problems), 1, word)
            self.assertIn(word, problems[0])

    def test_a_seam_the_source_already_has_is_allowed(self) -> None:
        self.assertEqual(self.problems(seam=3.4, seam_source=2.9), [])
        self.assertEqual(len(self.problems(seam=4.4, seam_source=2.9)), 1)


if __name__ == "__main__":
    unittest.main()
