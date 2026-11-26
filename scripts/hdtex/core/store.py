"""The texture store: every plane, every variant, every skin and bake, in one folder.

    format                               the layout version
    <game>/planes/                       what the upscaler takes, named by the hash of its pixels
    <game>/upscaled/<hash>/              what the upscaler gave for one plane and model, as it wrote it
    <game>/variants/<origin>/<recipe>/   entry.json and one file per kept size; request.json while it is made
    <game>/datasets/<dataset>/           skins/, bakes.json, package record
    <game>/index/                        the game's own caches
    index.sqlite                         the state index (core/index.py)

A file this tooling writes gets a temporary name first and is renamed, so a
reader never sees half of one. A recipe's variants exist once its
entry.json does.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

import numpy as np
import workpaths
from PIL import Image

ENV = "TEXTURE_STORE"
# Of the layout, and of an entry. 3: every entry names `tiles` (results.TILES); storemigrate.py brings a store of 2 to 3.
FORMAT = 3
FORMAT_FILE = "format"
ENTRY = "entry.json"
PACKAGE_RECORD = "package.json"
# A recipe is also kept at each level below its own, down to the first one of this side or less,
# and always at half its own side.
SMALLEST_KEPT = 1024
NAME = re.compile(r"[a-z0-9][a-z0-9_.-]*")


class StoreError(RuntimeError):
    """The store cannot be read or written as asked."""


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


def kept_sizes(longest: int) -> tuple[int, ...]:
    """The longest sides a recipe with that own longest side is kept at, largest first.

    Half the own side is always kept: a 4x model's own side is 4x its input,
    so its half is the 2x a request may ask for (variants.FACTORS).
    """
    sizes = [longest]
    while sizes[-1] % 2 == 0 and (sizes[-1] > SMALLEST_KEPT or len(sizes) == 1):
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
        """Keep the variants of a recipe: its files, then its entry. Returns the entry as written."""
        self.drop_recipe(origin, recipe)
        folder = self.recipe_dir(origin, recipe)
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
            self.drop_recipe(origin, recipe)
            raise
        return written

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
