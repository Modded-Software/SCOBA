"""The transfer of an edit: the session's rendered planes become a new variant of the texture (SPEC-PHOTOCRAFT 10).

The new variant is its input's id, the step `edit` with 12 hex digits of a
hash of the planes, and the input's size: `pbrify@2048+edit3fa9c1d2aa10@2048`.
Equal planes give one id, so one variant (R-PC-54). The input, the
original, every skin and every bake stay as they are (R-PC-51).

A transfer is a request with no runner job (R-PC-57, R-PC-59): while it
runs, the recipe's folder holds request.json as for `requests.make`, and
each change goes to the state index. A failure leaves the reason there and
no variant.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time

import numpy as np

from . import edits, encode, results, variants
from .dataset import Dataset
from .edits import BASE_DIR, RENDERED_DIR, SESSION, EditError
from .interfaces import Planes, Texture
from .progress import ENCODING, FILE, started
from .roles import ROLES  # loading it registers the roles
from .store import plane_key, write_json

LOG = logging.getLogger(__name__)


def planes_digest(record: dict, said: dict) -> str:
    """The hash that names an edit: every plane's name and rendered pixel hash, in the session's order."""
    listed = [[name, said["planes"][name]] for name in record["planes"]]
    return hashlib.sha256(json.dumps(listed).encode()).hexdigest()


def _planes(dataset: Dataset, record: dict, said: dict, changed: list[str]) -> Planes:
    """The planes of the edited variant: a changed one as rendered, the others as the input has them (R-PC-52).

    Each is read from the session's files and checked against its
    recorded hash. A plane the role keeps as one channel becomes the mean
    of its three: a one-channel plane painted in colour has no other
    meaning there.
    """
    folder = edits.session_dir(dataset.game, record["session"])
    planes: Planes = {}
    for name in record["planes"]:
        source = folder / (RENDERED_DIR if name in changed else BASE_DIR) / f"{name}.png"
        want = said["planes"][name] if name in changed else record["bases"][name]
        rgb = edits.read_rgb(source, name)
        if plane_key(rgb) != want:
            raise EditError(f"{source} is not the picture the session recorded; check the session again")
        planes[name] = rgb if record["channels"][name] == 3 else np.rint(rgb.mean(axis=2)).astype(np.uint8)
    return planes


def _input_models(dataset: Dataset, texture: Texture, record: dict) -> dict:
    """The model of each plane of the input variant. The original's planes have none."""
    if record["variant"] == variants.ORIGINAL:
        return dict.fromkeys(record["planes"])
    recipe, _size = variants.split(record["variant"])
    entry = dataset.game.entry(texture.origin, recipe)
    if entry is None:
        raise EditError(f"{record['variant']} of {texture.asset} is gone")
    return {name: entry["models"].get(name) for name in record["planes"]}


def _encode(
    dataset: Dataset, texture: Texture, record: dict, said: dict, recipe: str, original: bytes, changed: list[str], digest: str
) -> dict:  # fmt: skip
    """Join, encode and keep the edited variant, at its one size. Returns its entry."""
    game = dataset.game
    role = ROLES.get(texture.role or "")
    planes = _planes(dataset, record, said, changed)
    # No source: the result is not matched to the original's coarse content. That would take a part of the edit back.
    # Joined across the border only for a texture that tiles (R-HD-91).
    encoded = encode.encode(original, role, planes, matched=False, tiles=texture.tiles)
    own = max(encoded.size)
    models = _input_models(dataset, texture, record)
    return game.write_recipe(
        texture.origin,
        recipe,
        {
            "role": role.name,
            "codec": encoded.format,
            "grid": list(texture.grid),
            "original": {"sha256": hashlib.sha256(original).hexdigest(), "size": list(encoded.source_size)},
            "size": list(encoded.size),
            "mips": encoded.mips,
            "planes": {name: game.put_plane(plane) for name, plane in planes.items()},
            "models": {name: variants.EDIT if name in changed else models[name] for name in record["planes"]},
            "runner": None,  # no upscaler made it
            "encoder": encode.ENCODER_VERSION,
            "numbers": encoded.numbers,
            results.TILES: texture.tiles,
            # A variant whose entry names a changed plane is user-made (R-PC-80).
            "edit": {"input": record["variant"], "changed": changed, "hash": digest, "session": record["session"]},
        },
        {own: encoded.files[own]},
    )


def transfer(dataset: Dataset, session: str) -> dict:
    """Make the edited variant of a session. Returns its id, its entry's files and the session's state.

    Refused, with nothing made: a stale session (R-PC-35), a scratch that
    cannot give every plane (R-PC-53), a scratch with no changed plane.
    The scratch is checked first when it is not the file the last check read.
    """
    game = dataset.game
    folder = edits.session_dir(game, session)
    record = edits.read_record(game, session)
    texture = edits.texture_of(dataset, record)
    if reason := edits.stale_reason(dataset, texture, record):
        raise EditError(f"the edit of {texture.asset} cannot be transferred: {reason}")
    said = edits.read_said(folder)
    if not edits.checked(folder, said):
        said = edits.check_folder(folder, record)
    if said["refused"]:
        raise EditError(f"the edit of {texture.asset} cannot be transferred: {said['refused']}")
    changed = edits.changed_planes(record, said)
    if not changed:
        raise EditError(f"the edit of {texture.asset} changes no plane: there is nothing to transfer")
    digest = planes_digest(record, said)
    variant = variants.edited(record["variant"], digest, max(record["width"], record["height"]))
    recipe, _size = variants.split(variant)
    original = dataset.original(texture)
    kept = game.entry(texture.origin, recipe)
    if kept is None or kept["original"]["sha256"] != hashlib.sha256(original).hexdigest():
        kept = _noted(dataset, texture, record, said, recipe, original, changed, digest)
    if not record["transfers"] or record["transfers"][-1] != {"variant": variant, "planes": said["planes"]}:
        record["transfers"].append({"variant": variant, "planes": said["planes"]})
        write_json(folder / SESSION, record)
    dataset.changed(texture)
    return {
        "made": [{"asset": texture.asset, "variant": variant, "recipe": recipe, "files": kept["files"]}],
        "failed": [],
        "session": edits.state(dataset, session),
    }


def _noted(
    dataset: Dataset, texture: Texture, record: dict, said: dict, recipe: str, original: bytes, changed: list[str], digest: str
) -> dict:  # fmt: skip
    """`_encode`, shown as a request while it runs: request.json in the recipe's folder, and the index written at each change."""
    folder = dataset.game.recipe_dir(texture.origin, recipe)
    steps = len(variants.parse_recipe(recipe))
    note = {"pid": os.getpid(), "started": started(os.getpid()), "since": time.time(), "step": steps, "steps": steps, "phase": ENCODING, "jobs": [], "failed": ""}

    def write(**fields: object) -> None:
        note.update(fields)
        write_json(folder / FILE, note)
        dataset.changed(texture)

    write()
    try:
        entry = _encode(dataset, texture, record, said, recipe, original, changed, digest)
    except BaseException as error:
        # Whatever stops the transfer is written down where the next reader looks.
        reason = str(error) if isinstance(error, EditError) else f"{type(error).__name__}: {error}"
        LOG.exception("transfer of %s to %s failed: %s", texture.asset, recipe, reason)
        write(failed=reason)
        if isinstance(error, EditError) or not isinstance(error, Exception):
            raise  # refused as said, or the program is being stopped
        raise EditError(f"{texture.asset}, {recipe}: {reason}") from error
    (folder / FILE).unlink()
    return entry
