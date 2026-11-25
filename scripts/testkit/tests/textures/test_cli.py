"""The commands: status, request, skin, bake, unbake, package, each with JSON on stdout (R-HD-97 to 99, R-HD-106, R-HD-120 to 145)."""

from __future__ import annotations

import contextlib
import io
import json

from hdtex.core import bakes, cli, package, progress
from hdtex.core.interfaces import FAILED

from testkit.tests.textures.doubles import FLOOR, GAME, NAMES, ROCK, Case
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
                answer["sizes"],
                answer["models"],
                answer["owners"],
                answer["unused"],
                answer["gaps"],
            ),
            (GAME, "one", [1024, 2048, 4096], ["pbrify", "fast", "seedvr2"], [], [], {}),
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
            ["256"],
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
            "request", "--asset", ROCK, "--model", "pbrify", "--size", "256"
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
            (ROCK, UP, "pbrify", ["256"], []),
        )
        found = self.texture()
        self.assertEqual(
            found["recipes"],
            {
                "pbrify": {
                    "folder": str(self.store.game(GAME).recipe_dir(ROCK_ORIGIN, "pbrify")),
                    "size": [256, 256], "variants": [UP], "stale": False, "problems": [], "accepted": "",
                    "models": {"color": "pbrify", "alpha": "fast"},
                }
            },
        )  # fmt: skip
        self.assertEqual(
            (found["requests"], found["bake"]),
            ({}, None),
            "a variant is not baked by being made",
        )

    def test_an_input_model_and_size_name_the_variant_of_a_variant(self) -> None:
        self.add(ROCK, size=16)
        self.ok("request", "--asset", ROCK, "--variant", "pbrify@64")
        [made] = self.ok(
            "request",
            "--asset",
            ROCK,
            "--input",
            "pbrify@64",
            "--model",
            "seedvr2",
            "--size",
            "256",
        )["made"]
        self.assertEqual(made["variant"], "pbrify@64+seedvr2@256")
        self.assertEqual(
            sorted(self.texture()["recipes"]), ["pbrify", "pbrify@64+seedvr2"]
        )

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
            ("--asset", ROCK, "--size", "256"),
            ("--asset", ROCK, "--variant", UP, "--model", "fast"),
        ):
            self.assertIn(
                "a request is --variant, or --input, --model and --size",
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
            "--size",
            "256",
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
            "--size",
            "256",
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
        self.assertEqual(owner["skins"], [{**hd, "stored": True}])


class BakeTest(CliCase):
    def test_a_skin_is_baked_and_unbaked(self) -> None:
        self.add(ROCK)
        self.ok("request", "--asset", ROCK, "--variant", UP)
        self.hd()
        self.assertEqual(
            self.ok("bake", "--owner", ROOM, "--skin", "hd"),
            {"owner": ROOM, "skin": "hd", "textures": {ROCK: UP}},
        )
        [owner] = self.ok("status")["owners"]
        self.assertEqual(owner["bake"], {"skin": "hd", "textures": {ROCK: UP}})
        self.assertEqual(
            self.ok("unbake", "--owner", ROOM), {"owner": ROOM, "bake": None}
        )
        self.assertIsNone(self.bakes_text())

    def test_a_bake_that_is_refused_writes_nothing(self) -> None:
        self.add(ROCK)
        self.hd()
        self.assertIn(
            "is not made", self.error("bake", "--owner", ROOM, "--skin", "hd")
        )
        self.assertIn(
            "there is no skin 'other'",
            self.error("bake", "--owner", ROOM, "--skin", "other"),
        )
        for words in (
            (),
            ("--owner", ROOM),
            ("--asset", ROCK),
            ("--owner", ROOM, "--asset", ROCK),
        ):
            self.error("bake", *words)
        self.assertIsNone(self.bakes_text())

    def test_a_texture_of_its_own_kind_is_baked_on_its_own(self) -> None:
        self.add(SAND, kind=FLOOR)
        self.ok("request", "--asset", SAND, "--variant", UP)
        self.assertEqual(
            self.ok("bake", "--asset", SAND, "--variant", UP),
            {"asset": SAND, "variant": UP},
        )
        self.assertEqual(self.texture(SAND)["bake"], UP)
        self.ok("unbake", "--asset", SAND)
        self.assertIsNone(self.texture(SAND)["bake"])


class PackageTest(CliCase):
    def test_the_bakes_are_packaged_into_the_store_and_recorded(self) -> None:
        self.add(ROCK)
        self.add(SAND, seed=4, kind=FLOOR)
        for asset in (ROCK, SAND):
            self.ok("request", "--asset", asset, "--variant", UP)
        self.hd()
        self.ok("bake", "--owner", ROOM, "--skin", "hd")
        self.ok("bake", "--asset", SAND, "--variant", UP)
        answer = self.ok("package")
        folder = self.dataset().folder / package.FOLDER
        self.assertEqual(answer["target"], str(folder))
        self.assertEqual(
            [(one["asset"], one["variant"]) for one in answer["files"]],
            [(ROCK, UP), (SAND, UP)],
        )
        for one in answer["files"]:
            self.assertTrue((folder / one["path"]).is_file())
        self.assertEqual(
            answer["owners"], {ROOM: {"skin": "hd", "textures": {ROCK: UP}}}
        )
        self.assertEqual(list(answer["textures"]), [SAND])
        shown = json.loads((folder / NAMES).read_text())
        self.assertEqual(
            (shown[ROOM], shown["alone"]),
            ({ROCK: f"hd/{UP}/rock.dds"}, {SAND: f"hd/{UP}/sand.dds"}),
        )
        [owner] = self.ok("status")["owners"]
        self.assertTrue(owner["held"])

    def test_a_bake_that_cannot_be_packaged_is_an_error_with_the_command(self) -> None:
        self.add(ROCK)
        self.ok("request", "--asset", ROCK, "--variant", UP)
        self.hd()
        self.ok("bake", "--owner", ROOM, "--skin", "hd")
        self.add(ROCK, seed=2)
        said = self.error("package")
        self.assertIn("stale", said)
        self.assertIn(
            f"scripts/hd_textures.py request --game {GAME} --dataset one --asset '{ROCK}' --variant {UP}",
            said,
        )
        self.assertFalse((self.dataset().folder / package.FOLDER / NAMES).exists())


class UpscalerTest(CliCase):
    def test_the_upscaler_names_the_worker_command_and_whether_one_runs(self) -> None:
        self.add(ROCK)
        log = self.root / "worker.log"
        answer = self.ok("upscaler", "--log", str(log))["upscaler"]
        self.assertEqual((answer["id"], answer["idle"]), ("standin", ""))
        self.assertIn(str(log), " ".join(answer["worker"]["command"]))
        self.runner.no_worker = "no worker runs"
        self.assertEqual(
            self.ok("upscaler", "--log", str(log))["upscaler"]["idle"], "no worker runs"
        )
        self.assertFalse(
            log.exists(), "negative: the command starts no worker; its caller does"
        )
