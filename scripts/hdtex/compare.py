"""A web page that compares every texture with its upscaled variants.

The page is `compare/<source>/index.html` in the cache. It opens from disk
and needs no server. Each plane of each texture is one entry. It shows, from
left to right:

    the original, decoded, at its own size
    one layer per cached variant, in the order of variants.VARIANTS: the
    finished DDS, decoded, so it shows what the game gets

A colour file gives a colour entry and a mask entry. The mask is dark, so
every side is spread over black to white with the range of the original.
A normal map is shown as the usual blue map, with Z rebuilt.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict

from PIL import Image

from . import roles, variants
from .inject import load_manifests
from .pipeline import TextureEntry, _fresh, _mark, _stamp, cache_root, read_texture, variant_root
from .preview import stretch

TEMPLATE = Path(__file__).with_name("compare.html")
DATA_MARK = "/*PAIRS*/[]"
PAGE_VERSION = 2  # raise it when the images change, so cached ones are redone
ORIGINAL = "original"  # the image folder of the originals, next to one per variant


class CompareError(RuntimeError):
    """The caches do not give a page. The message names the fix."""


class PlaneImage(TypedDict):
    """One image of one plane, as cached next to it."""

    plane: str
    image: str  # below the page folder
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
    texture: str
    role: str
    plane: str
    before: str
    before_size: list[int]
    note: str
    seam_source: float
    layers: list[Layer]


def stem_of(texture: TextureEntry) -> str:
    return texture["asset"].replace("/", "\\").rsplit("\\", 1)[-1].rsplit(".", 1)[0].lower()


def page_folder(source: str) -> Path:
    return cache_root() / "compare" / source


def cached_variants(source: str) -> list[tuple[str, Path, dict]]:
    """(variant key, cache folder, manifest) of every variant that has `source` cached, in display order."""
    return [
        (key, folder, manifest)
        for key in variants.VARIANTS
        for folder, manifest in load_manifests(variant_root(key))
        if manifest["source"] == source
    ]


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
        images.append({"plane": plane.name, "image": name, "size": [shown.shape[1], shown.shape[0]], "note": note})
    return images


def side_images(folder: Path, texture: TextureEntry, target: Path, side: str) -> list[PlaneImage]:
    """The images of one texture for one side. They are redone only when the texture changed."""
    record = target / "img" / side / f"{stem_of(texture)}.json"
    result = "" if side == ORIGINAL else texture["sha256"]
    stamp = _stamp("compare", PAGE_VERSION, side, texture["source_sha256"], result)
    if _fresh(record, stamp):
        images: list[PlaneImage] = json.loads(record.read_text())
        if all((target / image["image"]).is_file() for image in images):
            return images
    print(f"hdtex: writing comparison images, {side}, for {Path(texture['file']).name}", flush=True)
    images = _write_images(folder, texture, target, side)
    record.write_text(json.dumps(images, indent=2) + "\n")
    _mark(record, stamp)
    return images


def pairs_of(cached: list[tuple[str, Path, dict]], target: Path) -> list[Pair]:
    pairs: dict[str, Pair] = {}
    _first, folder, manifest = cached[0]
    for texture in sorted(manifest["textures"], key=stem_of):
        for image in side_images(folder, texture, target, ORIGINAL):
            key = f"{stem_of(texture)}.{image['plane']}"
            pairs[key] = {
                "id": key,
                "texture": texture["asset"].replace("/", "\\").rsplit("\\", 1)[-1],
                "role": texture["role"],
                "plane": image["plane"],
                "before": image["image"],
                "before_size": image["size"],
                "note": image["note"],
                "seam_source": texture["seam_source"],
                "layers": [],
            }
    for variant, folder, manifest in cached:
        keys = []
        for texture in manifest["textures"]:
            for image in side_images(folder, texture, target, variant):
                key = f"{stem_of(texture)}.{image['plane']}"
                keys.append(key)
                if key not in pairs:
                    continue
                pairs[key]["layers"].append(
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
        if sorted(keys) != sorted(pairs):
            raise CompareError(
                f"the {variant} cache holds other textures than the {cached[0][0]} cache; rebuild both for the same map"
            )
    return list(pairs.values())


def write_page(source: str) -> Path:
    """Write the images and the page for one source, with every cached variant. Returns the page."""
    cached = cached_variants(source)
    if not cached:
        raise CompareError(f"no cache for {source} below {cache_root()}")
    target = page_folder(source)
    pairs = pairs_of(cached, target)
    template = TEMPLATE.read_text(encoding="utf-8")
    if template.count(DATA_MARK) != 1:
        raise ValueError(f"{TEMPLATE} must hold {DATA_MARK} exactly once")
    # "</" would end the script block in the page.
    data = json.dumps(pairs).replace("</", "<\\/")
    page = target / "index.html"
    page.write_text(template.replace(DATA_MARK, data), encoding="utf-8")
    return page
