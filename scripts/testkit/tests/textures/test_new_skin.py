"""New Skin N on the command line (R-HD-137, SPEC-HD-TEXTURES 4.6)."""

from __future__ import annotations

from testkit.tests.textures.doubles import ROCK
from testkit.tests.textures.test_cli import ROOM, UP, CliCase


class NewSkinTest(CliCase):
    """A copy or an upscale without a name makes the next New Skin N; it is stored, baked and renamed as any skin."""

    def make(self, *words: str) -> dict:
        return self.ok("skin", "copy", "--owner", ROOM, *words)

    def test_copies_without_a_name_count_up_and_stand_side_by_side(self) -> None:
        self.add(ROCK)
        self.ok("request", "--asset", ROCK, "--variant", UP)
        first = self.make()
        self.assertEqual(first["skin"], "New Skin 1")
        self.ok("skin", "set", "--owner", ROOM, "--name", "New Skin 1", "--asset", ROCK, "--variant", UP)
        second = self.make("--from", "New Skin 1")
        self.assertEqual(second["skin"], "New Skin 2")
        self.assertEqual(
            second["skins"],
            {"New Skin 1": {"textures": {ROCK: UP}}, "New Skin 2": {"textures": {ROCK: UP}}},
        )
        # A deleted number below the highest is not taken again.
        self.ok("skin", "delete", "--owner", ROOM, "--name", "New Skin 1")
        self.assertEqual(self.make()["skin"], "New Skin 3")
        # Negative: a copy with a name makes that name, not a New Skin N.
        self.assertEqual(self.make("--name", "mine")["skin"], "mine")

    def test_a_new_skin_n_bakes_and_renames_as_any_skin(self) -> None:
        self.add(ROCK)
        self.ok("request", "--asset", ROCK, "--variant", UP)
        self.make()
        self.ok("skin", "set", "--owner", ROOM, "--name", "New Skin 1", "--asset", ROCK, "--variant", UP)
        self.assertEqual(self.ok("bake", "--owner", ROOM, "--skin", "New Skin 1")["textures"], {ROCK: UP})
        renamed = self.ok("skin", "rename", "--owner", ROOM, "--name", "New Skin 1", "--new", "Hull")
        self.assertEqual(renamed["skins"], {"Hull": {"textures": {ROCK: UP}}})
        self.assertIn('"skin": "Hull"', self.bakes_text() or "", "the bake follows the rename")

    def test_reserved_and_taken_names_are_refused(self) -> None:
        self.add(ROCK)
        self.make()
        self.make("--name", "hd")
        before = self.ok("skin", "list", "--owner", ROOM)
        for words, reason in (
            (("rename", "--name", "hd", "--new", "new skin 1"), "already"),
            (("rename", "--name", "New Skin 1", "--new", "original"), "is the Original skin"),
            (("copy", "--name", "HD"), "already"),
            (("set", "--name", "nosuch", "--asset", ROCK, "--variant", UP), "there is no skin 'nosuch'"),
        ):
            with self.subTest(words=words):
                self.assertIn(reason, self.error("skin", words[0], "--owner", ROOM, *words[1:]))
        self.assertEqual(self.ok("skin", "list", "--owner", ROOM), before)
        self.assertEqual(self.runner.asked, [], "negative: nothing was requested")
