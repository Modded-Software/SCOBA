"""One dataset of one game: its textures, their variants, its owners, skins and bakes, and its part of the state index.

Whatever changes a state goes through here and is written to the index in the same call (SPEC-HD-TEXTURES 4.9):
a request (`changed`), a skin (`owner_changed`), a bake, a package (`changed_all`), the dataset's files (`sync`).
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable, Iterable, Sequence
from functools import cached_property
from pathlib import Path

from . import bakes, dds, index, progress, results, skinplan, skins, variants
from .bakes import Bake, Bakes
from .index import Index, Kept, Row
from .interfaces import GameError, Owner, Runner, Texture
from .registry import GAMES, RUNNERS
from .results import Made, Original
from .runner import ID as DEFAULT_RUNNER
from .statewriter import StateWriter
from .store import Store

LOG = logging.getLogger(__name__)


class DatasetError(LookupError):
    """The game has no such dataset, or the dataset no such texture or owner."""

    def __str__(self) -> str:
        return str(self.args[0])


class Dataset:
    def __init__(
        self,
        store: Store,
        game: str,
        name: str,
        layer: Path | None = None,
        runner: Callable[[], Runner] | None = None,
    ) -> None:
        """`layer`: the folder of the dataset's own files, for a game that has the caller name it.

        `runner`: the upscaler that says how far an open request is; arc-upscale when not given.
        """
        self.adapter = GAMES.get(game)
        if layer is not None:
            self.adapter.use(name, layer)
        if name not in self.adapter.datasets():
            raise DatasetError(
                f"{game} has no dataset {name}; datasets: {', '.join(self.adapter.datasets())}"
            )
        self.name = name
        self.game = store.game(game)
        self.folder = self.game.dataset_dir(name)
        self.index = Index(store.root)
        # Textures read from their index rows (`texture`).
        self._rows: dict[str, Texture] = {}
        self._has_listed = False  # `listed` was read
        # No runner given: the declared default runner.
        self.runner = runner if runner is not None else lambda: RUNNERS.get(DEFAULT_RUNNER)()

    @cached_property
    def listed(self) -> dict[str, Texture]:
        """The dataset's textures by asset, as the game lists them now. Listing reads no original."""
        self._has_listed = True
        return {texture.asset: texture for texture in self.adapter.textures(self.name)}

    def _from_game(self) -> bool:  # this object listed the game already, or the dataset was never synced
        return self._has_listed or not self.synced

    @cached_property
    def textures(self) -> dict[str, Texture]:
        """The dataset's textures by asset, each with its role once it was asked for (`texture`)."""
        return dict(self.listed)

    @cached_property
    def owners(self) -> dict[str, Owner]:
        """The dataset's owners by id. Listing them reads no original."""
        return {owner.id: owner for owner in self.adapter.owners(self.name)}

    def texture(self, asset: str) -> Texture:
        """One texture, with its role known. Once synced, and while this object has not listed the game (as `sync` does first), it is read from its index row (see `owner`)."""
        if not self._from_game():
            if asset not in self._rows:
                with self.index.reading() as con:
                    row = (
                        index.rows(con, self.adapter.id, self.name, [asset]).get(asset)
                        if con is not None
                        else None
                    )
                if row is None:
                    raise DatasetError(f"{self.name} has no texture {asset}")
                found = row.texture
                self._rows[asset] = (
                    found if found.judged else self.adapter.judge(self.name, found)
                )
            return self._rows[asset]
        if asset not in self.textures:
            raise DatasetError(f"{self.name} has no texture {asset}")
        if not self.textures[asset].judged:
            self.textures[asset] = self.adapter.judge(self.name, self.textures[asset])
        return self.textures[asset]

    @cached_property
    def synced(self) -> bool:
        """Whether the state index describes every texture and owner of this dataset: a `sync` wrote them from the game's files."""
        with self.index.reading() as con:
            return con is not None and index.synced(con, self.adapter.id, self.name)

    def owner(self, owner: str) -> Owner:
        """One owner. Once synced it is read from the index: listing the owners reads the game's data (seconds for a large dataset). The next `sync` brings a change of the game's files in."""
        if self.synced:
            with self.index.reading() as con:
                found = (
                    index.owners(con, self.adapter.id, self.name, [owner])
                    if con is not None
                    else {}
                )
            if owner not in found:
                raise DatasetError(f"{self.name} has no owner {owner}")
            return found[owner][0]
        if owner not in self.owners:
            raise DatasetError(f"{self.name} has no owner {owner}")
        return self.owners[owner]

    def _kinds(self, assets: Sequence[str]) -> dict[str, str]:
        """The kind of each texture, from the index once synced; no original is read. An asset without a row is refused."""
        if self._from_game():
            rows = self.listed
        else:
            with self.index.reading() as con:
                if not con:
                    raise DatasetError(f"{self.name}: the index is synced but cannot be read")
                rows = {a: row.texture for a, row in index.rows(con, self.adapter.id, self.name, list(assets)).items()}  # fmt: skip
        if missing := sorted(set(assets) - set(rows)):
            raise DatasetError(f"{self.name} has no texture {missing[0]}")
        return {asset: rows[asset].kind for asset in assets}

    def known_owners(self) -> dict[str, Owner]:
        """Every owner, from the index once synced, else as the game lists them (see `owner`)."""
        if not self.synced:
            return self.owners
        with self.index.reading() as con:
            found = index.owners(con, self.adapter.id, self.name) if con else {}
        return {name: described for name, (described, _state) in found.items()}

    def original(self, texture: Texture) -> bytes:
        return self.adapter.original(self.name, texture).read_bytes()

    def read_original(self, texture: Texture) -> Kept:
        """Read the original now: its hash and its longest side, with the size and time of its file."""
        path = self.adapter.original(self.name, texture)
        stat = path.stat()
        data = path.read_bytes()
        sha256 = hashlib.sha256(data).hexdigest()
        try:
            header = dds.parse(data)
        except dds.DdsError as error:
            # Kept as a fact of the texture: its state says why, and every request of it is refused.
            original = Original(sha256, 0, f"its original's header cannot be read: {error}")
        else:
            original = Original(sha256, max(header.width, header.height), "")
        return Kept(
            original,
            stat.st_size,
            stat.st_mtime_ns,
        )

    def made(self, texture: Texture) -> dict[str, Made]:
        """The texture's recipes. The original is read only when there is one."""
        if not self.game.recipes(texture.origin):
            return {}
        return results.of(
            self.game, texture, hashlib.sha256(self.original(texture)).hexdigest()
        )

    @property
    def baked(self) -> Bakes:
        return bakes.load(self.folder)

    # ------------------------------------------------------------- skins

    def skins_of(self, owner: str) -> dict[str, skins.Skin]:
        return skins.load(self.folder, owner)

    def _refusal(self, asset: str, variant: str) -> str:
        """Why a bake cannot name `variant` of `asset`. Empty: it can."""
        return (
            ""
            if variant == variants.ORIGINAL
            else results.refusal(self.made(self.texture(asset)), variant)
        )

    def _named(self, asset: str, variant: str) -> str:
        """Why a skin cannot name `variant` of `asset`. A variant not made yet may be named (SPEC-HD-TEXTURES 4.6)."""
        if variant == variants.ORIGINAL:
            return ""
        texture = self.texture(asset)
        recipe, _size = variants.split(variant)
        return progress.model_refusal(texture, recipe)

    def change_skin(
        self,
        owner: str,
        change: Callable[[dict[str, skins.Skin]], dict[str, skins.Skin]],
    ) -> dict[str, skins.Skin]:
        """Apply one change to an owner's skins and keep it. A refused change leaves the file as it was."""
        self.owner(owner)
        before = self.skins_of(owner)
        found = change(before)
        skins.save(self.folder, owner, found)
        self.owner_changed(owner)
        # Who names a texture is in the texture's state (R-HD-156): the rows of what the skins named or name now.
        self.names_changed({asset for held in (before, found) for skin in held.values() for asset in skin.textures})
        return found

    def set_texture(self, owner: str, name: str, asset: str, variant: str | None) -> dict[str, skins.Skin]:  # fmt: skip
        """Set one texture of a skin."""
        assets = set(self.owner(owner).textures)
        return self.change_skin(owner, lambda found: skins.with_texture(found, name, asset, variant, assets, self._named))  # fmt: skip

    def named_by(self, owner: str, name: str) -> dict[str, str]:
        """What a skin names."""
        return skins.textures_of(self.skins_of(owner), name)

    def new_name(self, owner: str, name: str | None) -> str:
        """`name`, or for None the next New Skin N of the owner (R-HD-137)."""
        return skins.next_new(self.skins_of(owner)) if name is None else name

    def copy_skin(self, owner: str, source: str, name: str | None) -> tuple[str, dict[str, skins.Skin]]:  # fmt: skip
        """Make a skin naming what `source` names (R-HD-133); without a name, the next New Skin N. Returns its name and the skins."""
        chosen = self.new_name(owner, name)
        return chosen, self.change_skin(owner, lambda now: skins.copied(now, source, chosen))

    def upscale_skin(
        self, owner: str, source: str, name: str | None, model: str, factor: int
    ) -> dict:
        """Make skin `name` (None: the next New Skin N) from `source` with a variant of each texture by `model` at
        `factor` times its input (R-HD-134). Nothing is requested here.

        Returns the new skin's name, its requests and the textures that keep what `source` shows, each with the reason.
        Refused, and nothing stored, when no texture would be asked for.
        """
        name = self.new_name(owner, name)
        given_by_source = self.named_by(owner, source)
        found = {  # what `source` shows: what it names, else the original (R-HD-131)
            **dict.fromkeys(self.owner(owner).textures, variants.ORIGINAL),
            **given_by_source,
        }
        named, kept = skinplan.plan(
            found,
            self.texture,
            lambda one: self.read_original(one).original,
            model,
            factor,
            variants.max_side(),
            lambda one, read: results.of(self.game, one, read.sha256),
        )
        skinplan.refuse_empty(owner, factor, named, kept)
        self.change_skin(
            owner,
            lambda now: skins.made(now, name, {**given_by_source, **named}),
        )
        return {"skin": name, "requests": named, "kept": kept}

    def revert_refused(self, owner: str, name: str, asset: str, *ids: str) -> dict | None:
        """Put a texture's input back in the skin a request was for, when what it made is a variant a bake would
        refuse (R-HD-162). `ids`: the id the request was asked as and the id that serves it.

        Returns what changed, or None: the variant is sound, the skin is gone, or it names something else by now.
        The variant stays kept; a bake is not changed.
        """
        found = self.skins_of(owner)
        if name not in found:
            return None
        now = found[name].textures.get(asset)
        if now is None or now not in ids:
            return None
        why = results.made_refusal(self.made(self.texture(asset)), now)
        if not why:
            return None
        given = variants.input_of(now)
        self.set_texture(owner, name, asset, None if given == variants.ORIGINAL else given)
        return {"owner": owner, "skin": name, "asset": asset, "from": now, "to": given, "reason": why}

    # -------------------------------------------------------------- bakes

    def bake(self, owner: str, name: str) -> Bake:
        """Bake a skin of an owner: refused when a named variant is missing, stale or has a problem not accepted (R-HD-140, R-HD-102)."""
        bakes.refuse(self.adapter)
        found = self.owner(owner)
        if name == skins.ORIGINAL_SKIN:
            raise bakes.BakeError(
                f"{owner}: Original needs no bake; remove the bake to show the game's textures"
            )
        named = skins.textures_of(self.skins_of(owner), name)
        # A texture the skin does not name shows its original, in the game
        # too (R-HD-131); one of a kind baked alone keeps its own bake (R-HD-145).
        kinds = self._kinds(found.textures)
        plain = [a for a in found.textures if kinds[a] not in self.adapter.alone]
        textures = {**dict.fromkeys(plain, variants.ORIGINAL), **named}
        problems = [
            f"{asset}: {reason}"
            for asset, variant in sorted(textures.items())
            if asset in found.textures and (reason := self._refusal(asset, variant))
        ]
        problems += [
            f"{asset}: it is no texture of {owner}"
            for asset in sorted(textures)
            if asset not in found.textures
        ]
        if problems:
            raise bakes.BakeError(
                f"{owner}, skin {name} cannot be baked:\n" + "\n".join(problems)
            )
        bake = Bake(name, textures)
        # The file each variant has now: the package compares it with the file of then (R-HD-160).
        pins = {asset: self._pin(asset, variant) for asset, variant in textures.items() if variant != variants.ORIGINAL}
        before = self.baked
        bakes.save(self.folder, bakes.with_owner(before, owner, bake, pins))
        self.owner_changed(owner, below=True)
        old = before.owners.get(owner)
        self.names_changed({*textures, *(old.textures if old is not None else ())})
        return bake

    def _pin(self, asset: str, variant: str) -> str:
        """The hash of a made variant's file, as its entry holds it."""
        recipe, size = variants.split(variant)
        return self.made(self.texture(asset))[recipe].entry["files"][str(size)]["sha256"]

    def unbake(self, owner: str) -> None:
        bakes.refuse(self.adapter)
        before = self.baked
        bakes.save(self.folder, bakes.with_owner(before, skins.check_owner(owner), None))
        if owner in self.known_owners():
            self.owner_changed(owner, below=True)
        old = before.owners.get(owner)
        if old is not None:
            self.names_changed(old.textures)

    def bake_texture(self, asset: str, variant: str | None) -> None:
        """Bake one texture on its own, or unbake it with None (R-HD-145)."""
        bakes.refuse(self.adapter)
        texture = self.texture(asset)
        if variant is not None and (reason := self._refusal(asset, variant)):
            raise bakes.BakeError(f"{asset}: {reason}")
        pin = None if variant in (None, variants.ORIGINAL) else self._pin(asset, variant)
        bakes.save(self.folder, bakes.with_texture(self.baked, asset, variant, pin))
        self.changed(texture, everywhere=False)

    # ----------------------------------------------------------- state index

    def changed(self, texture: Texture, everywhere: bool = True) -> None:
        """A variant, a request, the bake or the role of this texture changed: write its state again.

        `everywhere`: in every dataset that holds its origin too. They share
        its variants and its requests. A bake is this dataset's alone, and
        reads no original that has no variant.
        """
        game = self.adapter.id
        with self.index.writing() as con:
            writer = StateWriter(self, con)
            mine = index.rows(con, game, self.name, [texture.asset]).get(texture.asset)
            listed = (
                mine.listed
                if mine is not None
                else self.listed.get(texture.asset, texture)
            )
            if mine is not None and not texture.judged:
                texture = mine.texture  # the role that was found for it before
            original, _moved = writer.known(texture, asked=everywhere and texture.judged)
            writer.put(mine, Row(self.name, listed, texture, {}), original)
            if not everywhere:
                return
            for row in index.rows_at(con, game, texture.origin):
                if (row.dataset, row.texture.asset) != (self.name, texture.asset):
                    writer.put(row, row, original)

    def owner_changed(self, owner: str, below: bool = False) -> None:
        """A skin or a bake of an owner changed: write its row again. `below`: and every owner above it, whose default shows its bake."""
        with self.index.writing() as con:
            writer = StateWriter(self, con)
            writer.put_owner(self.owner(owner))
            if below:
                for other in self.known_owners().values():
                    if owner in other.below:
                        writer.put_owner(other)

    def names_changed(self, assets: Iterable[str]) -> None:
        """A skin or a bake that names these textures changed: write their rows again, for `namedBy` (R-HD-156).

        Only rows the index holds: `index` writes the others. No original is looked at: the change is none of it.
        """
        wanted = sorted(set(assets))
        if not wanted:
            return
        game = self.adapter.id
        with self.index.writing() as con:
            writer = StateWriter(self, con)
            for row in index.rows(con, game, self.name, wanted).values():
                original, _moved = writer.known(row.texture, asked=False, look=False)
                writer.put(row, row, original)

    def changed_all(self) -> None:
        """The package or a texture bake of this dataset changed: write the state of each of its rows again.

        A row whose original file is gone since the last sync is refused, not
        dropped: the index is out of date, and `index` brings it up to date.
        """
        game = self.adapter.id
        with self.index.writing() as con:
            writer = StateWriter(self, con)
            writer.of(self.name)
            for asset, row in index.rows(con, game, self.name).items():
                try:
                    original, _moved = writer.known(row.texture, asked=False, look=False)
                except (GameError, OSError) as error:
                    raise DatasetError(
                        f"{self.name}: {asset}: its original cannot be read ({error}); "
                        "the index is out of date: run index, then this again"
                    ) from error
                writer.put(row, row, original)
            # An owner's row holds its description: its state is written again without listing the owners.
            for described, _state in index.owners(con, game, self.name).values():
                writer.put_owner(described)

    def sync(self, judge: Sequence[str] = ()) -> dict:
        """Bring this dataset's part of the index up to date with its files. Returns what was done, in numbers.

        `judge`: find the role of these textures too; an unknown one is refused.

        Every state is worked out again from the files, so an index that was
        removed or holds something else comes back whole (R-HD-114). A role
        that was found is kept while the game lists the texture as before
        and the file of its original is as it was read.
        """
        game = self.adapter.id
        listed = self.listed
        asked = {asset: self.texture(asset) for asset in judge}
        origins = self.adapter.origins(self.name)
        owners = self.owners
        written = 0
        with self.index.writing() as con:
            writer = StateWriter(self, con)
            writer.of(self.name)
            before = index.rows(con, game, self.name)
            for asset, fresh in listed.items():
                row = before.get(asset)
                same = row is not None and row.listed == fresh
                texture = asked.get(asset) or (
                    row.texture if row is not None and same else fresh
                )
                original, moved = writer.known(texture, asked=asset in asked)
                if asset not in asked and (
                    moved or (original is None and texture.judged and not fresh.judged)
                ):
                    texture = (
                        fresh  # its role was read from a file that is another one now
                    )
                written += writer.put(row, Row(self.name, fresh, texture, {}), original)
            removed = sorted(set(before) - set(listed))
            index.drop(con, game, self.name, removed)
            moved_origins = index.put_origins(con, game, self.name, origins)
            held = index.owners(con, game, self.name)
            gone_owners = sorted(set(held) - set(owners))
            index.drop_owners(con, game, self.name, gone_owners)
            for owner in owners.values():
                written += writer.put_owner(owner, held.get(owner.id))
        LOG.info(
            "%s: the index holds %d textures and %d owners; %d rows written, %d removed; %d origins%s",
            self.name, len(listed), len(owners), written, len(removed), len(origins), "" if moved_origins else ", as before",
        )  # fmt: skip
        return {
            "textures": len(listed),
            "owners": len(owners),
            "written": written,
            "removed": len(removed),
            "judged": sorted(asked),
            "origins": len(origins),
        }
