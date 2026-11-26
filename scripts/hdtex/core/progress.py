"""How far a request is, and whether one may be made.

While a request runs, the recipe's folder holds request.json: which
program, which step, which upscale folders (`requests.make` writes it).
Nobody stores "queued" or "upscaling" there: `read` asks the runner where
the jobs are. A request whose program is gone has failed.

The job that makes an upscale folder is named in the folder's job.json, so
two requests for one plane wait for one job.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from . import variants
from .interfaces import DONE, FAILED, RUNNING, Runner, Texture
from .roles import ROLES  # loading it registers the roles
from .store import GameStore, origin_folder, read_json

FILE = "request.json"
LOG_FILE = "request.log"
JOB_FILE = "job.json"

QUEUED = "queued"
UPSCALING = "upscaling"
ENCODING = "encoding"


class RequestError(RuntimeError):
    """Why a request failed."""


def started(pid: int) -> int | None:
    """When the process began, in clock ticks since the host started. None: there is no such process.

    A process ID is given out again. The ID and this time together name one process.
    """
    path = Path(f"/proc/{pid}/stat")
    if not path.exists():
        return None
    return int(path.read_text().rsplit(")", 1)[1].split()[19])


def job_of(folder: Path) -> str | None:
    """The job that was last asked to fill an upscale folder. None: nobody asked."""
    path = folder / JOB_FILE
    return str(read_json(path)["job"]) if path.is_file() else None


def asked(game: GameStore, origin: str) -> list[str]:
    """The recipes of an origin that somebody makes, or failed to make."""
    return sorted(
        path.parent.name
        for path in (game.variants / origin_folder(origin)).glob(f"*/{FILE}")
    )


def read(
    game: GameStore, runner: Callable[[], Runner], origin: str, recipe: str
) -> dict | None:
    """The state of the request for one recipe. None: nobody makes it and nobody failed at it.

    A request that has not failed names its program by `pid` and `started`:
    whoever keeps the state can tell later that the program is gone.
    """
    folder = game.recipe_dir(origin, recipe)
    if not (folder / FILE).is_file():
        return None
    note = read_json(folder / FILE)
    where = {
        "step": note["step"],
        "steps": note["steps"],
        "planes": len(note["jobs"]),
        "done": 0,
        # The id it was asked as, for asking again; empty for the transfer of an edit.
        "variant": str(note.get("variant", "")),
        # Its start in seconds since 1970; None: a note written before it was kept.
        "since": note.get("since"),
        "log": str(folder / LOG_FILE),
    }
    if note["failed"]:
        return {"state": FAILED, "reason": note["failed"], **where}
    if started(note["pid"]) != note["started"]:
        return {"state": FAILED, "reason": gone(note["pid"]), **where}
    where |= {"pid": note["pid"], "started": note["started"]}
    if note["phase"] == ENCODING:
        return {"state": ENCODING, "reason": "", **where}
    jobs = [job for job in map(job_of, map(Path, note["jobs"])) if job is not None]
    found = [runner().state(job).state for job in jobs]
    states = set(found)
    return {
        "state": UPSCALING if states & {RUNNING, DONE} else QUEUED,
        "reason": "",
        **where,
        "done": found.count(DONE),
    }


def gone(pid: int) -> str:
    """Why a request whose program is gone has failed."""
    return f"the program that made it (process {pid}) stopped before it was done; ask again"


def has_colour(texture: Texture) -> bool:
    """Whether the texture has a colour plane. A texture without a role has none."""
    return texture.role is not None and any(
        plane.colour for plane in ROLES.get(texture.role).planes
    )


def model_refusal(texture: Texture, recipe: str) -> str:
    """Why nobody can ask for `recipe` of this texture, whatever its size. Empty: one can."""
    if texture.role is None:
        return f"it cannot be upscaled: {texture.reason}"
    return variants.model_refusal(recipe, has_colour(texture))


def refusal(texture: Texture, recipe: str, longest: int) -> str:
    """Why nobody can ask for `recipe` of this texture with that longest side. Empty: one can.

    A refusal is a fact of the texture and the recipe. It is worked out
    when asked and never kept.
    """
    if texture.role is None:
        return f"it cannot be upscaled: {texture.reason}"
    return variants.refusal(recipe, longest, has_colour(texture))
