"""What a game, a texture format, a channel layout and an upscaler must offer.

The core reaches each of them by id, through `registry`. It imports none.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple, Protocol

import numpy as np

Planes = dict[str, np.ndarray]

WAITING = "waiting"
RUNNING = "running"
DONE = "done"
FAILED = "failed"
LOST = "lost"  # the upscaler does not know the job


class GameError(RuntimeError):
    """A game cannot answer: its data is missing, or not as its adapter reads it."""


class Texture(NamedTuple):
    """One texture of a dataset, as its game describes it."""

    asset: str  # lower case, backslashes between folders
    origin: (
        str  # where the original lies; datasets with the same origin share its results
    )
    kind: str  # the game's word for what it is, such as "terrain"
    role: str | None  # None: the texture cannot be upscaled
    reason: str  # why it cannot; empty when it has a role
    tiles: bool
    grid: tuple[int, int]  # (columns, rows) of a flip book; (1, 1) otherwise
    users: tuple[str, ...]
    # False: the game must read the original to know the role, and has not. `judge` fills it in.
    judged: bool = True
    # The game's data entries that name it; the files one entry names belong together (a colour file and its normal map).
    entries: tuple[str, ...] = ()


class Packed(NamedTuple):
    """One baked variant file for a package."""

    texture: Texture
    variant: str
    file: Path
    sha256: str


UNIT, ACTOR, MODEL = (
    "unit",
    "actor",
    "model",
)  # the layers of an owner, top first (R-HD-130)


class Owner(NamedTuple):
    """What a skin belongs to (SPEC-HD-TEXTURES 4.1)."""

    id: str  # "<layer>:<key>"
    title: str
    layer: str  # UNIT, ACTOR or MODEL
    below: tuple[
        str, ...
    ]  # the owners of the layer below that it shows: its model files
    textures: tuple[str, ...]  # the assets of its model files


class OwnerBake(NamedTuple):
    """One owner's bake, for a package: the variant of each texture it names."""

    owner: Owner
    # asset -> variant id; `original` names no file and shows the original over the layer below
    textures: dict[str, str]


class Plane(NamedTuple):
    name: str
    colour: bool = (
        False  # a picture in light; otherwise amounts, which no model may invent
    )


class Role(NamedTuple):
    """How a texture splits into planes and joins again.

    `join(planes, source, wrap)` builds the mip chain, largest level first.
    `source` holds the planes of the original: the coarse content of the
    result is matched to it. `finish(levels, original)` restores what the
    planes do not carry, from the original's pixels.
    """

    name: str
    planes: tuple[Plane, ...]
    split: Callable[[np.ndarray], Planes]
    join: Callable[[Planes, Planes | None, bool], list[np.ndarray]]
    finish: Callable[[list[np.ndarray], np.ndarray], list[np.ndarray]] = (
        lambda levels, _original: levels
    )


class Codec(Protocol):
    """One compression format of a mip level."""

    id: str
    opaque: bool  # the encoder writes no alpha

    def level_size(self, width: int, height: int) -> int: ...

    def decode(self, data: bytes, width: int, height: int) -> np.ndarray: ...

    def encode(self, rgba: np.ndarray) -> bytes: ...


class JobState(NamedTuple):
    state: str  # WAITING, RUNNING, DONE, FAILED or LOST
    error: str = ""  # why, for FAILED and LOST


class Runner(Protocol):
    """An upscaler that enlarges one plane four times per side, some time after it is asked.

    A job is known by the name `submit` gives it.
    """

    id: str

    def version(self) -> str:
        """Changes when the same input and model would give other pixels."""
        ...

    def output(self, plane: Path, folder: Path) -> Path:
        """The file a job for `plane` leaves in `folder`. It is there once the job is done."""
        ...

    def submit(self, plane: Path, folder: Path, model: str) -> str:
        """Ask for the image file `plane` enlarged into `folder`, with edges made to match. Returns the job's name."""
        ...

    def state(self, job: str) -> JobState:
        """Where the job is. Every job has a state: one the upscaler does not know is LOST."""
        ...

    def idle(self) -> str:
        """Why a job that waits will not start. Empty: a worker runs."""
        ...

    def worker(self, log: Path) -> tuple[list[str], dict[str, str]]:
        """The command line and the settings that start the upscaler's one worker, which logs to `log`.

        The caller starts it, so the worker outlives the caller. A second worker is refused by the upscaler.
        """
        ...


class GameAdapter(Protocol):
    """One game."""

    id: str
    alone: frozenset[
        str
    ]  # the kinds of texture that are baked on their own, not through an owner (R-HD-145)

    def use(self, dataset: str, layer: Path) -> None:
        """Take the folder of a dataset's own files from the caller. A game that finds them itself refuses."""
        ...

    def datasets(self) -> tuple[str, ...]: ...

    def textures(self, dataset: str) -> list[Texture]:
        """Every texture of the dataset. Listing them reads no original."""
        ...

    def judge(self, dataset: str, texture: Texture) -> Texture:
        """The texture with its role, or the reason it has none. This may read the original."""
        ...

    def original(self, dataset: str, texture: Texture) -> Path:
        """The original as a file."""
        ...

    def origins(self, dataset: str) -> dict[str, str]:
        """The origin of every texture file the dataset can show, by asset: of those `textures` does not list too.

        Whoever shows a texture of the dataset finds its original here, so
        that nobody else decides where a file lies.
        """
        ...

    def fetch(self, dataset: str, textures: list[Texture]) -> None:
        """Have the originals of these textures at hand. A game whose storage is slow takes them out in one go."""
        ...

    def owners(self, dataset: str) -> list[Owner]:
        """Every owner the dataset shows, with its textures. Listing them reads no original."""
        ...

    def gaps(self, dataset: str) -> dict[str, list[str]]:
        """What the game data leaves out, found by the listings done so far: kind -> one line per entry, with the reason.

        A game without such gaps returns {}.
        """
        ...

    def package(
        self,
        dataset: str,
        files: list[Packed],
        owners: list[OwnerBake],
        terrain: dict[str, str],
        target: Path,
    ) -> dict[tuple[str, str], str]:
        """Put the baked files into `target` and point the game at them.

        `files`: every (asset, variant) a bake names, once. `owners`: the
        bakes of owners. `terrain`: asset -> variant of each terrain bake.
        Returns the path each (asset, variant) got.
        """
        ...

    def check(self, target: Path) -> None:
        """Raise when the package in `target` is not sound."""
        ...
