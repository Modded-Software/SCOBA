"""An upscaler without a GPU, for the viewer's tests (SPEC-VIEWER 17.6).

It enlarges a plane by repeating each pixel, at once: a job is done when
`submit` returns. Its pixels say nothing of a real upscale. Chosen by
HDTEX_RUNNER=repeat (core/cli.py); webviewer/scripts/test.sh sets it.

A job is known by its output file, so a later process finds its state.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

from .interfaces import DONE, LOST, JobState
from .registry import RUNNERS
from .steps import SCALE

ID = "repeat"


class RepeatRunner:
    id = ID

    def version(self) -> str:
        return "repeat-1"

    def output(self, plane: Path, folder: Path) -> Path:
        return folder / f"{plane.stem}_{SCALE}x.png"

    def submit(self, plane: Path, folder: Path, model: str, tiles: bool) -> str:
        output = self.output(plane, folder)
        output.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(plane) as image:
            image.resize(
                (image.width * SCALE, image.height * SCALE), Image.Resampling.NEAREST
            ).save(output)
        return str(output)

    def state(self, job: str) -> JobState:
        return (
            JobState(DONE)
            if Path(job).is_file()
            else JobState(LOST, f"the output {job} is gone")
        )

    def idle(self) -> str:
        return ""  # every job is done when it is asked for: nothing waits for a worker

    def worker(self, log: Path) -> tuple[list[str], dict[str, str]]:
        """No worker is needed; this one only says it ran."""
        return [
            sys.executable,
            "-c",
            f"open({str(log)!r}, 'a').write('repeat runner: no worker needed\\n')",
        ], {}


RUNNERS.add(ID, RepeatRunner)
