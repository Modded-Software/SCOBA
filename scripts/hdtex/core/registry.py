"""Games, codecs, roles and runners by id.

A game or a format adds itself here from its own package. Nothing in the
core names one.
"""

from __future__ import annotations

from collections.abc import Callable

from .interfaces import Codec, GameAdapter, Role, Runner


class RegistryError(KeyError):
    """An id is unknown, or taken."""

    def __str__(self) -> str:
        return str(self.args[0])


class Table[Item]:
    def __init__(self, word: str) -> None:
        self.word = word
        self.items: dict[str, Item] = {}

    def add(self, key: str, item: Item) -> Item:
        if key in self.items and self.items[key] is not item:
            raise RegistryError(f"{self.word} {key} is registered twice")
        self.items[key] = item
        return item

    def get(self, key: str) -> Item:
        if key not in self.items:
            known = ", ".join(sorted(self.items)) or "none"
            raise RegistryError(f"unknown {self.word} {key}; known: {known}")
        return self.items[key]

    def has(self, key: str) -> bool:
        return key in self.items

    def ids(self) -> tuple[str, ...]:
        return tuple(sorted(self.items))


GAMES: Table[GameAdapter] = Table("game")
CODECS: Table[Codec] = Table("texture format")
ROLES: Table[Role] = Table("role")
# A runner is made when it is first needed: making one looks for its tool.
RUNNERS: Table[Callable[[], Runner]] = Table("runner")
