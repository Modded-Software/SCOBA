"""Request logs: each step with its time and process, and errors with their trace (R-HD-6, R-HD-90)."""

from __future__ import annotations

import logging
import os
from unittest import mock

from hdtex.core import encode, progress
from hdtex.core.interfaces import FAILED
from hdtex.core.requests import RequestError

from testkit.tests.textures.doubles import ROCK
from testkit.tests.textures.test_requests import UP, RequestCase


class LogTest(RequestCase):
    def log(self, variant: str = UP) -> str:
        return self.note(variant).with_name(progress.LOG_FILE).read_text()

    def test_a_request_writes_each_step_with_its_time_and_its_process(self) -> None:
        self.add()
        self.make()
        lines = self.log().splitlines()
        for line in lines:
            self.assertRegex(
                line,
                rf"^\d{{4}}-\d\d-\d\d \d\d:\d\d:\d\d,\d{{3}} {os.getpid()} hdtex\.core\.requests: ",
            )
        said = "\n".join(lines)
        self.assertIn(f"request: {ROCK}, pbrify, in dataset one", said)
        self.assertIn("job 0001.json for", said)
        self.assertIn("job 0002.json for", said)
        self.assertIn("step 1, pbrify: encoding", said)
        self.assertRegex(lines[-1], r"done after \d+\.\d s$")

    def test_the_log_is_closed_once_the_request_is_over_or_has_failed(self) -> None:
        self.add()
        core = logging.getLogger("hdtex.core")
        self.make()
        self.assertEqual((core.handlers, core.level), ([], logging.NOTSET))
        self.runner.fail = {"pbrify": "out of GPU memory", "fast": "out of GPU memory"}
        self.add(seed=2)
        with self.assertRaises(RequestError):
            self.make()
        self.assertEqual((core.handlers, core.level), ([], logging.NOTSET))

    def test_an_error_nobody_expected_is_kept_with_its_kind_and_its_trace(self) -> None:
        self.add()
        with (
            mock.patch.object(
                encode, "encode", side_effect=ZeroDivisionError("division by zero")
            ),
            self.assertRaises(RequestError) as failed,
        ):
            self.make()
        self.assertIn("ZeroDivisionError: division by zero", str(failed.exception))
        self.assertIn(
            str(self.note().with_name(progress.LOG_FILE)), str(failed.exception)
        )
        self.assertIsInstance(failed.exception.__cause__, ZeroDivisionError)
        state = self.read()
        self.assertEqual(
            (state["state"], state["reason"]),
            (FAILED, "ZeroDivisionError: division by zero"),
        )
        self.assertIn("Traceback (most recent call last)", self.log())
        self.assertIn("ZeroDivisionError: division by zero", self.log())

    def test_a_request_that_is_stopped_says_so_and_stops(self) -> None:
        self.add()
        self.runner.hold = True

        def stop(_seconds: float) -> None:
            raise KeyboardInterrupt

        with self.assertRaises(KeyboardInterrupt):
            self.make(wait=stop)
        self.assertEqual(self.read()["reason"], "KeyboardInterrupt: ")
        self.assertIn("KeyboardInterrupt", self.log())

    def test_a_failed_job_is_logged_with_the_upscalers_reason(self) -> None:
        self.add()
        self.runner.fail = {"fast": "out of GPU memory"}
        with self.assertRaises(RequestError):
            self.make()
        self.assertIn("job 0002.json for", self.log())
        self.assertIn("failed: out of GPU memory", self.log())
