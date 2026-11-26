"""The commands bake, unbake, package and upscaler, each with JSON on stdout (R-HD-140 to 145, R-HD-106)."""

from __future__ import annotations

import json

from hdtex.core import package

from testkit.tests.textures.doubles import FLOOR, GAME, NAMES, ROCK
from testkit.tests.textures.test_cli import ROOM, SAND, UP, CliCase


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
