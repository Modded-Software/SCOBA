"""The recipes of one texture, as that texture sees them: stale or not, and the problems of each (R-HD-88, R-HD-90)."""

from __future__ import annotations

from typing import NamedTuple

from . import limits, variants
from .interfaces import Texture
from .store import GameStore

ACCEPTED = "accepted"  # key of an entry: why its problems do not refuse a bake


class Original(NamedTuple):
    """What was read of a texture's original."""

    sha256: str
    longest: int  # its longest side; read only when `unreadable` is empty
    unreadable: str  # why its header cannot be read; empty: it was read


class Made(NamedTuple):
    """A recipe's variants, as one texture sees them."""

    entry: dict
    stale: bool  # the original changed since
    missed: tuple[limits.Missed, ...]  # the limits it misses for this texture: its problems

    @property
    def accepted(self) -> str:
        """Why its problems do not refuse a bake. Empty: they do (R-HD-90)."""
        return str(self.entry.get(ACCEPTED, ""))

    @property
    def own(self) -> int:
        return max(self.entry["size"])

    def sizes(self) -> list[int]:
        """The sizes its variants are kept at, smallest first."""
        return sorted(int(size) for size in self.entry["files"])

    def refusal(self, variant: str) -> str:
        """Why a bake cannot name this variant. Empty: it can."""
        _recipe, size = variants.split(variant)
        if self.stale:
            return f"{variant} is stale: the original changed since it was made"
        if str(size) not in self.entry["files"]:
            return f"{variant} is not kept; its recipe is kept at {', '.join(map(str, self.sizes()))}"
        if self.missed and not self.accepted:
            return f"{variant} has problems: " + ", ".join(
                f"{miss['limit']} {miss['value']} against {miss['bound']}"
                for miss in self.missed
            )
        return ""


def of(game: GameStore, texture: Texture, original_sha256: str) -> dict[str, Made]:
    """The texture's recipes. `original_sha256`: the hash of its original now."""
    found = {}
    for recipe in game.recipes(texture.origin):
        entry = game.entry(texture.origin, recipe)
        if entry is not None:
            missed = tuple(limits.missed(entry["numbers"], texture.tiles))
            found[recipe] = Made(
                entry, entry["original"]["sha256"] != original_sha256, missed
            )
    return found


def refusal(made: dict[str, Made], variant: str) -> str:
    """Why a bake cannot name `variant` of a texture with these recipes. Empty: it can; the original always can."""
    if variant == variants.ORIGINAL:
        return ""
    recipe, _size = variants.split(variant)
    if recipe not in made:
        return f"{variant} is not made"
    return made[recipe].refusal(variant)
