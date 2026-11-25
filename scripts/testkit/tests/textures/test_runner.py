"""The arc-upscale runner: the tool's submit and queue commands, and a read of its queue (R-HD-95, R-HD-98, R-HD-99)."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from hdtex.core import registry, runner
from hdtex.core.interfaces import DONE, FAILED, LOST, RUNNING, WAITING, JobState
from hdtex.core.runner import ArcRunner, RunnerError

# A stand-in for the tool's launcher: it writes down what it was called with,
# into the project folder the runner names, and answers what the test left there.
RECORDER = """#!/bin/bash
printf '%s\\n' "$@" > "$ARC_UPSCALE_ROOT/called.txt"
printf '%s %s' "${VIRTUAL_ENV-unset}" "${PYTHONPATH-unset}" > "$ARC_UPSCALE_ROOT/python.txt"
if [[ -f "$ARC_UPSCALE_ROOT/refuse" ]]; then
    echo "error: unknown model" >&2
    exit 2
fi
cat "$ARC_UPSCALE_ROOT/answer.txt"
"""
JOB = "00000000001763998455-4242-0a1b2c3d.json"
PLANE = Path("/planes/ab/abcd.png")


class RunnerCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.checkout = Path(self.temp.name).resolve() / "tool"
        for name in runner.PIXEL_FILES + ("arc_upscale/jobs.py",):
            path = self.checkout / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(name)
        self.tool = self.checkout / "arc-upscale"
        self.tool.write_text(RECORDER)
        self.tool.chmod(0o755)
        self.queue = self.checkout / "queue"
        self.folder = Path(self.temp.name).resolve() / "store" / "upscaled" / "recipe"
        environment = mock.patch.dict(
            os.environ,
            {
                runner.ENV: str(self.tool),
                "VIRTUAL_ENV": "/some/venv",
                "PYTHONPATH": "/some/scripts",
            },
        )
        environment.start()
        self.addCleanup(environment.stop)
        os.environ.pop(runner.ROOT_ENV, None)
        self.answer(job=JOB)

    def answer(self, text: str | None = None, **said: object) -> None:
        """What the tool prints next. Without `text`: JSON for this queue, with what is `said`."""
        (self.checkout / "answer.txt").write_text(
            json.dumps({"queue": str(self.queue), **said}) if text is None else text
        )

    def called(self) -> list[str]:
        return (self.checkout / "called.txt").read_text().splitlines()

    def job(self, place: str, name: str = JOB, error: str | None = None) -> Path:
        """A job file as the tool writes it, in one folder of its queue."""
        path = self.queue / place / name
        path.parent.mkdir(parents=True, exist_ok=True)
        job = {
            "input": "/in.png",
            "output": str(self.folder),
            "model": "fast",
            "tile": None,
            "tiling": True,
            "error": error,
            "retries": 0,
        }
        path.write_text(json.dumps(job))
        return path

    def queue_files(self) -> list[str]:
        return sorted(
            str(path.relative_to(self.queue))
            for path in self.queue.rglob("*")
            if path.is_file()
        )


class ToolTest(RunnerCase):
    def test_the_runner_is_registered_and_made_when_needed(self) -> None:
        self.assertIs(registry.RUNNERS.get(runner.ID), ArcRunner)
        made = registry.RUNNERS.get(runner.ID)()
        self.assertEqual((made.tool, made.queue), (self.tool, self.queue))

    def test_a_missing_tool_is_refused_with_the_setting_to_use(self) -> None:
        self.tool.unlink()
        with self.assertRaises(RunnerError) as missing:
            ArcRunner()
        self.assertIn(runner.ENV, str(missing.exception))

    def test_the_version_follows_the_files_that_decide_the_pixels_only(self) -> None:
        before = ArcRunner().version()
        (self.checkout / "arc_upscale" / "jobs.py").write_text("another queue")
        self.assertEqual(ArcRunner().version(), before)
        (self.checkout / "arc_upscale" / "catalog.py").write_text("another model")
        self.assertNotEqual(ArcRunner().version(), before)

    def test_an_incomplete_checkout_has_no_version(self) -> None:
        (self.checkout / "uv.lock").unlink()
        with self.assertRaises(RunnerError):
            ArcRunner().version()

    def test_the_output_is_named_as_the_tool_names_it(self) -> None:
        self.assertEqual(
            ArcRunner().output(PLANE, self.folder), self.folder / "abcd_4x.png"
        )


class SubmitTest(RunnerCase):
    def test_a_job_goes_in_through_the_tools_submit_command_and_has_the_tools_name(
        self,
    ) -> None:
        with self.assertLogs(runner.LOG, "INFO") as logged:
            self.assertEqual(ArcRunner().submit(PLANE, self.folder, "pbrify"), JOB)
        self.assertEqual(
            self.called(),
            [
                "submit",
                "--json",
                str(PLANE),
                "-o",
                str(self.folder),
                "-m",
                "pbrify",
                "--tiling",
            ],
        )
        self.assertEqual(
            (self.checkout / "python.txt").read_text(),
            "unset unset",
            "the caller's Python settings stay out",
        )
        self.assertIn(
            f"job {JOB}: abcd.png with pbrify into {self.folder}",
            "\n".join(logged.output),
        )
        self.assertIn("exit status 0 after", "\n".join(logged.output))

    def test_the_runner_writes_nothing_into_the_queue_and_starts_no_worker(
        self,
    ) -> None:
        ArcRunner().submit(PLANE, self.folder, "fast")
        self.assertFalse(self.queue.exists())
        self.assertNotIn("worker", self.called())
        self.assertNotIn("--queue", self.called())

    def test_a_refused_job_raises_with_the_tools_words_and_its_exit_status(
        self,
    ) -> None:
        (self.checkout / "refuse").write_text("")
        with self.assertRaises(RunnerError) as refused:
            ArcRunner().submit(PLANE, self.folder, "nomodel")
        self.assertIn("exit status 2: error: unknown model", str(refused.exception))

    def test_an_answer_that_names_no_job_is_refused_with_the_answer(self) -> None:
        for text, reason in (
            ("queued something", "did not answer in JSON"),
            (
                json.dumps({"queue": "/another/queue", "job": JOB}),
                "did not answer for the queue",
            ),
            (json.dumps({"queue": str(self.queue)}), "named no job file"),
            (
                json.dumps({"queue": str(self.queue), "job": "../../etc/passwd"}),
                "named no job file",
            ),
        ):
            with self.subTest(text=text):
                self.answer(text)
                with self.assertRaises(RunnerError) as refused:
                    ArcRunner().submit(PLANE, self.folder, "fast")
                self.assertIn(reason, str(refused.exception))


class StateTest(RunnerCase):
    def test_a_job_is_where_its_file_is(self) -> None:
        made = ArcRunner()
        waiting = self.job("pending")
        self.assertEqual(made.state(JOB), JobState(WAITING))
        running = self.queue / "working" / "gpu1" / JOB
        running.parent.mkdir(parents=True)
        waiting.rename(running)
        self.assertEqual(made.state(JOB), JobState(RUNNING))
        done = self.queue / "done" / JOB
        done.parent.mkdir()
        running.rename(done)
        self.assertEqual(made.state(JOB), JobState(DONE))
        done.unlink()
        self.job("failed", error="out of GPU memory")
        self.assertEqual(made.state(JOB), JobState(FAILED, "out of GPU memory"))

    def test_a_job_in_no_folder_is_lost_and_the_queue_is_named(self) -> None:
        self.job("pending", name="another.json")
        self.job("failed", name="third.json", error="x")
        found = ArcRunner().state(JOB)
        self.assertEqual(found.state, LOST)
        self.assertIn(
            f"job {JOB} is in no folder of the queue {self.queue}", found.error
        )

    def test_a_queue_that_is_not_there_holds_no_job(self) -> None:
        self.assertEqual(ArcRunner().state(JOB).state, LOST)

    def test_a_failed_job_without_a_reason_has_none(self) -> None:
        self.job("failed")
        self.assertEqual(ArcRunner().state(JOB), JobState(FAILED, ""))

    def test_a_failed_job_that_cannot_be_read_is_an_error_with_its_path(self) -> None:
        self.job("failed").write_text("{")
        with self.assertRaises(RunnerError) as broken:
            ArcRunner().state(JOB)
        self.assertIn(str(self.queue / "failed" / JOB), str(broken.exception))

    def test_reading_the_state_changes_nothing_in_the_queue_and_calls_no_tool(
        self,
    ) -> None:
        self.job("pending")
        self.job("failed", name="another.json", error="x")
        before = self.queue_files()
        ArcRunner().state(JOB)
        self.assertEqual(self.queue_files(), before)
        self.assertFalse((self.checkout / "called.txt").exists())


class IdleTest(RunnerCase):
    def test_a_worker_that_runs_is_seen_through_the_tools_queue_command(self) -> None:
        self.answer(workers=[1])
        self.assertEqual(ArcRunner().idle(), "")
        self.assertEqual(self.called(), ["queue", "--json"])

    def test_no_worker_is_said_with_the_queue(self) -> None:
        self.answer(workers=[])
        self.assertIn(
            f"no arc-upscale worker runs on the queue {self.queue}", ArcRunner().idle()
        )

    def test_an_answer_without_workers_is_refused(self) -> None:
        self.answer(pending=[])
        with self.assertRaises(RunnerError) as refused:
            ArcRunner().idle()
        self.assertIn("named no workers", str(refused.exception))

    def test_a_queue_command_that_fails_is_an_error_with_the_tools_words(self) -> None:
        (self.checkout / "refuse").write_text("")
        with self.assertRaises(RunnerError) as refused:
            ArcRunner().idle()
        self.assertIn(
            "arc-upscale queue ended with exit status 2", str(refused.exception)
        )
