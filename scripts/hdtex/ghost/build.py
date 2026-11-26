"""The StarCraft: Ghost build on disk (SPEC-HD-TEXTURES 6.1): where it is, its NODExport, and the files the listing reads.

`GHOST_PATH` and `NODSDK_EXPORT` are the viewer's settings (SPEC-VIEWER-GHOST 3).
They are read when asked for, never at import.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import NamedTuple

import workpaths

from ..core.interfaces import GameError

MODELS = "3D/Models"
# The folders whose texture files a material may name (SPEC-VIEWER-GHOST 4.4).
TEXTURE_FOLDERS = ("3D/Materials", "Materials")
# What the listing reads: the models, the materials, the templates (SPEC-VIEWER-GHOST 3).
READ_FOLDERS = (MODELS, *TEXTURE_FOLDERS, "Misc/Templates")
READ_FILES = ("MaterialDirs.txt",)


class BuildError(GameError):
    """The build or NODExport is not there, or NODExport refused."""


class Build(NamedTuple):
    root: Path
    exporter: Path


def settings() -> Build:
    """The build and NODExport, or the reason the game cannot answer."""
    root = os.environ.get("GHOST_PATH", "")
    if not root:
        raise BuildError("GHOST_PATH is not set: name the extracted StarCraft: Ghost build in webviewer/local.env")
    if not (Path(root) / MODELS).is_dir():
        raise BuildError(f"GHOST_PATH ({root}) has no {MODELS}")
    named = os.environ.get("NODSDK_EXPORT", "")
    exporter = Path(named) if named else workpaths.path("WEBVIEWER_WORK") / "build" / "nodsdk" / "cmake" / "NODExport"
    if not os.access(exporter, os.X_OK):
        raise BuildError(f"NODExport is not built ({exporter}): run make install-deps")
    return Build(Path(root), exporter)


def files(root: Path) -> list[str]:
    """Every file the listing reads, relative to the build with '/', sorted."""
    found = [
        path.relative_to(root).as_posix()
        for folder in READ_FOLDERS
        if (root / folder).is_dir()
        for path in (root / folder).rglob("*")
        if path.is_file()
    ]
    found += [name for name in READ_FILES if (root / name).is_file()]
    return sorted(found)


def signature(root: Path, listed: list[str]) -> str:
    """A hash over the path, size and change time of every file read: a change of any makes the listing again."""
    digest = hashlib.sha256()
    for rel in listed:
        info = (root / rel).stat()
        digest.update(f"{rel}\t{info.st_size}\t{info.st_mtime_ns}\n".encode())
    return digest.hexdigest()


def by_lower(listed: list[str]) -> dict[str, str]:
    """Lower-case path to the path on disk. Of two spellings the first in sort order wins."""
    found: dict[str, str] = {}
    for rel in listed:
        found.setdefault(rel.lower(), rel)
    return found


def asset_of(rel: str) -> str:
    """The pipeline's name of a build file: lower case, backslashes (SPEC-HD-TEXTURES 6.2)."""
    return rel.replace("/", "\\").lower()
