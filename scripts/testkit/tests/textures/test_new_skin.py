"""New Skin on the command line (R-HD-137, SPEC-HD-TEXTURES 4.6)."""

from __future__ import annotations

from testkit.tests.textures.doubles import ROCK
from testkit.tests.textures.test_cli import ROOM, UP, CliCase


class NewSkinTest(CliCase):
    """Made by the first change, saved by a rename, never baked."""

    def set_new(self, variant: str) -> dict:
        return self.ok(
            "skin", "set", "--owner", ROOM, "--name", "new", "--asset", ROCK,
            "--variant", variant,
        )  # fmt: skip

    def test_the_first_change_makes_new_skin_and_a_save_names_it(self) -> None:
        self.add(ROCK)
        self.ok("request", "--asset", ROCK, "--variant", UP)
        self.assertEqual(self.ok("skin", "list", "--owner", ROOM)["skins"], {})
        self.assertEqual(
            self.set_new(UP)["skins"],
            {"new": {"textures": {ROCK: UP}}},
        )
        self.assertIn(
            "not saved",
            self.error("bake", "--owner", ROOM, "--skin", "new"),
            "negative: New Skin is not baked",
        )
        self.assertIsNone(self.bakes_text(), "negative: no bake was written")
        saved = self.ok(
            "skin", "rename", "--owner", ROOM, "--name", "new", "--new", "mine"
        )
        self.assertEqual(
            saved["skins"], {"mine": {"textures": {ROCK: UP}}}
        )
        self.assertEqual(
            self.ok("bake", "--owner", ROOM, "--skin", "mine")["textures"], {ROCK: UP}
        )

    def test_reserved_names_and_a_second_new_skin_are_refused(self) -> None:
        self.add(ROCK)
        self.hd()
        self.set_new("original")
        before = self.ok("skin", "list", "--owner", ROOM)
        for words, reason in (
            (("rename", "--name", "hd", "--new", "new"), "is New Skin"),
            (("rename", "--name", "new", "--new", "original"), "is the Original skin"),
            (("copy", "--name", "new"), "already"),
            (
                ("upscale", "--name", "new", "--model", "pbrify", "--size", "256"),
                "save or discard New Skin first",
            ),
        ):
            with self.subTest(words=words):
                self.assertIn(
                    reason, self.error("skin", words[0], "--owner", ROOM, *words[1:])
                )
        self.assertEqual(self.ok("skin", "list", "--owner", ROOM), before)
        self.assertEqual(self.runner.asked, [], "negative: nothing was requested")

    def test_a_discard_removes_new_skin(self) -> None:
        self.add(ROCK)
        self.set_new("original")
        self.assertEqual(
            self.ok("skin", "delete", "--owner", ROOM, "--name", "new")["skins"], {}
        )
