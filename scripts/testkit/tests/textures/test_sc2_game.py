"""StarCraft II as a game of the pipeline: its textures, their roles, its package (R-HD-3, 4, 53, 54, 56, 101, 108)."""

from __future__ import annotations

from hdtex.core.interfaces import GameError, Texture
from hdtex.sc2 import game, modelindex
from hdtex.sc2.packaged import HD_MODEL_DIR, name_files
from hdtex.sc2.sources import stored_name

from testkit.tests.textures.fixtures import colour_rgba, texture_file
from testkit.tests.textures.sc2_fixtures import (
    ASSETS,
    MODEL_LAYERS,
    SCOBA,
    TEXTURES,
    FakeModels,
    Sc2Case,
    layer,
    model_bytes,
    objects,
)

T = TEXTURES
STORED = ASSETS + TEXTURES


class GameCase(Sc2Case):
    def textures(self, dataset: str = game.STOCK) -> dict[str, Texture]:
        return {texture.asset: texture for texture in self.game.textures(dataset)}

    def judged(self, asset: str, dataset: str = game.STOCK) -> tuple[str | None, str]:
        found = self.game.judge(dataset, self.textures(dataset)[asset])
        self.assertTrue(found.judged)
        return found.role, found.reason


class DatasetTest(GameCase):
    def test_stock_is_always_there_and_another_dataset_is_named_by_its_caller(
        self,
    ) -> None:
        self.assertEqual(self.game.datasets(), (game.STOCK,))
        self.game.use(SCOBA, self.map_dir)
        self.assertEqual(self.game.datasets(), (game.STOCK, SCOBA))
        self.game.use(SCOBA, self.map_dir)  # the same folder again changes nothing

    def test_a_folder_that_fits_no_dataset_is_refused(self) -> None:
        with self.assertRaises(GameError) as stock:
            self.game.use(game.STOCK, self.map_dir)
        self.assertIn("takes no folder", str(stock.exception))
        self.game.use(SCOBA, self.map_dir)
        with self.assertRaises(GameError) as other:
            self.game.use(SCOBA, self.root / "other")
        self.assertIn("has the folder", str(other.exception))
        self.game.use("bare", self.root)
        with self.assertRaises(GameError) as bare:
            self.game.textures("bare")
        self.assertIn("no DocumentInfo", str(bare.exception))
        with self.assertRaises(GameError) as unknown:
            self.game.textures("nobody")
        self.assertIn("--layer", str(unknown.exception))


class TerrainTest(GameCase):
    def test_every_terrain_entry_gives_its_files_with_role_users_and_origin(
        self,
    ) -> None:
        found = self.textures()
        grass = found[T + "grass.dds"]
        self.assertEqual(
            grass,
            Texture(
                T + "grass.dds",
                STORED + "grass.dds",
                "terrain",
                "diffuse",
                "",
                True,
                (1, 1),
                ("Meadow",),
                entries=("Grass",),
            ),
        )
        shared = found[T + "grass_normal.dds"]
        self.assertEqual(
            (shared.role, shared.users, shared.entries),
            ("normal", ("Field", "Meadow"), ("Dirt", "Grass")),
            "two entries name one file",
        )
        self.assertEqual(
            found[T + "tree_diffuse.dds"].entries,
            ("Made",),
            "negative: the default an entry is built on is no entry",
        )
        self.assertEqual(found[T + "dirt.dds"].users, ("Field", "Meadow"))

    def test_an_entry_built_on_a_named_default_is_resolved_and_the_default_is_no_entry(
        self,
    ) -> None:
        found = self.textures()
        self.assertEqual(
            (found[T + "tree_diffuse.dds"].kind, found[T + "tree_diffuse.dds"].users),
            ("terrain", ()),
        )
        self.assertNotIn(T + "##texid##.dds", found)

    def test_a_file_the_dataset_cannot_show_has_no_role_and_a_campaign_map_inside_an_archive_does_not_count(
        self,
    ) -> None:
        lost = self.textures()[T + "lost.dds"]
        self.assertEqual(
            (lost.role, lost.reason, lost.judged),
            (None, "not in the game storage", True),
        )

    def test_listing_takes_no_texture_out_of_the_storage(self) -> None:
        self.textures()
        self.assertEqual(
            [path for path in self.casc.taken if path.endswith(".dds")], []
        )


class ModelTest(GameCase):
    def test_every_model_entry_gives_its_textures_with_the_model_files_as_users(
        self,
    ) -> None:
        found = self.textures()
        normal = found[T + "tree_normal.dds"]
        self.assertEqual(
            (normal.kind, normal.origin, normal.tiles, normal.users),
            (
                "model",
                STORED + "tree_normal.dds",
                False,
                ("assets\\doodads\\tree\\tree_00.m3",),
            ),
        )
        self.assertEqual(
            (normal.judged, normal.role, normal.reason),
            (False, None, ""),
            "its role needs its file",
        )
        self.assertEqual(found[T + "cells.dds"].grid, (2, 2))

    def test_a_texture_the_terrain_names_too_stays_a_terrain_texture(self) -> None:
        self.assertEqual(self.textures()[T + "grass.dds"].kind, "terrain")

    def test_what_the_users_say_is_known_without_the_file(self) -> None:
        found = self.textures()
        self.assertEqual(
            (found[T + "nowhere.dds"].judged, found[T + "nowhere.dds"].reason),
            (True, "not in the game storage"),
        )
        self.assertIn(
            "flip book: its cells are not known", found[T + "boom.dds"].reason
        )

    def test_the_cells_most_model_files_read_a_flip_book_with_hold(self) -> None:
        cells = layer("Assets\\Textures\\cells.dds", flipbook=True, grid=(2, 2))
        other = layer("Assets\\Textures\\cells.dds", flipbook=True, grid=(4, 2))
        self.casc.files[ASSETS + "assets\\doodads\\rock\\rock.m3"] = model_bytes(
            [cells]
        )
        self.casc.files[ASSETS + "assets\\doodads\\tree\\tree_00.m3"] = model_bytes(
            [other]
        )
        use = self.game.model_uses(game.STOCK)[T + "cells.dds"]
        self.assertEqual(
            (
                use.grid,
                [file.entry for file in use.files],
                [file.entry for file in use.others],
            ),
            ((2, 2), ["Mist", "Rock"], ["Tree"]),
        )
        self.assertEqual(self.textures()[T + "cells.dds"].reason, "")

    def test_a_flip_book_as_many_files_read_one_way_as_another_has_no_role(
        self,
    ) -> None:
        self.casc.files[ASSETS + "assets\\doodads\\rock\\rock.m3"] = model_bytes(
            [layer("Assets\\Textures\\cells.dds", flipbook=True, grid=(4, 2))]
        )
        found = self.textures()[T + "cells.dds"]
        self.assertEqual((found.role, found.judged), (None, True))
        self.assertIn("as many model files read it one way as another", found.reason)

    def test_a_file_that_reads_a_texture_two_ways_agrees_with_nobody(self) -> None:
        both = [
            layer("Assets\\Textures\\cells.dds", flipbook=True, grid=(2, 2)),
            layer("Assets\\Textures\\cells.dds"),
        ]
        self.casc.files[ASSETS + "assets\\doodads\\rock\\rock.m3"] = model_bytes(both)
        use = self.game.model_uses(game.STOCK)[T + "cells.dds"]
        self.assertEqual(
            (
                use.grid,
                [file.entry for file in use.files],
                [file.entry for file in use.others],
            ),
            ((2, 2), ["Mist"], ["Rock"]),
        )

    def test_a_role_comes_from_the_slots_and_the_file(self) -> None:
        self.assertEqual(self.judged(T + "tree_normal.dds"), ("normal", ""))
        self.assertEqual(self.judged(T + "rock_normal.dds"), ("normal_red", ""))
        self.assertEqual(self.judged(T + "rock_spec.dds"), ("data", ""))
        self.assertEqual(self.judged(T + "cells.dds"), ("diffuse", ""))
        self.assertEqual(
            self.judged(T + "waves.dds"), (None, "normal slot of displacementMaterials")
        )
        self.assertEqual(
            sorted(path for path in self.casc.taken if path.endswith(".dds")),
            sorted(
                STORED + name
                for name in (
                    "tree_normal.dds",
                    "rock_normal.dds",
                    "rock_spec.dds",
                    "cells.dds",
                    "waves.dds",
                )
            ),
        )

    def test_a_file_that_is_no_texture_or_too_small_has_no_role(self) -> None:
        self.casc.files[STORED + "tree_normal.dds"] = b"no texture"
        self.casc.files[STORED + "rock_spec.dds"] = texture_file(
            "diffuse", colour_rgba(1, 16, 16)
        )
        self.casc.files[STORED + "cells.dds"] = texture_file(
            "diffuse", colour_rgba(1, 32, 32)
        )
        self.assertIsNone(self.judged(T + "tree_normal.dds")[0])
        self.assertEqual(
            self.judged(T + "rock_spec.dds"), (None, "smaller than 32 pixels")
        )
        self.assertEqual(
            self.judged(T + "cells.dds"),
            (None, "flip book: its cells are smaller than 32 pixels"),
        )

    def test_entries_without_a_file_are_passed_over(self) -> None:
        files = modelindex.model_files(self.game.storage(game.STOCK))
        self.assertEqual(
            sorted({file.entry for file in files}), ["Mist", "Rock", "Tree"]
        )
        self.assertEqual(len(files), 4, "both variations of Tree")


class IndexTest(GameCase):
    def test_a_model_file_is_read_once(self) -> None:
        self.textures()
        self.assertEqual(
            sorted(FakeModels.read), ["mist.m3", "rock.m3", "tree_00.m3", "tree_01.m3"]
        )
        FakeModels.read.clear()
        again = game.Sc2Game(self.casc, self.game.index)
        self.assertEqual(len(again.textures(game.STOCK)), len(self.textures()))
        self.assertEqual(FakeModels.read, [])

    def test_a_model_file_that_cannot_be_read_names_nothing_and_is_not_read_again(
        self,
    ) -> None:
        self.casc.files[ASSETS + "assets\\doodads\\mist\\mist.m3"] = b"no model"
        self.assertNotIn(T + "cells.dds", self.textures())
        FakeModels.read.clear()
        game.Sc2Game(self.casc, self.game.index).textures(game.STOCK)
        self.assertEqual(FakeModels.read, [])


class LayerTest(GameCase):
    def setUp(self) -> None:
        super().setUp()
        self.game.use(SCOBA, self.map_dir)

    def test_a_file_of_the_layer_wins_and_has_an_origin_of_its_own(self) -> None:
        own = texture_file("diffuse", colour_rgba(9))
        self.map_file("Assets\\Textures\\Grass.dds", own)
        grass = self.textures(SCOBA)[T + "grass.dds"]
        self.assertEqual(grass.origin, f"dataset\\{SCOBA}\\{T}grass.dds")
        self.assertEqual(self.game.original(SCOBA, grass).read_bytes(), own)
        self.assertEqual(
            self.textures()[T + "grass.dds"].origin,
            STORED + "grass.dds",
            "stock does not see it",
        )

    def test_a_model_of_the_layer_is_read_from_it_and_read_again_when_it_changes(
        self,
    ) -> None:
        rock = "Assets\\Doodads\\Rock\\Rock.m3"
        self.map_file(
            rock,
            model_bytes([layer("Assets\\Textures\\tree_normal.dds", "normalLayer")]),
        )
        self.assertNotIn(T + "rock_spec.dds", self.textures(SCOBA))
        self.assertIn(T + "rock_spec.dds", self.textures())
        self.map_file(rock, model_bytes(MODEL_LAYERS["assets\\doodads\\rock\\rock.m3"]))
        self.assertIn(T + "rock_spec.dds", self.fresh())

    def fresh(self) -> dict[str, Texture]:
        again = game.Sc2Game(self.casc, self.game.index)
        again.use(SCOBA, self.map_dir)
        return {texture.asset: texture for texture in again.textures(SCOBA)}


class ShownTest(GameCase):
    """The models a map shows: those the package covers in the map (R-HD-54).

    The dataset itself lists every model of its catalogs (operator
    2026-11-25; ListedTest below).
    """

    TREE, ROCK, MIST = T + "tree_normal.dds", T + "rock_spec.dds", T + "cells.dds"

    def setUp(self) -> None:
        super().setUp()
        self.game.use(SCOBA, self.map_dir)
        (self.map_dir / "Objects").write_text(objects())

    def catalog(self, name: str, body: str) -> None:
        self.map_file(
            f"Base.SC2Data\\GameData\\{name}", f"<Catalog>{body}</Catalog>".encode()
        )

    def shown(self) -> set[str]:
        storage = self.game.storage(SCOBA)
        files = modelindex.model_files(storage, shown_only=True)
        layers = modelindex.layers(storage, files, self.game.index)
        named = {
            stored_name(layer.path) for file in files for layer in layers[file.origin]
        }
        return {self.TREE, self.ROCK, self.MIST}.intersection(named)

    def test_a_map_that_places_and_names_nothing_shows_no_model_and_stock_shows_all(
        self,
    ) -> None:
        self.assertEqual(self.shown(), set())
        self.assertLessEqual({self.TREE, self.ROCK, self.MIST}, set(self.textures()))

    def test_the_dataset_lists_every_model_of_its_catalogs_shown_or_not(self) -> None:
        # Unplaced units and doodads can get skins (operator 2026-11-25).
        self.assertEqual(self.shown(), set(), "the map shows none of them")
        self.assertLessEqual(
            {self.TREE, self.ROCK, self.MIST}, set(self.textures(SCOBA))
        )

    def test_the_doodads_and_units_a_map_places_are_shown(self) -> None:
        (self.map_dir / "Objects").write_text(objects(("Tree",), ("Guard",)))
        self.assertEqual(
            self.shown(),
            {self.TREE, self.ROCK},
            "Guard shows the model Rock; nothing shows Mist",
        )

    def test_a_unit_of_the_maps_own_catalog_is_shown(self) -> None:
        self.catalog("UnitData.xml", '<CUnit id="Guard"/>')
        self.assertEqual(self.shown(), {self.ROCK})

    def test_an_actor_of_the_maps_own_catalog_is_shown_with_the_models_its_lines_link(
        self,
    ) -> None:
        self.catalog(
            "ActorData.xml",
            '<CActorUnit id="Scout"><Model value="Mist"/><DeathArray index="Normal" ModelLink="Tree" SoundLink=""/></CActorUnit>',
        )
        self.assertEqual(self.shown(), {self.MIST, self.TREE})

    def test_a_model_entry_the_maps_own_catalog_gives_a_file_is_shown(self) -> None:
        self.catalog(
            "ModelData.xml",
            '<CModel id="Rock"><Model value="Assets\\Doodads\\Rock\\Rock.m3"/></CModel><CModel id="Mist"><Radius value="1"/></CModel>',
        )
        self.assertEqual(self.shown(), {self.ROCK}, "Mist gets a radius, no file")

    def test_a_line_the_package_step_wrote_shows_nothing(self) -> None:
        self.catalog("ModelData.xml", '<CModel id="Mist"><Radius value="1"/></CModel>')
        name_files(
            self.map_dir,
            {
                ("ModelData.xml", "CModel"): {
                    ("Mist", "Model"): f"{HD_MODEL_DIR}\\Mist.m3",
                    ("Rock", "Model"): f"{HD_MODEL_DIR}\\Rock.m3",
                }
            },
        )
        self.assertEqual(
            self.shown(),
            set(),
            "neither the entry of the map nor the entry the step made",
        )
