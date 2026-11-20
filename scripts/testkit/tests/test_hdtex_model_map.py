"""Host tests for model textures in the map: injection, validation, the page, and the built map.

The real model reader is tested on the built map in BuiltModelsTest.
"""

from __future__ import annotations

import contextlib
import io
import json
import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from hdtex import (
    check,
    compare,
    inject,
    m3tex,
    models,
    roles,
    variants,
)
from hdtex.sources import HD_DIR

from testkit.tests.hdtex_model_fixtures import (
    BUILT_MAP,
    MODEL_CATALOG,
    FakeModels,
    ModelCase,
    layer,
    write_model_map,
)


class ModelInjectTest(ModelCase):
    def test_textures_models_and_overrides_land_in_the_map(self) -> None:
        manifest = self.build()
        self.assertEqual(self.inject(), 4)
        for entry in manifest["textures"]:
            self.assertTrue(self.map_file(entry["map_path"]).is_file())
        for name in ("Tree_00.m3", "Tree_01.m3", "Rock.m3", "CommandCenter.m3", "Psi.m3"):
            self.assertTrue(self.map_file(f"{models.HD_MODEL_DIR}\\{name}").is_file(), name)
        self.assertFalse(self.map_file(f"{models.HD_MODEL_DIR}\\Mist.m3").exists())
        root = ET.parse(self.map_dir / MODEL_CATALOG).getroot()
        values = {node.get("id"): node.find("Model").get("value") for node in root.iter("CModel")}
        self.assertEqual(
            values,
            {
                "Tree": f"{models.HD_MODEL_DIR}\\Tree.m3",
                "Rock": f"{models.HD_MODEL_DIR}\\Rock.m3",
                "CommandCenter": f"{models.HD_MODEL_DIR}\\CommandCenter.m3",
                "PsiDecimator": f"{models.HD_MODEL_DIR}\\Psi.m3",
            },
        )
        self.assertIn("5 model files", self.output.getvalue())

    def test_other_model_catalog_content_is_kept(self) -> None:
        self.build()
        catalog = self.map_dir / MODEL_CATALOG
        catalog.parent.mkdir(parents=True)
        catalog.write_text('<Catalog><CModel id="PsiDecimator"><ScaleMax value="3.5,3.5,3.5"/></CModel><CModel id="Other"><Occlusion value="None"/></CModel></Catalog>')
        self.inject()
        root = ET.parse(catalog).getroot()
        psi = next(node for node in root.iter("CModel") if node.get("id") == "PsiDecimator")
        self.assertEqual(psi.find("ScaleMax").get("value"), "3.5,3.5,3.5")
        self.assertEqual(psi.find("Model").get("value"), f"{models.HD_MODEL_DIR}\\Psi.m3")
        self.assertIsNotNone(next(node for node in root.iter("CModel") if node.get("id") == "Other").find("Occlusion"))

    def test_a_doodad_the_cache_has_not_seen_is_an_error(self) -> None:
        self.build()
        write_model_map(self.map_dir, ("Tree", "Rock", "Mist", "Bush"))
        with self.assertRaises(inject.InjectError) as raised:
            self.inject()
        self.assertIn("Bush", str(raised.exception))
        self.assertIn("--source models build", str(raised.exception))
        self.assertFalse(self.map_file(models.HD_MODEL_DIR).exists())

    def test_an_actor_the_map_build_made_is_covered_by_its_model(self) -> None:
        self.build()
        write_model_map(self.map_dir, ("Tree", "Rock", "Mist", "TreeFp9"))
        catalog = self.map_dir / "Base.SC2Data" / "GameData" / "ActorData.xml"
        catalog.parent.mkdir(parents=True)
        catalog.write_text('<Catalog><CActorDoodad id="TreeFp9" parent="Tree"><Model value="Tree"/></CActorDoodad></Catalog>')
        self.assertEqual(self.inject(), 4)

    def own_rock(self, layers: list[dict]) -> Path:
        path = self.map_file("Assets\\Doodads\\Rock\\Rock.m3")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(layers))
        return path

    def test_a_model_the_map_build_made_is_the_one_copied(self) -> None:
        own = [layer("Assets\\Textures\\rock_spec.dds", "specularLayer"), layer("Assets\\Textures\\own.dds", "decalLayer")]
        self.own_rock(own)
        rock = next(entry for entry in self.build()["models"] if entry["entry"] == "Rock")
        self.assertEqual(rock["files"][0]["casc_path"], models.MAP_MARK + "Assets\\Doodads\\Rock\\Rock.m3")
        copy = FakeModels.layers(FakeModels.load(self.folder / "m3" / "Rock.m3"))
        self.assertEqual([item.path for item in copy], [f"{HD_DIR}\\scoba_hd_m_rock_spec.dds", "Assets\\Textures\\own.dds"])
        self.inject()
        self.assertEqual(json.loads(self.map_file(f"{models.HD_MODEL_DIR}\\Rock.m3").read_text()), json.loads((self.folder / "m3" / "Rock.m3").read_text()))

    def test_a_map_model_that_changed_since_the_cache_is_an_error(self) -> None:
        own = self.own_rock([layer("Assets\\Textures\\rock_spec.dds", "specularLayer")])
        self.build()
        self.own_rock([layer("Assets\\Textures\\rock_spec.dds", "specularLayer"), layer("Assets\\Textures\\new.dds")])
        with self.assertRaises(inject.InjectError) as raised:
            self.inject()
        self.assertIn("Rock.m3", str(raised.exception))
        own.unlink()
        with self.assertRaises(inject.InjectError):
            self.inject()

    def test_a_map_model_that_appeared_since_the_cache_is_an_error(self) -> None:
        self.build()
        self.own_rock([layer("Assets\\Textures\\rock_spec.dds", "specularLayer")])
        with self.assertRaises(inject.InjectError):
            self.inject()

    def test_a_cached_model_that_changed_is_an_error(self) -> None:
        self.build()
        (self.folder / "m3" / "Rock.m3").write_text("[]")
        with self.assertRaises(inject.InjectError):
            self.inject()

    def test_the_map_holds_the_variant(self) -> None:
        self.build()
        self.inject()
        self.assertEqual(inject.variant_in_map(self.map_dir), variants.DEFAULT)
        self.map_file(f"{models.HD_MODEL_DIR}\\Rock.m3").write_text("[]")
        self.assertIsNone(inject.variant_in_map(self.map_dir))


class ModelCheckTest(ModelCase):
    """The check reads real files, so the copies get the mark of a model file and plain-text paths."""

    def setUp(self) -> None:
        super().setUp()
        self.build()
        self.inject()
        for path in self.map_file(models.HD_MODEL_DIR).glob("*.m3"):
            names = [item.path for item in FakeModels.layers(FakeModels.load(path))]
            path.write_bytes(b"43DM" + "\0".join(names).encode("ascii"))

    def test_a_complete_map_passes(self) -> None:
        check.check_hd_textures(self.map_dir)

    def test_a_texture_no_model_names_fails(self) -> None:
        self.map_file(f"{models.HD_MODEL_DIR}\\Psi.m3").write_bytes(b"43DM[]")
        self.map_file(f"{models.HD_MODEL_DIR}\\Rock.m3").write_bytes(b"43DM[]")
        self.check_fails("no catalog points at it")

    def test_a_model_file_that_is_gone_fails(self) -> None:
        self.map_file(f"{models.HD_MODEL_DIR}\\CommandCenter.m3").unlink()
        self.check_fails("no such model file")

    def test_a_model_file_no_entry_names_fails(self) -> None:
        self.map_file(f"{models.HD_MODEL_DIR}\\Stray.m3").write_bytes(b"43DM[]")
        self.check_fails("no model entry points at it")

    def test_a_file_that_is_not_a_model_fails(self) -> None:
        self.map_file(f"{models.HD_MODEL_DIR}\\Rock.m3").write_bytes(self.map_file(f"{models.HD_MODEL_DIR}\\Rock.m3").read_bytes()[4:])
        self.check_fails("not a model file")


class ModelComparePageTest(ModelCase):
    def pairs(self) -> tuple[Path, list[dict]]:
        with contextlib.redirect_stdout(io.StringIO()):
            page = compare.write_index()
        found = re.search(r"^const PAIRS = (.*);$", page.read_text(encoding="utf-8"), re.M)
        return page, json.loads(found.group(1))

    def test_every_plane_of_every_model_texture_is_on_the_page(self) -> None:
        manifest = self.build()
        page, pairs = self.pairs()
        self.assertEqual(page, self.cache / "compare" / "index.html")
        wanted = sorted(
            f"{entry['asset'].rsplit(chr(92), 1)[-1].rsplit('.', 1)[0]}.{plane.name}"
            for entry in manifest["textures"]
            for plane in roles.ROLES[entry["role"]].planes
        )
        self.assertEqual(sorted(pair["id"] for pair in pairs), wanted)
        self.assertEqual(len(wanted), 7)
        for pair in pairs:
            self.assertEqual(pair["source"], models.SOURCE)
            self.assertEqual([layer["variant"] for layer in pair["layers"]], ["Upscale 4x"])
            for image in (pair["before"], pair["thumb"], pair["layers"][0]["image"]):
                self.assertTrue((page.parent / image).is_file(), image)

    def test_a_texture_is_in_the_category_of_what_uses_it(self) -> None:
        self.build()
        by_texture = {pair["texture"]: pair for pair in self.pairs()[1]}
        self.assertEqual(by_texture["tree_normal.dds"]["category"], compare.DOODADS)
        self.assertEqual(by_texture["tree_normal.dds"]["users"], ["Tree"])
        self.assertEqual(by_texture["rock_normal.dds"]["category"], compare.DOODADS)
        # A doodad and a named unit both use these.
        self.assertEqual(by_texture["tree_diffuse.dds"]["category"], compare.SHARED)
        self.assertEqual(by_texture["tree_diffuse.dds"]["users"], ["CommandCenter", "Tree"])
        self.assertEqual(by_texture["rock_spec.dds"]["users"], ["PsiDecimator", "Rock"])
        self.assertEqual(by_texture["rock_spec.dds"]["format"], "DXT1")

    def test_a_texture_only_a_named_unit_uses_is_in_the_category_of_that_unit(self) -> None:
        write_model_map(self.map_dir, ("Mist",))
        self.build()
        categories = {pair["texture"]: pair["category"] for pair in self.pairs()[1]}
        self.assertEqual(categories, {"tree_diffuse.dds": "CommandCenter", "rock_spec.dds": "PsiDecimator"})


class BuiltModelsTest(unittest.TestCase):
    """The real model reader on the built map. Skipped when the map holds no patched models."""

    def setUp(self) -> None:
        self.files = check.hd_model_files(BUILT_MAP)
        if not self.files:
            self.skipTest("the built map holds no patched models")

    def test_every_patched_model_reads_and_names_files_of_the_map(self) -> None:
        folder = BUILT_MAP.joinpath(*HD_DIR.split("\\"))
        present = {path.name.lower() for path in folder.glob("*")}
        named = 0
        for path in self.files.values():
            for item in m3tex.layers(m3tex.load(path)):
                if item.path.lower().startswith(HD_DIR.lower() + "\\"):
                    self.assertIn(item.path.rsplit("\\", 1)[-1].lower(), present, path.name)
                    named += 1
        self.assertGreater(named, 0)

    def test_every_model_override_has_its_files(self) -> None:
        check.check_model_overrides(BUILT_MAP)


if __name__ == "__main__":
    unittest.main()
