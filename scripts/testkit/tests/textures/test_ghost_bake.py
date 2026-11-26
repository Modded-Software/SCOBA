"""A game that bakes nothing: every bake, unbake and package is refused with its reason; requests and skins still work (R-HD-154, R-VIEW-151)."""

from __future__ import annotations

from hdtex.core import bakes, index, package, skins
from hdtex.core.bakes import BakeError
from hdtex.core.index import Index

from testkit.tests.textures.doubles import GAME, ROCK
from testkit.tests.textures.test_cli import CliCase

REASON = "baking is not enabled for this game"
UP = "pbrify@256"
ROOM = "model:room"


class NoBakeTest(CliCase):
    def setUp(self) -> None:
        super().setUp()
        self.add(ROCK)

    def head(self) -> dict:
        with Index(self.store.root).reading() as con:
            self.assertIsNotNone(con)
            found = index.head(con, GAME, "one")
        self.assertIsNotNone(found)
        return found

    def test_head_names_no_reason_when_the_game_bakes(self) -> None:
        self.ok("index")
        self.assertEqual(self.head()["bake"], "")

    def test_head_names_the_reason(self) -> None:
        self.folder_game.bakes = REASON
        self.ok("index")
        self.assertEqual(self.head()["bake"], REASON)

    def test_bake_unbake_and_package_are_refused(self) -> None:
        self.folder_game.bakes = REASON
        self.ok("request", "--asset", ROCK, "--model", "pbrify", "--factor", "4")
        found = self.dataset()
        found.change_skin(ROOM, lambda one: skins.copied(one, skins.ORIGINAL_SKIN, "hd"))
        found.set_texture(ROOM, "hd", ROCK, UP)
        # The skin is kept: only baking is refused.
        self.assertIn("hd", self.dataset().skins_of(ROOM))
        expected = f"{GAME}: {REASON}"
        for act in (
            lambda: found.bake(ROOM, "hd"),
            lambda: found.unbake(ROOM),
            lambda: found.bake_texture(ROCK, UP),
            lambda: package.package(found, self.root / "target"),
            lambda: package.package_in_store(found),
        ):
            with self.assertRaises(BakeError) as caught:
                act()
            self.assertEqual(str(caught.exception), expected)
        self.assertEqual(self.error("bake", "--owner", ROOM, "--skin", "hd"), expected)
        self.assertEqual(self.error("package"), expected)
        # Nothing was written: no bakes file, no target.
        self.assertFalse((self.dataset().folder / bakes.FILE).exists())
        self.assertFalse((self.root / "target").exists())
