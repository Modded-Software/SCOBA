"""The state index: whoever changes a texture's or an owner's state writes it, and a reader only reads (R-HD-113, R-HD-114)."""

from __future__ import annotations

import os
from pathlib import Path
from unittest import mock

from hdtex.core import encode, index, limits, progress, requests
from hdtex.core.index import FILE, Index
from hdtex.core.interfaces import FAILED
from hdtex.core.store import file_sha256

from testkit.tests.textures.doubles import FLOOR, GAME, ORIGIN, ROCK, StandIn
from testkit.tests.textures.fixtures import (
    colour_rgba,
    invert,
    normal_rgba,
    texture_file,
)
from testkit.tests.textures.test_cli import ROOM, UP, CliCase

SAND = "textures\\sand.dds"
MOSS = "textures\\moss.diffuse.dds"  # the folder game reads its role from its name, when asked
NONE = "textures\\none.dds"
MODELS = ["fast", "pbrify", "seedvr2"]


def askable(state: dict, given: str = "original") -> list[str]:
    """The models a request on `given` may take, by the state."""
    for ask in state["asks"]:
        if ask["input"] == given:
            return sorted(
                model for model, one in ask["models"].items() if not one["reason"]
            )
    return []


def inputs(state: dict) -> list[str]:
    return [ask["input"] for ask in state["asks"]]


class IndexCase(CliCase):
    def run_in(self, dataset: str, command: str, *words: str) -> dict:
        status, answer = self.call(command, *words, dataset=dataset)
        self.assertEqual(status, 0, answer)
        return answer

    def read(self, *assets: str, dataset: str = "one") -> dict:
        """What a reader gets with no pipeline code run: the dataset's head, the named states, and the names without a row."""
        with Index(self.store.root).reading() as con:
            self.assertIsNotNone(con, "there is an index of this schema")
            found = index.rows(con, GAME, dataset, assets)
            return {
                "head": index.head(con, GAME, dataset),
                "textures": {asset: row.state for asset, row in found.items()},
                "unknown": sorted(set(assets) - set(found)),
            }

    def state(self, asset: str = ROCK, dataset: str = "one") -> dict:
        return self.read(asset, dataset=dataset)["textures"][asset]

    def owner(self, owner: str = ROOM, dataset: str = "one") -> dict | None:
        with Index(self.store.root).reading() as con:
            found = index.owners(con, GAME, dataset, [owner])
        return found[owner][1] if owner in found else None

    def storage_file(self, asset: str) -> Path:
        return self.root / "game" / "storage" / asset.replace("\\", "/")

    def rewrite(self, asset: str, seed: int) -> None:
        """Give a texture of the storage other pixels, at a later time: the file's time has a coarse clock."""
        path = self.storage_file(asset)
        before = path.stat().st_mtime_ns
        path.write_bytes(texture_file("diffuse", colour_rgba(seed, 64, 64)))
        os.utime(path, ns=(before + 10**9, before + 10**9))


class StateTest(IndexCase):
    """The shape of webviewer/src/shared/textures.ts (SPEC-VIEWER 17.2)."""

    def test_a_texture_without_variants_may_ask_for_each_model_and_holds_nothing(
        self,
    ) -> None:
        self.add(ROCK)
        self.ok("index", "--asset", ROCK)
        found = self.read(ROCK, NONE)
        self.assertEqual(
            (found["head"]["sizes"], found["unknown"]), ([1024, 2048, 4096], [NONE])
        )
        self.assertEqual(
            [model["id"] for model in found["head"]["models"]],
            ["pbrify", "fast", "seedvr2"],
        )
        rock = found["textures"][ROCK]
        self.assertEqual(
            (
                rock["variants"],
                rock["bake"],
                rock["bakeProblem"],
                rock["packaged"],
                rock["requests"],
                rock["colour"],
            ),
            ([], None, "", None, {}, True),
        )
        self.assertEqual(
            (rock["judged"], inputs(rock), askable(rock)), (True, ["original"], MODELS)
        )
        sizes = rock["asks"][0]["models"]["pbrify"]["sizes"]
        self.assertEqual(sizes["256"], "", "the own size of a small texture is offered")
        self.assertIn(
            "not at 4096", sizes["4096"], "negative: a size it cannot reach says why"
        )

    def test_a_texture_without_colour_may_ask_for_fast_only(self) -> None:
        self.folder_game.add(
            "one", SAND, texture_file("normal", normal_rgba()), role="normal"
        )
        self.ok("index", "--asset", SAND)
        sand = self.state(SAND)
        self.assertEqual((sand["colour"], askable(sand)), (False, ["fast"]))
        self.assertIn("use fast", sand["asks"][0]["models"]["seedvr2"]["reason"])

    def test_a_variant_is_listed_with_its_file_and_is_an_input_of_the_next_step(
        self,
    ) -> None:
        self.add(ROCK)
        self.ok("request", "--asset", ROCK, "--variant", UP)
        rock = self.state()
        [variant] = rock["variants"]
        kept = self.store.game(GAME).variant_file(ORIGIN + ROCK, "pbrify", 256)
        self.assertEqual(
            (
                variant["id"],
                variant["input"],
                variant["recipe"],
                variant["size"],
                variant["own"],
                variant["stale"],
                variant["problems"],
            ),
            (UP, "original", "pbrify", 256, 256, False, []),
        )
        self.assertEqual(
            (variant["path"], variant["sha256"]), (str(kept), file_sha256(kept))
        )
        self.assertEqual(inputs(rock), ["original", UP])
        self.assertEqual(askable(rock, UP), MODELS)
        sizes = rock["asks"][1]["models"]["pbrify"]["sizes"]
        self.assertEqual(sizes["1024"], "", "a variant of 256 goes on to 1024")
        self.assertIn("not at 2048", sizes["2048"])

    def test_a_failed_request_is_listed_with_its_reason_and_may_be_asked_again(
        self,
    ) -> None:
        self.add(ROCK)
        self.runner.fail = {"fast": "out of GPU memory"}
        self.error("request", "--asset", ROCK, "--variant", UP)
        rock = self.state()
        self.assertEqual(rock["requests"]["pbrify"]["state"], FAILED)
        self.assertIn("out of GPU memory", rock["requests"]["pbrify"]["reason"])
        self.assertNotIn(
            "pid",
            rock["requests"]["pbrify"],
            "a request that failed names no program to look for",
        )
        self.assertIn("pbrify", askable(rock))
        self.assertEqual(rock["variants"], [])

    def test_an_unsound_variant_is_listed_with_its_problems_and_bands(self) -> None:
        self.runner = StandIn(invert)
        self.add(ROCK)
        self.ok("request", "--asset", ROCK, "--variant", UP)
        [variant] = self.state()["variants"]
        self.assertTrue(variant["problems"], "the limits it misses")
        self.assertEqual(variant["accepted"], "")
        self.assertIn(limits.PROBLEM, {band["band"] for band in variant["numbers"]})

    def test_packaged_is_held_only_when_the_package_has_the_file_of_the_bake(
        self,
    ) -> None:
        self.add(SAND, kind=FLOOR)
        self.ok("request", "--asset", SAND, "--variant", UP)
        self.ok("bake", "--asset", SAND, "--variant", UP)
        self.assertEqual(
            (self.state(SAND)["bake"], self.state(SAND)["packaged"]),
            (UP, None),
            "negative: baked is not packaged",
        )
        self.ok("package")
        self.assertEqual(self.state(SAND)["packaged"], {"variant": UP, "held": True})
        self.ok("unbake", "--asset", SAND)
        self.assertEqual(
            self.state(SAND)["packaged"],
            {"variant": UP, "held": False},
            "negative: the bake moved on",
        )


class OwnerTest(IndexCase):
    def test_an_owner_row_follows_its_skins_and_its_bake(self) -> None:
        self.add(ROCK)
        self.ok("index")
        self.assertEqual(
            (self.owner()["skins"], self.owner()["bake"], self.owner()["shows"]),
            ([], None, {ROCK: "original"}),
        )
        self.ok("request", "--asset", ROCK, "--variant", UP)
        self.hd()
        self.assertEqual(
            self.owner()["skins"],
            [{"name": "hd", "textures": {ROCK: UP}, "stored": True}],
        )
        self.ok("bake", "--owner", ROOM, "--skin", "hd")
        self.assertEqual(
            (self.owner()["bake"], self.owner()["held"], self.owner()["shows"]),
            ({"skin": "hd", "textures": {ROCK: UP}}, False, {ROCK: UP}),
        )
        self.assertEqual(
            [skin["name"] for skin in self.owner()["skins"]],
            ["hd"],
            "negative: the bake is a saved skin's, so no New Skin is offered",
        )
        self.ok("package")
        self.assertTrue(self.owner()["held"])

    def test_an_owner_above_a_bake_is_offered_it_as_new_skin(self) -> None:
        # Operator 2026-11-25: "currently baked user texture automatically
        # fall under unsaved New Skins".
        self.add(ROCK)
        self.add(SAND, seed=4, users=["room"])
        self.folder_game.above("one", "unit:Room", [ROOM])
        self.ok("request", "--asset", ROCK, "--variant", UP)
        self.hd()
        self.ok("bake", "--owner", ROOM, "--skin", "hd")
        unit = self.owner("unit:Room")
        self.assertEqual(
            (unit["layer"], unit["below"], unit["shows"]),
            ("unit", [{"owner": ROOM, "bake": "hd"}], {ROCK: UP, SAND: "original"}),
        )
        offer = {"name": "new", "textures": {ROCK: UP}, "stored": False}
        self.assertEqual(unit["skins"], [offer])
        self.assertEqual(
            self.ok("skin", "list", "--owner", "unit:Room")["skins"],
            {},
            "negative: an offer writes nothing",
        )
        # The first change stores it: what was offered, and the change.
        self.ok(
            "skin", "set", "--owner", "unit:Room", "--name", "new", "--asset", SAND,
            "--variant", "original",
        )  # fmt: skip
        self.assertEqual(
            self.owner("unit:Room")["skins"],
            [{**offer, "textures": {ROCK: UP, SAND: "original"}, "stored": True}],
        )
        self.ok("skin", "delete", "--owner", "unit:Room", "--name", "new")
        self.ok("unbake", "--owner", ROOM)
        unit = self.owner("unit:Room")
        self.assertEqual(
            (unit["shows"], unit["skins"]),
            ({ROCK: "original", SAND: "original"}, []),
            "negative: unbaked, it shows the original and nothing is offered",
        )

    def test_an_owner_the_game_lists_no_longer_leaves_the_index(self) -> None:
        self.add(ROCK)
        self.add(SAND, seed=4, users=["hall"])
        self.ok("index")
        self.assertIsNotNone(self.owner("model:hall"))
        self.folder_game.drop("one", SAND)
        self.ok("index")
        self.assertIsNone(self.owner("model:hall"))
        self.assertIsNotNone(self.owner(), "negative: the other owner stays")


class AskedTest(IndexCase):
    """What needs a texture's file is read when the texture is asked for by name, and kept."""

    def test_a_texture_nobody_asked_for_is_listed_and_its_original_is_not_read(
        self,
    ) -> None:
        self.add(ROCK)
        answer = self.ok("index")
        self.assertEqual(
            (answer["textures"], answer["owners"], answer["written"], answer["judged"]),
            (1, 1, 2, []),
            "one texture row and one owner row written",
        )
        self.assertEqual(
            self.ok("index")["written"], 0, "negative: rows as before are not written again"
        )
        rock = self.state()
        self.assertEqual(
            (rock["judged"], rock["asks"], rock["variants"]), (False, [], [])
        )
        self.assertEqual(
            self.folder_game.read, [], "negative: listing reads no original"
        )
        self.assertEqual(self.ok("index", "--asset", ROCK)["judged"], [ROCK])
        self.assertEqual(
            (self.state()["judged"], askable(self.state())), (True, MODELS)
        )

    def test_a_role_that_needs_the_file_is_found_once_and_kept(self) -> None:
        self.add(ROCK)
        self.folder_game.add(
            "one",
            MOSS,
            texture_file("diffuse", colour_rgba(4)),
            role=None,
            judged=False,
        )
        self.ok("index")
        self.assertEqual(
            (self.state(MOSS)["judged"], self.state(MOSS)["asks"]), (False, [])
        )
        self.assertEqual(self.folder_game.judged, [])
        self.ok("index", "--asset", MOSS)
        self.assertEqual(
            (self.state(MOSS)["judged"], askable(self.state(MOSS))), (True, MODELS)
        )
        self.assertEqual(
            self.ok("index")["written"],
            0,
            "a second run with nothing changed writes no row",
        )
        self.assertEqual(self.state(MOSS)["judged"], True)
        self.assertEqual(
            self.folder_game.judged, [MOSS], "negative: it is not judged again"
        )

    def test_a_role_is_forgotten_when_the_file_it_was_read_from_changed(self) -> None:
        self.add(ROCK)
        self.folder_game.add(
            "one",
            MOSS,
            texture_file("diffuse", colour_rgba(4)),
            role=None,
            judged=False,
        )
        self.ok("index", "--asset", MOSS)
        self.rewrite(MOSS, 5)
        self.ok("index")
        self.assertEqual(
            (self.state(MOSS)["judged"], self.state(MOSS)["asks"]), (False, [])
        )
        self.ok("index", "--asset", MOSS)
        self.assertEqual(self.state(MOSS)["judged"], True)
        self.assertEqual(self.folder_game.judged, [MOSS, MOSS])

    def test_a_texture_that_cannot_be_upscaled_says_why_and_its_file_is_not_read(
        self,
    ) -> None:
        self.folder_game.add("one", SAND, b"", role=None, reason="it is a cube map")
        self.ok("index")
        sand = self.state(SAND)
        self.assertEqual(
            (sand["judged"], sand["reason"], sand["asks"]),
            (True, "it is a cube map", []),
        )
        self.assertEqual(self.folder_game.read, [])

    def test_an_original_whose_header_cannot_be_read_says_why_and_offers_nothing(
        self,
    ) -> None:
        # Schema 3 keeps the reason with the original; no size stands in for it.
        self.add(ROCK)
        self.folder_game.add("one", SAND, b"not a texture", role="diffuse")
        self.ok("index", "--asset", SAND, "--asset", ROCK)
        sand = self.state(SAND)
        self.assertIn("its original's header cannot be read", sand["reason"])
        self.assertEqual(sand["asks"], [], "negative: no request is offered")
        rock = self.state(ROCK)
        self.assertEqual(
            (rock["reason"], askable(rock)),
            ("", MODELS),
            "negative: a readable original is offered every model",
        )

    def test_a_texture_the_dataset_lacks_cannot_be_asked_for(self) -> None:
        self.add(ROCK)
        self.assertIn(
            f"one has no texture {NONE}", self.error("index", "--asset", NONE)
        )
        self.assertFalse(
            (self.store.root / FILE).exists(),
            "negative: a refused command writes no index",
        )


class WriteTest(IndexCase):
    def test_a_request_writes_the_state_of_a_dataset_that_was_never_indexed(
        self,
    ) -> None:
        self.add(ROCK)
        self.add(SAND, seed=4)
        self.ok("request", "--asset", ROCK, "--variant", UP)
        found = self.read(ROCK, SAND)
        self.assertEqual(
            [one["id"] for one in found["textures"][ROCK]["variants"]], [UP]
        )
        self.assertEqual(
            found["unknown"],
            [SAND],
            "negative: only the texture that changed is written",
        )

    def test_datasets_that_share_an_original_both_show_its_variant(self) -> None:
        self.add(ROCK)
        self.add(ROCK, dataset="two")
        self.folder_game.add(
            "three", ROCK, texture_file("diffuse", colour_rgba(7, 64, 64)), own=True
        )
        self.run_in("two", "index")
        self.run_in("three", "index")
        self.ok("request", "--asset", ROCK, "--variant", UP)
        self.assertEqual(
            [one["id"] for one in self.state(dataset="two")["variants"]],
            [UP],
            "R-HD-87",
        )
        self.assertEqual(
            self.state(dataset="three")["variants"],
            [],
            "negative: a file of its own is another original",
        )

    def test_a_texture_bake_writes_its_row_only(self) -> None:
        self.add(SAND, kind=FLOOR)
        self.add(ROCK, seed=4)
        self.ok("request", "--asset", SAND, "--variant", UP)
        self.ok("index")
        before = self.state(ROCK)
        self.ok("bake", "--asset", SAND, "--variant", UP)
        self.assertEqual(self.state(SAND)["bake"], UP)
        self.assertEqual(
            self.state(ROCK), before, "negative: another texture's row is as it was"
        )
        self.assertIn(
            "is not made", self.error("bake", "--asset", ROCK, "--variant", UP)
        )
        self.assertIsNone(
            self.state(ROCK)["bake"], "negative: a refused bake changes no row"
        )

    def test_the_state_follows_a_request_while_it_runs(self) -> None:
        self.add(ROCK)
        self.runner.hold = True
        seen: list[str] = []
        programs: set[tuple[int, int]] = set()

        def look() -> None:
            request = self.state()["requests"]["pbrify"]
            seen.append(request["state"])
            programs.add((request["pid"], request["started"]))

        def wait(_seconds: float) -> None:
            look()
            self.runner.advance()

        encoder = encode.encode

        def watched(*args, **kwargs):
            look()
            return encoder(*args, **kwargs)

        found = self.dataset()
        with mock.patch.object(encode, "encode", watched):
            requests.make(found, self.runner, found.texture(ROCK), UP, wait=wait)
        self.assertEqual(
            seen,
            [
                progress.QUEUED,
                progress.UPSCALING,
                progress.UPSCALING,
                progress.ENCODING,
            ],
        )
        self.assertEqual(
            programs,
            {(os.getpid(), progress.started(os.getpid()))},
            "a reader can tell that the program is gone",
        )
        rock = self.state()
        self.assertEqual(
            (rock["requests"], [one["id"] for one in rock["variants"]]), ({}, [UP])
        )
