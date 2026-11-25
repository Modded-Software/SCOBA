"""The files a dataset can show: its own layer first, then the archives it loads (R-HD-4).

Only this module resolves an asset to a file. A file is named by its
origin: the path the game's storage keeps it at, or `dataset\\<name>\\`
and its path in the dataset's own layer. Datasets that resolve an asset to
the same origin share its results.

A layer is a map folder. What this tooling packaged into it is not part of
it: the packaged textures, the model copies, and the catalog lines that
name them.
"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Iterable
from functools import cached_property
from pathlib import Path

from .casc import Casc
from .catalog import Catalog
from .packaged import is_packaged, own_catalog
from .sources import DEPENDENCY_ARCHIVES, SourceError, map_archives, stored_name

# What a dataset without a layer loads: the game with every campaign.
STOCK_ARCHIVES = DEPENDENCY_ARCHIVES["campaigns/voidstory.sc2campaign"]
GAMEDATA = "\\base.sc2data\\gamedata\\"
ASSET_KINDS = (".dds", ".m3")
# The asset folder of an archive the game shows by default. The other
# `*.sc2assets` folders of an archive hold variants: one per language
# (`enus`, `dede`, ...), and `teen` and `team` (SPEC-HD-TEXTURES H14).
BASE_ASSETS = "base.sc2assets"
# The language of the installed game (H14). 133 assets have no base file,
# only one per language.
LANGUAGE_ASSETS = "enus.sc2assets"
OWN = "dataset\\"
EXTRACT_BATCH = 100  # paths per stormex call: its pattern has a state limit
# The kinds of gap a listing records in `Storage.gaps`.
GAP_ACTORS = "actors whose model cannot be read"
GAP_SHOWN = "names the map shows that have no model"
GAP_TERRAIN = "terrain fields that cannot be read"
GAP_MODELS = "model entries that name no file"
GAP_FILES = "model files the data names that are not there"

LOG = logging.getLogger(__name__)


def asset_of(path: str, archives: tuple[str, ...]) -> tuple[int, str] | None:
    """The load position of the archive that holds a stored path, and the asset path it answers to.

    An archive keeps assets at its root or in a `*.sc2assets` folder. A
    deeper file is in a campaign map inside the archive, which no dataset loads.
    """
    for index, archive in enumerate(archives):
        if not path.startswith(archive + "\\"):
            continue
        rest = path[len(archive) + 1 :]
        folder, _, tail = rest.partition("\\")
        if folder.endswith(".sc2assets"):
            return index, tail
        return None if folder.endswith((".sc2maps", ".sc2data")) else (index, rest)
    return None


def standing(path: str, archive: str) -> int:
    """How far a stored path is the file the game shows (R-HD-112).

    2: the default file, at the archive's root or in its base asset folder.
    1: the file for the installed language. 0: a file for another language
    or for an age rating.
    """
    folder = path[len(archive) + 1 :].partition("\\")[0]
    if not folder.endswith(".sc2assets") or folder == BASE_ASSETS:
        return 2
    return 1 if folder == LANGUAGE_ASSETS else 0


class Storage:
    def __init__(self, name: str, layer: Path | None, casc: Casc, keep: Path) -> None:
        """`keep`: where files taken out of the game's storage stay, for every dataset."""
        if layer is not None and not (layer / "DocumentInfo").is_file():
            raise SourceError(f"{layer} is no map folder: it has no DocumentInfo")
        self.name, self.layer, self.casc, self.keep = name, layer, casc, keep
        self.archives = STOCK_ARCHIVES if layer is None else map_archives(layer)
        # What the game data leaves out, by what found it: each line names the entry and why.
        # The listings write it; status and package report it.
        self.gaps: dict[str, tuple[str, ...]] = {}
        # Origins found kept by `fetch`: not looked for again.
        self._seen: set[str] = set()

    @cached_property
    def listed(self) -> list[str]:
        """Every asset file and every catalog file of the game's storage. One call of stormex."""
        start = time.monotonic()
        found = self.casc.find([*ASSET_KINDS, ".xml"])
        LOG.info(
            "%s: the storage lists %d files, read in %.1f s",
            self.name,
            len(found),
            time.monotonic() - start,
        )
        return found

    @cached_property
    def stored(self) -> dict[str, str]:
        """Asset path -> where the game's storage keeps it.

        The file of the highest standing wins, in whatever archive
        (`standing`). Among files of one standing the archive loaded last
        wins, then the path that sorts last: the answer does not depend on
        the order of the listing.
        """
        best: dict[str, tuple[int, int, str]] = {}
        for path in self.listed:
            found = (
                asset_of(path, self.archives) if path.endswith(ASSET_KINDS) else None
            )
            if found is None:
                continue
            index, asset = found
            rank = (standing(path, self.archives[index]), index, path)
            if asset not in best or rank > best[asset]:
                best[asset] = rank
        return {asset: path for asset, (_standing, _index, path) in best.items()}

    @cached_property
    def own(self) -> dict[str, Path]:
        """Asset path -> the file of the dataset's own layer."""
        if self.layer is None:
            return {}
        found = {}
        for folder, _folders, names in os.walk(self.layer):
            for name in names:
                if name.lower().endswith(ASSET_KINDS):
                    path = Path(folder) / name
                    asset = stored_name("\\".join(path.relative_to(self.layer).parts))
                    if not is_packaged(asset):
                        found[asset] = path
        return found

    def origin(self, asset: str) -> str | None:
        """Where the file of an asset lies. None: the dataset cannot show it."""
        asset = stored_name(asset)
        if asset in self.own:
            return f"{OWN}{self.name}\\{asset}"
        return self.stored.get(asset)

    def origins(self, ending: str) -> dict[str, str]:
        """The origin of every asset of one file kind the dataset can show, by asset."""
        found = {
            asset: path for asset, path in self.stored.items() if asset.endswith(ending)
        }
        found.update(
            {
                asset: f"{OWN}{self.name}\\{asset}"
                for asset in self.own
                if asset.endswith(ending)
            }
        )
        return dict(sorted(found.items()))

    @cached_property
    def present(self) -> frozenset[str]:
        """Every path the listing holds, for a lookup."""
        return frozenset(self.listed)

    def _kept(self, origin: str) -> Path:
        return self.keep.joinpath(*origin.split("\\"))

    def fetch(self, origins: Iterable[str]) -> None:
        """Take every named file that is not kept yet out of the game's storage.

        A file found kept is not looked for again by this object: nothing
        deletes a kept file (stormex writes only the missing ones).
        """
        stored = {
            origin
            for origin in origins
            if not origin.startswith(OWN) and origin not in self._seen
        }
        missing = sorted(origin for origin in stored if not self._kept(origin).is_file())
        if missing:
            start = time.monotonic()
            self.casc.extract(
                missing,
                self.keep,
                batch=EXTRACT_BATCH,
                jobs=min(8, os.cpu_count() or 1),
            )
            LOG.info(
                "%s: took %d files out of the storage in %.1f s",
                self.name,
                len(missing),
                time.monotonic() - start,
            )
        self._seen.update(stored)

    def file(self, origin: str) -> Path:
        """The file at an origin."""
        mine = f"{OWN}{self.name}\\"
        if origin.startswith(mine):
            if origin[len(mine) :] not in self.own:
                raise SourceError(f"{origin} is not in the layer {self.layer}")
            return self.own[origin[len(mine) :]]
        if origin.startswith(OWN):
            raise SourceError(f"{origin} is a file of another dataset than {self.name}")
        self.fetch([origin])
        return self._kept(origin)

    def catalog_texts(self, name: str) -> list[str]:
        """One catalog file from every archive the dataset loads, then from its layer, as texts."""
        tail = GAMEDATA + name.lower()
        stored = [
            archive + tail for archive in self.archives if archive + tail in self.present
        ]
        self.fetch(stored)
        texts = [self._kept(path).read_text(encoding="utf-8-sig") for path in stored]
        own = None if self.layer is None else own_catalog(self.layer, name)
        if own is not None:
            texts.append(own)
        return texts

    def catalog(self, name: str) -> Catalog:
        return Catalog(self.catalog_texts(name))
