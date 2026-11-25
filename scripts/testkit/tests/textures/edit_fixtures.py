"""Edit sessions for the host tests: a session of the folder game's rock, and its scratch changed as a person would.

The scratch is changed by the commands of PhotoCraft's own renderer, so
these tests need it: without the install they fail and name
`make install-photocraft` (SPEC-PHOTOCRAFT 12). No GPU is used.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
from hdtex.core import edits, index, photocraft
from hdtex.core.index import Index
from hdtex.core.store import GameStore

from testkit.tests.textures.doubles import GAME, ROCK
from testkit.tests.textures.test_cli import CliCase

ORIGIN = f"storage\\{ROCK}"
RED = "#ff0000"


cmd = photocraft.cmd


def base_of(planes: list[str], plane: str) -> list[str]:
    """Select the layer `base` of a plane's group. The renderer counts the layers of one name from the bottom."""
    return cmd("layer.select", name=photocraft.BASE, occurrence=len(planes) - 1 - planes.index(plane))


def painted(planes: list[str], plane: str, colour: str = RED, name: str = "paint") -> list[str]:
    """A new layer over a plane's base, in its group, filled with one colour."""
    return base_of(planes, plane) + cmd("layer.new.layer", name=name) + cmd("edit.fill", contents="color", color=colour)


def left_half(size: int) -> list[str]:
    """A layer mask on the picked layer that shows its left half only."""
    return (
        cmd("select.rect", x=0, y=0, width=size // 2, height=size, antiAlias=False)
        + cmd("layer.layerMask.revealSelection")
        + cmd("select.deselect")
    )


def run_on(scratch: Path, *steps: list[str]) -> None:
    """Apply renderer commands to a scratch and save it over itself, as another program would."""
    words = [word for step in steps for word in step]
    saved = scratch.with_name(f"saved.{scratch.name}")
    try:
        subprocess.run(
            [str(photocraft.program()), "run", str(scratch), *words, "--out", str(saved), photocraft.NO_GPU],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as error:
        raise AssertionError(f"the renderer refused {words}: {error.stderr[-1500:]}") from error
    saved.replace(scratch)


class EditCase(CliCase):
    """A 64 by 64 colour texture, the rock, with its planes `color` and `alpha`."""

    SIZE = 64
    PLANES = ["color", "alpha"]

    def setUp(self) -> None:
        super().setUp()
        self.add()

    @property
    def game(self) -> GameStore:
        return self.store.game(GAME)

    def open(self, variant: str | None = None, asset: str = ROCK) -> dict:
        words = ["--asset", asset] + (["--variant", variant] if variant else [])
        return self.ok("edit", "open", *words)["session"]

    def check(self, session: str) -> dict:
        return self.ok("edit", "check", "--session", session)["session"]

    def folder(self, session: str) -> Path:
        return edits.session_dir(self.game, session)

    def scratch(self, session: str) -> Path:
        return self.folder(session) / edits.SCRATCH

    def change(self, session: str, *steps: list[str]) -> dict:
        """Change the scratch, then check it. Returns the session's state."""
        run_on(self.scratch(session), *steps)
        return self.check(session)

    def picture(self, session: str, folder: str, plane: str) -> np.ndarray:
        return edits.read_rgb(self.folder(session) / folder / f"{plane}.png", plane)

    def recipes(self) -> list[str]:
        return self.game.recipes(ORIGIN)

    def indexed(self, asset: str = ROCK) -> dict:
        """The texture's state as a reader gets it from the state index."""
        with Index(self.store.root).reading() as con:
            self.assertIsNotNone(con, "there is an index")
            return index.rows(con, GAME, "one", [asset])[asset].state
