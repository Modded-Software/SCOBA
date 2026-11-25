"""The commands of scripts/hd_textures.py. Every command prints one JSON value.

    status   the textures of a dataset: descriptions, variants, requests; the owners with skins and bakes
    index    bring the dataset's part of the state index up to date with its files
    request  make one variant: an input variant, a model and a size
    remove   remove one variant of a texture, unless something still needs it
    skin     list, copy, rename, delete or change the skins of one owner; upscale a whole skin
    bake     bake a skin of an owner, or a variant of a texture baked on its own
    unbake   remove a bake
    package  package a dataset no build packages, into the store
    upscaler the upscaler's tool and whether a worker runs, for whoever starts one
    edit     open, check, transfer or discard the edit session of a texture's variant (SPEC-PHOTOCRAFT 10)

A command that fails prints {"error": ...} and ends with exit status 1.
No command takes a tile size, a GPU or a force flag. A command that
changes a state writes it to the state index (core/index.py). A reader
reads it there and runs no command. The upscaler is arc-upscale;
HDTEX_RUNNER=repeat takes the one without a GPU that the viewer's tests
use (core/repeat.py).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from . import bakes, edits, edittransfer, package, photocraft, progress, removal, requests, skinbakes, skins, variants, view  # fmt: skip
from .dataset import Dataset, DatasetError
from .interfaces import GameError, Runner, Texture
from .registry import RUNNERS, RegistryError
from .repeat import ID as REPEAT
from .runner import ID as RUNNER
from .runner import RunnerError
from .store import Store, StoreError

REFUSED = (
    DatasetError, requests.RequestError, variants.VariantError, skins.SkinError, bakes.BakeError,
    StoreError, RegistryError, RunnerError, package.PackageError, GameError,
    edits.EditError, photocraft.RendererError, removal.RemovalError,
)  # fmt: skip
RUNNER_ENV = "HDTEX_RUNNER"
RUNNER_IDS = (RUNNER, REPEAT)


class UsageError(ValueError):
    """The words of a command do not fit together."""


def _runner() -> Runner:
    """The upscaler HDTEX_RUNNER names; arc-upscale when it is not set."""
    chosen = os.environ.get(RUNNER_ENV) or RUNNER
    if chosen not in RUNNER_IDS:
        raise UsageError(
            f"{RUNNER_ENV} is one of {', '.join(RUNNER_IDS)}, not {chosen!r}"
        )
    return RUNNERS.get(chosen)()


def _texture(dataset: Dataset, texture: Texture, runner: Callable[[], Runner]) -> dict:
    made = dataset.made(texture)
    return {
        "asset": texture.asset,
        "origin": texture.origin,
        "kind": texture.kind,
        "judged": texture.judged,  # false: the role is not known yet; ask for the texture by --asset
        "role": texture.role,
        "reason": texture.reason,
        "tiles": texture.tiles,
        "grid": list(texture.grid),
        "users": list(texture.users),
        "entries": list(texture.entries),
        "recipes": {
            recipe: {
                "folder": str(dataset.game.recipe_dir(texture.origin, recipe)),
                "size": one.entry["size"],
                "variants": [variants.variant_id(recipe, size) for size in one.sizes()],
                "stale": one.stale,
                "problems": list(one.missed),
                "accepted": one.accepted,
                "models": one.entry["models"],
            }
            for recipe, one in made.items()
        },
        "requests": {
            recipe: progress.read(dataset.game, runner, texture.origin, recipe)
            for recipe in progress.asked(dataset.game, texture.origin)
        },
        "bake": dataset.baked.textures.get(texture.asset),
    }


def status(
    dataset: Dataset, runner: Callable[[], Runner], args: argparse.Namespace
) -> dict:
    wanted = (
        [dataset.texture(asset) for asset in args.asset]
        if args.asset
        else list(dataset.textures.values())
    )
    baked = dataset.baked
    return {
        "game": dataset.adapter.id,
        "dataset": dataset.name,
        "sizes": list(variants.SIZES),
        "models": list(variants.MODELS),
        "textures": [
            _texture(dataset, texture, runner)
            for texture in sorted(wanted, key=lambda item: item.asset)
            if args.kind is None or texture.kind == args.kind
        ],
        "owners": [
            view.owner_state(
                dataset.owner(owner),
                dataset.skins_of(owner),
                baked,
                package.record(dataset),
            )
            for owner in sorted(set(baked.owners) | set(skins.owners(dataset.folder)))
            if owner in dataset.owners
        ],
        "unused": sorted(set(baked.owners) - set(dataset.owners))
        + sorted(set(baked.textures) - set(dataset.textures)),
        # Read last: the texture and owner listings above record them.
        "gaps": dataset.adapter.gaps(dataset.name),
    }


def indexed(
    dataset: Dataset, _runner: Callable[[], Runner], args: argparse.Namespace
) -> dict:
    """Bring the index up to date; with --asset, find the role of those textures too."""
    return {"index": str(dataset.index.path), **dataset.sync(args.asset or ())}


def request(
    dataset: Dataset, runner: Callable[[], Runner], args: argparse.Namespace
) -> dict:
    """Make one variant: by --variant, or by --input, --model and --size."""
    if args.variant is not None and (
        args.input is not None or args.model is not None or args.size is not None
    ):
        raise UsageError("a request is --variant, or --input, --model and --size")
    if args.variant is None and (args.model is None or args.size is None):
        raise UsageError("a request is --variant, or --input, --model and --size")
    variant = args.variant or variants.join(
        args.input or variants.ORIGINAL, args.model, args.size
    )
    texture = dataset.texture(args.asset)
    entry = requests.make(dataset, runner(), texture, variant)
    return {
        "made": [
            {
                "asset": texture.asset,
                "variant": variant,
                "recipe": entry["recipe"],
                "files": entry["files"],
            }
        ],
        "failed": [],
    }


def remove(
    dataset: Dataset, _runner: Callable[[], Runner], args: argparse.Namespace
) -> dict:
    """Remove one variant of a texture (R-HD-146)."""
    texture = dataset.texture(args.asset)
    removal.remove(dataset, texture, args.variant)
    return {"asset": texture.asset, "removed": args.variant}


def skin(
    dataset: Dataset, runner: Callable[[], Runner], args: argparse.Namespace
) -> dict:
    owner = args.owner
    if args.action == "list":
        found = dataset.skins_of(owner)
    elif args.action == "copy":
        found = dataset.change_skin(
            owner, lambda now: skins.copied(now, args.source, args.name)
        )
    elif args.action == "rename":
        found = skinbakes.rename(dataset, owner, args.name, args.new)
    elif args.action == "delete":
        found = skinbakes.delete(dataset, owner, args.name)
    elif args.action == "set":
        if args.clear == (args.variant is not None):
            raise UsageError("skin set takes --variant, or --clear")
        found = dataset.set_texture(
            owner, args.name, args.asset, None if args.clear else args.variant
        )
    else:
        made = dataset.upscale_skin(
            owner, args.source, args.name, args.model, args.size
        )
        if args.defer:
            # The caller starts each request as a process of its own (SPEC-VIEWER 17.1).
            return {**made, "failed": []}
        failed = []
        for asset, variant in sorted(made["requests"].items()):
            try:
                requests.make(dataset, runner(), dataset.texture(asset), variant)
            except requests.RequestError as error:
                failed.append({"asset": asset, "variant": variant, "error": str(error)})
        return {**made, "failed": failed}
    return {
        "owner": owner,
        "skins": {
            name: {"textures": one.textures}
            for name, one in sorted(found.items())
        },
    }


def bake(
    dataset: Dataset, _runner: Callable[[], Runner], args: argparse.Namespace
) -> dict:
    if (args.owner is None) == (args.asset is None):
        raise UsageError("bake takes --owner and --skin, or --asset and --variant")
    if args.owner is not None:
        if args.skin is None:
            raise UsageError("bake --owner takes --skin")
        found = dataset.bake(args.owner, args.skin)
        return {"owner": args.owner, "skin": found.skin, "textures": found.textures}
    if args.variant is None:
        raise UsageError("bake --asset takes --variant")
    dataset.bake_texture(args.asset, args.variant)
    return {"asset": args.asset, "variant": args.variant}


def unbake(
    dataset: Dataset, _runner: Callable[[], Runner], args: argparse.Namespace
) -> dict:
    if (args.owner is None) == (args.asset is None):
        raise UsageError("unbake takes --owner or --asset")
    if args.owner is not None:
        dataset.unbake(args.owner)
        return {"owner": args.owner, "bake": None}
    dataset.bake_texture(args.asset, None)
    return {"asset": args.asset, "bake": None}


def packaged(
    dataset: Dataset, _runner: Callable[[], Runner], _args: argparse.Namespace
) -> dict:
    made = package.package_in_store(dataset)
    return {**made, "gaps": dataset.adapter.gaps(dataset.name)}


def upscaler(
    _dataset: Dataset, runner: Callable[[], Runner], args: argparse.Namespace
) -> dict:
    """The command and settings that start the upscaler's worker, and why none runs now."""
    made = runner()
    command, settings = made.worker(args.log)
    return {
        "upscaler": {
            "id": made.id,
            "idle": made.idle(),
            "worker": {"command": command, "env": settings},
        }
    }


def edit(
    dataset: Dataset, _runner: Callable[[], Runner], args: argparse.Namespace
) -> dict:
    """One action on an edit session. No action hands anything to the upscaler."""
    if args.action == "open":
        texture = dataset.texture(args.asset)
        return {"session": edits.open_session(dataset, texture, args.variant or variants.ORIGINAL)}
    if args.action == "check":
        return {"session": edits.check(dataset, args.session)}
    if args.action == "transfer":
        return edittransfer.transfer(dataset, args.session)
    return edits.discard(dataset.game, args.session)


def parser() -> argparse.ArgumentParser:
    made = argparse.ArgumentParser(
        prog="hd_textures.py", description=(__doc__ or "").split("\n\n")[0]
    )
    commands = made.add_subparsers(dest="command", required=True)

    def command(name: str, run: Callable[..., dict]) -> argparse.ArgumentParser:
        added = commands.add_parser(name)
        added.add_argument("--game", required=True)
        added.add_argument("--dataset", required=True)
        added.add_argument(
            "--layer",
            type=Path,
            help="the folder of the dataset's own files, for a game that has the caller name it",
        )
        added.set_defaults(run=run)
        return added

    shown = command("status", status)
    shown.add_argument(
        "--asset", action="append", help="one texture; may be given more than once"
    )
    shown.add_argument("--kind", help="only the textures of this kind")
    synced = command("index", indexed)
    synced.add_argument(
        "--asset",
        action="append",
        help="find the role of this texture too; may be given more than once",
    )
    asked = command("request", request)
    asked.add_argument("--asset", required=True)
    asked.add_argument("--variant", help="the variant id, such as pbrify@2048")
    asked.add_argument(
        "--input", help=f"the input variant; {variants.ORIGINAL} when not given"
    )
    asked.add_argument("--model", choices=sorted(variants.MODELS))
    asked.add_argument(
        "--size",
        type=int,
        help=f"{', '.join(map(str, variants.SIZES))}, or the variant's own size where it is smaller",
    )
    removing = command("remove", remove)
    removing.add_argument("--asset", required=True)
    removing.add_argument("--variant", required=True, help="the variant id, such as pbrify@2048")
    skinned = command("skin", skin)
    skinned.add_argument(
        "action", choices=("list", "copy", "rename", "delete", "set", "upscale")
    )
    skinned.add_argument(
        "--owner", required=True, help="unit:<id>, actor:<id> or model:<file>"
    )
    skinned.add_argument("--name", help="the skin")
    skinned.add_argument(
        "--from",
        dest="source",
        default=skins.ORIGINAL_SKIN,
        help="the skin a copy or an upscale is made from",
    )
    skinned.add_argument(
        "--new", help="the new name, for rename; a rename of 'new' saves New Skin"
    )
    skinned.add_argument("--asset", help="the texture, for set")
    skinned.add_argument("--variant", help="the variant id, for set")
    skinned.add_argument(
        "--clear",
        action="store_true",
        help="for set: name nothing; the texture shows its original",
    )
    skinned.add_argument("--model", choices=sorted(variants.MODELS), help="for upscale")
    skinned.add_argument(
        "--size",
        type=int,
        help="for upscale; a texture that cannot have it keeps its variant, with the reason",
    )
    skinned.add_argument(
        "--defer",
        action="store_true",
        help="for upscale: write the skin and name its requests; start none",
    )
    baking = command("bake", bake)
    baking.add_argument("--owner")
    baking.add_argument("--skin")
    baking.add_argument("--asset", help="a texture baked on its own")
    baking.add_argument("--variant")
    unbaking = command("unbake", unbake)
    unbaking.add_argument("--owner")
    unbaking.add_argument("--asset")
    command("package", packaged)
    command("upscaler", upscaler).add_argument(
        "--log", type=Path, required=True, help="the file the worker logs to"
    )
    edited = command("edit", edit)
    edited.add_argument("action", choices=("open", "check", "transfer", "discard"))
    edited.add_argument("--asset", help="the texture, for open")
    edited.add_argument(
        "--variant", help=f"the variant to edit, for open; {variants.ORIGINAL} when not given"
    )
    edited.add_argument("--session", help="the session, for check, transfer and discard")
    return made


def _check(args: argparse.Namespace) -> None:
    if args.command == "skin":
        if args.action != "list" and args.name is None:
            raise UsageError(f"skin {args.action} takes --name")
        if args.action == "rename" and args.new is None:
            raise UsageError("skin rename takes --new")
        if args.action == "set" and args.asset is None:
            raise UsageError("skin set takes --asset")
        if args.action == "upscale" and (args.model is None or args.size is None):
            raise UsageError("skin upscale takes --model and --size")
    if args.command == "edit":
        opening = args.action == "open"
        if opening and (args.asset is None or args.session is not None):
            raise UsageError("edit open takes --asset, and --variant for a variant; no --session")
        if not opening and (args.session is None or args.asset is not None or args.variant is not None):
            raise UsageError(f"edit {args.action} takes --session, and no --asset or --variant")


def main(
    argv: Sequence[str] | None = None,
    runner: Callable[[], Runner] | None = None,
    store: Store | None = None,
) -> int:
    """Run one command. `runner` and `store` are for tests: the upscaler and the store to use."""
    args = parser().parse_args(argv)
    try:
        _check(args)
        made = runner if runner is not None else _runner
        dataset = Dataset(
            store if store is not None else Store(),
            args.game,
            args.dataset,
            args.layer,
            made,
        )
        answer = args.run(dataset, made, args)
    except (*REFUSED, UsageError) as error:
        print(json.dumps({"error": str(error)}))
        return 1
    print(json.dumps(answer, indent=2, allow_nan=False))
    return 1 if answer.get("failed") else 0


def run() -> int:
    """The program: one command, with what the core logs on stderr. stdout holds the JSON only."""
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.INFO,
        format="%(asctime)s %(name)s: %(message)s",
    )
    return main()
