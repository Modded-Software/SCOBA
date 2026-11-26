"""The state index: whoever changes a texture's or an owner's state writes it, and a reader only reads (R-HD-113, R-HD-114).

IndexCase and the names here serve test_index_write.py too.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest import mock

from hdtex.core import index, limits, requests, variants, view
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
HALF = "pbrify@128"  # the half of UP, 2x of 64: kept when it is asked for (R-HD-123)


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
            (found["head"]["factors"], found["head"]["maxSide"], found["unknown"]),
            ([2, 4], 4096, [NONE]),
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
        self.assertEqual(
            rock["asks"][0]["models"]["pbrify"]["factors"],
            {"2": {"size": 128, "reason": ""}, "4": {"size": 256, "reason": ""}},
            "2x and 4x of its side of 64",
        )

    def test_a_variant_whose_edges_were_made_for_the_other_rule_is_shown_with_edges_off_and_not_stale(self) -> None:
        self.add(ROCK)
        found = self.dataset()
        requests.make(found, self.runner, found.texture(ROCK), UP, wait=lambda _seconds: self.runner.advance())
        self.ok("index", "--asset", ROCK)
        [before] = [one for one in self.read(ROCK)["textures"][ROCK]["variants"] if one["id"] == UP]
        self.add(ROCK, tiles=False)  # the same file: it no longer repeats
        self.ok("index", "--asset", ROCK)
        [after] = [one for one in self.read(ROCK)["textures"][ROCK]["variants"] if one["id"] == UP]
        # Negative: made for its own rule, it is not marked.
        self.assertEqual((before["edgesOff"], before["stale"]), (False, False))
        self.assertEqual((after["edgesOff"], after["stale"], after["staleWhy"]), (True, False, ""))

    def test_a_variant_names_the_id_that_serves_a_request_of_it(self) -> None:
        """R-HD-158: `remake` is the variant's own id while it is sound, else the revision a request makes or finds."""
        self.add(ROCK)

        def ask() -> None:
            # Each size is asked for: one request keeps one size (R-HD-123).
            for variant in (UP, HALF):
                found = self.dataset()
                requests.make(found, self.runner, found.texture(ROCK), variant, wait=lambda _seconds: self.runner.advance())

        def remakes() -> dict[str, str]:
            return {one["id"]: one["remake"] for one in self.state()["variants"]}

        ask()
        self.ok("index", "--asset", ROCK)
        # Negative: sound, each is its own.
        self.assertEqual(remakes(), {UP: UP, HALF: HALF})
        self.add(ROCK, tiles=False)  # the same file: it no longer repeats
        self.ok("index", "--asset", ROCK)
        self.assertEqual(remakes(), {UP: "pbrify~2@256", HALF: "pbrify~2@128"})
        # The request writes the state: the revision is listed beside the kept one, and serves both.
        ask()
        self.assertEqual(
            remakes(),
            {UP: "pbrify~2@256", HALF: "pbrify~2@128", "pbrify~2@256": "pbrify~2@256", "pbrify~2@128": "pbrify~2@128"},
        )
        titles = {one["id"]: (one["title"], one["recipe"], one["edgesOff"]) for one in self.state()["variants"]}
        self.assertEqual(titles[UP], ("PBRify at 256", "pbrify", True))
        self.assertEqual(titles["pbrify~2@256"], ("PBRify #2 at 256", "pbrify~2", False))

    def test_the_head_names_the_hash_of_the_pipeline_code(self) -> None:
        self.add(ROCK)
        self.ok("index", "--asset", ROCK)
        code = self.read(ROCK)["head"]["code"]
        self.assertRegex(code, r"^[0-9a-f]{64}$")
        self.assertEqual(code, view.code())
        # Negative: another file content gives another hash.
        view.code.cache_clear()
        real = Path.read_bytes

        def changed(path: Path) -> bytes:
            return real(path) + (b"#" if path.name == "view.py" else b"")

        with mock.patch.object(Path, "read_bytes", changed):
            self.assertNotEqual(view.code(), code)
        view.code.cache_clear()
        self.assertEqual(view.code(), code)

    def test_index_states_writes_the_head_and_states_again_for_another_largest_side(self) -> None:
        self.add(ROCK, size=512)
        self.ok("index", "--asset", ROCK)
        read = list(self.folder_game.read)
        with mock.patch.dict(os.environ, {variants.MAX_SIDE_ENV: "1024"}):
            self.assertEqual(self.ok("index", "--states")["states"], True)
        found = self.read(ROCK)
        self.assertEqual(found["head"]["maxSide"], 1024)
        factors = found["textures"][ROCK]["asks"][0]["models"]["pbrify"]["factors"]
        self.assertEqual(factors["4"], {"size": 1024, "reason": ""}, "4x of 512 capped at 1024")
        self.assertEqual(self.folder_game.read, read, "negative: no original is read again")
        self.assertIn("index --states takes no --asset", self.error("index", "--states", "--asset", ROCK))

    def test_a_factor_past_the_largest_side_says_why(self) -> None:
        self.add(ROCK, size=2048)
        with mock.patch.dict(os.environ, {variants.MAX_SIDE_ENV: "2048"}):
            self.ok("index", "--asset", ROCK)
            found = self.read(ROCK)
        self.assertEqual(found["head"]["maxSide"], 2048)
        factors = found["textures"][ROCK]["asks"][0]["models"]["pbrify"]["factors"]
        self.assertEqual([factors[one]["size"] for one in ("2", "4")], [2048, 2048])
        for one in ("2", "4"):
            self.assertIn("that adds nothing", factors[one]["reason"], f"negative: {one}x")

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
        self.assertEqual([one["id"] for one in rock["variants"]], [UP], "negative: no half nobody asked for (R-HD-123)")
        variant = rock["variants"][0]
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
        # The half, asked for, is added: a variant and an input of its own.
        self.ok("request", "--asset", ROCK, "--variant", HALF)
        rock = self.state()
        self.assertEqual([one["id"] for one in rock["variants"]], [UP, HALF])
        self.assertEqual(inputs(rock), ["original", UP, HALF])
        self.assertEqual(
            rock["asks"][1]["models"]["pbrify"]["factors"],
            {"2": {"size": 512, "reason": ""}, "4": {"size": 1024, "reason": ""}},
            "a variant of 256 goes on to 512 or 1024",
        )

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
        variant = self.state()["variants"][0]
        self.assertEqual(variant["id"], UP)
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
            [{"name": "hd", "textures": {ROCK: UP}}],
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

    def test_an_owner_above_a_bake_shows_it_and_lists_only_the_skins_it_holds(self) -> None:
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
        # Negative: no unsaved New Skin is offered (R-HD-137).
        self.assertEqual(unit["skins"], [])
        self.ok("skin", "copy", "--owner", "unit:Room")
        self.assertEqual(self.owner("unit:Room")["skins"], [{"name": "New Skin 1", "textures": {}}])
        self.ok("skin", "delete", "--owner", "unit:Room", "--name", "New Skin 1")
        self.ok("unbake", "--owner", ROOM)
        unit = self.owner("unit:Room")
        self.assertEqual(
            (unit["shows"], unit["skins"]),
            ({ROCK: "original", SAND: "original"}, []),
            "negative: unbaked, it shows the original",
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
