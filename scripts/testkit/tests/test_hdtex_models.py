"""Host tests for the model texture source: catalogs, codec, roles, verdicts, flip book cells.

The build, the map injection, and the page are in test_hdtex_model_build.py
and test_hdtex_model_map.py.
"""

from __future__ import annotations

import types
import unittest
from unittest import mock

import numpy as np
from hdtex import (
    bc1,
    dds,
    m3tex,
    models,
    pipeline,
    roles,
)
from hdtex.catalog import Catalog, CatalogError

from testkit.tests.hdtex_fixtures import (
    SIZE,
    diffuse_rgba,
)
from testkit.tests.hdtex_model_fixtures import (
    ACTORS,
    MODELS,
    TEXTURES,
    free_red_normal,
)


class CatalogResolveTest(unittest.TestCase):
    def setUp(self) -> None:
        self.models = Catalog([MODELS])
        self.actors = Catalog([ACTORS])

    def test_a_field_comes_from_the_parent_with_the_id_filled_in(self) -> None:
        self.assertEqual(self.models.need("Rock", "Model"), "Assets\\Doodads\\Rock\\Rock.m3")

    def test_a_token_is_an_attribute_of_the_entry_or_a_declared_default(self) -> None:
        self.assertEqual(
            self.models.need("CommandCenter", "Model"), "Assets\\Buildings\\Terran\\CommandCenter\\CommandCenter.m3"
        )
        both = Catalog([MODELS, '<Catalog><CModel id="Hut" parent="Building"/></Catalog>'])
        self.assertEqual(both.need("Hut", "Model"), "Assets\\Buildings\\Neutral\\Hut\\Hut.m3")

    def test_an_own_value_beats_the_parent(self) -> None:
        self.assertEqual(self.models.need("PsiDecimator", "Model"), "Assets\\Doodads\\Psi\\Psi.m3")

    def test_an_entry_without_a_parent_takes_the_class_default_and_that_of_the_base_class(self) -> None:
        self.assertEqual(self.actors.need("Tree", "Model"), "Tree")
        self.assertEqual(self.actors.need("Tree", "Radius"), "0.5")

    def test_a_later_text_adds_to_an_entry_and_keeps_its_parent(self) -> None:
        later = Catalog([MODELS, '<Catalog><CModel id="Rock"><VariationCount value="3"/></CModel></Catalog>'])
        self.assertEqual(later.need("Rock", "VariationCount"), "3")
        self.assertEqual(later.need("Rock", "Model"), "Assets\\Doodads\\Rock\\Rock.m3")

    def test_a_field_nobody_sets_is_none_and_need_fails(self) -> None:
        self.assertIsNone(self.models.field("Rock", "VariationCount"))
        with self.assertRaises(CatalogError):
            self.models.need("Rock", "VariationCount")

    def test_an_unknown_entry_a_missing_parent_and_a_loop_are_errors(self) -> None:
        broken = Catalog(['<Catalog><CModel id="A" parent="B"/><CModel id="B" parent="A"/><CModel id="C" parent="Gone"/></Catalog>'])
        for entry in ("Nobody", "A", "C"):
            with self.assertRaises(CatalogError):
                broken.field(entry, "Model")

    def test_a_token_without_a_value_is_an_error(self) -> None:
        catalog = Catalog(['<Catalog><CModel id="A"><Model value="##Race##.m3"/></CModel></Catalog>'])
        with self.assertRaises(CatalogError):
            catalog.field("A", "Model")


class Bc1Test(unittest.TestCase):
    def test_a_block_is_eight_bytes(self) -> None:
        self.assertEqual(len(bc1.encode(diffuse_rgba(1))), (SIZE // 4) ** 2 * bc1.BLOCK_BYTES)

    def test_flat_colours_come_back_exact_and_opaque(self) -> None:
        image = np.zeros((8, 8, 4), dtype=np.uint8)
        image[:, :, :3] = (255, 0, 255)
        image[:, 4:, :3] = (0, 0, 0)
        decoded = bc1.decode(bc1.encode(image), 8, 8)
        self.assertTrue(np.array_equal(decoded[:, :, :3], image[:, :, :3]))
        self.assertEqual(int(decoded[:, :, 3].min()), 255)

    def test_a_smooth_picture_survives(self) -> None:
        image = diffuse_rgba(4)
        decoded = bc1.decode(bc1.encode(image), SIZE, SIZE)
        error = np.abs(decoded[:, :, :3].astype(int) - image[:, :, :3].astype(int)).mean()
        self.assertLess(error, 3.0)
        self.assertEqual(int(decoded[:, :, 3].min()), 255)

    def test_a_three_colour_block_decodes_its_transparent_pixel(self) -> None:
        # Endpoint 0 below endpoint 1: three colours, index 3 is transparent black.
        block = bytes([0x00, 0x00, 0xFF, 0xFF]) + (3).to_bytes(4, "little")
        decoded = bc1.decode(block, 4, 4)
        self.assertEqual(decoded[0, 0].tolist(), [0, 0, 0, 0])
        self.assertEqual(decoded[0, 1].tolist(), [0, 0, 0, 255])

    def test_the_container_reads_and_writes_dxt1(self) -> None:
        parsed = dds.parse(TEXTURES["rock_spec.dds"])
        self.assertEqual((parsed.format, parsed.width, len(parsed.levels)), ("DXT1", SIZE, dds.full_mip_count(SIZE, SIZE)))
        self.assertEqual(parsed.levels[0].size, (SIZE // 4) ** 2 * 8)
        self.assertEqual(dds.describe(TEXTURES["rock_spec.dds"]).format, "DXT1")
        self.assertEqual(dds.describe(TEXTURES["tree_diffuse.dds"]).format, "DXT5")


class ModelRoleTest(unittest.TestCase):
    def test_data_keeps_every_channel(self) -> None:
        rgba = diffuse_rgba(5)
        role = roles.ROLES["data"]
        levels = role.join(role.split(rgba), None, True)
        self.assertTrue(np.array_equal(levels[0], rgba))
        self.assertEqual(levels[-1].shape[:2], (1, 1))

    def test_data_mips_average_the_bytes(self) -> None:
        rgba = np.zeros((2, 2, 4), dtype=np.uint8)
        rgba[0, 0] = 200
        levels = roles.join_data(roles.split_data(rgba), None, True)
        self.assertEqual(levels[1][0, 0].tolist(), [50, 50, 50, 50])

    def test_a_free_red_normal_keeps_red_and_blue_and_the_tilt(self) -> None:
        rgba = free_red_normal()
        self.assertTrue(roles.has_free_red(rgba))
        with self.assertRaises(roles.RoleError):
            roles.normal_layout(rgba)
        role = roles.ROLES["normal_red"]
        level = role.join(role.split(rgba), role.split(rgba), True)[0]
        self.assertTrue(np.array_equal(level[:, :, 0], rgba[:, :, 0]))
        self.assertEqual(int(level[:, :, 2].max()), 0)
        for channel in (1, 3):
            self.assertLessEqual(int(np.abs(level[:, :, channel].astype(int) - rgba[:, :, channel].astype(int)).max()), 1)

    def test_a_picture_with_blue_is_not_a_free_red_normal(self) -> None:
        with self.assertRaises(roles.RoleError):
            roles.split_normal_red(diffuse_rgba(1))


class JudgeTest(unittest.TestCase):
    def use(self, slots=("diffuseLayer",), asset="assets\\textures\\a.dds", **changes) -> models.Use:
        base = models.Use(asset, "stored", tuple(slots), ("standardMaterials",), ("Tree",), False, False, True)
        return base._replace(**changes)

    def test_slots_give_the_role(self) -> None:
        picture = TEXTURES["tree_diffuse.dds"]
        self.assertEqual(models.judge(self.use(("diffuseLayer", "specularLayer")), picture).role, "diffuse")
        self.assertEqual(models.judge(self.use(("emissiveLayer",)), picture).role, "diffuse")
        self.assertEqual(models.judge(self.use(("specularLayer", "alphaMaskLayer")), picture).role, "data")
        self.assertEqual(models.judge(self.use(("normalLayer",)), TEXTURES["tree_normal.dds"]).role, "normal")
        self.assertEqual(models.judge(self.use(("normalLayer",)), TEXTURES["rock_normal.dds"]).role, "normal_red")

    def test_what_cannot_be_upscaled_is_left_with_a_reason(self) -> None:
        picture = TEXTURES["tree_diffuse.dds"]
        cases = (
            (self.use(casc_path=None), None, "storage"),
            (self.use(asset="assets\\textures\\a.tga"), picture, "DDS"),
            (self.use(video=True), picture, "video"),
            (self.use(flipbook=True), picture, "flip book"),
            (self.use(("normalLayer",)), picture, "normal slot"),
            (self.use(("normalLayer",), materials=("displacementMaterials",)), TEXTURES["tree_normal.dds"], "displacement"),
        )
        for use, data, word in cases:
            verdict = models.judge(use, data)
            self.assertIsNone(verdict.role, word)
            self.assertIn(word, verdict.reason)

    def test_a_flip_book_with_known_cells_gets_its_role(self) -> None:
        use = self.use(flipbook=True, grid=(2, 2))
        self.assertEqual(models.judge(use, TEXTURES["tree_diffuse.dds"]).role, "diffuse")

    def test_a_flip_book_whose_cells_do_not_fit_is_left(self) -> None:
        picture = TEXTURES["tree_diffuse.dds"]
        self.assertIn("do not divide", models.judge(self.use(flipbook=True, grid=(3, 2)), picture).reason)
        self.assertIn("smaller", models.judge(self.use(flipbook=True, grid=(SIZE // 16, 1)), picture).reason)
        self.assertIn("not known", models.judge(self.use(flipbook=True, grid=None), picture).reason)

    def test_other_formats_small_and_large_files_are_left(self) -> None:
        dxt3 = bytearray(TEXTURES["tree_diffuse.dds"])
        dxt3[84:88] = b"DXT3"
        self.assertIn("DXT3", models.judge(self.use(), bytes(dxt3)).reason)
        small = dds.build(16, 16, [bytes(dds.level_size(16, 16))])
        self.assertIn("smaller", models.judge(self.use(), small).reason)
        with mock.patch.object(models, "MODEL_MAX_SIZE", SIZE):
            self.assertIn("already", models.judge(self.use(), TEXTURES["tree_diffuse.dds"]).reason)

    def test_dxt1_with_transparent_pixels_is_left(self) -> None:
        block = bytes([0x00, 0x00, 0xFF, 0xFF]) + (0xFFFFFFFF).to_bytes(4, "little")
        levels = [block * ((max(4, size) // 4) ** 2) for size in (64, 32, 16, 8, 4, 2, 1)]
        verdict = models.judge(self.use(), dds.build(64, 64, levels, b"", "DXT1"))
        self.assertIn("transparent", verdict.reason)


def particle_model(*systems: tuple[int, int, int], references=((1, 0), (1, 1), (2, 0))):
    """A model with particle systems (material reference, columns, rows)."""
    return types.SimpleNamespace(
        materialReferences=[types.SimpleNamespace(materialType=kind, materialIndex=index) for kind, index in references],
        particles=[
            types.SimpleNamespace(materialReferenceIndex=reference, numberOfColumns=columns, numberOfRows=rows)
            for reference, columns, rows in systems
        ],
    )


class FlipGridTest(unittest.TestCase):
    def test_the_particle_system_gives_the_cells_of_its_material(self) -> None:
        grids = m3tex.flip_grids(particle_model((1, 8, 4)))
        self.assertEqual(grids, {("standardMaterials", 1): (8, 4)})

    def test_no_columns_is_one_cell(self) -> None:
        self.assertEqual(m3tex.flip_grids(particle_model((0, 0, 0))), {("standardMaterials", 0): (1, 1)})

    def test_systems_that_disagree_give_no_cells(self) -> None:
        self.assertEqual(m3tex.flip_grids(particle_model((0, 8, 8), (0, 2, 2))), {("standardMaterials", 0): None})

    def test_another_kind_of_material_and_a_bad_reference_are_not_followed(self) -> None:
        self.assertEqual(m3tex.flip_grids(particle_model((2, 8, 8), (9, 2, 2))), {})


class FlipCellTest(unittest.TestCase):
    def picture(self) -> np.ndarray:
        # Four cells of 4x4, each of one value: 10, 20, 30, 40.
        return np.kron(np.array([[10, 20], [30, 40]], dtype=np.uint8), np.ones((4, 4), dtype=np.uint8))

    def test_the_rim_of_a_cell_holds_only_that_cell(self) -> None:
        grown = pipeline.explode(self.picture(), (2, 2), 3)
        self.assertEqual(grown.shape, (20, 20))
        for row, column, value in ((0, 0, 10), (0, 1, 20), (1, 0, 30), (1, 1, 40)):
            cell = grown[row * 10 : (row + 1) * 10, column * 10 : (column + 1) * 10]
            self.assertEqual(set(cell.ravel().tolist()), {value})

    def test_cutting_the_rim_gives_the_picture_back(self) -> None:
        picture = np.arange(8 * 12 * 3, dtype=np.uint8).reshape(8, 12, 3)
        grown = pipeline.explode(picture, (3, 2), 2)
        self.assertEqual(grown.shape, (16, 24, 3))
        self.assertTrue(np.array_equal(pipeline.implode(grown, (3, 2), 2), picture))

    def test_a_picture_upscaled_whole_would_mix_the_cells(self) -> None:
        # The reason for the rim: without it, the edge of a cell borders the next cell.
        picture = self.picture()
        self.assertNotEqual(int(picture[0, 3]), int(picture[0, 4]))
        grown = pipeline.explode(picture, (2, 2), 3)
        self.assertEqual(int(grown[3, 9]), int(grown[3, 6]))
