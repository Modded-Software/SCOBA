"""The upscaler without a GPU (core/repeat.py) and the choice of the upscaler by HDTEX_RUNNER (SPEC-VIEWER 17.6)."""

from __future__ import annotations

import contextlib
import io
import json
import os
from unittest import mock

import numpy as np
from hdtex.core import cli
from hdtex.core.interfaces import DONE, LOST
from hdtex.core.repeat import RepeatRunner
from PIL import Image

from testkit.tests.textures.doubles import GAME, ROCK, Case


class RepeatTest(Case):
    def test_a_job_is_done_at_once_and_each_pixel_becomes_a_block(self) -> None:
        plane = self.root / "plane.png"
        pixels = np.array([[[10, 20, 30], [40, 50, 60]]], dtype=np.uint8)
        Image.fromarray(pixels).save(plane)
        runner = RepeatRunner()
        job = runner.submit(plane, self.root / "out", "fast", True)
        self.assertEqual(runner.state(job).state, DONE)
        with Image.open(runner.output(plane, self.root / "out")) as made:
            got = np.asarray(made)
        self.assertEqual(got.shape, (4, 8, 3))
        self.assertTrue(
            (got[:, :4] == pixels[0, 0]).all() and (got[:, 4:] == pixels[0, 1]).all()
        )
        self.assertEqual(runner.idle(), "", "no job waits for a worker")

    def test_negative_a_job_whose_output_is_gone_is_lost(self) -> None:
        self.assertEqual(RepeatRunner().state(str(self.root / "none.png")).state, LOST)


class ChoiceTest(Case):
    def run_cli(self, *words: str, runner: str | None) -> tuple[int, dict]:
        env = {
            key: value for key, value in os.environ.items() if key != cli.RUNNER_ENV
        } | ({cli.RUNNER_ENV: runner} if runner is not None else {})
        printed = io.StringIO()
        with (
            mock.patch.dict(os.environ, env, clear=True),
            contextlib.redirect_stdout(printed),
        ):
            status = cli.main(
                [*words[:1], "--game", GAME, "--dataset", "one", *words[1:]],
                store=self.store,
            )
        return status, json.loads(printed.getvalue())

    def test_repeat_makes_a_variant_without_a_gpu(self) -> None:
        self.add(ROCK)
        status, answer = self.run_cli(
            "request",
            "--asset",
            ROCK,
            "--model",
            "pbrify",
            "--factor",
            "4",
            runner="repeat",
        )
        self.assertEqual(status, 0, answer)
        made = answer["made"]
        self.assertEqual(
            [(one["asset"], one["variant"], one["recipe"]) for one in made],
            [(ROCK, "pbrify@256", "pbrify")],
        )
        self.assertEqual(sorted(made[0]["files"]), ["256"], "the size asked for; negative: no half (R-HD-123)")

    def test_negative_an_unknown_runner_is_refused_and_nothing_is_made(self) -> None:
        self.add(ROCK)
        status, answer = self.run_cli(
            "request", "--asset", ROCK, "--variant", "pbrify@256", runner="gpu0"
        )
        self.assertEqual(
            (status, answer),
            (1, {"error": "HDTEX_RUNNER is one of arc, repeat, not 'gpu0'"}),
        )
        self.assertEqual(self.dataset().made(self.dataset().texture(ROCK)), {})
