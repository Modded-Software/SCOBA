"""The statements of the state index, read from the repository's SQL tree, sql/texture-index/ (SPEC-HD-TEXTURES 4.9).

One file holds one statement, named by the file. A file of several
statements (the schema) parts them with ";". A missing file raises.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

from project_root import project_root


def folder() -> Path:
    return project_root() / "sql" / "texture-index"


@cache
def query(name: str) -> str:
    """The text of `name`.sql. A name with a "/" names a file in a subfolder."""
    return (folder() / f"{name}.sql").read_text(encoding="utf-8")


def statements(name: str) -> list[str]:
    """Each statement of a file of several, in order."""
    return [one for one in map(str.strip, query(name).split(";")) if one]
