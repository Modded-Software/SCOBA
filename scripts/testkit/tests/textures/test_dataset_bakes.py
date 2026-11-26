"""A dataset's bakes: a bake holds its skin as it was, with the hash of each file it names (R-HD-140, R-HD-160)."""

from __future__ import annotations

from hdtex.core import bakes, skinbakes, skins, variants
from hdtex.core.bakes import Bake, BakeError
from hdtex.core.skins import SkinError

from testkit.tests.textures.doubles import FLOOR, ROCK, StandIn
from testkit.tests.textures.fixtures import (
    invert,
)
from testkit.tests.textures.test_dataset import ROOM, SAND, UP, DatasetCase


class BakeTest(DatasetCase):
    def test_a_bake_holds_the_skin_as_it_was_and_unbake_removes_it(self) -> None:
        self.add(ROCK)
        self.make()
        self.skin()
        found = self.dataset()
        found.set_texture(ROOM, "hd", ROCK, UP)
        self.assertEqual(found.bake(ROOM, "hd"), Bake("hd", {ROCK: UP}))
        found.set_texture(ROOM, "hd", ROCK, None)
        self.assertEqual(
            found.baked.owners[ROOM],
            Bake("hd", {ROCK: UP}),
            "a change of the skin leaves the bake",
        )
        found.unbake(ROOM)
        self.assertEqual(found.baked.owners, {})
        self.assertFalse(self.bakes_file().exists())

    def test_a_second_bake_replaces_the_first(self) -> None:
        self.add(ROCK)
        self.make()
        self.skin()
        self.skin(name="other")
        found = self.dataset()
        found.set_texture(ROOM, "hd", ROCK, UP)
        found.bake(ROOM, "hd")
        found.bake(ROOM, "other")
        # A texture the skin does not name is baked as its original (R-HD-131).
        self.assertEqual(found.baked.owners, {ROOM: Bake("other", {ROCK: "original"})})

    def test_original_is_not_baked_and_a_new_skin_n_is(self) -> None:
        self.add(ROCK)
        self.make()
        self.skin()
        found = self.dataset()
        found.set_texture(ROOM, "hd", ROCK, UP)
        found.bake(ROOM, "hd")
        with self.assertRaises(BakeError) as refused:
            found.bake(ROOM, skins.ORIGINAL_SKIN)
        self.assertIn("remove the bake", str(refused.exception))
        self.assertEqual(found.baked.owners[ROOM].skin, "hd", "negative: kept after Original")
        name, _ = found.copy_skin(ROOM, "hd", None)
        self.assertEqual(found.bake(ROOM, name), Bake("New Skin 1", {ROCK: UP}))

    def test_an_owner_above_a_bake_is_offered_no_skin(self) -> None:
        self.add(ROCK)
        self.folder_game.above("one", "unit:Room", [ROOM])
        self.make()
        self.skin()
        found = self.dataset()
        found.set_texture(ROOM, "hd", ROCK, UP)
        found.bake(ROOM, "hd")
        # Negative: the unit above shows the bake below, and has no skin it did not make (R-HD-137).
        self.assertEqual(found.skins_of("unit:Room"), {})

    def test_a_rename_of_a_baked_skin_renames_it_in_the_bake_and_keeps_its_textures(self) -> None:
        self.add(ROCK)
        self.make()
        self.skin()
        self.skin(name="other")
        found = self.dataset()
        found.set_texture(ROOM, "hd", ROCK, UP)
        found.bake(ROOM, "hd")
        skinbakes.rename(found, ROOM, "hd", "sharp")
        self.assertEqual(found.baked.owners, {ROOM: Bake("sharp", {ROCK: UP})})
        # Negative: a rename of a skin that is not baked leaves the bake.
        skinbakes.rename(found, ROOM, "other", "two")
        self.assertEqual(found.baked.owners, {ROOM: Bake("sharp", {ROCK: UP})})

    def test_a_delete_of_a_baked_skin_is_refused_and_changes_nothing(self) -> None:
        self.add(ROCK)
        self.make()
        self.skin()
        self.skin(name="other")
        found = self.dataset()
        found.set_texture(ROOM, "hd", ROCK, UP)
        found.bake(ROOM, "hd")
        before = (found.skins_of(ROOM), found.baked)
        with self.assertRaises(SkinError) as refused:
            skinbakes.delete(found, ROOM, "hd")
        self.assertIn("is baked; unbake it or bake another skin first", str(refused.exception))
        self.assertEqual((found.skins_of(ROOM), found.baked), before)
        # Negative: a skin that is not baked is deleted.
        skinbakes.delete(found, ROOM, "other")
        self.assertEqual(set(found.skins_of(ROOM)), {"hd"})
        # Unbaked, the skin can go.
        found.unbake(ROOM)
        skinbakes.delete(found, ROOM, "hd")
        self.assertEqual(found.skins_of(ROOM), {})

    def test_an_upscale_to_a_taken_name_is_refused(self) -> None:
        self.add(ROCK)
        found = self.dataset()
        found.copy_skin(ROOM, skins.ORIGINAL_SKIN, "hd")
        before = found.skins_of(ROOM)
        with self.assertRaises(SkinError) as refused:
            found.upscale_skin(ROOM, skins.ORIGINAL_SKIN, "HD", "pbrify", 4)
        self.assertIn("there is a skin 'hd' already", str(refused.exception))
        self.assertEqual(found.skins_of(ROOM), before, "negative: nothing changed")

    def test_a_missing_stale_or_unsound_variant_refuses_the_bake_and_writes_nothing(
        self,
    ) -> None:
        self.add(ROCK)
        self.skin()
        found = self.dataset()
        found.set_texture(ROOM, "hd", ROCK, UP)
        with self.assertRaises(BakeError) as missing:
            found.bake(ROOM, "hd")
        self.assertIn("not made", str(missing.exception))
        self.make()
        self.add(ROCK, seed=2)
        with self.assertRaises(BakeError) as stale:
            self.dataset().bake(ROOM, "hd")
        self.assertIn("stale", str(stale.exception))
        self.runner = StandIn(invert)
        self.make()
        # The request made a revision beside the stale one (R-HD-158): the skin names the stale one as before.
        with self.assertRaises(BakeError) as still:
            self.dataset().bake(ROOM, "hd")
        self.assertIn(f"{UP} is stale", str(still.exception))
        self.dataset().set_texture(ROOM, "hd", ROCK, "pbrify~2@256")
        with self.assertRaises(BakeError) as unsound:
            self.dataset().bake(ROOM, "hd")
        self.assertIn("pbrify~2@256 has problems", str(unsound.exception))
        self.assertFalse(self.bakes_file().exists())

    def test_a_bake_pins_the_hash_of_each_variant_file_it_names(self) -> None:
        """R-HD-160: the bake holds which file it took, not only its id."""
        self.add(ROCK)
        self.add(SAND, seed=4)
        made = self.make()
        self.skin()
        found = self.dataset()
        found.set_texture(ROOM, "hd", ROCK, UP)
        found.bake(ROOM, "hd")
        pin = made["files"]["256"]["sha256"]
        baked = self.dataset().baked
        self.assertEqual(baked.owners[ROOM].textures, {ROCK: UP, SAND: variants.ORIGINAL})
        # Negative: the original has no file of the store, so no pin.
        self.assertEqual(baked.pins, bakes.Pins({ROOM: {ROCK: pin}}, {}))
        # A rename keeps them: the bake's textures do not change.
        skinbakes.rename(self.dataset(), ROOM, "hd", "sharp")
        self.assertEqual(self.dataset().baked.pins.owners, {ROOM: {ROCK: pin}})
        # A bake of a skin that names no variant has none; an unbake leaves none.
        self.skin(name="plain")
        self.dataset().bake(ROOM, "plain")
        self.assertEqual(self.dataset().baked.pins, bakes.Pins({}, {}))
        self.dataset().bake(ROOM, "sharp")
        self.dataset().unbake(ROOM)
        self.assertEqual(self.dataset().baked.pins, bakes.Pins({}, {}))

    def test_a_texture_baked_alone_is_pinned_too(self) -> None:
        self.add(SAND, kind=FLOOR, seed=4)
        made = self.make(SAND)
        self.dataset().bake_texture(SAND, UP)
        self.assertEqual(self.dataset().baked.pins, bakes.Pins({}, {SAND: made["files"]["256"]["sha256"]}))
        self.dataset().bake_texture(SAND, None)
        self.assertEqual(self.dataset().baked.pins, bakes.Pins({}, {}))

    def test_a_size_that_is_not_kept_refuses_the_bake(self) -> None:
        self.add(ROCK)
        self.make()
        self.skin()
        self.dataset().set_texture(ROOM, "hd", ROCK, "pbrify@1024")
        with self.assertRaises(BakeError) as refused:
            self.dataset().bake(ROOM, "hd")
        self.assertIn("is not kept", str(refused.exception))

    def test_a_texture_of_its_own_kind_is_baked_alone(self) -> None:
        self.add(SAND, kind=FLOOR)
        self.make(SAND)
        self.dataset().bake_texture(SAND, UP)
        self.assertEqual(self.dataset().baked.textures, {SAND: UP})
        self.dataset().bake_texture(SAND, None)
        self.assertEqual(self.dataset().baked.textures, {})
        with self.assertRaises(BakeError):
            self.dataset().bake_texture(SAND, "fast@256")
        self.assertFalse(self.bakes_file().exists())

    def test_datasets_do_not_share_bakes(self) -> None:
        self.add(ROCK, dataset="one")
        self.add(ROCK, dataset="two")
        self.make()
        self.skin(dataset="one")
        self.dataset("one").bake(ROOM, "hd")
        self.assertEqual(self.dataset("two").baked.owners, {})
