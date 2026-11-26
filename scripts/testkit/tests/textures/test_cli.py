"""The commands status, request and skin, each with JSON on stdout (R-HD-97 to 99, R-HD-120 to 138).

CliCase and the names here serve test_cli_bake.py too.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
from unittest import mock

from hdtex.core import bakes, cli, progress, variants
from hdtex.core.interfaces import FAILED

from testkit.tests.textures.doubles import GAME, ROCK, Case
from testkit.tests.textures.fixtures import colour_rgba, texture_file

SAND = "textures\\sand.dds"
ROCK_ORIGIN = f"storage\\{ROCK}"
UP = "pbrify@256"
ROOM = "model:room"


class CliCase(Case):
    def call(
        self, command: str, *words: str, game: str = GAME, dataset: str = "one"
    ) -> tuple[int, dict]:
        """Run one command. Returns its exit status and what it printed, which is one JSON value."""
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            status = cli.main(
                [command, "--game", game, "--dataset", dataset, *words],
                runner=lambda: self.runner,
                store=self.store,
            )
        return status, json.loads(printed.getvalue())

    def ok(self, command: str, *words: str) -> dict:
        status, answer = self.call(command, *words)
        self.assertEqual(status, 0, answer)
        return answer

    def error(self, command: str, *words: str, **where: str) -> str:
        status, answer = self.call(command, *words, **where)
        self.assertEqual((status, list(answer)), (1, ["error"]))
        return answer["error"]

    def usage(self, command: str, *words: str) -> str:
        """What argparse says of words it refuses, before any command runs."""
        said = io.StringIO()
        with contextlib.redirect_stderr(said), self.assertRaises(SystemExit) as stopped:
            cli.main([command, "--game", GAME, "--dataset", "one", *words], runner=lambda: self.runner, store=self.store)
        self.assertEqual(stopped.exception.code, 2)
        return said.getvalue()

    def texture(self, asset: str = ROCK) -> dict:
        [found] = self.ok("status", "--asset", asset)["textures"]
        return found

    def bakes_text(self) -> str | None:
        path = self.dataset().folder / bakes.FILE
        return path.read_text() if path.is_file() else None

    def hd(self, variant: str = UP) -> None:
        """Skin hd of the room, naming `variant` of the rock."""
        self.ok("skin", "copy", "--owner", ROOM, "--name", "hd")
        self.ok(
            "skin",
            "set",
            "--owner",
            ROOM,
            "--name",
            "hd",
            "--asset",
            ROCK,
            "--variant",
            variant,
        )


class StatusTest(CliCase):
    def test_a_dataset_is_listed_with_what_its_game_says(self) -> None:
        self.add(ROCK)
        self.add(SAND, seed=4, kind="floor", tiles=False, users=["hall"])
        answer = self.ok("status")
        self.assertEqual(
            (
                answer["game"],
                answer["dataset"],
                answer["factors"],
                answer["maxSide"],
                answer["models"],
                answer["owners"],
                answer["unused"],
                answer["gaps"],
            ),
            (GAME, "one", [2, 4], 4096, ["pbrify", "fast", "seedvr2"], [], [], {}),
        )
        rock, sand = answer["textures"]
        self.assertEqual(
            rock,
            {
                "asset": ROCK, "origin": ROCK_ORIGIN, "kind": "wall", "judged": True, "role": "diffuse", "reason": "",
                "tiles": True, "grid": [1, 1], "users": ["room"], "entries": [], "recipes": {}, "requests": {}, "bake": None,
            },
        )  # fmt: skip
        self.assertEqual(
            (sand["asset"], sand["kind"], sand["tiles"], sand["users"]),
            (SAND, "floor", False, ["hall"]),
        )
        self.assertEqual(
            self.folder_game.read,
            [],
            "no original is read for a texture without variants",
        )

    def test_the_list_can_be_cut_to_a_kind_or_to_some_textures(self) -> None:
        self.add(ROCK)
        self.add(SAND, seed=4, kind="floor", entries=["Hall"])
        [sand] = self.ok("status", "--kind", "floor")["textures"]
        self.assertEqual(
            (sand["asset"], sand["entries"]),
            (SAND, ["Hall"]),
            "with the data entries that name it",
        )
        found = self.ok("status", "--asset", SAND, "--asset", ROCK)["textures"]
        self.assertEqual([one["asset"] for one in found], [ROCK, SAND])
        self.assertEqual(self.ok("status", "--kind", "roof")["textures"], [])
        self.assertIn(
            "one has no texture textures\\none.dds",
            self.error("status", "--asset", "textures\\none.dds"),
        )

    def test_a_role_that_needs_the_original_is_found_only_for_a_texture_asked_by_name(
        self,
    ) -> None:
        late = "textures\\moss.diffuse.dds"
        self.add(ROCK)
        self.folder_game.add(
            "one",
            late,
            texture_file("diffuse", colour_rgba(4)),
            role=None,
            judged=False,
        )
        listed = self.ok("status")["textures"][0]
        self.assertEqual(
            (listed["asset"], listed["judged"], listed["role"]), (late, False, None)
        )
        self.assertEqual(self.folder_game.judged, [])
        named = self.texture(late)
        self.assertEqual((named["judged"], named["role"]), (True, "diffuse"))
        self.assertEqual(
            list(
                self.ok("request", "--asset", late, "--variant", UP)["made"][0]["files"]
            ),
            ["128", "256"],
        )

    def test_an_unknown_game_or_dataset_is_an_error_in_json(self) -> None:
        self.add(ROCK)
        self.assertIn("unknown game nogame", self.error("status", game="nogame"))
        self.assertIn(f"{GAME} has no dataset two", self.error("status", dataset="two"))

    def test_a_folder_for_a_game_that_takes_none_is_an_error(self) -> None:
        self.add(ROCK)
        self.assertIn(
            "it takes no folder", self.error("status", "--layer", str(self.root))
        )


class RequestTest(CliCase):
    def test_a_request_makes_one_variant_and_the_status_shows_its_recipe(self) -> None:
        self.add(ROCK)
        answer = self.ok(
            "request", "--asset", ROCK, "--model", "pbrify", "--factor", "4"
        )
        [made] = answer["made"]
        self.assertEqual(
            (
                made["asset"],
                made["variant"],
                made["recipe"],
                list(made["files"]),
                answer["failed"],
            ),
            (ROCK, UP, "pbrify", ["128", "256"], []),
            "4x of 64 is 256; its half, 2x, is kept too",
        )
        found = self.texture()
        self.assertEqual(
            found["recipes"],
            {
                "pbrify": {
                    "folder": str(self.store.game(GAME).recipe_dir(ROCK_ORIGIN, "pbrify")),
                    "size": [256, 256], "variants": ["pbrify@128", UP], "stale": False, "staleWhy": "", "problems": [], "accepted": "",
                    "models": {"color": "pbrify", "alpha": "fast"},
                }
            },
        )  # fmt: skip
        self.assertEqual(
            (found["requests"], found["bake"]),
            ({}, None),
            "a variant is not baked by being made",
        )

    def test_an_input_model_and_factor_name_the_variant_of_a_variant(self) -> None:
        self.add(ROCK, size=16)
        self.ok("request", "--asset", ROCK, "--variant", "pbrify@64")
        words = ("request", "--asset", ROCK, "--input", "pbrify@64", "--model", "seedvr2")
        [made] = self.ok(*words, "--factor", "2")["made"]
        self.assertEqual(made["variant"], "pbrify@64+seedvr2@128", "2x of the input's 64")
        self.assertEqual(
            sorted(self.texture()["recipes"]), ["pbrify", "pbrify@64+seedvr2"]
        )

    def test_a_factor_is_capped_at_the_largest_side(self) -> None:
        self.add(ROCK, size=512)
        with mock.patch.dict(os.environ, {variants.MAX_SIDE_ENV: "1024"}):
            [made] = self.ok("request", "--asset", ROCK, "--model", "pbrify", "--factor", "4")["made"]
            self.assertEqual(made["variant"], "pbrify@1024", "4x of 512 is 2048; the cap is 1024")
            self.assertIn(
                "above the largest side, 1024",
                self.error("request", "--asset", ROCK, "--variant", "pbrify@2048"),
                "negative: a variant above the cap is refused",
            )
            self.assertEqual(self.ok("status")["maxSide"], 1024)
        with mock.patch.dict(os.environ, {variants.MAX_SIDE_ENV: "3000"}):
            self.assertIn("it is one of 1024, 2048, 4096", self.error("status"))

    def test_a_factor_that_adds_nothing_is_refused(self) -> None:
        self.add(ROCK, size=2048)
        with mock.patch.dict(os.environ, {variants.MAX_SIDE_ENV: "2048"}):
            self.assertIn(
                "gives 2048 here (the largest side is 2048); that adds nothing",
                self.error("request", "--asset", ROCK, "--model", "pbrify", "--factor", "2"),
            )
        self.assertIn(
            "invalid choice",
            self.usage("request", "--asset", ROCK, "--model", "fast", "--factor", "3"),
        )
        self.assertEqual(self.runner.asked, [], "negative: nothing was asked")

    def test_a_failed_request_is_an_error_and_the_status_shows_its_reason_and_its_log(
        self,
    ) -> None:
        self.add(ROCK)
        self.runner.fail = {"fast": "out of GPU memory"}
        self.assertIn(
            "out of GPU memory", self.error("request", "--asset", ROCK, "--variant", UP)
        )
        state = self.texture()["requests"]["pbrify"]
        self.assertEqual(state["state"], FAILED)
        self.assertIn("out of GPU memory", state["reason"])
        self.assertEqual(
            state["log"],
            str(
                self.store.game(GAME).recipe_dir(ROCK_ORIGIN, "pbrify")
                / progress.LOG_FILE
            ),
        )
        self.assertEqual(self.texture()["recipes"], {})

    def test_a_request_that_fits_no_texture_no_variant_or_no_size_asks_for_nothing(
        self,
    ) -> None:
        self.add(ROCK)
        self.assertIn(
            "has no texture", self.error("request", "--asset", SAND, "--variant", UP)
        )
        self.assertIn(
            "sharpen",
            self.error("request", "--asset", ROCK, "--variant", "sharpen@256"),
        )
        self.assertIn(
            "not at 4096",
            self.error("request", "--asset", ROCK, "--variant", "pbrify@4096"),
        )
        for words in (
            ("--asset", ROCK),
            ("--asset", ROCK, "--model", "pbrify"),
            ("--asset", ROCK, "--factor", "4"),
            ("--asset", ROCK, "--variant", UP, "--model", "fast"),
        ):
            self.assertIn(
                "a request is --variant, or --input, --model and --factor",
                self.error("request", *words),
                words,
            )
        self.assertEqual(self.runner.asked, [])


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
