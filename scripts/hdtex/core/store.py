"""The texture store: every plane, every variant, every skin and bake, in one folder.

    format                               the layout version
    <game>/planes/                       what the upscaler takes, named by the hash of its pixels
    <game>/upscaled/<hash>/              what the upscaler gave for one plane and model, as it wrote it
    <game>/variants/<origin>/<recipe>/   entry.json and one file per kept size; request.json while it is made
    <game>/locks/                        one empty file per recipe ever written: the lock of its write
    <game>/datasets/<dataset>/           skins/, bakes.json, package record
    <game>/index/                        the game's own caches
    index.sqlite                         the state index (core/index.py)

A file this tooling writes gets a temporary name first and is renamed, so a
reader never sees half of one. A recipe's variants exist once its
entry.json does.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import numpy as np
import workpaths
from PIL import Image

ENV = "TEXTURE_STORE"
# Of the layout, and of an entry. 3: every entry names `tiles` (results.TILES); storemigrate.py brings a store of 2 to 3.
FORMAT = 3
FORMAT_FILE = "format"
ENTRY = "entry.json"
# Key of an entry: why its problems do not refuse a bake. A person writes it by hand; `write_recipe` refuses it (R-HD-161).
ACCEPTED = "accepted"
PACKAGE_RECORD = "package.json"
# A request may also ask for each level below a recipe's own, down to the first one of this side or less,
# and always for half its own side.
SMALLEST_OFFERED = 1024
NAME = re.compile(r"[a-z0-9][a-z0-9_.-]*")


class StoreError(RuntimeError):
    """The store cannot be read or written as asked."""


class RecipeKept(StoreError):
    """A write of a recipe that is kept (R-HD-158)."""


class SizeKept(StoreError):
    """A write of a size its recipe is kept at (R-HD-158)."""


def store_root() -> Path:
    return workpaths.path(ENV)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    scratch = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    scratch.write_bytes(data)
    scratch.replace(path)


def write_json(path: Path, value: object) -> None:
    # allow_nan=False: a file with Infinity in it is not JSON to other readers.
    write_atomic(
        path,
        (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode(),
    )


Json = str | int | float | bool | None | list["Json"] | dict[str, "Json"]
"""A value json.loads gives."""


def _unique_keys(pairs: list[tuple[str, Json]]) -> dict[str, Json]:
    """An object whose keys are each given once; a key given twice is refused, not overwritten."""
    found: dict[str, Json] = {}
    for key, value in pairs:
        if key in found:
            raise StoreError(f"the key {key!r} is given twice")
        found[key] = value
    return found


def read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_keys)
    except json.JSONDecodeError as error:
        raise StoreError(f"{path} is not JSON: {error}") from error
    except StoreError as error:
        raise StoreError(f"{path}: {error}") from error


def plane_key(image: np.ndarray) -> str:
    """The name of a plane: a hash of its size and pixels."""
    if image.dtype != np.uint8 or image.ndim not in (2, 3):
        raise StoreError(
            f"a plane is 8-bit grey or RGB, got {image.dtype} {image.shape}"
        )
    digest = hashlib.sha256(repr(image.shape).encode())
    digest.update(np.ascontiguousarray(image).tobytes())
    return digest.hexdigest()


def read_plane(path: Path) -> np.ndarray:
    """An image file as 8-bit grey or RGB. A file that is not a whole image is refused."""
    try:
        with Image.open(path) as image:
            return np.asarray(
                image if image.mode in ("L", "RGB") else image.convert("RGB")
            ).copy()
    except (OSError, SyntaxError) as error:
        raise StoreError(f"{path} is not a whole image: {error}") from error


def upscale_recipe(plane: str, model: str, runner: str, tiles: bool) -> str:
    """The name of one upscale: what went in, which model, which version of the upscaler, whether its edges match.

    The words of an upscale with matched edges are the first four alone; one whose edges come as the model gives
    them adds a fifth. So the cache of the store's earlier upscales, which all matched edges, keeps its names.
    """
    words = ["upscale", plane, model, runner] + ([] if tiles else ["edges as they come"])
    return hashlib.sha256(json.dumps(words).encode()).hexdigest()


def origin_folder(origin: str) -> str:
    """A folder name for an origin: the end of it, readable, and a hash of all of it."""
    tail = (
        re.sub(
            r"[^a-z0-9_.-]+", "_", origin.lower().replace("/", "\\").rsplit("\\", 1)[-1]
        ).strip("._-")
        or "texture"
    )
    return f"{tail[:80]}-{hashlib.sha256(origin.encode()).hexdigest()[:16]}"


def offered_sizes(longest: int) -> tuple[int, ...]:
    """The longest sides a request may ask for of a recipe with that own longest side, largest first. The recipe
    is kept at those that were asked for (R-HD-123).

    Half the own side is always one: a 4x model's own side is 4x its input,
    so its half is the 2x of the model (variants.FACTORS).
    """
    sizes = [longest]
    while sizes[-1] % 2 == 0 and (sizes[-1] > SMALLEST_OFFERED or len(sizes) == 1):
        sizes.append(sizes[-1] // 2)
    return tuple(sizes)


def checked_name(value: str, word: str) -> str:
    if not isinstance(value, str) or not NAME.fullmatch(value):
        raise StoreError(
            f"{word} {value!r} cannot name a folder: use lower-case letters, digits, '_', '.', '-'"
        )
    return value


class GameStore:
    """One game's part of the store."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.planes = root / "planes"
        self.upscaled = root / "upscaled"
        self.variants = root / "variants"
        self.locks = root / "locks"
        self.index = root / "index"

    # ---------------------------------------------------------------- planes

    def plane_path(self, key: str) -> Path:
        return self.planes / key[:2] / f"{key}.png"

    def put_plane(self, image: np.ndarray) -> str:
        key = plane_key(image)
        path = self.plane_path(key)
        if not path.is_file():
            path.parent.mkdir(parents=True, exist_ok=True)
            scratch = path.with_name(f".{path.name}.{os.getpid()}.tmp")
            Image.fromarray(image).save(scratch, format="PNG")
            scratch.replace(path)
        return key

    def get_plane(self, key: str) -> np.ndarray:
        path = self.plane_path(key)
        if not path.is_file():
            raise StoreError(f"plane {key} is not in the store at {path}")
        pixels = read_plane(path)
        if plane_key(pixels) != key:
            raise StoreError(f"{path} does not hold the pixels its name says")
        return pixels

    def upscale_dir(self, plane: str, model: str, runner: str, tiles: bool) -> Path:
        """The folder the upscaler writes one upscale into. Equal recipes share it."""
        return self.upscaled / upscale_recipe(plane, model, runner, tiles)

    # -------------------------------------------------------------- variants

    def recipe_dir(self, origin: str, recipe: str) -> Path:
        return self.variants / origin_folder(origin) / recipe

    def entry(self, origin: str, recipe: str) -> dict | None:
        path = self.recipe_dir(origin, recipe) / ENTRY
        if not path.is_file():
            return None
        entry = read_json(path)
        if (
            not isinstance(entry, dict)
            or entry.get("format") != FORMAT
            or entry.get("origin") != origin
        ):
            raise StoreError(f"{path} is not an entry of {origin} in format {FORMAT}")
        return entry

    def recipes(self, origin: str) -> list[str]:
        """The recipes this origin has variants of."""
        folder = self.variants / origin_folder(origin)
        return (
            sorted(path.parent.name for path in folder.glob(f"*/{ENTRY}"))
            if folder.is_dir()
            else []
        )

    def variant_file(self, origin: str, recipe: str, size: int) -> Path:
        return self.recipe_dir(origin, recipe) / f"{size}.dds"

    def drop_recipe(self, origin: str, recipe: str) -> None:
        """Remove the variants of a recipe. The entry goes first, so half a recipe is never taken for one."""
        folder = self.recipe_dir(origin, recipe)
        (folder / ENTRY).unlink(missing_ok=True)
        for path in folder.glob("*.dds"):
            path.unlink()

    def write_recipe(
        self, origin: str, recipe: str, entry: dict, files: dict[int, bytes]
    ) -> dict:
        """Keep the variants of a recipe: its files, then its entry. Returns the entry as written.

        A kept recipe is never written again (R-HD-158): what names it keeps
        its files and its marks. Files left without an entry are no variant;
        they go first.
        """
        folder = self.recipe_dir(origin, recipe)
        if ACCEPTED in entry:
            raise StoreError(
                f"{recipe} of {origin}: its entry holds {ACCEPTED!r}; only a person marks a variant accepted, no program writes the mark"
            )
        # The check and the write are one step: of two programs that make one recipe, the second finds it kept.
        with self._writing(origin, recipe):
            if (folder / ENTRY).is_file():
                raise RecipeKept(
                    f"{recipe} of {origin} is kept at {folder}; a kept variant is not written again, a new one gets a revision"
                )
            self.drop_recipe(origin, recipe)
            try:
                for size, data in sorted(files.items()):
                    write_atomic(folder / f"{size}.dds", data)
                written = {
                    **entry,
                    "format": FORMAT,
                    "origin": origin,
                    "recipe": recipe,
                    "files": {
                        str(size): {
                            "sha256": hashlib.sha256(data).hexdigest(),
                            "bytes": len(data),
                        }
                        for size, data in sorted(files.items())
                    },
                }
                write_json(folder / ENTRY, written)
            except BaseException:
                # Its own half only: the recipe had no entry when the lock was taken.
                self.drop_recipe(origin, recipe)
                raise
        return written

    def add_size(self, origin: str, recipe: str, size: int, data: bytes) -> dict:
        """Keep one more size of a kept recipe: its file, then its hash in the entry. Returns the entry as written.

        A request keeps the size it asks for (R-HD-123); one asked for later
        is added here. A size that is kept is never written again, and
        nothing else of the entry changes (R-HD-158).
        """
        folder = self.recipe_dir(origin, recipe)
        with self._writing(origin, recipe):
            entry = self.entry(origin, recipe)
            if entry is None:
                raise StoreError(f"{recipe} of {origin} is not kept; a size is added to a kept recipe only")
            if str(size) in entry["files"]:
                raise SizeKept(f"{recipe} of {origin} is kept at {size}; a kept file is not written again")
            path = folder / f"{size}.dds"
            try:
                write_atomic(path, data)
                written = {
                    **entry,
                    "files": {
                        **entry["files"],
                        str(size): {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)},
                    },
                }
                write_json(folder / ENTRY, written)
            except BaseException:
                # Its own file only: the entry did not name the size when the lock was taken.
                path.unlink(missing_ok=True)
                raise
        return written

    @contextmanager
    def _writing(self, origin: str, recipe: str) -> Iterator[None]:
        """Hold the lock of one recipe's write: `locks/<origin>.<recipe>.lock`, by flock. The system frees it when
        the program ends, however it ends. The file stays; it holds nothing."""
        self.locks.mkdir(parents=True, exist_ok=True)
        with (self.locks / f"{origin_folder(origin)}.{recipe}.lock").open("a") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    # -------------------------------------------------------------- datasets

    def dataset_dir(self, dataset: str) -> Path:
        return self.root / "datasets" / checked_name(dataset, "dataset")

    def package_record(self, dataset: str) -> dict | None:
        """What the last package of a dataset held. None: it was never packaged."""
        path = self.dataset_dir(dataset) / PACKAGE_RECORD
        if not path.is_file():
            return None
        record = read_json(path)
        if not isinstance(record, dict) or not isinstance(record.get("textures"), dict):
            raise StoreError(f"{path} is not a package record")
        return record


class Store:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root if root is not None else store_root()
        marker = self.root / FORMAT_FILE
        if not marker.is_file():
            if self.root.is_dir() and any(self.root.iterdir()):
                raise StoreError(
                    f"{self.root} is not empty and has no {FORMAT_FILE} file; it is not a texture store"
                )
            write_atomic(marker, f"{FORMAT}\n".encode())
        elif (found := marker.read_text().strip()) != str(FORMAT):
            raise StoreError(
                f"{self.root} has layout {found!r}; this tooling reads layout {FORMAT}"
                + ("; bring it up with: make texture-store-migrate" if found == str(FORMAT - 1) else "")
            )

    def game(self, game: str) -> GameStore:
        return GameStore(self.root / checked_name(game, "game"))
