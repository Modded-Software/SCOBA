"""The removal of a variant: it goes, unless something still needs it (R-HD-146)."""

from __future__ import annotations

import os

from hdtex.core import edits, progress, removal, requests, skins
from hdtex.core.removal import RemovalError
from hdtex.core.store import ENTRY, write_json

from testkit.tests.textures.doubles import ROCK, Case

ORIGIN = f"storage\\{ROCK}"
UP = "pbrify@256"  # of a 64 texture: its own size
SMALL = "pbrify@128"  # its half, the 2x size: kept when it is asked for (R-HD-123)
ON_TOP = "pbrify@64+seedvr2@256"  # of a 16 texture: made from pbrify@64
ROOM = "model:room"


class RemovalCase(Case):
    def make(self, variant: str = UP, dataset: str = "one") -> None:
        found = self.dataset(dataset)
        requests.make(found, self.runner, found.texture(ROCK), variant, wait=lambda _seconds: None)

    def remove(self, variant: str = UP, dataset: str = "one") -> None:
        found = self.dataset(dataset)
        removal.remove(found, found.texture(ROCK), variant)

    def folder(self, recipe: str = "pbrify"):
        return self.store.game(self.folder_game.id).recipe_dir(ORIGIN, recipe)

    def refused(self, variant: str, words: str) -> None:
        with self.assertRaises(RemovalError) as caught:
            self.remove(variant)
        self.assertIn(words, str(caught.exception))

class RemoveTest(RemovalCase):
    def both(self) -> None:
        """The recipe at two sizes: each asked for."""
        self.add()
        self.make()
        self.make(SMALL)

    def test_the_last_size_takes_the_recipe_folder(self) -> None:
        self.both()
        self.remove(SMALL)
        self.assertTrue(self.folder().exists(), "negative: one size is left")
        self.remove()
        self.assertFalse(self.folder().exists())
        self.assertEqual(self.dataset().made(self.dataset().texture(ROCK)), {})

    def test_one_size_goes_and_the_others_stay(self) -> None:
        self.both()
        self.remove(SMALL)
        self.assertFalse((self.folder() / "128.dds").exists())
        self.assertTrue((self.folder() / "256.dds").is_file())
        made = self.dataset().made(self.dataset().texture(ROCK))
        self.assertEqual(made["pbrify"].sizes(), [256])

    def test_a_failed_request_keeps_its_note(self) -> None:
        self.both()
        write_json(self.folder() / progress.FILE, {"pid": 1, "started": 0, "step": 1, "steps": 1, "phase": "upscaling", "jobs": [], "failed": "it broke"})
        self.remove(SMALL)
        self.remove()
        self.assertTrue((self.folder() / progress.FILE).is_file())
        self.assertFalse((self.folder() / ENTRY).exists())


class RefusalTest(RemovalCase):
    def test_the_original_and_a_variant_not_made_are_refused(self) -> None:
        self.add()
        self.refused("original", "the original")
        self.refused(UP, "has no variant")

    def test_a_skin_of_this_dataset_lets_it_go_and_names_the_original_after(self) -> None:
        self.add(users=["room"])
        self.make()
        found = self.dataset()
        found.change_skin(ROOM, lambda now: skins.copied(now, skins.ORIGINAL_SKIN, "hd"))
        found.set_texture(ROOM, "hd", ROCK, UP)
        found.change_skin(ROOM, lambda now: skins.made(now, "New Skin 1", {ROCK: UP}))
        # Negative: a skin that names another size keeps it.
        found.change_skin(ROOM, lambda now: skins.made(now, "small", {ROCK: SMALL}))
        self.remove(UP)
        self.assertFalse((self.folder() / "256.dds").exists())
        held = self.dataset().skins_of(ROOM)
        self.assertEqual(
            {name: skin.textures for name, skin in held.items()},
            {"hd": {}, "New Skin 1": {}, "small": {ROCK: SMALL}},
        )

    def test_a_skin_of_another_dataset_refuses_it_too(self) -> None:
        self.add(users=["room"])
        self.add(dataset="two", users=["room"])
        self.make()
        self.dataset("two").change_skin(ROOM, lambda found: skins.copied(found, skins.ORIGINAL_SKIN, "hd"))
        self.dataset("two").set_texture(ROOM, "hd", ROCK, UP)
        self.refused(UP, "in two")

    def test_a_baked_variant_is_refused(self) -> None:
        self.add(users=["room"])
        self.make()
        found = self.dataset()
        found.change_skin(ROOM, lambda now: skins.copied(now, skins.ORIGINAL_SKIN, "hd"))
        found.set_texture(ROOM, "hd", ROCK, UP)
        found.bake(ROOM, "hd")
        found.set_texture(ROOM, "hd", ROCK, None)
        self.refused(UP, "the bake of model:room")

    def test_a_variant_another_is_made_from_is_refused(self) -> None:
        self.add(size=16)
        self.make(ON_TOP)
        self.refused("pbrify@64", "pbrify@64+seedvr2 is made from it")

    def test_an_open_edit_session_refuses_it(self) -> None:
        self.add()
        self.make()
        folder = edits.session_dir(self.store.game(self.folder_game.id), edits.session_id(ORIGIN, UP))
        folder.mkdir(parents=True)
        (folder / edits.SESSION).write_text("{}")
        self.refused(UP, "edit session")

    def test_an_open_request_refuses_it(self) -> None:
        self.add()
        self.make()
        # A request that runs: this process names itself in the note.
        note = {"pid": os.getpid(), "started": progress.started(os.getpid()), "step": 1, "steps": 1, "phase": progress.ENCODING, "jobs": [], "failed": ""}
        write_json(self.folder() / progress.FILE, note)
        self.refused(UP, "is encoding")
