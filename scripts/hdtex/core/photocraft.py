"""PhotoCraft's renderer, as the pipeline runs it (SPEC-PHOTOCRAFT 10).

    build    pictures -> one layered PSD: a group per picture, each with one layer `base`
    info     the size and the layer tree of a document
    render   each top-level layer of a document, composed alone, as a PNG

The renderer is `bin/photocraft-cli` of the install at PHOTOCRAFT_HOME
(`make install-photocraft`). Its `run` command, the one that composes
pixels, is always given `--no-gpu`, so nothing here needs a GPU or waits
for one. `info` reads the file only and has no such flag.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import NamedTuple

import workpaths

ENV = "PHOTOCRAFT_HOME"
PROGRAM = Path("bin") / "photocraft-cli"
BASE = "base"  # the one layer of a group as it is built
GROUP = "Group"  # the kind `info` gives a group
PREFIX = "plane"  # of the files `render` has the renderer write
NO_GPU = "--no-gpu"
# One run on three 4096 by 4096 planes takes about 2 s (trial S8). A run this long hangs.
RUN_SECONDS = 600.0
SAID = 2000  # how much of the renderer's own words an error repeats


class RendererError(RuntimeError):
    """The renderer is not installed, failed, or answered what cannot be read."""


class Layer(NamedTuple):
    """One layer of a document, as `info` tells it."""

    name: str
    kind: str  # GROUP, "Pixel", "Adjustment" and others
    children: tuple[Layer, ...]  # top first; empty for what is no group


class Info(NamedTuple):
    width: int
    height: int
    mode: str  # the colour mode, such as "Rgb"
    depth: int  # bits a channel
    layers: tuple[Layer, ...]  # the top-level layers, top first


def program() -> Path:
    path = workpaths.path(ENV) / PROGRAM
    if not path.is_file():
        raise RendererError(
            f"PhotoCraft's renderer is not installed: {path} is not there; run make install-photocraft"
        )
    return path


def _run(*args: str) -> str:
    """One call of the renderer. Returns what it printed."""
    command = [str(program()), *args]
    try:
        done = subprocess.run(
            command, capture_output=True, text=True, check=False, timeout=RUN_SECONDS
        )
    except subprocess.TimeoutExpired as error:
        raise RendererError(
            f"the renderer did not end in {RUN_SECONDS:.0f} s: {args[0]} {args[1]}"
        ) from error
    if done.returncode != 0:
        said = (done.stderr.strip() or done.stdout.strip())[-SAID:]
        raise RendererError(
            f"the renderer failed ({done.returncode}) on {args[0]} {args[1]}: {said}"
        )
    return done.stdout


def cmd(command: str, **params: object) -> list[str]:
    """One command of the renderer with its values, as words of a `run` command line."""
    return ["--cmd", command, "--params", json.dumps(params)]


def build(pictures: list[tuple[str, Path]], document: Path) -> None:
    """Write `document`: one top-level group per picture, named as given, top group first, each with one layer `base`.

    `pictures`: (group name, image file). The files have one size and
    names that differ. The document gets that size. It is written under
    another name first and renamed, so nobody reads half of it.
    """
    lowest_first = list(reversed(pictures))
    if len({path.name for _name, path in pictures}) != len(pictures):
        raise RendererError("the pictures of a document need file names that differ")
    steps = ["run", "--new", json.dumps({"width": 1, "height": 1})]
    steps += cmd(
        "file.scripts.loadFilesIntoStack",
        paths=[str(path) for _name, path in lowest_first],
    )
    for name, path in lowest_first:
        # Each loaded file is a layer with the file's name.
        steps += cmd("layer.select", name=path.name)
        steps += cmd("layer.setProps", name=BASE)
        steps += cmd("layer.groupLayers", name=name)
    # The suffix stays last: it names the format.
    scratch = document.with_name(f".{os.getpid()}.{document.name}")
    try:
        _run(*steps, "--out", str(scratch), NO_GPU)
        scratch.replace(document)
    finally:
        scratch.unlink(missing_ok=True)


def _layer(node: object, document: Path) -> Layer:
    if (
        not isinstance(node, dict)
        or not isinstance(node.get("name"), str)
        or not isinstance(node.get("kind"), str)
        or not isinstance(node.get("children", []), list)
    ):
        raise RendererError(f"the renderer's answer for {document} has a layer that cannot be read: {node!r}")
    return Layer(
        node["name"],
        node["kind"],
        tuple(_layer(child, document) for child in node.get("children", [])),
    )


def info(document: Path) -> Info:
    """The size and the layers of a document. A file the renderer cannot open is refused with its words."""
    said = _run("info", str(document), "--compact")
    try:
        found = json.loads(said)
    except json.JSONDecodeError as error:
        raise RendererError(
            f"the renderer's answer for {document} is not JSON: {error}"
        ) from error
    if (
        not isinstance(found, dict)
        or not isinstance(found.get("width"), int)
        or not isinstance(found.get("height"), int)
        or not isinstance(found.get("mode"), str)
        or not isinstance(found.get("depth"), int)
        or not isinstance(found.get("layers"), list)
    ):
        raise RendererError(
            f"the renderer's answer for {document} names no width, height, mode, depth and layers"
        )
    return Info(
        found["width"],
        found["height"],
        found["mode"],
        found["depth"],
        tuple(_layer(node, document) for node in found["layers"]),
    )


def render(document: Path, folder: Path) -> dict[int, Path]:
    """Each top-level layer of `document` as a PNG in the new folder `folder`, by the layer's place from the top (0 first).

    A layer is composed alone, whether it is shown or hidden. A layer
    with no pixels of its own, such as an adjustment layer at the top
    level, gets no file and so no place in the answer.
    """
    folder.mkdir(parents=True)
    _run(
        "run",
        str(document),
        *cmd(
            "file.export.layersToFiles",
            dir=str(folder),
            format="png",
            visibleOnly=False,
            prefix=PREFIX,
        ),
        NO_GPU,
    )
    found: dict[int, Path] = {}
    for path in sorted(folder.iterdir()):
        # plane_<place, four digits>_<layer name>.png
        parts = path.name.split("_", 2)
        if len(parts) != 3 or parts[0] != PREFIX or not parts[1].isdigit():
            raise RendererError(
                f"the renderer wrote {path.name} into {folder}, which is no layer's file"
            )
        found[int(parts[1])] = path
    return found
