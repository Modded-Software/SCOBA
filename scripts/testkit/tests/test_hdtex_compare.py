from __future__ import annotations

import contextlib
import io
import json
import re
from pathlib import Path
from unittest import mock

import numpy as np
from PIL import Image

from hdtex import compare, pipeline
from testkit.tests.hdtex_fixtures import SIZE
from testkit.tests.test_hdtex_build import CacheCase

PAIR_IDS = [
    "zerus_1.color",
    "zerus_1.alpha",
    "zerus_1normal.normal",
    "zerus_2.color",
    "zerus_2.alpha",
    "zerus_2normal.normal",
]
GENERATIVE = pipeline.Settings(variant="generative")


def pixels(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("RGB")).astype(int)


class ComparePageTest(CacheCase):
    def setUp(self) -> None:
        super().setUp()
        self.manifest = self.build()

    def write(self) -> Path:
        with contextlib.redirect_stdout(io.StringIO()) as self.output:
            return compare.write_page("terrain")

    def pairs(self, page: Path) -> list[compare.Pair]:
        found = re.search(r"^const PAIRS = (.*);$", page.read_text(encoding="utf-8"), re.M)
        self.assertIsNotNone(found)
        return json.loads(found.group(1))

    def pair(self, page: Path, key: str) -> compare.Pair:
        return next(pair for pair in self.pairs(page) if pair["id"] == key)

    def test_the_page_lists_every_plane_of_every_texture(self) -> None:
        page = self.write()
        self.assertEqual(page, self.cache / "compare" / "terrain" / "index.html")
        self.assertNotIn(compare.DATA_MARK, page.read_text(encoding="utf-8"))
        pairs = self.pairs(page)
        self.assertEqual([pair["id"] for pair in pairs], PAIR_IDS)
        self.assertEqual({pair["texture"] for pair in pairs}, {entry["asset"].rsplit("\\", 1)[-1] for entry in self.manifest["textures"]})

    def test_one_cached_variant_gives_one_layer(self) -> None:
        for pair in self.pairs(self.write()):
            self.assertEqual([layer["variant"] for layer in pair["layers"]], ["Upscale 4x"], pair["id"])

    def test_the_layers_are_ordered_upscaled_then_generative(self) -> None:
        # The generative cache is the newer one here. The order is fixed all the same.
        self.build(GENERATIVE)
        self.build()
        for pair in self.pairs(self.write()):
            self.assertEqual([layer["variant"] for layer in pair["layers"]], ["Upscale 4x", "Generative 4x"], pair["id"])

    def test_each_layer_shows_the_file_of_its_own_variant(self) -> None:
        self.build(GENERATIVE)
        page = self.write()
        color = self.pair(page, "zerus_1.color")
        upscaled, generative = (pixels(page.parent / layer["image"]) for layer in color["layers"])
        self.assertEqual([layer["model"] for layer in color["layers"]], ["pbrify", "seedvr2"])
        self.assertFalse(np.array_equal(upscaled, generative))
        # Both variants upscale the normal map with the same model.
        normal = self.pair(page, "zerus_1normal.normal")
        upscaled, generative = (pixels(page.parent / layer["image"]) for layer in normal["layers"])
        self.assertEqual([layer["model"] for layer in normal["layers"]], ["fast", "fast"])
        self.assertTrue(np.array_equal(upscaled, generative))
        self.assertNotEqual(normal["layers"][0]["image"], normal["layers"][1]["image"])

    def test_every_image_exists_at_the_size_the_page_states(self) -> None:
        self.build(GENERATIVE)
        page = self.write()
        for pair in self.pairs(page):
            sides = [(pair["before"], pair["before_size"], SIZE)]
            sides += [(layer["image"], layer["size"], SIZE * 4) for layer in pair["layers"]]
            self.assertEqual(len(sides), 3, pair["id"])
            for image, stated, size in sides:
                with Image.open(page.parent / image) as opened:
                    self.assertEqual(list(opened.size), [size, size], image)
                self.assertEqual(stated, [size, size], image)

    def test_before_is_the_original_and_a_layer_is_the_cached_file(self) -> None:
        page = self.write()
        pair = self.pair(page, "zerus_1.color")
        before = pixels(page.parent / pair["before"])
        after = pixels(page.parent / pair["layers"][0]["image"])
        # The test upscaler only enlarges, so the two sides show the same picture.
        shrunk = after.reshape(SIZE, 4, SIZE, 4, 3).mean(axis=(1, 3))
        self.assertLess(float(np.abs(shrunk - before).mean()), 4.0)
        unrelated = pixels(page.parent / self.pair(page, "zerus_2.color")["before"])
        self.assertFalse(np.array_equal(before, unrelated))

    def test_the_mask_uses_the_whole_grey_range_and_says_so(self) -> None:
        page = self.write()
        pair = self.pair(page, "zerus_1.alpha")
        before = np.asarray(Image.open(page.parent / pair["before"]))
        self.assertEqual((int(before.min()), int(before.max())), (0, 255))
        self.assertRegex(pair["note"], r"^values \d+ to \d+ are shown as black to white$")
        self.assertEqual(self.pair(page, "zerus_1.color")["note"], "")

    def test_each_layer_carries_its_model_and_numbers(self) -> None:
        pair = self.pair(self.write(), "zerus_1.color")
        layer = pair["layers"][0]
        entry = next(e for e in self.manifest["textures"] if e["asset"].endswith("Zerus_1.dds"))
        self.assertEqual(layer["model"], "pbrify")
        self.assertEqual(layer["coarse_rmse"], entry["coarse_rmse"])
        self.assertEqual(layer["encode_psnr"], min(entry["encode_psnr"]))
        self.assertEqual(layer["seam"], entry["seam"])
        self.assertEqual(pair["seam_source"], entry["seam_source"])

    def test_a_second_run_keeps_the_images_and_a_changed_texture_redoes_its_own(self) -> None:
        page = self.write()
        images = [page.parent / "img" / side / name for side, name in (("upscale", "zerus_1.color.png"), ("upscale", "zerus_2.color.png"), ("original", "zerus_1.color.png"))]
        stamps = [image.stat().st_mtime_ns for image in images]
        self.write()
        self.assertEqual(self.output.getvalue(), "")
        self.assertEqual([image.stat().st_mtime_ns for image in images], stamps)
        path = self.folder / pipeline.MANIFEST
        manifest = json.loads(path.read_text())
        next(e for e in manifest["textures"] if e["asset"].endswith("Zerus_1.dds"))["sha256"] = "changed"
        path.write_text(json.dumps(manifest))
        self.write()
        self.assertIn("upscale, for scoba_hd_Zerus_1.dds", self.output.getvalue())
        self.assertNotIn("Zerus_2.dds", self.output.getvalue())
        self.assertNotIn("original", self.output.getvalue())
        self.assertNotEqual(images[0].stat().st_mtime_ns, stamps[0])
        self.assertEqual([image.stat().st_mtime_ns for image in images[1:]], stamps[1:])

    def test_a_missing_image_is_written_again(self) -> None:
        page = self.write()
        image = page.parent / "img" / "original" / "zerus_2normal.normal.png"
        image.unlink()
        self.write()
        self.assertTrue(image.is_file())

    def test_no_cache_is_an_error(self) -> None:
        with mock.patch.object(compare, "cache_root", return_value=self.cache / "empty"), mock.patch.object(
            compare, "variant_root", side_effect=lambda key: self.cache / "empty" / key
        ), self.assertRaises(compare.CompareError):
            self.write()

    def test_variants_with_other_textures_are_an_error(self) -> None:
        self.build(GENERATIVE)
        path = self.cache / "generative" / "terrain" / pipeline.MANIFEST
        manifest = json.loads(path.read_text())
        manifest["textures"] = manifest["textures"][:1]
        path.write_text(json.dumps(manifest))
        with self.assertRaises(compare.CompareError) as raised:
            self.write()
        self.assertIn("generative", str(raised.exception))

    def test_a_template_without_the_data_mark_is_an_error(self) -> None:
        self.assertEqual(compare.TEMPLATE.read_text(encoding="utf-8").count(compare.DATA_MARK), 1)
        broken = self.cache / "broken.html"
        broken.write_text("<html></html>")
        with mock.patch.object(compare, "TEMPLATE", broken), self.assertRaises(ValueError):
            self.write()
