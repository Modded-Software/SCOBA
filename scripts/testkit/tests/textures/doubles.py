"""The second implementations of the core's interfaces: a made-up game and a stand-in upscaler (R-HD-111)."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path
from unittest import mock

import numpy as np
from hdtex.core import registry
from hdtex.core.dataset import Dataset, DatasetError
from hdtex.core.interfaces import (
    DONE,
    FAILED,
    LOST,
    MODEL,
    RUNNING,
    WAITING,
    JobState,
    Owner,
    OwnerBake,
    Packed,
    Texture,
)
from hdtex.core.steps import SCALE
from hdtex.core.store import Store
from PIL import Image

from testkit.tests.textures.fixtures import colour_rgba, smooth, texture_file

GAME = "foldergame"
FLOOR = "floor"  # the kind of texture the folder game bakes on its own
ORIGINAL_WORD = (
    "original"  # what names.json holds for a texture a bake shows as its original
)
PACKED = "hd"
NAMES = "names.json"
ROCK = "textures\\rock.dds"
ORIGIN = "storage\\"  # an origin in the game's storage begins with it


class FolderGame:
    """A game whose storage is a folder.

    <root>/storage/<asset>                    the game's own files
    <root>/datasets/<dataset>/textures.json   what the dataset uses, as a list of descriptions
    <root>/datasets/<dataset>/files/<asset>   a file of the dataset's own; it wins over the storage
    """

    id = GAME
    alone = frozenset({FLOOR})  # a floor texture is baked on its own, as SC2's terrain

    def __init__(self, root: Path) -> None:
        self.root = root
        self.bakes = ""  # it bakes; a test sets a reason to have it bake nothing (R-HD-115)
        self.read: list[str] = []  # the assets whose original was asked for
        self.judged: list[str] = []  # the assets whose role was asked for
        self.owners_listed = 0  # how often every owner was listed
        self.textures_listed = 0  # how often every texture was listed

    def _own(self, dataset: str, asset: str) -> Path:
        return self.root / "datasets" / dataset / "files" / asset.replace("\\", "/")

    def add(
        self,
        dataset: str,
        asset: str,
        data: bytes,
        own: bool = False,
        **described: object,
    ) -> None:
        """Put a texture into the storage, or into the dataset's own files, and describe it."""
        path = (
            self._own(dataset, asset)
            if own
            else self.root / "storage" / asset.replace("\\", "/")
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        listing = self.root / "datasets" / dataset / "textures.json"
        listing.parent.mkdir(parents=True, exist_ok=True)
        known = json.loads(listing.read_text()) if listing.is_file() else []
        entry = {
            "asset": asset,
            "kind": "wall",
            "role": "diffuse",
            "reason": "",
            "tiles": True,
            "grid": [1, 1],
            "users": ["room"],
            **described,
        }
        listing.write_text(
            json.dumps([item for item in known if item["asset"] != asset] + [entry])
        )

    def use(self, dataset: str, layer: Path) -> None:
        raise DatasetError(
            f"{GAME} keeps the files of {dataset} itself; it takes no folder"
        )

    def drop(self, dataset: str, asset: str) -> None:
        """The dataset uses the texture no longer. Its file stays."""
        listing = self.root / "datasets" / dataset / "textures.json"
        listing.write_text(
            json.dumps(
                [
                    item
                    for item in json.loads(listing.read_text())
                    if item["asset"] != asset
                ]
            )
        )

    def datasets(self) -> tuple[str, ...]:
        folder = self.root / "datasets"
        return (
            tuple(sorted(path.name for path in folder.iterdir()))
            if folder.is_dir()
            else ()
        )

    def textures(self, dataset: str) -> list[Texture]:
        self.textures_listed += 1
        found = []
        for item in json.loads(
            (self.root / "datasets" / dataset / "textures.json").read_text()
        ):
            own = self._own(dataset, item["asset"]).is_file()
            origin = (
                f"dataset\\{dataset}\\{item['asset']}"
                if own
                else f"storage\\{item['asset']}"
            )
            described = (
                item["asset"],
                origin,
                item["kind"],
                item["role"],
                item["reason"],
                item["tiles"],
                tuple(item["grid"]),
                tuple(item["users"]),
            )
            found.append(
                Texture(
                    *described,
                    judged=item.get("judged", True),
                    entries=tuple(item.get("entries", ())),
                )
            )
        return found

    def judge(self, dataset: str, texture: Texture) -> Texture:
        """A texture described as not judged gets the role its file name ends with: rock.diffuse.dds."""
        self.judged.append(texture.asset)
        return texture._replace(role=texture.asset.rsplit(".", 2)[-2], judged=True)

    def original(self, dataset: str, texture: Texture) -> Path:
        self.read.append(texture.asset)
        own = self._own(dataset, texture.asset)
        return (
            own
            if own.is_file()
            else self.root / "storage" / texture.asset.replace("\\", "/")
        )

    def origins(self, dataset: str) -> dict[str, str]:
        """Every file of the storage, and over it every file of the dataset's own."""
        found = {}
        for prefix, folder in (
            (ORIGIN, self.root / "storage"),
            (f"dataset\\{dataset}\\", self.root / "datasets" / dataset / "files"),
        ):
            for path in sorted(folder.rglob("*")) if folder.is_dir() else ():
                if path.is_file():
                    asset = "\\".join(path.relative_to(folder).parts)
                    found[asset] = prefix + asset
        return found

    def fetch(self, dataset: str, textures: list[Texture]) -> None:
        """The folder is at hand already."""

    def owners(self, dataset: str) -> list[Owner]:
        """Each user of a texture is a model owner; `owners.json` of the dataset adds owners above them."""
        self.owners_listed += 1
        found: dict[str, set[str]] = {}
        for texture in self.textures(dataset):
            for user in texture.users:
                found.setdefault(f"{MODEL}:{user}", set()).add(texture.asset)
        owners = [
            Owner(key, key.split(":", 1)[1], MODEL, (), tuple(sorted(assets)))
            for key, assets in sorted(found.items())
        ]
        extra = self.root / "datasets" / dataset / "owners.json"
        for item in json.loads(extra.read_text()) if extra.is_file() else []:
            below = tuple(item["below"])
            assets = sorted(
                {
                    asset
                    for owner in owners
                    if owner.id in below
                    for asset in owner.textures
                }
            )
            owners.append(
                Owner(
                    item["id"],
                    item["id"].split(":", 1)[1],
                    item["id"].split(":", 1)[0],
                    below,
                    tuple(assets),
                )
            )
        return owners

    def gaps(self, dataset: str) -> dict[str, list[str]]:
        """A folder game leaves nothing out."""
        return {}

    def above(self, dataset: str, owner: str, below: list[str]) -> None:
        """Add an owner of a layer above the model files `below`."""
        extra = self.root / "datasets" / dataset / "owners.json"
        known = json.loads(extra.read_text()) if extra.is_file() else []
        extra.write_text(json.dumps([*known, {"id": owner, "below": below}]))

    def package(
        self,
        dataset: str,
        files: list[Packed],
        owners: list[OwnerBake],
        alone: dict[str, str],
        target: Path,
    ) -> dict[tuple[str, str], str]:
        """Each file under its asset and variant; `names.json` holds what each owner and texture shows."""
        paths: dict[tuple[str, str], str] = {}
        for item in files:
            name = (
                f"{PACKED}/{item.variant}/{item.texture.asset.rsplit(chr(92), 1)[-1]}"
            )
            (target / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(item.file, target / name)
            paths[item.texture.asset, item.variant] = name
        # `original` names no file: names.json holds the word.
        shows = {
            bake.owner.id: {
                asset: paths.get((asset, variant), variant)
                for asset, variant in bake.textures.items()
            }
            for bake in owners
        }
        shows["alone"] = {
            asset: paths[asset, variant] for asset, variant in alone.items()
        }
        (target / NAMES).write_text(json.dumps(shows))
        return paths

    def check(self, target: Path) -> None:
        names = json.loads((target / NAMES).read_text())
        if missing := sorted(
            name
            for shown in names.values()
            for name in shown.values()
            if name != ORIGINAL_WORD and not (target / name).is_file()
        ):
            raise ValueError(f"the package names {missing[0]}, which is not in it")


class StandIn:
    """An upscaler without a GPU. A job is done when `submit` returns, unless the test holds it."""

    id = "standin"

    def __init__(self, enlarge: Callable[[np.ndarray], np.ndarray] = smooth) -> None:
        self.enlarge = enlarge
        self.tool = "v1"
        self.asked: list[
            tuple[str, str]
        ] = []  # (plane file name, model) of every submit
        self.hold = False  # jobs wait until `advance`
        self.fail: dict[str, str] = {}  # model to the error its jobs fail with
        self.broken = False  # a job leaves half a file
        self.empty = False  # a job ends and writes nothing
        self.no_worker = ""  # why no job will start; empty: a worker runs
        self.looks = 0  # how often `idle` was asked
        self.tiling: list[bool] = []  # `tiles` of each submit, in order
        self.jobs: dict[
            str, tuple[JobState, Path, Path]
        ] = {}  # every job ever asked for, by name

    def version(self) -> str:
        return self.tool

    def output(self, plane: Path, folder: Path) -> Path:
        return folder / f"{plane.stem}_{SCALE}x.png"

    def _finish(self, job: str) -> None:
        _state, plane, output = self.jobs[job]
        self.jobs[job] = (JobState(DONE), plane, output)
        if self.empty:
            return
        output.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(plane) as image:
            Image.fromarray(self.enlarge(np.asarray(image))).save(output)
        if self.broken:
            output.write_bytes(output.read_bytes()[:40])

    def submit(self, plane: Path, folder: Path, model: str, tiles: bool) -> str:
        self.asked.append((plane.name, model))
        self.tiling.append(tiles)
        job = f"{len(self.asked):04d}.json"
        state = (
            JobState(FAILED, self.fail[model])
            if model in self.fail
            else JobState(WAITING)
        )
        self.jobs[job] = (state, plane, self.output(plane, folder))
        if state.state == WAITING and not self.hold:
            self._finish(job)
        return job

    def state(self, job: str) -> JobState:
        return (
            self.jobs[job][0]
            if job in self.jobs
            else JobState(LOST, f"job {job} is not in the queue")
        )

    def idle(self) -> str:
        self.looks += 1
        return self.no_worker

    def worker(self, log: Path) -> tuple[list[str], dict[str, str]]:
        """A worker that only says it ran: the test starts it and reads the log."""
        return [
            sys.executable,
            "-c",
            f"open({str(log)!r}, 'a').write('standin worker\\n')",
        ], {"STANDIN_WORKER": "1"}

    def forget(self) -> None:
        """Somebody empties the queue."""
        self.jobs.clear()

    def advance(self) -> None:
        """One move of the worker: the job that runs ends, and the oldest that waits starts."""
        for job, (state, _plane, _output) in list(self.jobs.items()):
            if state.state == RUNNING:
                self._finish(job)
        for job, (state, plane, output) in self.jobs.items():
            if state.state == WAITING:
                self.jobs[job] = (JobState(RUNNING), plane, output)
                return


class Case(unittest.TestCase):
    """A store, the folder game registered for the length of one test, and a stand-in upscaler."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.folder_game = FolderGame(self.root / "game")
        registered = mock.patch.dict(registry.GAMES.items, {GAME: self.folder_game})
        registered.start()
        self.addCleanup(registered.stop)
        self.store = Store(self.root / "store")
        self.runner = StandIn()

    def add(
        self,
        asset: str = ROCK,
        dataset: str = "one",
        seed: int = 1,
        size: int = 64,
        role: str = "diffuse",
        **described: object,
    ) -> None:
        """A small colour texture in the game's storage, used by `dataset`."""
        self.folder_game.add(
            dataset,
            asset,
            texture_file(role, colour_rgba(seed, size, size)),
            role=role,
            **described,
        )

    def dataset(self, name: str = "one") -> Dataset:
        """The dataset as the game lists it now. The stand-in upscaler says how far its requests are."""
        return Dataset(self.store, GAME, name, runner=lambda: self.runner)
