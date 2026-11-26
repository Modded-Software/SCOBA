"""The state index: a change writes the rows it changes, and a request's row follows it while it runs (R-HD-113, R-HD-114)."""

from __future__ import annotations

import os
from unittest import mock

from hdtex.core import encode, progress, requests

from testkit.tests.textures.doubles import FLOOR, ROCK
from testkit.tests.textures.fixtures import colour_rgba, texture_file
from testkit.tests.textures.test_cli import UP
from testkit.tests.textures.test_index import HALF, SAND, IndexCase


class WriteTest(IndexCase):
    def test_a_request_writes_the_state_of_a_dataset_that_was_never_indexed(
        self,
    ) -> None:
        self.add(ROCK)
        self.add(SAND, seed=4)
        self.ok("request", "--asset", ROCK, "--variant", UP)
        found = self.read(ROCK, SAND)
        self.assertEqual(
            [one["id"] for one in found["textures"][ROCK]["variants"]], [UP, HALF]
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
            [UP, HALF],
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
            (rock["requests"], [one["id"] for one in rock["variants"]]), ({}, [UP, HALF])
        )
