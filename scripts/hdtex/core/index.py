"""The state index: what a reader shows of every texture and owner, in one SQLite file of the store (SPEC-HD-TEXTURES 4.9).

It is a copy. The files of the store and of the dataset hold the truth;
`Dataset.sync` writes a dataset's part again from them. Only the pipeline
writes here. A reader, such as the viewer's server, opens the
file read-only and runs no pipeline code.

    dataset   one row per game and dataset: what holds for all its textures
    texture   one row per game, dataset and asset: description and state
    original  one row per game and origin: what was read of the original
    origin    one row per game, dataset and asset: where a texture file lies
    owner     one row per game, dataset and owner: its textures, skins and bake
    text      each JSON text once, by its SHA-256, with how many row fields name it

A texture or owner row holds the keys of its texts, not the texts. The
datasets of a game share most of their textures and owners, and most of
those are described and stand alike in each: such a text is kept once.
A text no field names any more is deleted in the change that let it go.

The file is in WAL mode: a reader does not wait for a writer. A writer
takes the write lock before it works a state out, so the state written
last is the one worked out last.

This module knows the file and its rows. `Dataset` decides what is written.
Its statements are files of sql/texture-index/ (`queries`).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import zlib
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import NamedTuple

from .interfaces import Owner, Texture
from .queries import query, statements
from .results import Original

FILE = "index.sqlite"
SCHEMA = 4
# How long a writer waits for another one. A writer holds the lock while it works states out.
BUSY_SECONDS = 120.0
# zlib level of a kept text: a JSON text of paths shrinks to about a fifth.
COMPRESSION = 6


class Row(NamedTuple):
    """One texture of one dataset, as the index holds it."""

    dataset: str
    listed: Texture  # as the game listed it: what a later listing is compared with
    texture: Texture  # the same with its role, once that was found
    state: dict


class Kept(NamedTuple):
    """What was read of an original, and the size and time of its file then."""

    original: Original
    bytes: int
    changed: int  # the file's modification time, in nanoseconds


def _pack(texture: Texture) -> str:
    return json.dumps(texture._asdict(), sort_keys=True)


def _unpack(text: str) -> Texture:
    value = json.loads(text)
    return Texture(
        **{
            **value,
            "grid": tuple(value["grid"]),
            "users": tuple(value["users"]),
            "entries": tuple(value["entries"]),
        }
    )


def _text(value: object) -> str:
    return json.dumps(value, sort_keys=True, allow_nan=False)


def _hold(con: sqlite3.Connection, body: str) -> int:
    """Keep a text for one more field: its id. A text kept already is not written again.

    The body is kept compressed (zlib); its key is the SHA-256 of the text.
    """
    data = body.encode()
    key = hashlib.sha256(data).digest()
    found = con.execute(query("text_hold"), (key,)).fetchone()
    if found is not None:
        return found[0]
    return con.execute(
        query("text_add"), (key, zlib.compress(data, COMPRESSION))
    ).fetchone()[0]


def _release(con: sqlite3.Connection, ids: Iterable[int]) -> None:
    """One field fewer names each text; a text no field names is deleted."""
    for one in ids:
        con.execute(query("text_release"), (one,))
        con.execute(query("text_delete_unused"), (one,))


def _ids(con: sqlite3.Connection, statement: str, values: tuple) -> list[int]:
    """The text ids of the rows a statement selects (texture_text_ids, owner_text_ids), for their release."""
    found = con.execute(query(statement), values).fetchall()
    return [one for row in found for one in row]


def _body(data: bytes) -> str:
    return zlib.decompress(data).decode()


def _prepare(con: sqlite3.Connection) -> None:
    """Give the file its tables. A file of another schema is emptied: each dataset's part comes back with its next sync."""
    if con.execute("PRAGMA user_version").fetchone()[0] == SCHEMA:
        return
    for (name,) in con.execute(query("tables")).fetchall():
        quoted = '"' + name.replace('"', '""') + '"'
        con.execute(query("drop_table").replace("{table}", quoted))  # its indexes go with it
    for statement in statements("schema"):
        con.execute(statement)
    con.execute(f"PRAGMA user_version = {SCHEMA}")


class Index:
    def __init__(self, root: Path) -> None:
        """`root`: the folder of the texture store."""
        self.path = root / FILE

    @contextmanager
    def writing(self) -> Iterator[sqlite3.Connection]:
        """One change: the write lock is held from here to the end, and all of it is kept or none."""
        con = sqlite3.connect(self.path, timeout=BUSY_SECONDS, isolation_level=None)
        try:
            con.execute("PRAGMA journal_mode = WAL")
            con.execute("BEGIN IMMEDIATE")
            try:
                _prepare(con)  # under the lock: two writers do not both make the tables
                yield con
            except BaseException:
                con.execute("ROLLBACK")
                raise
            con.execute("COMMIT")
        finally:
            con.close()

    @contextmanager
    def reading(self) -> Iterator[sqlite3.Connection | None]:
        """The file as a reader sees it. None: there is no index of this schema."""
        if not self.path.is_file():
            yield None
            return
        con = sqlite3.connect(
            f"{self.path.as_uri()}?mode=ro", uri=True, timeout=BUSY_SECONDS
        )
        try:
            yield (
                con
                if con.execute("PRAGMA user_version").fetchone()[0] == SCHEMA
                else None
            )
        finally:
            con.close()


# ------------------------------------------------------------------ textures


def _row(found: tuple[str, str, str, str]) -> Row:
    dataset, listed, description, state = found
    return Row(dataset, _unpack(_body(listed)), _unpack(_body(description)), json.loads(_body(state)))


def rows(
    con: sqlite3.Connection,
    game: str,
    dataset: str,
    assets: Iterable[str] | None = None,
) -> dict[str, Row]:
    """The textures of a dataset by asset: all of them, or those named."""
    if assets is None:
        found = con.execute(query("texture_rows"), (game, dataset)).fetchall()
    else:
        ask = query("texture_row")
        found = [
            one
            for asset in dict.fromkeys(assets)
            if (one := con.execute(ask, (game, dataset, asset)).fetchone()) is not None
        ]
    return {row.texture.asset: row for row in map(_row, found)}


def rows_at(con: sqlite3.Connection, game: str, origin: str) -> list[Row]:
    """Every texture, of every dataset, whose original lies at an origin."""
    found = con.execute(query("texture_rows_at"), (game, origin))
    return list(map(_row, found.fetchall()))


def rows_of_kind(
    con: sqlite3.Connection, game: str, dataset: str, kind: str
) -> list[Row]:
    found = con.execute(query("texture_rows_of_kind"), (game, dataset, kind))
    return list(map(_row, found.fetchall()))


def put(con: sqlite3.Connection, game: str, row: Row) -> None:
    texture = row.texture
    where = (game, row.dataset, texture.asset)
    before = _ids(con, "texture_text_ids", where)
    con.execute(
        query("texture_put"),
        (
            *where,
            texture.origin,
            texture.kind,
            _hold(con, _pack(row.listed)),
            _hold(con, _pack(texture)),
            _hold(con, _text(row.state)),
        ),
    )
    _release(con, before)


def drop(
    con: sqlite3.Connection, game: str, dataset: str, assets: Iterable[str]
) -> None:
    for asset in assets:
        where = (game, dataset, asset)
        before = _ids(con, "texture_text_ids", where)
        con.execute(query("texture_drop"), where)
        _release(con, before)


# ----------------------------------------------------------------- originals


def kept(con: sqlite3.Connection, game: str, origin: str) -> Kept | None:
    found = con.execute(query("original_kept"), (game, origin)).fetchone()
    return (
        None
        if found is None
        else Kept(Original(found[0], found[1], found[2]), found[3], found[4])
    )


def keep(con: sqlite3.Connection, game: str, origin: str, read: Kept) -> None:
    con.execute(
        query("original_keep"),
        (
            game,
            origin,
            read.original.sha256,
            read.original.longest,
            read.original.unreadable,
            read.bytes,
            read.changed,
        ),
    )


def forget(con: sqlite3.Connection, game: str, origin: str) -> None:
    con.execute(query("original_forget"), (game, origin))


# ------------------------------------------------------------------ datasets


def put_head(con: sqlite3.Connection, game: str, dataset: str, head: dict) -> None:
    con.execute(query("dataset_put_head"), (game, dataset, _text(head)))


def head(con: sqlite3.Connection, game: str, dataset: str) -> dict | None:
    found = con.execute(query("dataset_head"), (game, dataset)).fetchone()
    return None if found is None else json.loads(found[0])


def put_origins(
    con: sqlite3.Connection, game: str, dataset: str, origins: dict[str, str]
) -> bool:
    """Keep where every texture file of a dataset lies. False: they are as they were, and nothing was written.

    The dataset must have its head row.
    """
    digest = hashlib.sha256(_text(origins).encode()).hexdigest()
    before = con.execute(query("dataset_origins"), (game, dataset)).fetchone()
    if before is not None and before[0] == digest:
        return False
    con.execute(query("origin_clear"), (game, dataset))
    con.executemany(
        query("origin_add"),
        [(game, dataset, asset, origin) for asset, origin in origins.items()],
    )
    con.execute(query("dataset_set_origins"), (digest, game, dataset))
    return True


def origin(con: sqlite3.Connection, game: str, dataset: str, asset: str) -> str | None:
    found = con.execute(query("origin_of"), (game, dataset, asset)).fetchone()
    return None if found is None else found[0]


# -------------------------------------------------------------------- owners


def _owner(text: str) -> Owner:
    value = json.loads(text)
    return Owner(
        **{
            **value,
            "below": tuple(value["below"]),
            "textures": tuple(value["textures"]),
        }
    )


def synced(con: sqlite3.Connection, game: str, dataset: str) -> bool:
    """Whether a sync wrote the dataset: it writes the origins and every owner in one change, and only it writes origins.

    A skin change writes one owner's row before any sync, so an owner row is no such mark.
    """
    found = con.execute(query("origin_any"), (game, dataset)).fetchone()
    return found is not None


def owners(
    con: sqlite3.Connection, game: str, dataset: str, ids: Iterable[str] | None = None
) -> dict[str, tuple[Owner, dict]]:
    """Owner id -> its description and its state."""
    if ids is None:
        found = con.execute(query("owner_rows"), (game, dataset)).fetchall()
    else:
        named = json.dumps(list(ids))  # a JSON array (owner_rows_named)
        found = con.execute(query("owner_rows_named"), (game, dataset, named)).fetchall()
    return {
        name: (_owner(_body(description)), json.loads(_body(state)))
        for name, description, state in found
    }


def put_owner(
    con: sqlite3.Connection, game: str, dataset: str, owner: Owner, state: dict
) -> None:
    where = (game, dataset, owner.id)
    before = _ids(con, "owner_text_ids", where)
    con.execute(
        query("owner_put"),
        (
            *where,
            _hold(con, json.dumps(owner._asdict(), sort_keys=True)),
            _hold(con, _text(state)),
        ),
    )
    _release(con, before)


def drop_owners(
    con: sqlite3.Connection, game: str, dataset: str, ids: Iterable[str]
) -> None:
    for name in ids:
        where = (game, dataset, name)
        before = _ids(con, "owner_text_ids", where)
        con.execute(query("owner_drop"), where)
        _release(con, before)
