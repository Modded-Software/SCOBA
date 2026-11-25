"""What StarCraft II's data says: a map's files, catalogs, the storage's archives, model particles, roles (R-HD-3, 4, 53, 56)."""

from __future__ import annotations

import tempfile
import types
import unittest
from pathlib import Path

from hdtex.core import dds
from hdtex.sc2 import game, m3tex, modelindex, sources
from hdtex.sc2.catalog import Catalog, CatalogError
from hdtex.sc2.sources import DEPENDENCY_ARCHIVES, SourceError
from hdtex.sc2.storage import Storage, asset_of

from testkit.tests.textures.fixtures import SIZE, colour_rgba, normal_rgba, texture_file
from testkit.tests.textures.sc2_fixtures import (
    ASSETS,
    DOCUMENT_INFO,
    TEXTURES,
    FakeCasc,
    free_red_normal,
)

ARCHIVES = DEPENDENCY_ARCHIVES["campaigns/voidstory.sc2campaign"]

ACTORS = """<Catalog>
<CActorModel default="1"><Model value="##id##"/></CActorModel>
<CActorDoodad default="1"><Radius value="0.5"/></CActorDoodad>
<CActorDoodad id="Tree"/>
</Catalog>"""

MODELS = """<Catalog>
<CModel default="1"><Radius value="0.5"/></CModel>
<CModel default="1" id="Doodad"><Model value="Assets\\Doodads\\##id##\\##id##.m3"/></CModel>
<CModel default="1" id="Building"><?token id="Race" value="Neutral"?><Model value="Assets\\Buildings\\##Race##\\##id##\\##id##.m3"/></CModel>
<CModel id="Rock" parent="Doodad"/>
<CModel id="CommandCenter" parent="Building" Race="Terran"/>
<CModel id="PsiDecimator" parent="Building"><Model value="Assets\\Doodads\\Psi\\Psi.m3"/></CModel>
</Catalog>"""


class MapFilesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.map_dir = Path(self.temp.name)
        (self.map_dir / "DocumentInfo").write_text(DOCUMENT_INFO)

    def paint(self, *names: str) -> None:
        rows = "".join(
            f'<texture i="{index}" name="{name}"/>' for index, name in enumerate(names)
        )
        (self.map_dir / sources.TERRAIN_FILE).write_text(
            f'<terrain><textureList num="64">{rows}<texture i="63" name=""/></textureList></terrain>'
        )

    def test_texture_ids_keep_order_and_drop_repeats_and_empty_slots(self) -> None:
        self.paint("Zerus7", "Zerus6", "Zerus7")
        self.assertEqual(
            sources.terrain_texture_ids(self.map_dir), ["Zerus7", "Zerus6"]
        )

    def test_a_map_without_textures_is_an_error(self) -> None:
        self.paint()
        with self.assertRaises(SourceError):
            sources.terrain_texture_ids(self.map_dir)

    def test_archives_come_in_load_order(self) -> None:
        archives = sources.map_archives(self.map_dir)
        self.assertEqual(archives, ARCHIVES)
        self.assertLess(
            archives.index("mods\\liberty.sc2mod"), archives.index("mods\\swarm.sc2mod")
        )

    def test_an_unknown_dependency_and_a_map_without_one_are_errors(self) -> None:
        (self.map_dir / "DocumentInfo").write_text(
            DOCUMENT_INFO.replace(
                "Campaigns/VoidStory.SC2Campaign", "Mods/Other.SC2Mod"
            )
        )
        with self.assertRaisesRegex(SourceError, "unknown dependency"):
            sources.map_archives(self.map_dir)
        (self.map_dir / "DocumentInfo").write_text("<DocInfo><Dependencies/></DocInfo>")
        with self.assertRaisesRegex(SourceError, "no dependencies"):
            sources.map_archives(self.map_dir)

    def test_names_are_spelled_as_the_storage_and_as_the_catalog_have_them(
        self,
    ) -> None:
        self.assertEqual(
            sources.stored_name("Assets/Textures\\Zerus_1.dds"),
            "assets\\textures\\zerus_1.dds",
        )
        self.assertEqual(
            sources.file_name("Assets/Textures\\Zerus_1.dds"), "Zerus_1.dds"
        )


class ArchiveTest(unittest.TestCase):
    """Where the storage keeps an asset, and which archive wins."""

    def test_an_archive_keeps_assets_in_its_assets_folder_or_at_its_root(self) -> None:
        liberty = ARCHIVES.index("mods\\liberty.sc2mod")
        self.assertEqual(
            asset_of(
                "mods\\liberty.sc2mod\\base.sc2assets\\assets\\textures\\zerus_1.dds",
                ARCHIVES,
            ),
            (liberty, "assets\\textures\\zerus_1.dds"),
        )
        swarm = ARCHIVES.index("mods\\swarm.sc2mod")
        self.assertEqual(
            asset_of("mods\\swarm.sc2mod\\assets\\textures\\zerus_1.dds", ARCHIVES),
            (swarm, "assets\\textures\\zerus_1.dds"),
        )

    def test_the_archive_loaded_later_has_the_higher_position(self) -> None:
        first = asset_of(
            "mods\\liberty.sc2mod\\base.sc2assets\\assets\\textures\\zerus_1.dds",
            ARCHIVES,
        )
        last = asset_of(
            "mods\\void.sc2mod\\base.sc2assets\\assets\\textures\\zerus_1.dds", ARCHIVES
        )
        self.assertIsNotNone(first)
        self.assertIsNotNone(last)
        self.assertLess(first[0], last[0])
        self.assertEqual(first[1], last[1])

    def test_a_campaign_map_inside_an_archive_does_not_count(self) -> None:
        nested = "campaigns\\voidstory.sc2campaign\\base.sc2maps\\maps\\a.sc2map\\assets\\textures\\zerus_1.dds"
        self.assertIsNone(asset_of(nested, ARCHIVES))

    def test_an_archive_the_dataset_does_not_load_does_not_count(self) -> None:
        self.assertIsNone(
            asset_of(
                "mods\\novastoryassets.sc2mod\\base.sc2assets\\assets\\textures\\zerus_1.dds",
                ARCHIVES,
            )
        )

    def test_the_storage_gives_the_file_of_the_archive_loaded_last(self) -> None:
        casc = FakeCasc()
        liberty = ASSETS + TEXTURES + "grass.dds"
        void = "mods\\void.sc2mod\\base.sc2assets\\" + TEXTURES + "grass.dds"
        root = "mods\\swarm.sc2mod\\" + TEXTURES + "only_here.dds"
        other = (
            "mods\\novastoryassets.sc2mod\\base.sc2assets\\" + TEXTURES + "grass.dds"
        )
        with tempfile.TemporaryDirectory() as keep:
            self.assertEqual(
                Storage("stock", None, casc, Path(keep)).origin(
                    "Assets/Textures/Grass.dds"
                ),
                liberty,
            )
            casc.files.update({void: b"", root: b"", other: b""})
            storage = Storage("stock", None, casc, Path(keep))
            self.assertEqual(storage.origin("Assets/Textures/Grass.dds"), void)
            self.assertEqual(storage.origin("Assets\\Textures\\only_here.dds"), root)
            self.assertIsNone(storage.origin("Assets\\Textures\\nobody.dds"))

    def test_the_base_folder_wins_over_a_variant(self) -> None:
        """R-HD-112: a file for one age rating or one language is not the original."""
        casc = FakeCasc()
        base = ASSETS + TEXTURES + "grass.dds"
        teen = "mods\\liberty.sc2mod\\teen.sc2assets\\" + TEXTURES + "grass.dds"
        chinese = "mods\\liberty.sc2mod\\zhcn.sc2assets\\" + TEXTURES + "grass.dds"
        only_teen = (
            "mods\\liberty.sc2mod\\teen.sc2assets\\" + TEXTURES + "only_teen.dds"
        )
        later = "mods\\void.sc2mod\\teen.sc2assets\\" + TEXTURES + "grass.dds"
        casc.files.update({teen: b"", chinese: b"", only_teen: b""})
        with tempfile.TemporaryDirectory() as keep:
            storage = Storage("stock", None, casc, Path(keep))
            self.assertEqual(storage.origin("Assets/Textures/Grass.dds"), base)
            # A file only a variant folder holds is still found.
            self.assertEqual(storage.origin("Assets/Textures/only_teen.dds"), only_teen)
            # Negative: a variant of an archive loaded later does not beat the base file of an earlier one.
            casc.files[later] = b""
            self.assertEqual(
                Storage("stock", None, casc, Path(keep)).origin(
                    "Assets/Textures/Grass.dds"
                ),
                base,
            )
            # Among variants alone, the archive loaded last wins.
            casc.files[later.replace("grass", "only_teen")] = b""
            self.assertEqual(
                Storage("stock", None, casc, Path(keep)).origin(
                    "Assets/Textures/only_teen.dds"
                ),
                later.replace("grass", "only_teen"),
            )

    def test_without_a_base_file_the_installed_language_wins(self) -> None:
        """R-HD-112: the answer does not depend on the order the storage lists its files in."""
        english = "mods\\liberty.sc2mod\\enus.sc2assets\\" + TEXTURES + "sign.dds"
        german = "mods\\liberty.sc2mod\\dede.sc2assets\\" + TEXTURES + "sign.dds"
        polish = "mods\\liberty.sc2mod\\plpl.sc2assets\\" + TEXTURES + "sign.dds"
        late_german = "mods\\void.sc2mod\\dede.sc2assets\\" + TEXTURES + "sign.dds"
        with tempfile.TemporaryDirectory() as keep:
            for order in (
                [german, english, polish],
                [polish, english, german],
                [english, polish, german],
            ):
                casc = FakeCasc()
                casc.files.update(dict.fromkeys(order, b""))
                self.assertEqual(
                    Storage("stock", None, casc, Path(keep)).origin(
                        "Assets/Textures/sign.dds"
                    ),
                    english,
                )
            # Negative: another language of an archive loaded later does not beat the installed one.
            casc.files[late_german] = b""
            self.assertEqual(
                Storage("stock", None, casc, Path(keep)).origin(
                    "Assets/Textures/sign.dds"
                ),
                english,
            )
            # No installed-language file: one answer for every listing order.
            for order in ([german, polish], [polish, german]):
                casc = FakeCasc()
                casc.files.update(dict.fromkeys(order, b""))
                self.assertEqual(
                    Storage("stock", None, casc, Path(keep)).origin(
                        "Assets/Textures/sign.dds"
                    ),
                    polish,
                )


class CatalogResolveTest(unittest.TestCase):
    def setUp(self) -> None:
        self.models = Catalog([MODELS])
        self.actors = Catalog([ACTORS])

    def test_a_field_comes_from_the_parent_with_the_id_filled_in(self) -> None:
        self.assertEqual(
            self.models.need("Rock", "Model"), "Assets\\Doodads\\Rock\\Rock.m3"
        )

    def test_a_token_is_an_attribute_of_the_entry_or_a_declared_default(self) -> None:
        self.assertEqual(
            self.models.need("CommandCenter", "Model"),
            "Assets\\Buildings\\Terran\\CommandCenter\\CommandCenter.m3",
        )
        both = Catalog(
            [MODELS, '<Catalog><CModel id="Hut" parent="Building"/></Catalog>']
        )
        self.assertEqual(
            both.need("Hut", "Model"), "Assets\\Buildings\\Neutral\\Hut\\Hut.m3"
        )

    def test_an_own_value_beats_the_parent(self) -> None:
        self.assertEqual(
            self.models.need("PsiDecimator", "Model"), "Assets\\Doodads\\Psi\\Psi.m3"
        )

    def test_an_entry_without_a_parent_takes_the_class_default_and_that_of_the_base_class(
        self,
    ) -> None:
        self.assertEqual(self.actors.need("Tree", "Model"), "Tree")
        self.assertEqual(self.actors.need("Tree", "Radius"), "0.5")

    def test_a_later_text_adds_to_an_entry_and_keeps_its_parent(self) -> None:
        later = Catalog(
            [
                MODELS,
                '<Catalog><CModel id="Rock"><VariationCount value="3"/></CModel></Catalog>',
            ]
        )
        self.assertEqual(later.need("Rock", "VariationCount"), "3")
        self.assertEqual(later.need("Rock", "Model"), "Assets\\Doodads\\Rock\\Rock.m3")

    def test_a_field_nobody_sets_is_none_and_need_fails(self) -> None:
        self.assertIsNone(self.models.field("Rock", "VariationCount"))
        with self.assertRaises(CatalogError):
            self.models.need("Rock", "VariationCount")

    def test_an_unknown_entry_a_missing_parent_and_a_loop_are_errors(self) -> None:
        broken = Catalog(
            [
                '<Catalog><CModel id="A" parent="B"/><CModel id="B" parent="A"/><CModel id="C" parent="Gone"/></Catalog>'
            ]
        )
        for entry in ("Nobody", "A", "C"):
            with self.assertRaises(CatalogError):
                broken.field(entry, "Model")

    def test_a_token_without_a_value_is_an_error(self) -> None:
        catalog = Catalog(
            ['<Catalog><CModel id="A"><Model value="##Race##.m3"/></CModel></Catalog>']
        )
        with self.assertRaises(CatalogError):
            catalog.field("A", "Model")


def particle_model(*systems: tuple[int, int, int], references=((1, 0), (1, 1), (2, 0))):
    """A model with particle systems (material reference, columns, rows)."""
    return types.SimpleNamespace(
        materialReferences=[
            types.SimpleNamespace(materialType=kind, materialIndex=index)
            for kind, index in references
        ],
        particles=[
            types.SimpleNamespace(
                materialReferenceIndex=reference,
                numberOfColumns=columns,
                numberOfRows=rows,
            )
            for reference, columns, rows in systems
        ],
    )


class FlipGridTest(unittest.TestCase):
    def test_the_particle_system_gives_the_cells_of_its_material(self) -> None:
        self.assertEqual(
            m3tex.flip_grids(particle_model((1, 8, 4))),
            {("standardMaterials", 1): (8, 4)},
        )

    def test_no_columns_is_one_cell(self) -> None:
        self.assertEqual(
            m3tex.flip_grids(particle_model((0, 0, 0))),
            {("standardMaterials", 0): (1, 1)},
        )

    def test_systems_that_disagree_give_no_cells(self) -> None:
        self.assertEqual(
            m3tex.flip_grids(particle_model((0, 8, 8), (0, 2, 2))),
            {("standardMaterials", 0): None},
        )

    def test_another_kind_of_material_and_a_bad_reference_are_not_followed(
        self,
    ) -> None:
        self.assertEqual(m3tex.flip_grids(particle_model((2, 8, 8), (9, 2, 2))), {})


class RoleTest(unittest.TestCase):
    """The role of a model texture, from the slots that name it and from its file."""

    PICTURE = texture_file("diffuse", colour_rgba(3))
    NORMAL = texture_file("normal", normal_rgba())

    def use(
        self, slots=("diffuseLayer",), asset="assets\\textures\\a.dds", **changes
    ) -> modelindex.Use:
        return modelindex.Use(
            asset,
            "stored",
            tuple(slots),
            ("standardMaterials",),
            (),
            False,
            False,
            (1, 1),
        )._replace(**changes)

    def test_slots_give_the_role(self) -> None:
        self.assertEqual(
            game.role_of(self.use(("diffuseLayer", "specularLayer")), self.PICTURE),
            ("diffuse", ""),
        )
        self.assertEqual(
            game.role_of(self.use(("emissiveLayer",)), self.PICTURE), ("diffuse", "")
        )
        self.assertEqual(
            game.role_of(self.use(("specularLayer", "alphaMaskLayer")), self.PICTURE),
            ("data", ""),
        )
        self.assertEqual(
            game.role_of(self.use(("normalLayer",)), self.NORMAL), ("normal", "")
        )
        self.assertEqual(
            game.role_of(
                self.use(("normalLayer",)),
                texture_file("normal_red", free_red_normal()),
            ),
            ("normal_red", ""),
        )

    def test_what_the_users_say_leaves_a_texture_without_reading_it(self) -> None:
        cases = (
            (self.use(origin=None), "storage"),
            (self.use(asset="assets\\textures\\a.tga"), "DDS"),
            (self.use(video=True), "video"),
            (self.use(flipbook=True, grid=None), "not known"),
        )
        for use, word in cases:
            self.assertIn(word, game.early_reason(use))
        self.assertEqual(game.early_reason(self.use()), "")
        self.assertEqual(game.early_reason(self.use(flipbook=True, grid=(2, 2))), "")

    def test_a_normal_slot_needs_a_normal_map_alone_on_a_surface_material(self) -> None:
        cases = (
            (self.use(("normalLayer",)), self.PICTURE, "normal slot, but"),
            (
                self.use(("normalLayer",), materials=("displacementMaterials",)),
                self.NORMAL,
                "displacementMaterials",
            ),
            (
                self.use(("normalLayer", "diffuseLayer")),
                self.NORMAL,
                "slots that disagree",
            ),
        )
        for use, data, word in cases:
            role, reason = game.role_of(use, data)
            self.assertIsNone(role, word)
            self.assertIn(word, reason)

    def test_a_flip_book_with_cells_that_fit_gets_its_role(self) -> None:
        self.assertEqual(
            game.role_of(self.use(flipbook=True, grid=(2, 2)), self.PICTURE),
            ("diffuse", ""),
        )

    def test_a_flip_book_whose_cells_do_not_fit_is_left(self) -> None:
        self.assertIn(
            "do not divide",
            game.role_of(self.use(flipbook=True, grid=(3, 2)), self.PICTURE)[1],
        )
        self.assertIn(
            "smaller",
            game.role_of(self.use(flipbook=True, grid=(SIZE // 16, 1)), self.PICTURE)[
                1
            ],
        )

    def test_another_format_a_small_file_and_no_texture_are_left(self) -> None:
        dxt3 = bytearray(self.PICTURE)
        dxt3[84:88] = b"DXT3"
        self.assertIn("DXT3", game.role_of(self.use(), bytes(dxt3))[1])
        small = dds.build(
            16, 16, [bytes(dds.level_size(size, size)) for size in (16, 8, 4, 2, 1)]
        )
        self.assertEqual(
            game.role_of(self.use(), small), (None, "smaller than 32 pixels")
        )
        self.assertIsNone(game.role_of(self.use(), b"no texture")[0])

    def test_dxt1_with_transparent_pixels_is_left(self) -> None:
        block = bytes([0x00, 0x00, 0xFF, 0xFF]) + (0xFFFFFFFF).to_bytes(4, "little")
        levels = [
            block * ((max(4, size) // 4) ** 2) for size in (64, 32, 16, 8, 4, 2, 1)
        ]
        self.assertEqual(
            game.role_of(self.use(), dds.build(64, 64, levels, b"", "DXT1")),
            (None, "DXT1 with transparent pixels"),
        )


if __name__ == "__main__":
    unittest.main()
