"""Edit sessions: a variant of a texture as a layered scratch a person edits (SPEC-PHOTOCRAFT 8, 10).

    <game>/edits/<session>/
        session.json          what was opened, each base's pixel hash, each transfer
        base/<plane>.png      each plane as it was opened, 8-bit RGB; never written again
        scratch.psd           the scratch: one top-level group per plane
        rendered/<plane>.png  each plane group as the renderer last wrote it
        scratch.json          what the check last read of the scratch

    open_session  make the session of a texture and a variant, or answer the one that is there
    check         render the scratch's plane groups and record their pixel hashes
    state         stale, unchanged, transferred or edited, from the files
    discard       remove the session

The transfer of an edit to a new variant is `edittransfer`. Nothing here
runs a model or needs a GPU: the renderer is PhotoCraft's own, without one
(`photocraft`).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from pathlib import Path

import numpy as np
from PIL import Image

from . import dds, encode, photocraft, variants
from .dataset import Dataset
from .interfaces import GameError, Planes, Texture
from .roles import ROLES, RoleError  # loading it registers the roles
from .store import GameStore, file_sha256, plane_key, read_json, write_json

EDITS = "edits"
SESSION = "session.json"
SCRATCH = "scratch.psd"
SCRATCH_RECORD = "scratch.json"
BASE_DIR = "base"
RENDERED_DIR = "rendered"
FORMAT = 1  # of session.json and scratch.json
SESSION_ID = re.compile(r"[0-9a-f]{16}")
# The groups of a scratch, top first: the editor opens showing the colour.
PLANE_ORDER = ("color", "normal", "data", "alpha")
MODE, DEPTH = "Rgb", 8  # what `info` says of a scratch as it is built

STALE, UNCHANGED, TRANSFERRED, EDITED = "stale", "unchanged", "transferred", "edited"


class EditError(RuntimeError):
    """Why an edit session cannot be opened, read, transferred or discarded."""


class ScratchRefused(EditError):
    """Why a scratch cannot give every plane (R-PC-75)."""


def session_id(origin: str, variant: str) -> str:
    """One origin and one input variant have one session, whichever plane's tile opened it (R-PC-30)."""
    return hashlib.sha256(json.dumps([origin, variant]).encode()).hexdigest()[:16]


def session_dir(game: GameStore, session: object) -> Path:
    if not isinstance(session, str) or not SESSION_ID.fullmatch(session):
        raise EditError(f"a session is named by 16 hex digits, not {session!r}")
    return game.root / EDITS / session


def read_record(game: GameStore, session: str) -> dict:
    """session.json of a session that is there."""
    path = session_dir(game, session) / SESSION
    if not path.is_file():
        raise EditError(f"there is no edit session {session}")
    record = read_json(path)
    if not isinstance(record, dict) or record.get("format") != FORMAT:
        raise EditError(f"{path} is not a session record in format {FORMAT}")
    return record


def read_said(folder: Path) -> dict:
    """scratch.json: what the last check read."""
    path = folder / SCRATCH_RECORD
    if not path.is_file():
        raise EditError(f"{folder} has no {SCRATCH_RECORD}: its scratch was never checked")
    said = read_json(path)
    if not isinstance(said, dict) or said.get("format") != FORMAT:
        raise EditError(f"{path} is not a scratch record in format {FORMAT}")
    return said


def texture_of(dataset: Dataset, record: dict) -> Texture:
    """The session's texture in this dataset. Datasets that share the origin share the session."""
    texture = dataset.texture(record["asset"])
    if texture.origin != record["origin"]:
        raise EditError(
            f"session {record['session']} is of {record['origin']}; {record['asset']} of {dataset.name} lies at {texture.origin}"
        )
    return texture


def input_file(dataset: Dataset, texture: Texture, variant: str) -> Path:
    """The file of a variant of a texture. What is no kept, fresh variant of it is refused."""
    if variant == variants.ORIGINAL:
        return dataset.adapter.original(dataset.name, texture)
    recipe, size = variants.split(variant)
    made = dataset.made(texture).get(recipe)
    if made is None:
        raise EditError(f"{texture.asset} has no variant {variant}")
    if made.stale:
        raise EditError(f"{variant} is stale: the original changed since it was made")
    if str(size) not in made.entry["files"]:
        raise EditError(
            f"{variant} is not kept; its recipe is kept at {', '.join(map(str, made.sizes()))}"
        )
    return dataset.game.variant_file(texture.origin, recipe, size)


def stale_reason(dataset: Dataset, texture: Texture, record: dict) -> str:
    """Why the session's input is not the file that was opened (R-PC-35). Empty: it is."""
    try:
        path = input_file(dataset, texture, record["variant"])
        found = file_sha256(path)
    except (EditError, GameError, OSError, variants.VariantError) as error:
        return f"its input is gone: {error}"
    if found != record["input"]["sha256"]:
        return f"{record['variant']} is another file now than the one that was opened"
    return ""


def _split(texture: Texture, data: bytes) -> Planes:
    """The planes of a texture file, as its role splits them."""
    role = ROLES.get(texture.role or "")
    try:
        _header, rgba = encode.read_texture(data)
        return role.split(rgba)
    except (dds.DdsError, RoleError) as error:
        raise EditError(f"{texture.asset} cannot be split into planes: {error}") from error


def as_rgb(plane: np.ndarray) -> np.ndarray:
    """A plane as 8-bit RGB (SPEC-PHOTOCRAFT D11): a one-channel plane is that channel three times."""
    if plane.dtype != np.uint8 or (plane.ndim, plane.shape[2:]) not in ((2, ()), (3, (3,))):
        raise EditError(f"a plane is 8-bit grey or RGB, got {plane.dtype} {plane.shape}")
    return plane if plane.ndim == 3 else np.repeat(plane[:, :, None], 3, axis=2)


def read_rgb(path: Path, plane: str) -> np.ndarray:
    """A picture of a plane as 8-bit RGB. One with a pixel that is not opaque is refused, with the count."""
    try:
        with Image.open(path) as image:
            if image.mode in ("RGBA", "LA", "PA") or "transparency" in image.info:
                rgba = np.asarray(image.convert("RGBA"))
                clear = int((rgba[:, :, 3] < 255).sum())
                if clear:
                    raise ScratchRefused(
                        f"the group {plane} has {clear} pixels that are not opaque; a plane covers the whole picture"
                    )
                return rgba[:, :, :3].copy()
            return np.asarray(image.convert("RGB")).copy()
    except (OSError, SyntaxError) as error:
        raise ScratchRefused(f"the picture of {plane} at {path} is not a whole image: {error}") from error


def _places(info: photocraft.Info, record: dict) -> dict[str, int]:
    """Where each plane's group lies among the top-level layers. A scratch that is not laid out as built is refused."""
    if (info.width, info.height) != (record["width"], record["height"]):
        raise ScratchRefused(
            f"the scratch is {info.width}x{info.height}; the texture is {record['width']}x{record['height']}"
        )
    if (info.mode, info.depth) != (MODE, DEPTH):
        raise ScratchRefused(
            f"the scratch is {info.mode} with {info.depth} bits a channel; a scratch is {MODE} with {DEPTH}"
        )
    places = {}
    for name in record["planes"]:
        found = [
            place
            for place, layer in enumerate(info.layers)
            if layer.kind == photocraft.GROUP and layer.name == name
        ]
        if len(found) != 1:
            count = "missing" if not found else f"there {len(found)} times"
            raise ScratchRefused(
                f"the group {name} is {count}; a scratch has one top-level group for each of {', '.join(record['planes'])}"
            )
        places[name] = found[0]
    return places


def _render(folder: Path, record: dict) -> tuple[dict[str, str], list[str]]:
    """Render the scratch's plane groups into rendered/. Returns each plane's pixel hash and the names of the layers left out.

    A top-level layer that is no plane's group belongs to no plane: it is
    left out and named (R-PC-76). A group is composed alone, so such a
    layer changes no plane.
    """
    scratch = folder / SCRATCH
    info = photocraft.info(scratch)
    places = _places(info, record)
    kept = set(places.values())
    left_out = [layer.name for place, layer in enumerate(info.layers) if place not in kept]
    fresh = folder / f".{RENDERED_DIR}.{os.getpid()}"
    if fresh.exists():
        shutil.rmtree(fresh)
    try:
        files = photocraft.render(scratch, fresh)
        hashes = {}
        for name, place in places.items():
            if place not in files:
                raise ScratchRefused(f"the group {name} holds no pixels")
            pixels = read_rgb(files[place], name)
            if pixels.shape[:2] != (record["height"], record["width"]):
                raise ScratchRefused(
                    f"the group {name} renders at {pixels.shape[1]}x{pixels.shape[0]}; the texture is {record['width']}x{record['height']}"
                )
            hashes[name] = plane_key(pixels)
            files[place].replace(fresh / f"{name}.png")
        for place, path in files.items():
            if place not in kept:
                path.unlink()
        rendered = folder / RENDERED_DIR
        if rendered.exists():
            shutil.rmtree(rendered)
        fresh.replace(rendered)
    finally:
        if fresh.exists():
            shutil.rmtree(fresh)
    return hashes, left_out


def check_folder(folder: Path, record: dict) -> dict:
    """Read the scratch of a session folder and write scratch.json. Returns what was written.

    The scratch's size and time are taken before it is read: a scratch
    that changes meanwhile differs from the record, and is checked again.
    The time is kept as text: it has more digits than a JSON number keeps
    in every reader.
    """
    photocraft.program()  # a missing renderer is no fact of the scratch
    scratch = folder / SCRATCH
    said: dict = {"format": FORMAT, "bytes": 0, "changed": "", "planes": {}, "left_out": [], "refused": ""}
    if not scratch.is_file():
        said["refused"] = f"the scratch is not there: {scratch}"
    else:
        stat = scratch.stat()
        said |= {"bytes": stat.st_size, "changed": str(stat.st_mtime_ns)}
        try:
            said["planes"], said["left_out"] = _render(folder, record)
        except (ScratchRefused, photocraft.RendererError) as error:
            said["refused"] = str(error)
    write_json(folder / SCRATCH_RECORD, said)
    return said


def checked(folder: Path, said: dict) -> bool:
    """Whether the scratch is the file the last check read: by its size and time."""
    scratch = folder / SCRATCH
    if not scratch.is_file():
        return (said["bytes"], said["changed"]) == (0, "")
    stat = scratch.stat()
    return (said["bytes"], said["changed"]) == (stat.st_size, str(stat.st_mtime_ns))


def verdict(record: dict, said: dict) -> str:
    """UNCHANGED, TRANSFERRED or EDITED, from the recorded hashes. Stale is judged before it (`state`)."""
    if said["refused"]:
        return EDITED
    if said["planes"] == record["bases"]:
        return UNCHANGED
    transfers = record["transfers"]
    if transfers and said["planes"] == transfers[-1]["planes"]:
        return TRANSFERRED
    return EDITED


def changed_planes(record: dict, said: dict) -> list[str]:
    """The planes whose rendered pixels are not their base's, in the session's order. Empty when the scratch is refused."""
    return [name for name in record["planes"] if name in said["planes"] and said["planes"][name] != record["bases"][name]]


def state(dataset: Dataset, session: str) -> dict:
    """One session as a reader shows it. It runs no check: `checked` false says the scratch changed since the last one."""
    folder = session_dir(dataset.game, session)
    record = read_record(dataset.game, session)
    said = read_said(folder)
    stale = stale_reason(dataset, texture_of(dataset, record), record)
    return {
        "session": session,
        "asset": record["asset"],
        "origin": record["origin"],
        "variant": record["variant"],
        "size": [record["width"], record["height"]],
        "planes": record["planes"],
        "state": STALE if stale else verdict(record, said),
        "reason": stale or said["refused"],
        "changed": changed_planes(record, said),
        "left_out": said["left_out"],
        "checked": checked(folder, said),
        "transfers": [one["variant"] for one in record["transfers"]],
        "scratch": str(folder / SCRATCH),
    }


def check(dataset: Dataset, session: str) -> dict:
    """Render the session's scratch, record it, and answer the session's state."""
    check_folder(session_dir(dataset.game, session), read_record(dataset.game, session))
    return state(dataset, session)


def _differing(folder: Path, name: str, base: np.ndarray) -> int:
    rendered = read_rgb(folder / RENDERED_DIR / f"{name}.png", name)
    return int((rendered != base).any(axis=2).sum())


def _make(dataset: Dataset, texture: Texture, variant: str, folder: Path) -> None:
    """Build a session folder under another name, then rename it: a failed open leaves no session."""
    photocraft.program()
    path = input_file(dataset, texture, variant)
    data = path.read_bytes()
    planes = _split(texture, data)
    names = [name for name in PLANE_ORDER if name in planes]
    if set(names) != set(planes):
        raise EditError(
            f"the role {texture.role} has the planes {', '.join(sorted(planes))}; a scratch lays out {', '.join(PLANE_ORDER)}"
        )
    height, width = planes[names[0]].shape[:2]
    fresh = folder.with_name(f".{folder.name}.{os.getpid()}")
    if fresh.exists():
        shutil.rmtree(fresh)
    (fresh / BASE_DIR).mkdir(parents=True)
    try:
        bases: dict[str, np.ndarray] = {name: as_rgb(planes[name]) for name in names}
        for name, rgb in bases.items():
            Image.fromarray(rgb).save(fresh / BASE_DIR / f"{name}.png", format="PNG")
        photocraft.build([(name, fresh / BASE_DIR / f"{name}.png") for name in names], fresh / SCRATCH)
        record = {
            "format": FORMAT,
            "session": folder.name,
            "origin": texture.origin,
            "asset": texture.asset,
            "dataset": dataset.name,
            "variant": variant,
            "input": {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)},
            "role": texture.role,
            "planes": names,
            "channels": {name: 1 if planes[name].ndim == 2 else 3 for name in names},
            "width": width,
            "height": height,
            "bases": {name: plane_key(rgb) for name, rgb in bases.items()},
            "transfers": [],
        }
        said = check_folder(fresh, record)
        if said["refused"]:
            raise EditError(f"the fresh scratch of {texture.asset} cannot be read back: {said['refused']}")
        # No tolerance (R-PC-42): a renderer that changes a pixel on the way would show every session as edited.
        for name in names:
            if said["planes"][name] != record["bases"][name]:
                raise EditError(
                    f"the renderer does not give the plane {name} of {texture.asset} back as it was built: "
                    f"{_differing(fresh, name, bases[name])} pixels differ; no session is made"
                )
        write_json(fresh / SESSION, record)
        folder.parent.mkdir(parents=True, exist_ok=True)
        try:
            fresh.rename(folder)
        except OSError:
            # Another open of the same session was first: its folder is the session.
            if not (folder / SESSION).is_file():
                raise
    finally:
        if fresh.exists():
            shutil.rmtree(fresh)


def open_session(dataset: Dataset, texture: Texture, variant: str) -> dict:
    """The session of a texture and one of its variants: made when it is not there, else left as it is. Returns its state."""
    if texture.role is None:
        raise EditError(f"{texture.asset} cannot be edited: {texture.reason}")
    session = session_id(texture.origin, variant)
    folder = session_dir(dataset.game, session)
    if not (folder / SESSION).is_file():
        _make(dataset, texture, variant, folder)
    return state(dataset, session)


def discard(game: GameStore, session: str) -> dict:
    """Remove a session's folder. The variants its transfers made stay (R-PC-32)."""
    folder = session_dir(game, session)
    if not (folder / SESSION).is_file():
        raise EditError(f"there is no edit session {session}")
    shutil.rmtree(folder)
    return {"session": session, "discarded": True}
