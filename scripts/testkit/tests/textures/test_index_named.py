"""The state of a texture says who names it: each owner's bake and skins (R-HD-156)."""

from __future__ import annotations

import os

from hdtex.core.index import FILE

from testkit.tests.textures.doubles import ROCK
from testkit.tests.textures.test_cli import ROOM, UP
from testkit.tests.textures.test_index import (
    HALF,
    SAND,
    IndexCase,
)


class NamedByTest(IndexCase):
    """R-HD-156: the state of a texture names each owner whose bake or skin names a variant of it."""

    HALL = "model:hall"

    def named(self, asset: str = ROCK) -> list[dict]:
        return self.state(asset)["namedBy"]

    def test_each_owner_whose_bake_or_skin_names_a_variant_is_listed_and_each_change_writes_the_row(self) -> None:
        room = {"owner": ROOM, "skin": "hd", "variant": UP}
        self.add(ROCK, users=["room", "hall"])
        self.add(SAND, seed=4)
        self.ok("index")
        self.ok("request", "--asset", ROCK, "--variant", UP)
        self.assertEqual(self.named(), [], "negative: made, and nobody names it")
        # A skin change writes the texture's row again.
        self.hd()
        self.assertEqual(self.named(), [{**room, "baked": False}])
        # So does a bake. The bake and the skin are two facts: both are listed, the bake first.
        self.ok("bake", "--owner", ROOM, "--skin", "hd")
        self.ok("skin", "copy", "--owner", self.HALL, "--name", "two")
        self.ok("skin", "set", "--owner", self.HALL, "--name", "two", "--asset", ROCK, "--variant", HALF)
        hall = {"owner": self.HALL, "skin": "two", "variant": HALF, "baked": False}
        self.assertEqual(self.named(), [hall, {**room, "baked": True}, {**room, "baked": False}])
        # Negative: a texture no owner names has none.
        self.assertEqual(self.named(SAND), [])
        # A skin that names the original again is not listed.
        self.ok("skin", "set", "--owner", self.HALL, "--name", "two", "--asset", ROCK, "--clear")
        self.assertEqual(self.named(), [{**room, "baked": True}, {**room, "baked": False}])
        # A rename of the baked skin renames both lines.
        self.ok("skin", "rename", "--owner", ROOM, "--name", "hd", "--new", "sharp")
        sharp = {**room, "skin": "sharp"}
        self.assertEqual(self.named(), [{**sharp, "baked": True}, {**sharp, "baked": False}])
        # An unbake takes the bake's line; a delete takes the skin's.
        self.ok("unbake", "--owner", ROOM)
        self.assertEqual(self.named(), [{**sharp, "baked": False}])
        self.ok("skin", "delete", "--owner", ROOM, "--name", "sharp")
        self.assertEqual(self.named(), [])

    def test_a_bake_keeps_its_line_when_its_skin_names_another_variant_since(self) -> None:
        """The bake holds the skin as it was: its line names what the game shows."""
        self.add(ROCK)
        self.ok("index")
        self.ok("request", "--asset", ROCK, "--variant", UP)
        self.hd()
        self.ok("bake", "--owner", ROOM, "--skin", "hd")
        self.ok("skin", "set", "--owner", ROOM, "--name", "hd", "--asset", ROCK, "--variant", HALF)
        self.assertEqual(
            self.named(),
            [{"owner": ROOM, "skin": "hd", "variant": UP, "baked": True}, {"owner": ROOM, "skin": "hd", "variant": HALF, "baked": False}],
        )
        # A full index of the dataset gives the same lines: they come from the files, not from the changes.
        before = self.named()
        os.remove(self.store.root / FILE)
        self.ok("index")
        self.assertEqual(self.named(), before)


