"""The texture store: planes, upscale folders, variants, names (R-HD-85 to 87, R-HD-100, R-HD-120)."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import workpaths
from hdtex.core import store
from hdtex.core.store import Store, StoreError
from PIL import Image

ORIGIN = "storage\\mods\\one\\assets\\textures\\rock.dds"


class StoreCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "store"
        self.game = Store(self.root).game("testgame")


class PlaceTest(StoreCase):
    def test_one_setting_names_the_store(self) -> None:
        with mock.patch.dict(os.environ, {store.ENV: str(self.root)}):
            self.assertEqual(store.store_root(), self.root)
        with mock.patch.dict(os.environ):
            os.environ.pop(store.ENV, None)
            with self.assertRaises(workpaths.PathsError):
                store.store_root()

    def test_a_new_store_says_its_layout(self) -> None:
        self.assertEqual((self.root / "format").read_text(), f"{store.FORMAT}\n")
        Store(self.root)

    def test_a_folder_that_is_no_store_is_refused(self) -> None:
        other = Path(self.temp.name) / "other"
        other.mkdir()
        (other / "note.txt").write_text("x")
        with self.assertRaises(StoreError):
            Store(other)
        self.assertEqual(sorted(path.name for path in other.iterdir()), ["note.txt"])

    def test_another_layout_is_refused(self) -> None:
        (self.root / "format").write_text("99\n")
        with self.assertRaises(StoreError):
            Store(self.root)

    def test_names_that_leave_the_store_are_refused(self) -> None:
        for name in ("../x", "A", "", "a/b", ".hidden"):
            with self.assertRaises(StoreError, msg=name):
                Store(self.root).game(name)
            with self.assertRaises(StoreError, msg=name):
                self.game.dataset_dir(name)
        self.assertEqual(self.game.dataset_dir("scoba-2").name, "scoba-2")


class PlaneTest(StoreCase):
    def test_a_plane_comes_back_as_it_went_in(self) -> None:
        rng = np.random.default_rng(1)
        for shape in ((8, 4), (8, 4, 3)):
            plane = rng.integers(0, 256, shape, dtype=np.uint8)
            key = self.game.put_plane(plane)
            self.assertTrue(np.array_equal(self.game.get_plane(key), plane))

    def test_equal_pixels_share_one_file(self) -> None:
        plane = np.full((4, 4), 7, dtype=np.uint8)
        first = self.game.put_plane(plane)
        stamp = self.game.plane_path(first).stat().st_mtime_ns
        self.assertEqual(self.game.put_plane(plane.copy()), first)
        self.assertEqual(self.game.plane_path(first).stat().st_mtime_ns, stamp)
        self.assertEqual(len(list(self.game.planes.rglob("*.png"))), 1)

    def test_other_pixels_or_another_shape_get_another_name(self) -> None:
        plane = np.zeros((4, 8), dtype=np.uint8)
        keys = {
            store.plane_key(plane),
            store.plane_key(plane.reshape(8, 4)),
            store.plane_key(plane + 1),
        }
        self.assertEqual(len(keys), 3)

    def test_what_is_no_plane_is_refused(self) -> None:
        with self.assertRaises(StoreError):
            self.game.put_plane(np.zeros((4, 4), dtype=np.float32))
        with self.assertRaises(StoreError):
            self.game.get_plane("0" * 64)

    def test_a_changed_file_is_refused(self) -> None:
        key = self.game.put_plane(np.zeros((4, 4), dtype=np.uint8))
        Image.fromarray(np.ones((4, 4), dtype=np.uint8)).save(self.game.plane_path(key))
        with self.assertRaises(StoreError):
            self.game.get_plane(key)

    def test_an_image_the_upscaler_wrote_is_read_as_a_plane(self) -> None:
        pixels = np.arange(48, dtype=np.uint8).reshape(4, 4, 3)
        source = Path(self.temp.name) / "out.png"
        Image.fromarray(pixels).save(source)
        self.assertTrue(np.array_equal(store.read_plane(source), pixels))
        Image.fromarray(pixels).convert("RGBA").save(source)
        self.assertTrue(np.array_equal(store.read_plane(source), pixels))

    def test_half_an_image_is_refused(self) -> None:
        source = Path(self.temp.name) / "out.png"
        Image.fromarray(
            np.random.default_rng(2).integers(0, 256, (64, 64, 3), dtype=np.uint8)
        ).save(source)
        source.write_bytes(source.read_bytes()[:400])
        with self.assertRaises(StoreError):
            store.read_plane(source)
        source.write_bytes(b"not an image")
        with self.assertRaises(StoreError):
            store.read_plane(source)


class UpscaleFolderTest(StoreCase):
    def test_equal_recipes_share_one_folder(self) -> None:
        self.assertEqual(
            self.game.upscale_dir("in", "fast", "v1"),
            self.game.upscale_dir("in", "fast", "v1"),
        )
        self.assertEqual(
            self.game.upscale_dir("in", "fast", "v1").parent, self.game.upscaled
        )

    def test_another_input_model_or_version_is_another_folder(self) -> None:
        folders = {
            self.game.upscale_dir("in", "fast", "v1"),
            self.game.upscale_dir("other", "fast", "v1"),
            self.game.upscale_dir("in", "pbrify", "v1"),
            self.game.upscale_dir("in", "fast", "v2"),
        }
        self.assertEqual(len(folders), 4)


class SizeTest(unittest.TestCase):
    def test_a_result_is_kept_at_its_own_size_and_the_levels_down_to_1024(self) -> None:
        self.assertEqual(store.kept_sizes(4096), (4096, 2048, 1024))
        self.assertEqual(store.kept_sizes(2048), (2048, 1024))
        self.assertEqual(store.kept_sizes(1024), (1024,))
        self.assertEqual(store.kept_sizes(512), (512,))
        self.assertEqual(store.kept_sizes(3072), (3072, 1536, 768))


class RecipeTest(StoreCase):
    def test_a_recipe_is_its_files_and_its_entry(self) -> None:
        self.assertIsNone(self.game.entry(ORIGIN, "pbrify"))
        written = self.game.write_recipe(
            ORIGIN, "pbrify", {"role": "diffuse"}, {256: b"large", 128: b"small"}
        )
        self.assertEqual(self.game.entry(ORIGIN, "pbrify"), written)
        self.assertEqual(
            (written["origin"], written["recipe"], written["format"]),
            (ORIGIN, "pbrify", store.FORMAT),
        )
        self.assertEqual(sorted(written["files"]), ["128", "256"])
        self.assertEqual(
            self.game.variant_file(ORIGIN, "pbrify", 256).read_bytes(), b"large"
        )
        self.assertEqual(
            written["files"]["128"],
            {
                "sha256": store.file_sha256(
                    self.game.variant_file(ORIGIN, "pbrify", 128)
                ),
                "bytes": 5,
            },
        )
        self.assertEqual(
            self.game.recipe_dir(ORIGIN, "pbrify").parents[1], self.game.variants
        )

    def test_recipes_of_one_origin_stand_side_by_side(self) -> None:
        self.game.write_recipe(ORIGIN, "pbrify", {}, {256: b"first"})
        before = self.game.entry(ORIGIN, "pbrify")
        self.game.write_recipe(ORIGIN, "pbrify@4096+seedvr2", {}, {256: b"second"})
        self.assertEqual(self.game.recipes(ORIGIN), ["pbrify", "pbrify@4096+seedvr2"])
        self.assertEqual(self.game.entry(ORIGIN, "pbrify"), before)
        self.assertEqual(
            self.game.variant_file(ORIGIN, "pbrify", 256).read_bytes(), b"first"
        )

    def test_two_origins_with_one_file_name_do_not_share(self) -> None:
        other = "dataset\\mine\\assets\\textures\\rock.dds"
        self.assertNotEqual(store.origin_folder(ORIGIN), store.origin_folder(other))
        self.assertTrue(store.origin_folder(ORIGIN).startswith("rock.dds-"))
        self.game.write_recipe(ORIGIN, "pbrify", {}, {256: b"x"})
        self.assertIsNone(self.game.entry(other, "pbrify"))
        self.assertEqual(self.game.recipes(other), [])

    def test_a_recipe_that_cannot_be_written_leaves_nothing(self) -> None:
        with self.assertRaises(ValueError):
            self.game.write_recipe(
                ORIGIN, "pbrify", {"seam": float("inf")}, {256: b"x"}
            )
        self.assertIsNone(self.game.entry(ORIGIN, "pbrify"))
        self.assertEqual(list(self.game.recipe_dir(ORIGIN, "pbrify").iterdir()), [])

    def test_new_variants_replace_all_of_the_old_ones(self) -> None:
        self.game.write_recipe(ORIGIN, "pbrify", {}, {256: b"old", 128: b"old"})
        self.game.write_recipe(ORIGIN, "pbrify", {}, {64: b"new"})
        self.assertEqual(
            sorted(
                path.name for path in self.game.recipe_dir(ORIGIN, "pbrify").iterdir()
            ),
            ["64.dds", "entry.json"],
        )

    def test_a_dropped_recipe_is_gone_and_its_request_stays(self) -> None:
        self.game.write_recipe(ORIGIN, "pbrify", {}, {256: b"x"})
        note = self.game.recipe_dir(ORIGIN, "pbrify") / "request.json"
        note.write_text("{}")
        self.game.drop_recipe(ORIGIN, "pbrify")
        self.assertIsNone(self.game.entry(ORIGIN, "pbrify"))
        self.assertEqual(self.game.recipes(ORIGIN), [])
        self.assertEqual(list(self.game.recipe_dir(ORIGIN, "pbrify").iterdir()), [note])

    def test_an_entry_of_another_origin_or_format_is_refused(self) -> None:
        self.game.write_recipe(ORIGIN, "pbrify", {}, {256: b"x"})
        path = self.game.recipe_dir(ORIGIN, "pbrify") / store.ENTRY
        text = path.read_text()
        path.write_text(text.replace("rock", "sand"))
        with self.assertRaises(StoreError):
            self.game.entry(ORIGIN, "pbrify")
        path.write_text(text.replace(f'"format": {store.FORMAT}', '"format": 1'))
        with self.assertRaises(StoreError):
            self.game.entry(ORIGIN, "pbrify")


class LayoutTest(StoreCase):
    def test_a_store_of_another_layout_is_refused(self) -> None:
        (self.root / "format").write_text("1\n")
        with self.assertRaises(StoreError) as caught:
            Store(self.root)
        self.assertIn(f"this tooling reads layout {store.FORMAT}", str(caught.exception))
