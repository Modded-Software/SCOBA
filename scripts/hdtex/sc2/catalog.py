"""Field values of game catalog entries, with parents, defaults, and tokens.

A catalog entry takes a field it does not set from its parent. An entry
without a parent takes it from the unnamed default of its class, then from
the unnamed default of each base class. A value may hold `##name##` tokens.
`##id##` is the id of the entry that is asked. Any other token is an
attribute of the entry or of an ancestor, or the value of a
`<?token id=".." value=".."?>` declaration in one of them.

Only fields of the form `<Field value=".."/>` are read.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import NamedTuple

from ..core.interfaces import GameError

# Classes whose entries also take fields from the default of another class.
CLASS_BASES = {
    "CActorDoodad": "CActorModel",
    "CActorUnit": "CActorModel",
    "CActorModel": "CActor",
}

TOKEN = re.compile(r"##([A-Za-z0-9_]+)##")
TOKEN_DECLARATION = re.compile(
    r'^token\s+id="([^"]+)"(?:.*?\svalue="([^"]*)")?', re.DOTALL
)
RESERVED = ("id", "parent", "default")


class CatalogError(GameError):
    """A field has no value, a parent is missing, or a token has no value."""


class OpenToken(CatalogError):
    """A field holds a `##name##` token that no entry of its chain gives a value."""


class Entry(NamedTuple):
    cls: str
    parent: str | None
    fields: dict[str, str]
    tokens: dict[str, str]  # attributes of the entry
    declared: dict[str, str]  # token declarations with a value


def _merge(old: Entry | None, new: Entry) -> Entry:
    if old is None:
        return new
    return Entry(
        old.cls,
        new.parent or old.parent,
        {**old.fields, **new.fields},
        {**old.tokens, **new.tokens},
        {**old.declared, **new.declared},
    )


def _read(node: ET.Element) -> Entry:
    fields: dict[str, str] = {}
    declared: dict[str, str] = {}
    for child in node:
        if child.tag is ET.ProcessingInstruction:
            match = TOKEN_DECLARATION.match(child.text or "")
            if match and match.group(2) is not None:
                declared[match.group(1)] = match.group(2)
        elif (
            isinstance(child.tag, str)
            and child.get("value") is not None
            and child.get("index") is None
        ):
            fields[child.tag] = child.get("value", "")
    tokens = {key: value for key, value in node.attrib.items() if key not in RESERVED}
    return Entry(node.tag, node.get("parent"), fields, tokens, declared)


class Catalog:
    """The entries of one catalog, from XML texts in load order. A later text wins."""

    def __init__(self, texts: list[str]) -> None:
        self.entries: dict[str, Entry] = {}
        self.defaults: dict[str, Entry] = {}  # unnamed default per class
        self.templates: set[str] = (
            set()
        )  # named defaults: entries that only others build on
        for text in texts:
            parser = ET.XMLParser(target=ET.TreeBuilder(insert_pis=True))
            for node in ET.fromstring(text, parser=parser):
                if not isinstance(node.tag, str):
                    continue
                entry = _read(node)
                entry_id = node.get("id")
                if entry_id:
                    self.entries[entry_id] = _merge(self.entries.get(entry_id), entry)
                    if node.get("default") == "1":
                        self.templates.add(entry_id)
                elif node.get("default") == "1":
                    self.defaults[node.tag] = _merge(self.defaults.get(node.tag), entry)

    def ids(self, prefix: str) -> list[str]:
        """The entries whose class starts with `prefix`, the named defaults left out, in id order."""
        return sorted(
            key
            for key, entry in self.entries.items()
            if entry.cls.startswith(prefix) and key not in self.templates
        )

    def chain(self, entry_id: str) -> list[Entry]:
        """The entry, its ancestors, and the class defaults, nearest first."""
        if entry_id not in self.entries:
            raise CatalogError(f"{entry_id} is not in the catalog")
        found: list[Entry] = []
        seen: set[str] = set()
        current: str | None = entry_id
        while current is not None:
            if current in seen:
                raise CatalogError(f"{entry_id}: parent loop at {current}")
            seen.add(current)
            if current not in self.entries:
                raise CatalogError(
                    f"{entry_id}: parent {current} is not in the catalog"
                )
            found.append(self.entries[current])
            current = self.entries[current].parent
        cls: str | None = found[0].cls
        while cls is not None:
            if cls in self.defaults:
                found.append(self.defaults[cls])
            cls = CLASS_BASES.get(cls)
        return found

    def token(self, entry_id: str, name: str) -> str:
        if name == "id":
            return entry_id
        chain = self.chain(entry_id)
        for values in ([e.tokens for e in chain], [e.declared for e in chain]):
            for found in values:
                if name in found:
                    return found[name]
        raise OpenToken(f"{entry_id}: token ##{name}## has no value")

    def field(self, entry_id: str, name: str) -> str | None:
        """The value of a field with its tokens filled in, or None when no entry of the chain sets it."""
        for entry in self.chain(entry_id):
            if name in entry.fields:
                return TOKEN.sub(
                    lambda match: self.token(entry_id, match.group(1)),
                    entry.fields[name],
                )
        return None

    def need(self, entry_id: str, name: str) -> str:
        value = self.field(entry_id, name)
        if not value:
            raise CatalogError(f"{entry_id} has no {name}")
        return value
