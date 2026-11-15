from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

import numpy as np
from PIL import Image

from hdtex import check, dds, inject, pipeline, roles, upscaler, variants
from hdtex.sources import HD_DIR, HD_PREFIX, terrain_texture_ids
from project_root import project_root
from testkit.tests.hdtex_fixtures import NORMAL_TRAILER, SIZE, FakeCasc, FakeUpscaler, write_map

BUILT_MAP = project_root() / "out" / "SCOBA256.SC2Map"
HD_FOLDER = Path(*HD_DIR.split("\\"))
CATALOG = Path("Base.SC2Data") / "GameData" / "TerrainTexData.xml"


class CacheCase(unittest.TestCase):
    """A temp map and a temp cache, with the storage and the upscaler faked."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.map_dir = write_map(root / "map")
        self.cache = root / "cache"
        self.folder = self.cache / variants.DEFAULT / "terrain"
        self.upscaler = FakeUpscaler()
        self.tool_version = "tool-1"
        patches = (
            mock.patch.dict(os.environ, {"SC2_HDTEX_CACHE": str(self.cache)}),
            mock.patch.object(pipeline.upscaler, "run", self.upscaler),
            mock.patch.object(pipeline.upscaler, "version", lambda: self.tool_version),
        )
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        os.environ.pop(variants.ENV, None)  # the patch above puts it back

    def build(self, settings: pipeline.Settings | None = None, numbers: tuple[int, ...] = (1, 2)) -> dict:
        with contextlib.redirect_stdout(io.StringIO()):
            path = pipeline.build("terrain", self.map_dir, settings or pipeline.Settings(), casc=FakeCasc(numbers))
        return json.loads(path.read_text())

    def inject(self, flag: str | None = None) -> int:
        """Run the build step, with SC2_HD_TEXTURES set to `flag` when given."""
        values = {} if flag is None else {variants.ENV: flag}
        with mock.patch.dict(os.environ, values), contextlib.redirect_stdout(io.StringIO()) as self.output:
            return inject.apply_hd_textures(self.map_dir)

    def check_fails(self, word: str) -> None:
        errors = io.StringIO()
        with contextlib.redirect_stderr(errors), self.assertRaises(SystemExit):
            check.check_hd_textures(self.map_dir)
        self.assertIn(word, errors.getvalue())


class PipelineTest(CacheCase):
    def test_build_writes_enlarged_textures_with_full_mip_chains(self) -> None:
        manifest = self.build()
        self.assertEqual(len(manifest["textures"]), 4)
        for entry in manifest["textures"]:
            texture = dds.parse((self.folder / entry["file"]).read_bytes())
            self.assertEqual((texture.width, texture.height), (SIZE * 4, SIZE * 4))
            self.assertEqual(len(texture.levels), dds.full_mip_count(SIZE * 4, SIZE * 4))
            self.assertEqual(entry["size"], [SIZE * 4, SIZE * 4])
            self.assertEqual(texture.trailer, NORMAL_TRAILER if entry["role"] == "normal" else b"")
            # Nearest-neighbour enlarging adds nothing, so the result must match its source closely.
            self.assertGreater(min(v for v in entry["fidelity_corr"] if v is not None), 0.95)
            self.assertLess(entry["coarse_rmse"], 1.5)

    def test_each_plane_goes_to_its_model(self) -> None:
        manifest = self.build()
        self.assertEqual(
            manifest["settings"]["models"],
            {
                "zerus_1.alpha": "fast",
                "zerus_1.color": "pbrify",
                "zerus_1normal.normal": "fast",
                "zerus_2.alpha": "fast",
                "zerus_2.color": "pbrify",
                "zerus_2normal.normal": "fast",
            },
        )
        self.assertEqual(
            self.upscaler.runs,
            [
                ("fast", ["zerus_1.alpha.png", "zerus_1normal.normal.png", "zerus_2.alpha.png", "zerus_2normal.normal.png"]),
                ("pbrify", ["zerus_1.color.png", "zerus_2.color.png"]),
            ],
        )

    def test_a_second_build_redoes_nothing(self) -> None:
        self.build()
        target = self.folder / "dds" / f"{HD_PREFIX}Zerus_1.dds"
        before = target.stat().st_mtime_ns
        self.upscaler.runs.clear()
        self.build()
        self.assertEqual(self.upscaler.runs, [])
        self.assertEqual(target.stat().st_mtime_ns, before)

    def test_another_version_of_the_upscaler_redoes_every_plane(self) -> None:
        first = self.build()
        self.assertEqual(first["upscaler"], "tool-1")
        self.upscaler.runs.clear()
        self.tool_version = "tool-2"
        second = self.build()
        self.assertEqual(second["upscaler"], "tool-2")
        self.assertEqual(sorted(name for _model, names in self.upscaler.runs for name in names), sorted(f"{key}.png" for key in second["settings"]["models"]))
        self.upscaler.runs.clear()
        self.build()
        self.assertEqual(self.upscaler.runs, [])

    def test_a_model_change_redoes_only_that_plane(self) -> None:
        self.build()
        other = self.folder / "dds" / f"{HD_PREFIX}Zerus_2.dds"
        before = other.stat().st_mtime_ns
        self.upscaler.runs.clear()
        manifest = self.build(pipeline.Settings(models=(("zerus_1.color", "fast"),)))
        self.assertEqual(self.upscaler.runs, [("fast", ["zerus_1.color.png"])])
        self.assertEqual(manifest["settings"]["models"]["zerus_1.color"], "fast")
        self.assertEqual(manifest["settings"]["models"]["zerus_2.color"], "pbrify")
        self.assertEqual(other.stat().st_mtime_ns, before)

    def test_a_model_for_a_texture_the_map_lacks_is_an_error(self) -> None:
        with self.assertRaises(roles.RoleError):
            self.build(pipeline.Settings(models=(("zerus_9.color", "fast"),)))
        self.assertEqual(self.upscaler.runs, [])

    def test_max_size_drops_the_largest_levels(self) -> None:
        manifest = self.build(pipeline.Settings(max_size=SIZE * 2))
        for entry in manifest["textures"]:
            self.assertEqual(entry["size"], [SIZE * 2, SIZE * 2])
            self.assertEqual(entry["mips"], dds.full_mip_count(SIZE * 2, SIZE * 2))


class UpscalerToolTest(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        for name in ("arc-upscale", "upscale.py", "uv.lock"):
            (self.root / name).write_text(name)
        patch = mock.patch.dict(os.environ, {"ARC_UPSCALE": str(self.root / "arc-upscale")})
        patch.start()
        self.addCleanup(patch.stop)

    def test_the_version_follows_the_code_and_the_locked_dependencies(self) -> None:
        first = upscaler.version()
        self.assertEqual(upscaler.version(), first)
        (self.root / "upscale.py").write_text("changed")
        second = upscaler.version()
        self.assertNotEqual(second, first)
        (self.root / "uv.lock").write_text("changed")
        self.assertNotIn(upscaler.version(), (first, second))

    def test_an_incomplete_checkout_is_an_error(self) -> None:
        (self.root / "uv.lock").unlink()
        with self.assertRaises(upscaler.UpscaleError):
            upscaler.version()


class InjectTest(CacheCase):
    def catalog_values(self) -> dict[tuple[str, str], str]:
        root = ET.parse(self.map_dir / CATALOG).getroot()
        return {(node.get("id"), child.tag): child.get("value") for node in root for child in node}

    def test_without_a_cache_the_map_is_left_alone(self) -> None:
        self.assertEqual(self.inject(), 0)
        self.assertIn("built-in textures", self.output.getvalue())
        self.assertFalse((self.map_dir / CATALOG).exists())
        self.assertFalse((self.map_dir / HD_FOLDER).exists())
        check.check_hd_textures(self.map_dir)

    def test_the_flag_turns_the_step_off(self) -> None:
        self.build()
        self.assertEqual(self.inject(variants.OFF), 0)
        self.assertIn("built-in textures", self.output.getvalue())
        self.assertFalse((self.map_dir / HD_FOLDER).exists())
        self.assertFalse((self.map_dir / CATALOG).exists())

    def test_textures_and_overrides_land_in_the_map(self) -> None:
        manifest = self.build()
        self.assertEqual(self.inject(), 4)
        for entry in manifest["textures"]:
            copy = self.map_dir / HD_FOLDER / Path(entry["file"]).name
            self.assertEqual(pipeline.file_sha256(copy), entry["sha256"])
        self.assertEqual(
            self.catalog_values(),
            {
                ("Zerus1", "Texture"): f"{HD_DIR}\\{HD_PREFIX}Zerus_1.dds",
                ("Zerus1", "Normalmap"): f"{HD_DIR}\\{HD_PREFIX}Zerus_1Normal.dds",
                ("Zerus2", "Texture"): f"{HD_DIR}\\{HD_PREFIX}Zerus_2.dds",
                ("Zerus2", "Normalmap"): f"{HD_DIR}\\{HD_PREFIX}Zerus_2Normal.dds",
            },
        )
        check.check_hd_textures(self.map_dir)

    def test_other_catalog_content_is_kept(self) -> None:
        self.build()
        (self.map_dir / CATALOG).parent.mkdir(parents=True)
        (self.map_dir / CATALOG).write_text(
            '<Catalog><CTerrainTex id="Zerus1"><Texture value="old.dds"/><Lookup value="Zerus"/></CTerrainTex>'
            '<CTerrainTex id="Other"><Texture value="other.dds"/></CTerrainTex></Catalog>'
        )
        self.inject()
        values = self.catalog_values()
        self.assertEqual(values["Zerus1", "Texture"], f"{HD_DIR}\\{HD_PREFIX}Zerus_1.dds")
        self.assertEqual(values["Zerus1", "Lookup"], "Zerus")
        self.assertEqual(values["Other", "Texture"], "other.dds")

    def test_a_cached_file_that_changed_is_an_error(self) -> None:
        self.build()
        with (self.folder / "dds" / f"{HD_PREFIX}Zerus_1.dds").open("ab") as stream:
            stream.write(b"x")
        with self.assertRaises(inject.InjectError):
            self.inject()

    def test_a_cached_file_that_is_gone_is_an_error(self) -> None:
        self.build()
        (self.folder / "dds" / f"{HD_PREFIX}Zerus_2Normal.dds").unlink()
        with self.assertRaises(inject.InjectError):
            self.inject()

    def test_a_texture_the_cache_lacks_is_an_error(self) -> None:
        self.build()
        write_map(self.map_dir, ("Zerus1", "Zerus2", "Zerus3"))
        with self.assertRaises(inject.InjectError) as raised:
            self.inject()
        self.assertIn("Zerus3", str(raised.exception))
        self.assertFalse((self.map_dir / HD_FOLDER).exists())

    def test_another_manifest_format_is_an_error(self) -> None:
        self.build()
        path = self.folder / pipeline.MANIFEST
        manifest = json.loads(path.read_text())
        manifest["format"] = pipeline.MANIFEST_FORMAT + 1
        path.write_text(json.dumps(manifest))
        with self.assertRaises(inject.InjectError):
            self.inject()


class VariantTest(CacheCase):
    """Two variants side by side, and the build flag that picks one."""

    GENERATIVE = pipeline.Settings(variant="generative")

    def hashes(self, manifest: dict) -> dict[str, str]:
        return {Path(entry["file"]).name: entry["sha256"] for entry in manifest["textures"]}

    def map_hashes(self) -> dict[str, str]:
        return {path.name: pipeline.file_sha256(path) for path in sorted((self.map_dir / HD_FOLDER).glob("*.dds"))}

    def test_a_variant_builds_into_its_own_folder_and_leaves_the_other_alone(self) -> None:
        upscale = self.build()
        target = self.folder / "dds" / f"{HD_PREFIX}Zerus_1.dds"
        before = (target.stat().st_mtime_ns, (self.folder / pipeline.MANIFEST).read_bytes())
        self.upscaler.runs.clear()
        generative = self.build(self.GENERATIVE)
        self.assertEqual((upscale["variant"], generative["variant"]), ("upscale", "generative"))
        self.assertTrue((self.cache / "generative" / "terrain" / "dds" / f"{HD_PREFIX}Zerus_1.dds").is_file())
        self.assertEqual((target.stat().st_mtime_ns, (self.folder / pipeline.MANIFEST).read_bytes()), before)
        self.assertEqual(generative["settings"]["models"]["zerus_1.color"], "seedvr2")
        self.assertEqual(generative["settings"]["models"]["zerus_1.alpha"], "fast")
        self.assertEqual(generative["settings"]["models"]["zerus_1normal.normal"], "fast")
        self.assertIn(("seedvr2", ["zerus_1.color.png", "zerus_2.color.png"]), self.upscaler.runs)
        self.assertNotIn("pbrify", [model for model, _names in self.upscaler.runs])

    def test_generative_colour_starts_from_the_upscaled_colour_at_half_size(self) -> None:
        self.build()
        self.upscaler.runs.clear()
        manifest = self.build(self.GENERATIVE)
        upscaled = np.asarray(Image.open(self.folder / "upscaled" / "pbrify" / "zerus_1.color.png").convert("RGB"))
        given = np.asarray(Image.open(self.cache / "generative" / "terrain" / "planes" / "seedvr2" / "zerus_1.color.png"))
        self.assertEqual(given.shape[:2], (SIZE * 2, SIZE * 2))
        self.assertTrue(np.array_equal(given, roles.shrink_color(upscaled, 2)))
        # The other planes still come from the original.
        alpha = np.asarray(Image.open(self.cache / "generative" / "terrain" / "planes" / "fast" / "zerus_1.alpha.png"))
        self.assertEqual(alpha.shape[:2], (SIZE, SIZE))
        # seedvr2 got 2x input and gave 8x; the file is still 4x, with a full chain.
        for entry in manifest["textures"]:
            self.assertEqual(entry["size"], [SIZE * 4, SIZE * 4])
            self.assertEqual(entry["mips"], dds.full_mip_count(SIZE * 4, SIZE * 4))

    def test_generative_needs_the_upscale_cache(self) -> None:
        with self.assertRaises(pipeline.InputError) as raised:
            self.build(self.GENERATIVE)
        self.assertIn("--variant upscale build", str(raised.exception))
        self.assertNotIn("seedvr2", [model for model, _names in self.upscaler.runs])

    def test_a_new_upscaled_colour_redoes_only_its_generative_texture(self) -> None:
        self.build()
        self.build(self.GENERATIVE)
        source = self.folder / "upscaled" / "pbrify" / "zerus_1.color.png"
        image = np.asarray(Image.open(source).convert("RGB")).copy()
        image[0, 0] = 255 - image[0, 0]
        Image.fromarray(image).save(source)
        self.upscaler.runs.clear()
        self.build(self.GENERATIVE)
        self.assertEqual(self.upscaler.runs, [("seedvr2", ["zerus_1.color.png"])])

    def test_the_variants_differ_in_colour_files_only(self) -> None:
        upscale, generative = self.hashes(self.build()), self.hashes(self.build(self.GENERATIVE))
        self.assertEqual(sorted(upscale), sorted(generative))
        for name in upscale:
            same = upscale[name] == generative[name]
            self.assertEqual(same, "Normal" in name, name)

    def test_the_flag_picks_the_variant(self) -> None:
        upscale, generative = self.hashes(self.build()), self.hashes(self.build(self.GENERATIVE))
        self.assertEqual(self.inject("generative"), 4)
        self.assertIn("Generative 4x", self.output.getvalue())
        self.assertEqual(self.map_hashes(), generative)
        self.assertNotEqual(self.map_hashes(), upscale)
        self.assertEqual(inject.variant_in_map(self.map_dir), "generative")
        check.check_hd_textures(self.map_dir)
        self.assertEqual(self.inject("upscale"), 4)
        self.assertIn("Upscale 4x", self.output.getvalue())
        self.assertEqual(self.map_hashes(), upscale)
        self.assertEqual(inject.variant_in_map(self.map_dir), "upscale")

    def test_without_the_flag_the_default_variant_is_used(self) -> None:
        upscale = self.hashes(self.build())
        self.build(self.GENERATIVE)
        self.assertEqual(variants.DEFAULT, "upscale")
        self.assertEqual(self.inject(), 4)
        self.assertEqual(self.map_hashes(), upscale)

    def test_a_map_without_upscaled_files_holds_no_variant(self) -> None:
        self.build()
        self.assertIsNone(inject.variant_in_map(self.map_dir))

    def test_a_variant_asked_by_name_needs_its_cache(self) -> None:
        self.build()
        with self.assertRaises(inject.InjectError) as raised:
            self.inject("generative")
        self.assertIn("--variant generative build", str(raised.exception))
        self.assertFalse((self.map_dir / HD_FOLDER).exists())
        self.assertFalse((self.map_dir / CATALOG).exists())

    def test_an_unknown_variant_is_an_error(self) -> None:
        self.build()
        with self.assertRaises(inject.InjectError) as raised:
            self.inject("sharper")
        self.assertIn("sharper", str(raised.exception))
        self.assertFalse((self.map_dir / HD_FOLDER).exists())

    def test_a_cache_folder_with_another_variant_in_it_is_an_error(self) -> None:
        self.build()
        (self.cache / "upscale").rename(self.cache / "generative")
        with self.assertRaises(inject.InjectError) as raised:
            self.inject("generative")
        self.assertIn("holds variant upscale", str(raised.exception))
        self.assertFalse((self.map_dir / HD_FOLDER).exists())


class CheckTest(CacheCase):
    def setUp(self) -> None:
        super().setUp()
        self.build()
        self.inject()

    def test_a_complete_map_passes(self) -> None:
        check.check_hd_textures(self.map_dir)

    def test_a_missing_file_fails(self) -> None:
        (self.map_dir / HD_FOLDER / f"{HD_PREFIX}Zerus_1.dds").unlink()
        self.check_fails("zerus_1.dds")

    def test_a_file_no_catalog_points_at_fails(self) -> None:
        source = self.map_dir / HD_FOLDER / f"{HD_PREFIX}Zerus_1.dds"
        (self.map_dir / HD_FOLDER / "Stray.dds").write_bytes(source.read_bytes())
        self.check_fails("stray.dds")

    def test_a_file_named_like_the_original_fails(self) -> None:
        # The game sizes a texture by its file name, so the original's name must not be reused.
        folder = self.map_dir / HD_FOLDER
        (folder / f"{HD_PREFIX}Zerus_1.dds").rename(folder / "Zerus_1.dds")
        catalog = self.map_dir / CATALOG
        catalog.write_text(catalog.read_text().replace(f"{HD_PREFIX}Zerus_1.dds", "Zerus_1.dds"))
        self.check_fails("must start with")

    def test_a_partly_upscaled_terrain_fails(self) -> None:
        write_map(self.map_dir, ("Zerus1", "Zerus2", "Zerus3"))
        self.check_fails("Zerus3")

    def test_a_short_mip_chain_fails(self) -> None:
        target = self.map_dir / HD_FOLDER / f"{HD_PREFIX}Zerus_1.dds"
        texture = dds.parse(target.read_bytes())
        blobs = [texture.level_bytes(index) for index in range(len(texture.levels) - 1)]
        target.write_bytes(dds.build(texture.width, texture.height, blobs))
        self.check_fails("mip chain")

    def test_a_file_that_is_not_a_texture_fails(self) -> None:
        (self.map_dir / HD_FOLDER / f"{HD_PREFIX}Zerus_1.dds").write_bytes(b"not a texture")
        self.check_fails("Zerus_1.dds")


class MapSourceTest(unittest.TestCase):
    def test_the_map_source_holds_no_upscaled_files(self) -> None:
        source = project_root() / "src" / "SCOBA.SC2Map"
        self.assertFalse((source / HD_FOLDER).exists())
        self.assertEqual(check.hd_references(source), set())


class BuiltMapTest(unittest.TestCase):
    @unittest.skipUnless((BUILT_MAP / HD_FOLDER).is_dir(), "the built map has no upscaled textures")
    def test_the_built_map_replaces_every_terrain_texture(self) -> None:
        check.check_hd_textures(BUILT_MAP)
        root = ET.parse(BUILT_MAP / CATALOG).getroot()
        values = {(node.get("id"), child.tag): child.get("value") for node in root for child in node}
        for entry in terrain_texture_ids(BUILT_MAP):
            for field in ("Texture", "Normalmap"):
                value = values[entry, field]
                self.assertTrue(value.startswith(f"{HD_DIR}\\{HD_PREFIX}"), value)
                self.assertTrue((BUILT_MAP / Path(*value.split("\\"))).is_file(), value)

    @unittest.skipUnless((BUILT_MAP / HD_FOLDER).is_dir(), "the built map has no upscaled textures")
    def test_the_built_map_holds_the_variant_the_flag_names(self) -> None:
        self.assertEqual(inject.variant_in_map(BUILT_MAP), variants.chosen().key)


if __name__ == "__main__":
    unittest.main()
