"""A dataset: its textures, their variants, its owners' skins and its bakes (R-HD-88, R-HD-90, R-HD-111, R-HD-130 to 136, R-HD-140, R-HD-145)."""

from __future__ import annotations

import os
from unittest import mock

from hdtex.core import bakes, requests, results, skins, variants
from hdtex.core.dataset import Dataset, DatasetError
from hdtex.core.registry import RegistryError
from hdtex.core.skins import SkinError
from hdtex.core.store import ENTRY, read_json, write_json

from testkit.tests.textures.doubles import GAME, ROCK, Case, StandIn
from testkit.tests.textures.fixtures import (
    colour_rgba,
    invert,
    normal_rgba,
    repeat,
    texture_file,
)

SAND = "textures\\sand.dds"
UP = "pbrify@256"
ROOM = "model:room"
HALL = "model:hall"


class DatasetCase(Case):
    def make(self, asset: str = ROCK, variant: str = UP, dataset: str = "one") -> dict:
        found = self.dataset(dataset)
        return requests.make(
            found,
            self.runner,
            found.texture(asset),
            variant,
            wait=lambda _seconds: None,
        )

    def bakes_file(self, dataset: str = "one"):
        return self.dataset(dataset).folder / bakes.FILE

    def skin(self, owner: str = ROOM, name: str = "hd", dataset: str = "one") -> None:
        self.dataset(dataset).change_skin(
            owner, lambda found: skins.copied(found, skins.ORIGINAL_SKIN, name)
        )


class ListingTest(DatasetCase):
    def test_a_dataset_lists_what_its_game_lists(self) -> None:
        self.add(ROCK)
        self.add(SAND, kind="floor", tiles=False, users=["hall", "room"])
        textures = self.dataset().textures
        self.assertEqual(sorted(textures), [ROCK, SAND])
        self.assertEqual(textures[SAND].kind, "floor")
        self.assertFalse(textures[SAND].tiles)
        self.assertEqual(textures[SAND].users, ("hall", "room"))
        self.assertEqual(textures[ROCK].origin, f"storage\\{ROCK}")

    def test_a_dataset_lists_the_owners_its_game_lists(self) -> None:
        self.add(ROCK)
        self.add(SAND, seed=4, users=["hall", "room"])
        owners = self.dataset().owners
        self.assertEqual(sorted(owners), [HALL, ROOM])
        self.assertEqual(owners[ROOM].textures, (ROCK, SAND))
        self.assertEqual(owners[HALL].textures, (SAND,))

    def test_an_unknown_game_dataset_texture_or_owner_is_refused(self) -> None:
        self.add(ROCK)
        with self.assertRaises(RegistryError):
            Dataset(self.store, "nogame", "one")
        with self.assertRaises(DatasetError) as refused:
            Dataset(self.store, GAME, "two")
        self.assertIn("datasets: one", str(refused.exception))
        with self.assertRaises(DatasetError):
            self.dataset().texture(SAND)
        with self.assertRaises(DatasetError):
            self.dataset().owner(HALL)

    def test_once_indexed_an_owner_is_read_from_the_index_and_the_owners_are_not_listed(
        self,
    ) -> None:
        self.add(ROCK)
        self.add(SAND, seed=4, users=["hall", "room"])
        self.dataset().sync()
        listed = self.folder_game.owners_listed
        self.skin(HALL)
        self.assertEqual(self.dataset().owner(HALL).textures, (SAND,))
        with self.assertRaises(DatasetError):
            self.dataset().owner("model:nothing")
        self.assertEqual(
            self.folder_game.owners_listed,
            listed,
            "negative: a skin change and an owner lookup list no owner",
        )

    def test_once_synced_a_skin_names_a_variant_without_listing_the_textures(
        self,
    ) -> None:
        self.add(SAND, users=["hall"])
        self.dataset().sync()
        self.skin(HALL)
        listed = self.folder_game.textures_listed
        found = self.dataset().set_texture(HALL, "hd", SAND, UP)
        self.assertEqual(found["hd"].textures, {SAND: UP})
        self.assertEqual(self.dataset().texture(SAND).asset, SAND)
        with self.assertRaises(DatasetError):
            self.dataset().texture(ROCK)
        self.assertEqual(
            self.folder_game.textures_listed,
            listed,
            "negative: naming a variant and reading a texture list no texture",
        )

    def test_before_any_sync_the_owners_are_listed_from_the_game(self) -> None:
        self.add(SAND, users=["hall", "room"])
        self.skin(HALL)
        self.assertEqual(self.folder_game.owners_listed, 1)
        # Negative: the skin change wrote one owner's row; it does not hide the others.
        self.skin(ROOM)
        self.assertEqual(skins.owners(self.dataset().folder), [HALL, ROOM])

    def test_a_texture_without_variants_is_not_read(self) -> None:
        self.add(ROCK)
        found = self.dataset()
        self.assertEqual(found.made(found.texture(ROCK)), {})
        self.assertEqual(self.folder_game.read, [])


class MadeTest(DatasetCase):
    def test_a_sound_recipe_is_neither_stale_nor_missing_a_limit(self) -> None:
        self.add(ROCK)
        self.make()
        found = self.dataset()
        made = found.made(found.texture(ROCK))
        self.assertEqual(list(made), ["pbrify"])
        self.assertEqual((made["pbrify"].own, made["pbrify"].sizes()), (256, [256]))
        self.assertFalse(made["pbrify"].stale)
        self.assertEqual(made["pbrify"].missed, ())
        self.assertEqual(made["pbrify"].refusal(UP), "")

    def test_a_changed_original_makes_the_recipe_stale(self) -> None:
        self.add(ROCK)
        self.make()
        self.add(ROCK, seed=2)
        found = self.dataset()
        made = found.made(found.texture(ROCK))["pbrify"]
        self.assertTrue(made.stale)
        self.assertIn("stale", made.refusal(UP))

    def test_a_seam_is_a_problem_where_the_texture_tiles_and_nowhere_else(self) -> None:
        self.runner = StandIn(repeat)
        self.add(ROCK, dataset="one", tiles=True)
        self.add(ROCK, dataset="two", tiles=False)
        self.make()
        tiled, loose = self.dataset("one"), self.dataset("two")
        self.assertEqual(
            [
                miss["limit"]
                for miss in tiled.made(tiled.texture(ROCK))["pbrify"].missed
            ],
            ["seam"],
        )
        self.assertEqual(loose.made(loose.texture(ROCK))["pbrify"].missed, ())

    def test_datasets_share_the_variants_of_a_shared_original(self) -> None:
        self.add(ROCK, dataset="one")
        self.add(ROCK, dataset="two")
        self.make(dataset="one")
        asked = len(self.runner.asked)
        other = self.dataset("two")
        self.assertEqual(list(other.made(other.texture(ROCK))), ["pbrify"])
        self.make(dataset="two")
        self.assertEqual(len(self.runner.asked), asked)

    def test_a_file_of_the_datasets_own_has_variants_of_its_own(self) -> None:
        self.add(ROCK, dataset="one")
        self.add(ROCK, dataset="two")
        self.folder_game.add(
            "two", ROCK, texture_file("diffuse", colour_rgba(3)), own=True
        )
        self.make(dataset="one")
        other = self.dataset("two")
        self.assertEqual(other.texture(ROCK).origin, f"dataset\\two\\{ROCK}")
        self.assertEqual(other.made(other.texture(ROCK)), {})


class SkinTest(DatasetCase):
    def test_a_skin_is_made_set_cleared_renamed_and_deleted(self) -> None:
        self.add(ROCK)
        self.skin()
        found = self.dataset()
        found.set_texture(ROOM, "hd", ROCK, UP)
        self.assertEqual(found.skins_of(ROOM)["hd"].textures, {ROCK: UP})
        found.set_texture(ROOM, "hd", ROCK, None)
        self.assertEqual(found.skins_of(ROOM)["hd"].textures, {})
        found.change_skin(ROOM, lambda now: skins.renamed(now, "hd", "sharp"))
        self.assertEqual(sorted(found.skins_of(ROOM)), ["sharp"])
        found.change_skin(ROOM, lambda now: skins.deleted(now, "sharp"))
        self.assertEqual(found.skins_of(ROOM), {})
        self.assertFalse(skins.file_of(found.folder, ROOM).exists())

    def test_a_skin_may_name_a_variant_not_made_yet(self) -> None:
        self.add(ROCK)
        self.skin()
        self.dataset().set_texture(ROOM, "hd", ROCK, UP)
        self.assertEqual(self.dataset().skins_of(ROOM)["hd"].textures, {ROCK: UP})
        self.assertEqual(self.runner.asked, [])

    def test_the_original_skin_cannot_be_changed_renamed_or_deleted(self) -> None:
        self.add(ROCK)
        found = self.dataset()
        for change in (
            lambda now: skins.with_texture(
                now, skins.ORIGINAL_SKIN, ROCK, UP, {ROCK}, lambda *_: ""
            ),
            lambda now: skins.renamed(now, skins.ORIGINAL_SKIN, "other"),
            lambda now: skins.deleted(now, skins.ORIGINAL_SKIN),
            lambda now: skins.copied(now, skins.ORIGINAL_SKIN, skins.ORIGINAL_SKIN),
        ):
            with self.assertRaises(SkinError):
                found.change_skin(ROOM, change)
        self.assertFalse(skins.file_of(found.folder, ROOM).exists())

    def test_a_skin_cannot_name_another_owners_texture_or_a_refused_model(self) -> None:
        self.add(ROCK)
        self.add(SAND, seed=4, users=["hall"])
        self.folder_game.add(
            "one",
            "textures\\wet.dds",
            texture_file("normal", normal_rgba()),
            role="normal",
        )
        self.skin()
        found = self.dataset()
        with self.assertRaises(SkinError) as other:
            found.set_texture(ROOM, "hd", SAND, UP)
        self.assertIn("no texture of this owner", str(other.exception))
        with self.assertRaises(SkinError) as data:
            found.set_texture(ROOM, "hd", "textures\\wet.dds", UP)
        self.assertIn("use fast", str(data.exception))
        self.assertEqual(found.skins_of(ROOM)["hd"].textures, {})

    def test_an_upscale_makes_a_new_skin_from_what_its_source_shows(self) -> None:
        self.add(ROCK)
        self.folder_game.add(
            "one",
            "textures\\wet.dds",
            texture_file("normal", normal_rgba()),
            role="normal",
        )
        said = self.dataset().upscale_skin(
            ROOM, skins.ORIGINAL_SKIN, "seed", "seedvr2", 4
        )
        self.assertEqual(
            said["requests"], {ROCK: "seedvr2@256", "textures\\wet.dds": "fast@256"}
        )
        self.assertEqual(said["kept"], {})
        self.assertEqual(
            self.dataset().skins_of(ROOM)["seed"].textures, said["requests"]
        )
        self.assertEqual(self.runner.asked, [], "nothing is requested by the skin")

    def test_an_upscale_is_by_factor_of_each_input(self) -> None:
        self.add(ROCK)
        self.add("textures\\big.dds", seed=3, size=128)
        said = self.dataset().upscale_skin(
            ROOM, skins.ORIGINAL_SKIN, "two", "pbrify", 2
        )
        self.assertEqual(
            said["requests"], {ROCK: "pbrify@128", "textures\\big.dds": "pbrify@256"}
        )

    def test_an_upscale_names_the_revision_where_the_kept_variant_cannot_serve(self) -> None:
        """R-HD-158: the skin names what its request will make, not the kept variant the request leaves alone."""
        self.add(ROCK)
        self.make()
        # Negative: a sound kept variant is named as it is.
        said = self.dataset().upscale_skin(ROOM, skins.ORIGINAL_SKIN, "same", "pbrify", 4)
        self.assertEqual(said["requests"], {ROCK: UP})
        self.add(ROCK, tiles=False)  # the same file: it no longer repeats
        said = self.dataset().upscale_skin(ROOM, skins.ORIGINAL_SKIN, "again", "pbrify", 4)
        self.assertEqual(said["requests"], {ROCK: "pbrify~2@256"})
        self.assertEqual(self.dataset().skins_of(ROOM)["again"].textures, {ROCK: "pbrify~2@256"})
        # Negative: the skin made before names the kept one as before.
        self.assertEqual(self.dataset().skins_of(ROOM)["same"].textures, {ROCK: UP})

    def test_an_upscale_does_not_name_a_made_variant_a_bake_would_refuse(self) -> None:
        """R-HD-162: its numbers are there already, so the skin never names it."""
        self.runner = StandIn(invert)
        self.add(ROCK)
        self.add(SAND, seed=4)
        self.make()
        asked = len(self.runner.asked)
        said = self.dataset().upscale_skin(ROOM, skins.ORIGINAL_SKIN, "up", "pbrify", 4)
        self.assertIn(f"{UP} has problems: ", said["kept"][ROCK])
        # Negative: the other texture is asked for; the rock is not named and nothing is requested here.
        self.assertEqual(said["requests"], {SAND: UP})
        self.assertEqual(self.dataset().skins_of(ROOM)["up"].textures, {SAND: UP})
        self.assertEqual(len(self.runner.asked), asked)
        # With a person's mark a bake takes it: it is named.
        path = self.store.game(GAME).recipe_dir(self.dataset().texture(ROCK).origin, "pbrify") / ENTRY
        write_json(path, {**read_json(path), results.ACCEPTED: "a person looked"})
        said = self.dataset().upscale_skin(ROOM, skins.ORIGINAL_SKIN, "marked", "pbrify", 4)
        self.assertEqual((said["requests"], said["kept"]), ({ROCK: UP, SAND: UP}, {}))

    def test_an_upscale_keeps_what_a_texture_cannot_have_with_the_reason(self) -> None:
        self.add(ROCK)
        self.add("textures\\big.dds", seed=3, size=2048)
        with mock.patch.dict(os.environ, {variants.MAX_SIDE_ENV: "2048"}):
            said = self.dataset().upscale_skin(
                ROOM, skins.ORIGINAL_SKIN, "big", "pbrify", 4
            )
        self.assertEqual(said["requests"], {ROCK: "pbrify@256"})
        self.assertIn("that adds nothing", said["kept"]["textures\\big.dds"])

    def test_an_upscale_that_asks_for_nothing_is_refused_and_stores_nothing(self) -> None:
        self.add(ROCK, size=2048)
        found = self.dataset()
        with mock.patch.dict(os.environ, {variants.MAX_SIDE_ENV: "2048"}):
            with self.assertRaises(SkinError) as refused:
                found.upscale_skin(ROOM, skins.ORIGINAL_SKIN, None, "pbrify", 2)
        self.assertIn("asks for no texture, so no skin is made", str(refused.exception))
        self.assertEqual(found.skins_of(ROOM), {}, "negative: no empty New Skin N is stored")

    def test_an_upscale_without_a_name_makes_the_next_new_skin_n_each_time(self) -> None:
        self.add(ROCK)
        found = self.dataset()
        names = [found.upscale_skin(ROOM, skins.ORIGINAL_SKIN, None, "pbrify", 2)["skin"] for _ in range(2)]
        self.assertEqual(names, ["New Skin 1", "New Skin 2"])
        self.assertEqual(set(found.skins_of(ROOM)), {"New Skin 1", "New Skin 2"}, "negative: the first is kept")

    def test_an_upscale_keeps_a_texture_whose_original_cannot_be_read(self) -> None:
        self.add(ROCK)
        self.folder_game.add("one", "textures\\bad.dds", b"not a texture", role="diffuse")
        said = self.dataset().upscale_skin(
            ROOM, skins.ORIGINAL_SKIN, "seed", "seedvr2", 4
        )
        self.assertIn("its original's header cannot be read", said["kept"]["textures\\bad.dds"])
        self.assertEqual(
            said["requests"], {ROCK: "seedvr2@256"}, "negative: the readable one is asked for"
        )

    def test_datasets_do_not_share_skins(self) -> None:
        self.add(ROCK, dataset="one")
        self.add(ROCK, dataset="two")
        self.skin(dataset="one")
        self.assertEqual(self.dataset("two").skins_of(ROOM), {})
