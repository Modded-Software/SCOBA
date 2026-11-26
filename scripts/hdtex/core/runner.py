"""The upscaler: the arc-upscale tool, through its job queue.

This module does three things: it hands a plane to `arc-upscale submit`, it
reads which folder of the tool's queue a job file is in, and it asks
`arc-upscale queue` whether a worker runs. The tool owns the queue, its
worker, its lock, its retries and its stall watch. Who starts the worker is
not this module's business.

A job is found again by the file name the tool gave it.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import subprocess
import time
from pathlib import Path

from project_root import project_root

from .interfaces import DONE, FAILED, LOST, RUNNING, WAITING, JobState
from .registry import RUNNERS
from .steps import SCALE

ID = "arc"
ENV = "ARC_UPSCALE"
ROOT_ENV = "ARC_UPSCALE_ROOT"  # the tool's own setting for its project folder
CALLERS_PYTHON = (
    "VIRTUAL_ENV",
    "PYTHONPATH",
)  # settings of this program's Python, not of the tool's
# What decides the tool's pixels: its locked dependencies, its models, and how it runs them.
# Its queue and its command line are not in the list.
PIXEL_FILES = (
    "uv.lock",
    "arc_upscale/catalog.py",
    "arc_upscale/upscalers.py",
    "arc_upscale/upscaling.py",
)
# The tool's queue folders, in the order a job passes them, and what each means.
PLACES = (
    ("pending", WAITING),
    ("working/*", RUNNING),
    ("done", DONE),
    ("failed", FAILED),
)
# A job goes back from working/ to pending/ once, when a new worker starts. A look
# that passes the folders in order can miss that one move. The second look finds it.
LOOKS = 2
JOB_NAME = re.compile(r"[0-9a-f-]+\.json")
# The GPU of the worker. GPU 0 drives the desktop (R-HD-98, operator 2026-11-24: "move it to GPU1").
WORKER_GPU = 1

LOG = logging.getLogger(__name__)


class RunnerError(RuntimeError):
    """The tool is missing, refused a job, or answered what this module cannot read."""


def find_tool() -> Path:
    """The arc-upscale script: ARC_UPSCALE, or the checkout next to this project."""
    value = os.environ.get(ENV)
    tool = (
        Path(value)
        if value
        else project_root().parent / "upscale-on-arc" / "arc-upscale"
    )
    if not tool.is_file():
        raise RunnerError(
            f"arc-upscale not found at {tool}; set {ENV} to its path, or run: make install-hdtex"
        )
    return tool.resolve()


class ArcRunner:
    id = ID

    def __init__(self) -> None:
        self.tool = find_tool()
        # The tool's project, by the tool's own rule.
        self.root = Path(os.environ.get(ROOT_ENV) or self.tool.parent)
        # The tool's default queue: one per host, so its lock keeps one worker per GPU.
        self.queue = self.root / "queue"

    def version(self) -> str:
        digest = hashlib.sha256()
        for name in PIXEL_FILES:
            path = self.root / name
            if not path.is_file():
                raise RunnerError(
                    f"{path} is missing; the arc-upscale checkout at {self.root} is not complete"
                )
            digest.update(name.encode())
            digest.update(path.read_bytes())
        return digest.hexdigest()

    def output(self, plane: Path, folder: Path) -> Path:
        """The file the tool writes for `plane` into `folder`."""
        return folder / f"{plane.stem}_{SCALE}x.png"

    def _ask(self, *words: str) -> dict:
        """Run one command of the tool that answers in JSON. Returns the answer."""
        # The caller's Python must not leak into the tool's own. The tool gets its
        # project folder from here, so it need not find it from its own path.
        env = {
            key: value for key, value in os.environ.items() if key not in CALLERS_PYTHON
        } | {ROOT_ENV: str(self.root)}
        command = [str(self.tool), *words]
        start = time.monotonic()
        result = subprocess.run(
            command, env=env, text=True, capture_output=True, check=False
        )
        LOG.info(
            "%s: exit status %d after %.1f s",
            " ".join(command),
            result.returncode,
            time.monotonic() - start,
        )
        if result.returncode != 0:
            raise RunnerError(
                f"arc-upscale {words[0]} ended with exit status {result.returncode}: "
                f"stderr {result.stderr.strip()!r}, stdout {result.stdout.strip()!r}"
            )
        try:
            answer = json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise RunnerError(
                f"arc-upscale {words[0]} did not answer in JSON ({error}): {result.stdout.strip()!r}"
            ) from error
        if (
            not isinstance(answer, dict)
            or Path(str(answer.get("queue"))) != self.queue.resolve()
        ):
            raise RunnerError(
                f"arc-upscale {words[0]} did not answer for the queue {self.queue.resolve()}: {result.stdout.strip()!r}"
            )
        return answer

    def submit(self, plane: Path, folder: Path, model: str, tiles: bool) -> str:
        # --tiling makes the edges match across the border: only for a texture that repeats.
        words = ["submit", "--json", str(plane), "-o", str(folder), "-m", model, *(["--tiling"] if tiles else [])]
        job = self._ask(*words).get("job")
        if not isinstance(job, str) or not JOB_NAME.fullmatch(job):
            raise RunnerError(
                f"arc-upscale submit named no job file for {plane.name}: {job!r}"
            )
        LOG.info("job %s: %s with %s into %s", job, plane.name, model, folder)
        return job

    def state(self, job: str) -> JobState:
        """Which folder of the queue the job's file is in."""
        for _look in range(LOOKS):
            for place, state in PLACES:
                for path in self.queue.glob(f"{place}/{job}"):
                    if state != FAILED:
                        return JobState(state)
                    try:
                        error = json.loads(path.read_text()).get("error")
                    except json.JSONDecodeError as broken:
                        raise RunnerError(
                            f"the failed job {path} is not JSON: {broken}"
                        ) from broken
                    return JobState(FAILED, str(error or ""))
        return JobState(
            LOST,
            f"job {job} is in no folder of the queue {self.queue}; somebody removed it",
        )

    def idle(self) -> str:
        workers = self._ask("queue", "--json").get("workers")
        if not isinstance(workers, list):
            raise RunnerError(f"arc-upscale queue named no workers: {workers!r}")
        return (
            ""
            if workers
            else f"no arc-upscale worker runs on the queue {self.queue}; the viewer starts one"
        )

    def worker(self, log: Path) -> tuple[list[str], dict[str, str]]:
        return [str(self.tool), "worker", "-g", str(WORKER_GPU), "--log", str(log)], {
            ROOT_ENV: str(self.root)
        }


RUNNERS.add(ID, ArcRunner)
