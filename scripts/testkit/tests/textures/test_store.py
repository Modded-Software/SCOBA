"""The texture store: planes, upscale folders, variants, names (R-HD-85 to 87, R-HD-100, R-HD-120)."""

from __future__ import annotations

import os
import tempfile
import threading
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
            self.game.upscale_dir("in", "fast", "v1", True),
            self.game.upscale_dir("in", "fast", "v1", True),
        )
        self.assertEqual(
            self.game.upscale_dir("in", "fast", "v1", True).parent, self.game.upscaled
        )

    def test_another_input_model_version_or_edge_rule_is_another_folder(self) -> None:
        folders = {
            self.game.upscale_dir("in", "fast", "v1", True),
            self.game.upscale_dir("other", "fast", "v1", True),
            self.game.upscale_dir("in", "pbrify", "v1", True),
            self.game.upscale_dir("in", "fast", "v2", True),
            self.game.upscale_dir("in", "fast", "v1", False),
        }
        self.assertEqual(len(folders), 5)


class SizeTest(unittest.TestCase):
    def test_a_request_may_ask_for_the_own_size_its_half_and_the_levels_down_to_1024(self) -> None:
        self.assertEqual(store.offered_sizes(4096), (4096, 2048, 1024))
        self.assertEqual(store.offered_sizes(2048), (2048, 1024))
        self.assertEqual(store.offered_sizes(1024), (1024, 512), "its half: the 2x of a 256 input")
        self.assertEqual(store.offered_sizes(512), (512, 256))
        self.assertEqual(store.offered_sizes(3072), (3072, 1536, 768))
        self.assertEqual(store.offered_sizes(75), (75,), "negative: an odd side has no half")


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

    def test_a_kept_recipe_is_never_written_again(self) -> None:
        """R-HD-158: what a skin or a bake names stays as it was made."""
        self.game.write_recipe(ORIGIN, "pbrify", {}, {256: b"old", 128: b"old"})
        folder = self.game.recipe_dir(ORIGIN, "pbrify")
        # A person's mark, by hand: no program writes it (R-HD-161).
        store.write_json(folder / store.ENTRY, {**store.read_json(folder / store.ENTRY), "accepted": "a person looked"})
        before = {path.name: path.read_bytes() for path in sorted(folder.iterdir())}
        with self.assertRaisesRegex(StoreError, "pbrify.*is kept"):
            self.game.write_recipe(ORIGIN, "pbrify", {}, {256: b"new", 64: b"new"})
        # Negative: no file changed, none came, none went.
        self.assertEqual({path.name: path.read_bytes() for path in sorted(folder.iterdir())}, before)
        self.assertEqual(sorted(before), ["128.dds", "256.dds", "entry.json"])
        # A revision is another recipe: it is written beside it.
        self.game.write_recipe(ORIGIN, "pbrify~2", {}, {64: b"new"})
        self.assertEqual(self.game.recipes(ORIGIN), ["pbrify", "pbrify~2"])
        self.assertEqual({path.name: path.read_bytes() for path in sorted(folder.iterdir())}, before)

    def test_a_size_is_added_to_a_kept_recipe_and_nothing_else_changes(self) -> None:
        """R-HD-123, R-HD-6: a size asked for later stands beside the first. R-HD-158: no kept file changes."""
        self.game.write_recipe(ORIGIN, "pbrify", {"role": "diffuse"}, {128: b"small"})
        folder = self.game.recipe_dir(ORIGIN, "pbrify")
        store.write_json(folder / store.ENTRY, {**store.read_json(folder / store.ENTRY), "accepted": "a person looked"})
        before = self.game.entry(ORIGIN, "pbrify")
        written = self.game.add_size(ORIGIN, "pbrify", 256, b"large")
        self.assertEqual(self.game.entry(ORIGIN, "pbrify"), written)
        self.assertEqual(self.game.variant_file(ORIGIN, "pbrify", 256).read_bytes(), b"large")
        self.assertEqual(
            written["files"]["256"],
            {"sha256": store.file_sha256(self.game.variant_file(ORIGIN, "pbrify", 256)), "bytes": 5},
        )
        # Negative: the first file, its hash, the mark and every other key are as they were.
        self.assertEqual(self.game.variant_file(ORIGIN, "pbrify", 128).read_bytes(), b"small")
        self.assertEqual({**written, "files": before["files"]}, before)
        self.assertEqual(written["files"]["128"], before["files"]["128"])
        self.assertEqual(sorted(path.name for path in folder.iterdir()), ["128.dds", "256.dds", "entry.json"])

    def test_a_size_that_is_kept_is_never_written_again(self) -> None:
        self.game.write_recipe(ORIGIN, "pbrify", {}, {128: b"small"})
        folder = self.game.recipe_dir(ORIGIN, "pbrify")
        before = {path.name: path.read_bytes() for path in sorted(folder.iterdir())}
        with self.assertRaisesRegex(StoreError, "pbrify.*is kept at 128"):
            self.game.add_size(ORIGIN, "pbrify", 128, b"other")
        # Negative: no byte changed, the same bytes are refused too, and no file came.
        with self.assertRaisesRegex(StoreError, "is kept at 128"):
            self.game.add_size(ORIGIN, "pbrify", 128, b"small")
        self.assertEqual({path.name: path.read_bytes() for path in sorted(folder.iterdir())}, before)

    def test_a_size_is_added_to_a_kept_recipe_only(self) -> None:
        with self.assertRaisesRegex(StoreError, "pbrify.*is not kept"):
            self.game.add_size(ORIGIN, "pbrify", 256, b"large")
        # Negative: no file and no entry came of it.
        self.assertIsNone(self.game.entry(ORIGIN, "pbrify"))
        self.assertFalse(self.game.variant_file(ORIGIN, "pbrify", 256).exists())

    def test_a_size_whose_entry_cannot_be_written_leaves_no_file(self) -> None:
        self.game.write_recipe(ORIGIN, "pbrify", {}, {128: b"small"})
        folder = self.game.recipe_dir(ORIGIN, "pbrify")
        before = {path.name: path.read_bytes() for path in sorted(folder.iterdir())}
        with mock.patch.object(store, "write_json", side_effect=OSError("disk full")), self.assertRaises(OSError):
            self.game.add_size(ORIGIN, "pbrify", 256, b"large")
        self.assertEqual({path.name: path.read_bytes() for path in sorted(folder.iterdir())}, before)

    def test_no_program_writes_the_accepted_mark(self) -> None:
        """R-HD-161: only a person marks a variant accepted."""
        with self.assertRaisesRegex(StoreError, "only a person marks a variant accepted"):
            self.game.write_recipe(ORIGIN, "pbrify", {"accepted": "a program says so"}, {256: b"x"})
        # Negative: nothing is kept of it, no entry and no file.
        self.assertIsNone(self.game.entry(ORIGIN, "pbrify"))
        self.assertEqual(self.game.recipes(ORIGIN), [])
        self.assertEqual(list(self.game.recipe_dir(ORIGIN, "pbrify").glob("*")), [])
        # The same entry without the mark is kept; a mark set by hand is read.
        self.game.write_recipe(ORIGIN, "pbrify", {}, {256: b"x"})
        path = self.game.recipe_dir(ORIGIN, "pbrify") / store.ENTRY
        store.write_json(path, {**store.read_json(path), "accepted": "a person looked"})
        self.assertEqual(self.game.entry(ORIGIN, "pbrify")["accepted"], "a person looked")

    def test_of_two_writers_of_one_recipe_the_second_is_refused_and_removes_nothing(self) -> None:
        """R-HD-158: the check and the write are one step. The first writer is held between its files and its entry."""
        entered, release = threading.Event(), threading.Event()
        real = store.write_json

        def held(path: Path, value: object) -> None:
            if threading.current_thread().name == "first":
                entered.set()
                release.wait(10)
            real(path, value)

        ended: dict[str, object] = {}

        def write(name: str, data: bytes) -> None:
            try:
                ended[name] = self.game.write_recipe(ORIGIN, "pbrify", {"by": name}, {256: data})
            except StoreError as error:
                ended[name] = error

        first = threading.Thread(target=write, args=("first", b"first"), name="first")
        second = threading.Thread(target=write, args=("second", b"second"), name="second")
        with mock.patch.object(store, "write_json", held):
            first.start()
            self.assertTrue(entered.wait(10))
            second.start()
            second.join(0.5)
            # The second waits for the first: it has neither written nor removed anything.
            self.assertTrue(second.is_alive(), ended.get("second"))
            self.assertEqual(self.game.variant_file(ORIGIN, "pbrify", 256).read_bytes(), b"first")
            release.set()
            first.join(10)
            second.join(10)
        self.assertIsInstance(ended["second"], StoreError)
        self.assertIn("is kept", str(ended["second"]))
        # Negative: the first one's variant is whole and its own.
        self.assertEqual(self.game.entry(ORIGIN, "pbrify")["by"], "first")
        self.assertEqual(self.game.entry(ORIGIN, "pbrify"), ended["first"])
        self.assertEqual(self.game.variant_file(ORIGIN, "pbrify", 256).read_bytes(), b"first")

    def test_files_left_without_an_entry_are_replaced(self) -> None:
        """Half a recipe is no variant: a write that was cut short does not stand in the way."""
        folder = self.game.recipe_dir(ORIGIN, "pbrify")
        folder.mkdir(parents=True)
        (folder / "256.dds").write_bytes(b"half")
        self.game.write_recipe(ORIGIN, "pbrify", {}, {64: b"new"})
        self.assertEqual(sorted(path.name for path in folder.iterdir()), ["64.dds", "entry.json"])

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
