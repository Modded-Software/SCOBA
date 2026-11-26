"""One write of a dataset's rows to the state index (SPEC-HD-TEXTURES 4.9).

`Dataset` opens the index for a change and hands the connection here. What
holds for every row of the write is read once: the bakes, the package
record, and who names each texture (R-HD-156).
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from . import bakes, index, skins, view
from .bakes import Bakes
from .index import Row
from .interfaces import Owner, Texture
from .results import Original

if TYPE_CHECKING:
    from .dataset import Dataset


class StateWriter:
    def __init__(self, dataset: Dataset, con: sqlite3.Connection) -> None:
        self.dataset, self.con = dataset, con
        self.found: dict[str, tuple[Bakes, dict | None]] = {}
        self.named: dict[str, dict[str, list[view.NamedBy]]] = {}

    def names(self, name: str) -> dict[str, list[view.NamedBy]]:
        """By asset: the owners of dataset `name` whose bake or skin names a variant of it. Every skin file is read."""
        if name not in self.named:
            folder = self.dataset.game.dataset_dir(name)
            skinned = {owner: skins.load(folder, owner) for owner in skins.owners(folder)}
            self.named[name] = view.named_by(self.of(name)[0], skinned)
        return self.named[name]

    def of(self, name: str) -> tuple[Bakes, dict | None]:
        """The bakes and the package record of dataset `name`. The first read writes the dataset's head."""
        if name not in self.found:
            game = self.dataset.game
            self.found[name] = (bakes.load(game.dataset_dir(name)), game.package_record(name))
            index.put_head(self.con, self.dataset.adapter.id, name, view.head(self.dataset.adapter.bakes))
        return self.found[name]

    def known(self, texture: Texture, asked: bool, look: bool = True) -> tuple[Original | None, bool]:
        """What is known of a texture's original, and whether its file changed since that was read.

        The file is read when the texture has a variant, or when it was
        `asked` for by name and has a file. Otherwise a file that changed
        is forgotten, not read. Without `look`, what is kept is taken as it
        is: the change at hand is none of the original.
        """
        dataset, game = self.dataset, self.dataset.adapter.id
        must = bool(dataset.game.recipes(texture.origin)) or (asked and bool(texture.origin))
        before = index.kept(self.con, game, texture.origin)
        if before is None and not must:
            return None, False
        if before is not None and not look:
            return before.original, False
        stat = dataset.adapter.original(dataset.name, texture).stat()
        if before is not None and (before.bytes, before.changed) == (stat.st_size, stat.st_mtime_ns):
            return before.original, False
        if not must:
            index.forget(self.con, game, texture.origin)
            return None, True
        read = dataset.read_original(texture)
        index.keep(self.con, game, texture.origin, read)
        return read.original, before is not None

    def put(self, before: Row | None, row: Row, original: Original | None) -> bool:
        """Work out a row's state and write the row. False: it is as it was."""
        dataset = self.dataset
        baked, record = self.of(row.dataset)
        named = self.names(row.dataset).get(row.texture.asset, ())
        state = view.texture_state(dataset.game, row.texture, original, baked, record, dataset.runner, named)
        after = row._replace(state=state)
        if after == before:
            return False
        index.put(self.con, dataset.adapter.id, after)
        return True

    def put_owner(self, owner: Owner, before: tuple[Owner, dict] | None = None) -> bool:
        """Work out an owner's state and write its row. False: it is as `before`, and nothing was written."""
        dataset = self.dataset
        baked, record = self.of(dataset.name)
        state = view.owner_state(owner, dataset.skins_of(owner.id), baked, record)
        if before == (owner, state):
            return False
        index.put_owner(self.con, dataset.adapter.id, dataset.name, owner, state)
        return True
