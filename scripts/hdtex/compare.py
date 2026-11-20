"""A web page that compares every texture with its upscaled variants.

There is one page per source, `compare/<source>/index.html` in the cache,
and one page with every cached source, `compare/index.html`. A page opens
from disk and needs no server. Each plane of each texture is one entry. It
shows, from left to right:

    the original, decoded, at its own size
    one layer per cached variant, in the order of variants.VARIANTS: the
    finished DDS, decoded, so it shows what the game gets

A colour file gives a colour entry and a mask entry. The mask is dark, so
every side is spread over black to white with the range of the original.
A normal map is shown as the usual blue map, with Z rebuilt.

Each entry has a category, so the page can filter: the terrain, each named
unit, the doodads, and the textures that more than one of them share.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict

from PIL import Image

from . import models, roles, variants
from .inject import load_manifests
from .pipeline import TextureEntry, _fresh, _mark, _stamp, cache_root, read_texture, variant_root
from .preview import stretch
from .sources import SOURCES, stored_name

TEMPLATE = Path(__file__).with_name("compare.html")
DATA_MARK = "/*PAIRS*/[]"
PAGE_VERSION = 3  # raise it when the images change, so cached ones are redone (3: thumbnails)
ORIGINAL = "original"  # the image folder of the originals, next to one per variant
THUMB = 64  # longest side of a list thumbnail

TERRAIN = "Terrain"
DOODADS = "Doodads"
SHARED = "Shared"


class CompareError(RuntimeError):
    """The caches do not give a page. The message names the fix."""


class PlaneImage(TypedDict):
    """One image of one plane, as cached next to it."""

    plane: str
    image: str  # below the page folder
    thumb: str  # a small copy for the list; empty for a variant's side
    size: list[int]
    note: str


class Layer(TypedDict):
    """One variant's side of an entry, with its texture's manifest numbers."""

    variant: str  # the variant's title, such as "Upscale 4x"
    image: str
    size: list[int]
    model: str
    encode_psnr: float
    correlation: float | None  # None when every channel is constant
    coarse_rmse: float
    seam: float


class Pair(TypedDict):
    """One entry of the page: a plane of a texture, its original, and its layers."""

    id: str
    source: str  # the source key, such as "models"
    category: str
    users: list[str]  # catalog entries that use the texture
    texture: str
    role: str
    plane: str
    format: str
    before: str
    thumb: str
    before_size: list[int]
    note: str
    seam_source: float
    layers: list[Layer]


def stem_of(texture: TextureEntry) -> str:
    return texture["asset"].replace("/", "\\").rsplit("\\", 1)[-1].rsplit(".", 1)[0].lower()


def page_root() -> Path:
    return cache_root() / "compare"


def page_folder(source: str) -> Path:
    return page_root() / source


def cached_variants(source: str) -> list[tuple[str, Path, dict]]:
    """(variant key, cache folder, manifest) of every variant that has `source` cached, in display order."""
    return [
        (key, folder, manifest)
        for key in variants.VARIANTS
        for folder, manifest in load_manifests(variant_root(key))
        if manifest["source"] == source
    ]


def categories(manifest: dict) -> dict[str, tuple[str, list[str]]]:
    """Texture asset (stored spelling) to its category and the catalog entries that use it.

    A terrain texture is in "Terrain". A model texture is in the category of
    the named unit that uses it, in "Doodads", or in "Shared" when more than
    one of those use it.
    """
    found: dict[str, tuple[str, list[str]]] = {}
    if manifest["source"] != models.SOURCE:
        for texture in manifest["textures"]:
            users = sorted({override["entry"] for override in texture["overrides"]})
            found[stored_name(texture["asset"])] = (TERRAIN, users)
        return found
    groups: dict[str, set[str]] = {}
    users_of: dict[str, set[str]] = {}
    for entry in manifest.get("models", []):
        units = [actor for actor in entry["actors"] if actor in models.MODEL_UNITS]
        group = units[0] if units else DOODADS
        for model in entry["files"]:
            for asset in model["textures"]:
                groups.setdefault(asset, set()).add(group)
                users_of.setdefault(asset, set()).add(entry["entry"])
    for texture in manifest["textures"]:
        asset = stored_name(texture["asset"])
        own = groups.get(asset, set())
        category = SHARED if len(own) != 1 else next(iter(own))
        found[asset] = (category, sorted(users_of.get(asset, set())))
    return found


def _thumbnail(shown, path: Path) -> None:
    image = Image.fromarray(shown).convert("RGB")
    image.thumbnail((THUMB, THUMB), Image.BILINEAR)
    image.save(path)


def _write_images(folder: Path, texture: TextureEntry, target: Path, side: str) -> list[PlaneImage]:
    """Decode the original, or the result when `side` names a variant, and save each plane."""
    role = roles.ROLES[texture["role"]]
    _source, source_rgba = read_texture(folder / "original" / Path(*texture["casc_path"].split("\\")))
    planes = source_planes = role.split(source_rgba)
    if side != ORIGINAL:
        planes = role.split(read_texture(folder / texture["file"])[1])
    images: list[PlaneImage] = []
    (target / "img" / side).mkdir(parents=True, exist_ok=True)
    for plane in role.planes:
        shown, note = planes[plane.name], ""
        if shown.ndim == 2:
            low, high = int(source_planes[plane.name].min()), int(source_planes[plane.name].max())
            shown = stretch(shown, low, high)
            note = f"values {low} to {high} are shown as black to white"
        name = f"img/{side}/{stem_of(texture)}.{plane.name}.png"
        Image.fromarray(shown).save(target / name)
        thumb = ""
        if side == ORIGINAL:
            thumb = f"img/{side}/{stem_of(texture)}.{plane.name}.thumb.png"
            _thumbnail(shown, target / thumb)
        images.append(
            {"plane": plane.name, "image": name, "thumb": thumb, "size": [shown.shape[1], shown.shape[0]], "note": note}
        )
    return images


def side_images(folder: Path, texture: TextureEntry, target: Path, side: str) -> list[PlaneImage]:
    """The images of one texture for one side. They are redone only when the texture changed."""
    record = target / "img" / side / f"{stem_of(texture)}.json"
    result = "" if side == ORIGINAL else texture["sha256"]
    stamp = _stamp("compare", PAGE_VERSION, side, texture["source_sha256"], result)
    if _fresh(record, stamp):
        images: list[PlaneImage] = json.loads(record.read_text())
        if all((target / name).is_file() for image in images for name in (image["image"], image["thumb"]) if name):
            return images
    print(f"hdtex: writing comparison images, {side}, for {Path(texture['file']).name}", flush=True)
    images = _write_images(folder, texture, target, side)
    record.write_text(json.dumps(images, indent=2) + "\n")
    _mark(record, stamp)
    return images


def pairs_of(cached: list[tuple[str, Path, dict]], target: Path) -> list[Pair]:
    """One entry per plane of every texture any variant holds.

    An entry has a layer for each variant that holds its texture. The caches
    may differ: models have no Generative 4x, and a texture added to the map
    later may be built for one variant only.
    """
    pairs: dict[str, Pair] = {}
    for variant, folder, manifest in cached:
        grouped = categories(manifest)
        for texture in sorted(manifest["textures"], key=stem_of):
            category, users = grouped[stored_name(texture["asset"])]
            originals = {image["plane"]: image for image in side_images(folder, texture, target, ORIGINAL)}
            for image in side_images(folder, texture, target, variant):
                key = f"{stem_of(texture)}.{image['plane']}"
                original = originals[image["plane"]]
                pair = pairs.setdefault(
                    key,
                    {
                        "id": key,
                        "source": manifest["source"],
                        "category": category,
                        "users": users,
                        "texture": texture["asset"].replace("/", "\\").rsplit("\\", 1)[-1],
                        "role": texture["role"],
                        "plane": image["plane"],
                        "format": texture.get("format", "DXT5"),
                        "before": original["image"],
                        "thumb": original["thumb"],
                        "before_size": original["size"],
                        "note": original["note"],
                        "seam_source": texture["seam_source"],
                        "layers": [],
                    },
                )
                pair["layers"].append(
                    {
                        "variant": variants.VARIANTS[variant].title,
                        "image": image["image"],
                        "size": image["size"],
                        "model": manifest["settings"]["models"].get(key, ""),
                        "encode_psnr": min(texture["encode_psnr"]),
                        "correlation": min((v for v in texture["fidelity_corr"] if v is not None), default=None),
                        "coarse_rmse": texture["coarse_rmse"],
                        "seam": texture["seam"],
                    }
                )
    return [pairs[key] for key in sorted(pairs, key=lambda key: key.rsplit(".", 1)[0])]


def _render(pairs: list[Pair], page: Path) -> Path:
    template = TEMPLATE.read_text(encoding="utf-8")
    if template.count(DATA_MARK) != 1:
        raise ValueError(f"{TEMPLATE} must hold {DATA_MARK} exactly once")
    # "</" would end the script block in the page.
    data = json.dumps(pairs).replace("</", "<\\/")
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(template.replace(DATA_MARK, data), encoding="utf-8")
    return page


def _source_pairs(source: str) -> list[Pair]:
    cached = cached_variants(source)
    if not cached:
        raise CompareError(f"no cache for {source} below {cache_root()}")
    return pairs_of(cached, page_folder(source))


def write_page(source: str) -> Path:
    """Write the images and the page for one source, with every cached variant. Returns the page."""
    return _render(_source_pairs(source), page_folder(source) / "index.html")


def _moved(pair: Pair, folder: str) -> Pair:
    """The entry as the page one folder up names its images."""
    moved = pair.copy()
    moved["before"] = f"{folder}/{pair['before']}"
    moved["thumb"] = f"{folder}/{pair['thumb']}" if pair["thumb"] else ""
    moved["layers"] = [{**layer, "image": f"{folder}/{layer['image']}"} for layer in pair["layers"]]
    return moved


def write_index() -> Path:
    """Write the page of every cached source, and one page with all of them. Returns that page."""
    every: list[Pair] = []
    for source in SOURCES:
        if not cached_variants(source):
            continue
        pairs = _source_pairs(source)
        _render(pairs, page_folder(source) / "index.html")
        every += [_moved(pair, source) for pair in pairs]
    if not every:
        raise CompareError(f"no cache below {cache_root()}")
    return _render(every, page_root() / "index.html")
