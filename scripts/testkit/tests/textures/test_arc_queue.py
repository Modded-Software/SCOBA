"""The arc-upscale runner against the tool's own queue and worker. No GPU (R-HD-95, R-HD-98, R-HD-99).

The tool's own code runs: its submit and queue commands, its spool, its
worker loop. Two things are stand-ins. The model and the GPU are those of
the tool's tests/stalled.py. The launcher is a script that starts the
tool's Python with a project folder of the test's own, so the queue of this
host is not touched.
"""

from __future__ import annotations

import os
import subprocess
import time
from collections.abc import Callable
from unittest import mock

from hdtex.core import requests, runner
from hdtex.core.interfaces import FAILED, LOST, WAITING, JobState
from hdtex.core.requests import RequestError
from hdtex.core.runner import ArcRunner, RunnerError

from testkit.tests.textures.doubles import ROCK, Case

LIMIT_SECONDS = 60.0  # for the worker to start, and for it to end


class ArcQueueCase(Case):
    def setUp(self) -> None:
        super().setUp()
        self.real = ArcRunner().root
        self.python = self.real / ".venv" / "bin" / "python3"
        self.assertTrue(
            self.python.is_file(), f"{self.python} is missing; run: make install-hdtex"
        )
        self.project = self.root.resolve() / "tool"
        for name in runner.PIXEL_FILES:
            link = self.project / name
            link.parent.mkdir(parents=True, exist_ok=True)
            link.symlink_to(self.real / name)
        launcher = self.project / "arc-upscale"
        launcher.write_text(
            f'#!/bin/bash\nexec "{self.python}" "{self.real / "upscale.py"}" "$@"\n'
        )
        launcher.chmod(0o755)
        environment = mock.patch.dict(
            os.environ, {runner.ENV: str(launcher), runner.ROOT_ENV: str(self.project)}
        )
        environment.start()
        self.addCleanup(environment.stop)
        self.arc = ArcRunner()
        self.worker_log = self.project / "worker.log"

    def worker(self, *words: str) -> subprocess.Popen:
        """The tool's worker with a stand-in model, on the test's queue."""
        env = {
            key: value
            for key, value in os.environ.items()
            if key not in runner.CALLERS_PYTHON
        }
        env |= {
            "STALL_CASE": "quick",
            "PYTHONPATH": str(self.real),
            runner.ROOT_ENV: str(self.project),
        }
        command = [
            str(self.python),
            str(self.real / "tests" / "stalled.py"),
            "worker",
            "-g",
            "1",
            "--log",
            str(self.worker_log),
            *words,
        ]
        said = (self.project / "worker.out").open("ab")
        self.addCleanup(said.close)
        process = subprocess.Popen(
            command, env=env, stdout=said, stderr=subprocess.STDOUT
        )
        self.addCleanup(self.stop, process)
        return process

    def stop(self, process: subprocess.Popen) -> None:
        if process.poll() is None:
            process.terminate()
        process.wait(timeout=LIMIT_SECONDS)

    def said(self) -> str:
        """What the worker wrote, for the message of a failed check."""
        return "\n".join(
            path.read_text()
            for path in (self.project / "worker.out", self.worker_log)
            if path.is_file()
        )

    def until(self, reached: Callable[[], bool], what: str) -> None:
        end = time.monotonic() + LIMIT_SECONDS
        while not reached():
            self.assertLess(
                time.monotonic(),
                end,
                f"after {LIMIT_SECONDS:.0f} s not yet: {what}\n{self.said()}",
            )
            time.sleep(0.2)

    def names(self, place: str) -> list[str]:
        return sorted(path.name for path in self.arc.queue.glob(f"{place}/*.json"))


class RequestTest(ArcQueueCase):
    def test_a_request_fails_without_a_worker_and_is_made_once_one_runs(self) -> None:
        self.add()
        found = self.dataset()
        with self.assertRaises(RequestError) as failed:
            requests.make(
                found,
                self.arc,
                found.texture(ROCK),
                "pbrify@256",
                wait=lambda _seconds: None,
            )
        self.assertIn(
            f"2 jobs waited 30 s and no arc-upscale worker runs on the queue {self.arc.queue}",
            str(failed.exception),
        )
        asked = self.names("pending")
        self.assertEqual(
            [self.arc.state(job) for job in asked],
            [JobState(WAITING), JobState(WAITING)],
        )

        worker = self.worker()
        self.until(lambda: self.arc.idle() == "", "the worker holds its lock")
        made = requests.make(found, self.arc, found.texture(ROCK), "pbrify@256")
        self.assertEqual(
            (made["size"], made["runner"]), ([256, 256], self.arc.version())
        )
        self.assertEqual(
            self.names("done"),
            asked,
            f"the jobs asked for first are the ones that were done\n{self.said()}",
        )
        self.assertEqual(
            self.names("pending") + self.names("working/*") + self.names("failed"), []
        )
        log = (
            self.store.game(self.folder_game.id).recipe_dir(
                f"storage\\{ROCK}", "pbrify"
            )
            / requests.LOG_FILE
        ).read_text()
        for job in asked:
            self.assertIn(f"job {job}", log)
        self.assertIn(f"{self.arc.tool} submit --json", log)

        self.stop(worker)
        self.assertIn("no arc-upscale worker runs", self.arc.idle())


class JobTest(ArcQueueCase):
    def test_a_job_the_tool_fails_has_the_tools_reason_and_a_removed_job_is_lost(
        self,
    ) -> None:
        plane = self.root.resolve() / "plane.png"
        plane.write_bytes(b"no image")
        job = self.arc.submit(plane, self.root / "out", "fast", True)
        self.assertEqual(self.arc.state(job), JobState(WAITING))
        self.assertEqual(
            self.worker("--until-empty").wait(timeout=LIMIT_SECONDS), 0, self.said()
        )
        self.assertEqual(
            self.arc.state(job),
            JobState(FAILED, f"not a readable image: {plane}"),
            self.said(),
        )
        (self.arc.queue / "failed" / job).unlink()
        self.assertEqual(self.arc.state(job).state, LOST)

    def test_a_job_the_tool_refuses_raises_with_the_tools_reason(self) -> None:
        with self.assertRaises(RunnerError) as refused:
            self.arc.submit(self.root / "missing.png", self.root / "out", "fast", True)
        self.assertIn(
            "exit status 1: stderr 'arc-upscale: error: input does not exist",
            str(refused.exception),
        )
        self.assertEqual(self.names("pending"), [])
