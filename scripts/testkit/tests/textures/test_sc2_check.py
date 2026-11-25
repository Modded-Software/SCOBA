"""The check of a packaged map, on a made map and on the built one (R-HD-1, 2, 54, 101, 104, 105)."""

from __future__ import annotations

import contextlib
import io
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import workpaths
from hdtex.core import dds, package
from hdtex.core.store import Store, file_sha256, read_json
from hdtex.sc2 import check, game, m3tex
from hdtex.sc2.packaged import GAMEDATA, HD_MODEL_DIR, PRIOR
from hdtex.sc2.sources import (
    HD_DIR,
    HD_MARK,
    TERRAIN_FILE,
    is_marked,
    terrain_texture_ids,
)
from project_root import project_root

from testkit.tests.built_map import needs_built
from testkit.tests.textures.sc2_fixtures import MAGIC, TEXTURES, PackCase

SOURCE_MAP = project_root() / "src" / "SCOBA.SC2Map"


def built_map():
    return workpaths.path("SC2_BUILT_MAP")


HD_FOLDER = Path(*HD_DIR.split("\\"))
TERRAIN_CATALOG = GAMEDATA / "TerrainTexData.xml"
# Only the terrain names it: no model copy holds its path.
NORMAL = f"{HD_DIR}\\grass_normal{HD_MARK}.dds"


class CheckTest(PackCase):
    """A map with packaged terrain textures, a packaged model texture and the model copies that name them."""

    def setUp(self) -> None:
        super().setUp()
        self.pick_terrain()
        self.pick(TEXTURES + "tree_normal.dds")
        package.package(self.dataset(), self.map_dir)

    def fails(self, word: str) -> None:
        with self.assertRaises(check.CheckError) as found:
            check.check(self.map_dir)
        self.assertIn(word, str(found.exception))

    def test_a_complete_map_passes(self) -> None:
        check.check(self.map_dir)
        check.check_hd_textures(self.map_dir)
        self.assertEqual(
            sorted(path.name for path in self.map_file(HD_MODEL_DIR).iterdir()),
            ["Rock.m3", "Tree_00.m3", "Tree_01.m3"],
        )

    def test_the_build_check_names_the_fault_and_ends_the_program(self) -> None:
        self.map_file(NORMAL).unlink()
        errors = io.StringIO()
        with contextlib.redirect_stderr(errors), self.assertRaises(SystemExit) as ended:
            check.check_hd_textures(self.map_dir)
        self.assertEqual(ended.exception.code, 1)
        self.assertIn("ERROR: a catalog points at", errors.getvalue())

    def test_a_missing_file_fails(self) -> None:
        self.map_file(NORMAL).unlink()
        self.fails("the file is not in the map")

    def test_a_file_no_catalog_points_at_fails(self) -> None:
        self.map_file(
            f"{HD_DIR}\\stray{HD_MARK}.dds", self.map_file(NORMAL).read_bytes()
        )
        self.fails("no catalog points at it")

    def test_a_file_named_like_the_original_fails(self) -> None:
        # The game sizes a texture by its file name, so the original's name must not be used again.
        self.map_file(NORMAL).rename(self.map_file(f"{HD_DIR}\\grass_normal.dds"))
        catalog = self.map_dir / TERRAIN_CATALOG
        catalog.write_text(
            catalog.read_text().replace(
                f"grass_normal{HD_MARK}.dds", "grass_normal.dds"
            )
        )
        self.fails("must end with")

    def test_a_file_with_the_mark_in_front_fails(self) -> None:
        # The old naming: the mark in front hides the name start a `CModel` declares its slots by.
        front = f"{HD_DIR}\\scoba_hd_grass_normal.dds"
        self.map_file(NORMAL).rename(self.map_file(front))
        catalog = self.map_dir / TERRAIN_CATALOG
        catalog.write_text(
            catalog.read_text().replace(
                f"grass_normal{HD_MARK}.dds", "scoba_hd_grass_normal.dds"
            )
        )
        self.fails("must end with")

    def test_a_partly_upscaled_terrain_fails(self) -> None:
        rows = "".join(
            f'<texture i="{index}" name="{name}"/>'
            for index, name in enumerate(("Grass", "Dirt", "Lost"))
        )
        (self.map_dir / TERRAIN_FILE).write_text(
            f'<terrain><textureList num="64">{rows}</textureList></terrain>'
        )
        self.fails("terrain texture Lost has no upscaled")

    def test_a_short_mip_chain_fails(self) -> None:
        texture = dds.parse(self.map_file(NORMAL).read_bytes())
        blobs = [texture.level_bytes(index) for index in range(len(texture.levels) - 1)]
        self.map_file(NORMAL, dds.build(texture.width, texture.height, blobs))
        self.fails("mip chain")

    def test_stray_bytes_after_the_last_mip_fail(self) -> None:
        texture = dds.parse(self.map_file(NORMAL).read_bytes())
        blobs = [texture.level_bytes(index) for index in range(len(texture.levels))]
        self.map_file(
            NORMAL,
            dds.build(
                texture.width, texture.height, blobs, bytes(check.MAX_TRAILER + 1)
            ),
        )
        self.fails("stray bytes")

    def test_a_file_that_is_not_a_texture_fails(self) -> None:
        self.map_file(NORMAL, b"not a texture")
        self.fails(f"grass_normal{HD_MARK}.dds")

    def test_a_texture_no_model_names_fails(self) -> None:
        self.map_file(f"{HD_MODEL_DIR}\\Tree_00.m3", MAGIC)
        self.fails("no catalog points at it")

    def test_a_model_file_that_is_gone_fails(self) -> None:
        self.map_file(f"{HD_MODEL_DIR}\\Rock.m3").unlink()
        self.fails("no such model file")

    def test_a_model_file_no_entry_names_fails(self) -> None:
        self.map_file(f"{HD_MODEL_DIR}\\Stray.m3", MAGIC)
        self.fails("no model entry points at it")

    def test_a_file_that_is_not_a_model_fails(self) -> None:
        rock = self.map_file(f"{HD_MODEL_DIR}\\Rock.m3")
        rock.write_bytes(b"XXXX" + rock.read_bytes()[4:])
        self.fails("not a model file")

    def test_a_map_without_the_note_of_what_stood_there_fails(self) -> None:
        (self.map_dir / PRIOR).unlink()
        self.fails("does not say what stood there")


class MapSourceTest(unittest.TestCase):
    def test_the_map_source_holds_nothing_packaged(self) -> None:
        self.assertFalse((SOURCE_MAP / HD_FOLDER).exists())
        self.assertFalse(SOURCE_MAP.joinpath(*HD_MODEL_DIR.split("\\")).exists())
        self.assertFalse((SOURCE_MAP / PRIOR).exists())
        self.assertEqual(check.hd_references(SOURCE_MAP), set())


@needs_built(*HD_FOLDER.parts)
class BuiltMapTest(unittest.TestCase):
    """The real model reader and the real files, on the built map."""

    def test_the_built_map_passes_the_check_and_replaces_every_terrain_texture(
        self,
    ) -> None:
        check.check(built_map())
        root = ET.parse(built_map() / TERRAIN_CATALOG).getroot()
        values = {
            (node.get("id"), child.tag): child.get("value")
            for node in root
            for child in node
        }
        for entry in terrain_texture_ids(built_map()):
            for field in ("Texture", "Normalmap"):
                value = values[entry, field]
                self.assertTrue(
                    value.startswith(f"{HD_DIR}\\") and is_marked(value), value
                )
                self.assertTrue((built_map() / Path(*value.split("\\"))).is_file(), value)

    def test_the_built_map_holds_the_files_the_package_record_lists(self) -> None:
        record = Store().game(game.ID).dataset_dir(game.MAP_DATASET) / package.FILE
        if not record.is_file():
            self.skipTest(f"the texture store has no package record: {record}")
        files = read_json(record)["files"]
        self.assertGreater(len(files), 0)
        for entry in files:
            path = built_map() / Path(*entry["path"].split("\\"))
            where = f"{entry['asset']} {entry['variant']}"
            self.assertTrue(path.is_file(), where)
            self.assertEqual(file_sha256(path), entry["sha256"], where)
        self.assertEqual(
            len(list((built_map() / HD_FOLDER).iterdir())),
            len(files),
            "no packaged texture besides the record's",
        )

    def test_every_model_copy_reads_and_names_files_of_the_map(self) -> None:
        files = check.hd_model_files(built_map())
        present = {path.name.lower() for path in (built_map() / HD_FOLDER).iterdir()}
        named = 0
        for path in files.values():
            for item in m3tex.layers(m3tex.load(path)):
                if item.path.lower().startswith(HD_DIR.lower() + "\\"):
                    self.assertIn(
                        item.path.rsplit("\\", 1)[-1].lower(), present, path.name
                    )
                    named += 1
        self.assertGreater(named, 0)


if __name__ == "__main__":
    unittest.main()
