"""The map of the `hdbake` profile: a unit bake and an actor bake, packaged (SPEC-HD-TEXTURES 5.2, E-1).

The map's own store holds model bakes only. This step makes a second
store beside the test map, adds two bakes to it, and builds the map from
`src/` with that store:

- `unit:Marine`, skin `hdtest`: every texture `original`. The model layer
  shows HD variants, so the package makes `<CModel>_hd_Marine`.
- `actor:Marauder`, skin `hdtest`: the same on the actor layer.

The game store is not written. Files that the store only replaces whole
(variants, planes, caches) are hard links; the bakes, the skins and the
state index are copies. The facts the harness and the checks need are
written to `facts.json`.

Run by the profile (`profiles/hdbake.py`), in a process of its own:
`uv run python -m testkit.hdbake_prep <work folder>`.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import workpaths
from normalize_eol import normalize
from project_root import project_root

EOL_SUFFIXES = (".xml", ".galaxy", ".SC2Layout", ".SC2Style", ".txt")  # as build.sh
ROOT = project_root()


def game_store():
    return workpaths.path("TEXTURE_STORE")


SOURCE = ROOT / "src" / "SCOBA.SC2Map"
SKIN = "hdtest"
CASES = (("unit", "Marine"), ("actor", "Marauder"))
NEGATIVE = "Goliath"  # model bake only: its actor keeps its entry
LINKED = ("index", "planes", "upscaled", "variants")


def copy_store(target: Path) -> None:
    """A store at `target` that reads as the game store and writes apart from it."""
    if target.exists():
        shutil.rmtree(target)
    (target / "sc2").mkdir(parents=True)
    shutil.copy2(game_store() / "format", target / "format")
    with (
        sqlite3.connect(game_store() / "index.sqlite") as source,
        sqlite3.connect(target / "index.sqlite") as copy,
    ):
        source.backup(copy)
    shutil.copytree(game_store() / "sc2" / "datasets", target / "sc2" / "datasets")
    for name in LINKED:
        if (game_store() / "sc2" / name).is_dir():
            shutil.copytree(
                game_store() / "sc2" / name,
                target / "sc2" / name,
                copy_function=os.link,
            )


def bake_cases(store: Path) -> dict[str, list[str]]:
    """Skin `hdtest` naming `original` for every texture, baked, on each case. Returns owner -> textures."""
    os.environ["TEXTURE_STORE"] = str(store)
    from hdtex.core import skins
    from hdtex.core.dataset import Dataset
    from hdtex.core.store import Store
    from hdtex.sc2.game import ID as SC2  # loading it registers the game (hdtex.core.registry)

    dataset = Dataset(Store(), SC2, "scoba", SOURCE)
    found: dict[str, list[str]] = {}
    for layer, name in CASES:
        owner = f"{layer}:{name}"
        assets = sorted(dataset.owner(owner).textures)
        if not assets:
            raise SystemExit(f"hdbake: {owner} has no textures")
        dataset.change_skin(
            owner, lambda found: skins.copied(found, skins.DEFAULT, SKIN)
        )
        for asset in assets:
            dataset.set_texture(owner, SKIN, asset, "original")
        dataset.bake(owner, SKIN)
        found[owner] = assets
    return found


def stock_facts() -> dict:
    """Per actor: its stock CModel entry, and the entry the package makes for its bake."""
    from hdtex.core.registry import GAMES
    from hdtex.sc2 import shown
    from hdtex.sc2.owned import SUFFIX

    actors = GAMES.get("sc2").storage("scoba").catalog(shown.ACTORS)
    facts: dict = {}
    for actor in [name for _layer, name in CASES] + [NEGATIVE]:
        entry = actors.need(actor, "Model")
        facts[actor] = {
            "entry": entry,
            "made": f"{entry}{SUFFIX}{actor}" if actor != NEGATIVE else entry,
        }
    return facts


def build_map(store: Path, out: Path) -> None:
    """The build steps of `build.sh` that make and check a map, into `out`, with the store at `store`."""
    env = {**os.environ, "TEXTURE_STORE": str(store)}
    interpreter = [sys.executable]
    subprocess.run(
        [*interpreter, str(ROOT / "scripts" / "expand_map.py"), "--out", str(out)],
        check=True,
        env=env,
        cwd=ROOT,
    )
    for path in sorted(out.rglob("*")):
        if path.is_file() and path.suffix in EOL_SUFFIXES:
            normalize(path, "crlf")
    print("hdbake: writing the map stamp", file=sys.stderr, flush=True)
    stamp = subprocess.run(
        [*interpreter, str(ROOT / "scripts" / "build-stamp.py"), str(SOURCE), str(out)],
        check=True,
        stdout=subprocess.PIPE,  # the stamp; errors go to the terminal
        text=True,
        cwd=ROOT,
    ).stdout.strip()
    print(f"hdbake: map stamp {stamp}")
    subprocess.run(
        [*interpreter, str(ROOT / "scripts" / "validate-map.py"), str(out)],
        check=True,
        env=env,
        cwd=ROOT,
    )


def main() -> int:
    work = Path(sys.argv[1])
    store, out = work / "store", work / "map"
    copy_store(store)
    textures = bake_cases(store)
    facts = {"textures": textures, "actors": stock_facts(), "skin": SKIN}
    build_map(store, out)
    (work / "facts.json").write_text(json.dumps(facts, indent=2), encoding="utf-8")
    print(f"hdbake: map {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
