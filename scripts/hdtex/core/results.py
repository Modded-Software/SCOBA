"""The recipes of one texture, as that texture sees them: stale or not, and the problems of each (R-HD-88, R-HD-90)."""

from __future__ import annotations

from typing import NamedTuple

from . import limits, variants
from .interfaces import Texture
from .store import ACCEPTED, GameStore, StoreError

EDIT = "edit"  # key of an entry a transfer made: its input, its changed planes, their hash
# Key of an entry: whether its edges were made to match across the border (store FORMAT 3).
TILES = "tiles"


def made_tiling(entry: dict) -> bool:
    """Whether the variants of this entry had their edges matched across the border. An entry without the key is
    refused: the store's entries of format 3 have it (storemigrate.py wrote it into the older ones)."""
    if not isinstance(entry.get(TILES), bool):
        raise StoreError(f"the entry of {entry.get('origin')!r} {entry.get('recipe')!r} has no {TILES!r}")
    return entry[TILES]


def edges_off(entry: dict, tiles: bool) -> bool:
    """A model's variants whose edges were made for the other rule: matched for a texture that does not repeat, or not
    matched for one that does. A person's edit is not upscaled: its edges are as the person left them.

    Such a variant is shown and may be baked; it is not stale (operator 2026-11-26). A request of it makes a new
    variant beside it (`served`, R-HD-158)."""
    return not user_made(entry) and made_tiling(entry) != tiles


def user_made(entry: dict) -> bool:
    """Whether a person made the variants of this entry: it names a changed plane (R-PC-80).

    The limits bind what a model made. A user-made variant has its
    numbers and no problem, and its bake is not refused for them.
    """
    return bool(entry.get(EDIT, {}).get("changed"))


class Original(NamedTuple):
    """What was read of a texture's original."""

    sha256: str
    longest: int  # its longest side; read only when `unreadable` is empty
    unreadable: str  # why its header cannot be read; empty: it was read


class Made(NamedTuple):
    """A recipe's variants, as one texture sees them."""

    entry: dict
    stale: bool  # it must be made again: the original changed since
    missed: tuple[limits.Missed, ...]  # the limits it misses for this texture: its problems
    why_stale: str = ""  # why it is stale, in words; empty: it is not
    edges_off: bool = False  # its edges were made for the other rule (edges_off): shown; a request makes a revision

    @property
    def accepted(self) -> str:
        """Why its problems do not refuse a bake. Empty: they do (R-HD-90)."""
        return str(self.entry.get(ACCEPTED, ""))

    @property
    def own(self) -> int:
        return max(self.entry["size"])

    @property
    def sound(self) -> bool:
        """It is what a request would make now: of the original as it is, its edges of the texture's rule."""
        return not self.stale and not self.edges_off

    def sizes(self) -> list[int]:
        """The sizes its variants are kept at, smallest first."""
        return sorted(int(size) for size in self.entry["files"])

    def refusal(self, variant: str) -> str:
        """Why a bake cannot name this variant. Empty: it can."""
        _recipe, size = variants.split(variant)
        if self.stale:
            return f"{variant} is stale: {self.why_stale}"
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
            missed = (
                ()
                if user_made(entry)
                else tuple(limits.missed(entry["numbers"], texture.tiles))
            )
            why = "the original changed since it was made" if entry["original"]["sha256"] != original_sha256 else ""
            found[recipe] = Made(entry, bool(why), missed, why, edges_off(entry, texture.tiles))
    return found


def served(made: dict[str, Made], variant: str) -> str:
    """The id that serves a request of `variant` of a texture with these recipes (R-HD-158).

    From the revision asked for upward: the first recipe that is sound, or
    not kept. A kept variant is never made again, so one that is stale or
    has edges of the other rule is passed over; what is made gets the first
    free revision. The original serves itself.
    """
    if variant == variants.ORIGINAL:
        return variant
    recipe, size = variants.split(variant)
    plain, revision = variants.revision_of(recipe)
    while True:
        one = variants.revised(plain, revision)
        if one not in made or made[one].sound:
            return variants.variant_id(one, size)
        revision += 1


def made_refusal(made: dict[str, Made], variant: str) -> str:
    """Why a bake cannot name `variant`, where it is made at its size. Empty: it can, or it is not made (yet).

    A skin upscale asks by it (R-HD-162): a variant whose numbers are there and miss a limit is not left in its skin.
    """
    if variant == variants.ORIGINAL:
        return ""
    recipe, size = variants.split(variant)
    if recipe not in made or str(size) not in made[recipe].entry["files"]:
        return ""
    return made[recipe].refusal(variant)


def refusal(made: dict[str, Made], variant: str) -> str:
    """Why a bake cannot name `variant` of a texture with these recipes. Empty: it can; the original always can."""
    if variant == variants.ORIGINAL:
        return ""
    recipe, _size = variants.split(variant)
    if recipe not in made:
        return f"{variant} is not made"
    return made[recipe].refusal(variant)
