"""The command line's skin commands: copy, set, rename, delete and upscale (R-HD-130 to 137, R-HD-162)."""

from __future__ import annotations

import os
from unittest import mock

from hdtex.core import variants

from testkit.tests.textures.doubles import ROCK, StandIn
from testkit.tests.textures.fixtures import invert
from testkit.tests.textures.test_cli import ROOM, SAND, UP, CliCase


class SkinTest(CliCase):
    def test_a_skin_is_copied_set_renamed_listed_and_deleted(self) -> None:
        self.add(ROCK)
        self.hd()
        self.assertEqual(
            self.ok("skin", "list", "--owner", ROOM),
            {
                "owner": ROOM,
                "skins": {"hd": {"textures": {ROCK: UP}}},
            },
        )
        self.ok("skin", "rename", "--owner", ROOM, "--name", "hd", "--new", "sharp")
        self.ok(
            "skin",
            "set",
            "--owner",
            ROOM,
            "--name",
            "sharp",
            "--asset",
            ROCK,
            "--clear",
        )
        self.assertEqual(
            self.ok("skin", "list", "--owner", ROOM)["skins"],
            {"sharp": {"textures": {}}},
        )
        self.assertEqual(
            self.ok("skin", "delete", "--owner", ROOM, "--name", "sharp")["skins"], {}
        )

    def test_a_skin_change_that_is_refused_changes_nothing(self) -> None:
        self.add(ROCK)
        self.add(SAND, seed=4, users=["hall"])
        self.hd()
        before = self.ok("skin", "list", "--owner", ROOM)
        self.assertIn(
            "names nothing",
            self.error(
                "skin",
                "set",
                "--owner",
                ROOM,
                "--name",
                "original",
                "--asset",
                ROCK,
                "--variant",
                UP,
            ),
        )
        self.assertIn(
            "no texture of this owner",
            self.error(
                "skin",
                "set",
                "--owner",
                ROOM,
                "--name",
                "hd",
                "--asset",
                SAND,
                "--variant",
                UP,
            ),
        )
        self.assertIn(
            "already", self.error("skin", "copy", "--owner", ROOM, "--name", "hd")
        )
        self.assertIn(
            "has no owner",
            self.error("skin", "copy", "--owner", "model:none", "--name", "hd"),
        )
        self.assertIn(
            "skin set takes --variant, or --clear",
            self.error("skin", "set", "--owner", ROOM, "--name", "hd", "--asset", ROCK),
        )
        self.assertIn(
            "skin rename takes --new",
            self.error("skin", "rename", "--owner", ROOM, "--name", "hd"),
        )
        self.assertEqual(self.ok("skin", "list", "--owner", ROOM), before)

    def test_an_upscale_makes_a_skin_and_its_variants(self) -> None:
        self.add(ROCK)
        answer = self.ok(
            "skin",
            "upscale",
            "--owner",
            ROOM,
            "--name",
            "up",
            "--model",
            "pbrify",
            "--factor",
            "4",
        )
        self.assertEqual(
            (answer["skin"], answer["requests"], answer["kept"], answer["failed"]),
            ("up", {ROCK: UP}, {}, []),
        )
        self.assertEqual(list(self.texture()["recipes"]), ["pbrify"])
        self.assertEqual(
            self.ok("skin", "list", "--owner", ROOM)["skins"]["up"]["textures"],
            {ROCK: UP},
        )

    def test_an_upscale_that_asks_for_nothing_stores_no_skin(self) -> None:
        self.add(ROCK, size=2048)
        words = ("skin", "upscale", "--owner", ROOM, "--model", "pbrify", "--factor", "2")
        with mock.patch.dict(os.environ, {variants.MAX_SIDE_ENV: "2048"}):
            said = self.error(*words)
        self.assertIn("2x asks for no texture, so no skin is made", said)
        self.assertIn(f"{ROCK}: 2x of a side of 2048 gives 2048", said, "with each texture's reason")
        self.assertEqual(self.ok("skin", "list", "--owner", ROOM)["skins"], {}, "negative: no skin stored")
        self.assertEqual(self.runner.asked, [], "negative: nothing was asked")

    def test_a_deferred_upscale_writes_the_skin_and_requests_nothing(self) -> None:
        self.add(ROCK)
        answer = self.ok(
            "skin",
            "upscale",
            "--owner",
            ROOM,
            "--name",
            "up",
            "--model",
            "pbrify",
            "--factor",
            "4",
            "--defer",
        )
        self.assertEqual((answer["requests"], answer["failed"]), ({ROCK: UP}, []))
        self.assertEqual(self.runner.asked, [], "negative: no job was submitted")
        self.assertEqual(self.texture()["recipes"], {}, "negative: no variant made")
        self.assertEqual(
            self.ok("skin", "list", "--owner", ROOM)["skins"]["up"]["textures"],
            {ROCK: UP},
        )

    UPSCALE = ("skin", "upscale", "--owner", ROOM, "--name", "up", "--model", "pbrify", "--factor", "4")

    def named(self, skin: str = "up") -> dict:
        return self.ok("skin", "list", "--owner", ROOM)["skins"][skin]["textures"]

    def test_a_request_for_a_skin_puts_the_input_back_when_its_result_misses_a_limit(self) -> None:
        """R-HD-162: the skin named the variant before its numbers were there."""
        self.runner = StandIn(invert)
        self.add(ROCK)
        self.assertEqual(self.ok(*self.UPSCALE, "--defer")["requests"], {ROCK: UP})
        answer = self.ok("request", "--asset", ROCK, "--variant", UP, "--owner", ROOM, "--skin", "up")
        reverted = answer["reverted"]
        self.assertEqual(
            {key: reverted[key] for key in ("owner", "skin", "asset", "from", "to")},
            {"owner": ROOM, "skin": "up", "asset": ROCK, "from": UP, "to": "original"},
        )
        self.assertIn(f"{UP} has problems: ", reverted["reason"])
        self.assertEqual(self.named(), {}, "the rock shows its original again")
        # The variant stays: a problem hides nothing (R-HD-90).
        self.assertTrue(self.texture()["recipes"]["pbrify"]["problems"])
        self.assertEqual(answer["made"][0]["variant"], UP)

    def test_a_request_for_a_skin_over_a_variant_puts_that_variant_back(self) -> None:
        """The input of the failing step, not the original."""
        self.add(ROCK)
        self.ok("request", "--asset", ROCK, "--variant", "pbrify@128")
        self.hd("pbrify@128")
        chained = "pbrify@128+pbrify@256"
        words = ("skin", "upscale", "--owner", ROOM, "--from", "hd", "--name", "up", "--model", "pbrify", "--factor", "2")
        self.assertEqual(self.ok(*words, "--defer")["requests"], {ROCK: chained})
        self.runner = StandIn(invert)
        answer = self.ok("request", "--asset", ROCK, "--variant", chained, "--owner", ROOM, "--skin", "up")
        self.assertEqual((answer["reverted"]["from"], answer["reverted"]["to"]), (chained, "pbrify@128"))
        self.assertEqual(self.named(), {ROCK: "pbrify@128"})
        # Negative: the source skin is as it was.
        self.assertEqual(self.named("hd"), {ROCK: "pbrify@128"})

    def test_a_request_for_a_skin_changes_nothing_it_should_not(self) -> None:
        """Negatives of R-HD-162."""
        self.add(ROCK)
        self.ok(*self.UPSCALE, "--defer")
        # A sound result: the skin names it, nothing is reverted.
        answer = self.ok("request", "--asset", ROCK, "--variant", UP, "--owner", ROOM, "--skin", "up")
        self.assertNotIn("reverted", answer)
        self.assertEqual(self.named(), {ROCK: UP})
        # A request that fails makes no variant: the name stays, to be asked again.
        self.add(SAND, seed=4)
        self.ok("skin", "upscale", "--owner", ROOM, "--name", "two", "--model", "seedvr2", "--factor", "4", "--defer")
        self.runner.fail = {"seedvr2": "out of GPU memory"}
        self.error("request", "--asset", SAND, "--variant", "seedvr2@256", "--owner", ROOM, "--skin", "two")
        self.assertEqual(self.named("two")[SAND], "seedvr2@256")
        # A skin that names another variant by then is not changed.
        self.runner = StandIn(invert)
        self.ok("skin", "set", "--owner", ROOM, "--name", "two", "--asset", SAND, "--variant", "fast@256")
        answer = self.ok("request", "--asset", SAND, "--variant", "seedvr2@256", "--owner", ROOM, "--skin", "two")
        self.assertNotIn("reverted", answer)
        self.assertEqual(self.named("two")[SAND], "fast@256")
        # A skin that is gone: the request still makes its variant.
        answer = self.ok("request", "--asset", SAND, "--variant", "pbrify@256", "--owner", ROOM, "--skin", "none")
        self.assertNotIn("reverted", answer)
        # One of the two alone is a usage error; nothing is made for it.
        said = self.error("request", "--asset", SAND, "--variant", "fast@256", "--owner", ROOM)
        self.assertIn("request takes --owner and --skin together", said)
        self.assertEqual(sorted(self.texture(SAND)["recipes"]), ["pbrify", "seedvr2"], "no fast was made")

    def test_an_upscale_that_runs_its_requests_puts_the_input_back_too(self) -> None:
        self.runner = StandIn(invert)
        self.add(ROCK)
        status, answer = self.call(*self.UPSCALE)
        self.assertEqual((status, answer["failed"]), (0, []), "a variant with a problem is made: no request failed")
        self.assertEqual([(one["asset"], one["from"], one["to"]) for one in answer["reverted"]], [(ROCK, UP, "original")])
        self.assertEqual(self.named(), {})
        # Negative: a sound upscale lists none.
        self.runner = StandIn()
        self.add(SAND, seed=4, users=["hall"])
        answer = self.ok("skin", "upscale", "--owner", "model:hall", "--name", "up", "--model", "pbrify", "--factor", "4")
        self.assertEqual(answer["reverted"], [])

    def test_the_status_lists_the_owners_with_skins_and_what_they_show_now(
        self,
    ) -> None:
        self.add(ROCK)
        self.hd()
        [owner] = self.ok("status")["owners"]
        self.assertEqual(
            (owner["owner"], owner["layer"], owner["shows"], owner["bake"]),
            (ROOM, "model", {ROCK: "original"}, None),
        )
        hd = {"name": "hd", "textures": {ROCK: UP}}
        self.assertEqual(owner["skins"], [hd])
