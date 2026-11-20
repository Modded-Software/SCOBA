"""Extract, split, upscale, and encode the textures of one source.

Everything lands in a cache folder, one subfolder per variant and source,
such as `upscale/terrain/`:

    original/   files as extracted from the game
    planes/     PNG planes per upscaler model, the upscaler's input
    upscaled/   PNG planes after upscaling
    dds/        finished textures, ready for the map
    manifest.json

Each output has a `.stamp` file next to it: a hash of the inputs and the
settings that made it. A stage is skipped when the stamp still matches, so a
second run only redoes what changed.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import NamedTuple, TypedDict

import numpy as np
from PIL import Image

from project_root import project_root

from . import dds, lowfreq, m3tex, metrics, models, roles, upscaler, variants
from .casc import Casc
from .flipbook import FLIP_MARGIN, explode, implode
from .sources import SOURCES, SourceError, TextureRef, stored_name

MANIFEST = "manifest.json"
MANIFEST_FORMAT = 2
MODEL_VERSION = 1  # raise it when the model stage changes
ENCODER_VERSION = 3  # raise it when the encode stage changes, so cached files are redone (3: normal layouts)


class TextureEntry(TypedDict, total=False):
    """One texture in the manifest."""

    asset: str
    role: str
    casc_path: str
    map_path: str
    file: str  # below the source's cache folder
    sha256: str
    source_sha256: str
    source_size: list[int]
    size: list[int]
    mips: int
    format: str
    encode_psnr: list[float]
    fidelity_psnr: list[float]
    fidelity_corr: list[float | None]
    coarse_rmse: float
    seam_source: float
    seam: float
    overrides: list[dict[str, str]]


class ModelFileEntry(TypedDict):
    asset: str
    casc_path: str
    file: str
    map_path: str
    sha256: str
    source_sha256: str
    textures: dict[str, str]


class ModelEntry(TypedDict):
    """One CModel in the manifest. `map_base` is None when no file of it is copied."""

    entry: str
    actors: list[str]
    base: str
    map_base: str | None
    files: list[ModelFileEntry]


class Settings(NamedTuple):
    # (key, model) pairs that replace the variant's models. The key is a plane
    # name, or "texture.plane" for one texture, such as "zerus_4.color".
    models: tuple[tuple[str, str], ...] = ()
    max_size: int = 4096
    wrap: bool = True  # the textures tile: opposite edges must match
    gpu: int | None = None
    tile: int | None = None
    variant: str = variants.DEFAULT

    def model_for(self, plane: roles.Plane, stem: str) -> str:
        """First match wins: asked per texture, asked per plane, the variant per texture, the variant per plane."""
        asked = dict(self.models)
        choice = asked.get(f"{stem}.{plane.name}") or asked.get(plane.name)
        return choice or variants.VARIANTS[self.variant].model_for(plane.name, stem)

    def unknown_models(self, known: set[str]) -> list[str]:
        """Asked keys that name no plane of this source."""
        plane_names = {key.rsplit(".", 1)[-1] for key in known}
        return sorted(key for key, _model in self.models if key not in known and key not in plane_names)


def cache_root() -> Path:
    value = os.environ.get("SC2_HDTEX_CACHE")
    return Path(value) if value else project_root() / "build" / "hdtex"


def variant_root(variant: str) -> Path:
    """The cache folder of one variant. It holds one folder per source."""
    return cache_root() / variant


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def _stamp(*parts: object) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True).encode()).hexdigest()


def _stamp_file(output: Path) -> Path:
    return output.with_name(output.name + ".stamp")


def _fresh(output: Path, stamp: str) -> bool:
    marker = _stamp_file(output)
    return output.is_file() and marker.is_file() and marker.read_text() == stamp


def _mark(output: Path, stamp: str) -> None:
    _stamp_file(output).write_text(stamp)


def stem_of(ref: TextureRef) -> str:
    """The game's own file name without the extension, lower case: the name used in the cache and in model keys."""
    return ref.asset.replace("/", "\\").rsplit("\\", 1)[-1].rsplit(".", 1)[0].lower()


def read_texture(path: Path) -> tuple[dds.Dds, np.ndarray]:
    """A DDS file and its largest level as (H, W, 4) uint8."""
    texture = dds.parse(path.read_bytes())
    return texture, texture.codec.decode(texture.level_bytes(0), texture.width, texture.height)


def _is_flip(ref: TextureRef) -> bool:
    return tuple(ref.grid) != (1, 1)


def _ref_stamp(ref: TextureRef) -> dict:
    """The ref as a stamp part. A texture without a flip book keeps the stamp it had before flip books."""
    fields = {**ref._asdict(), "overrides": _override_fields(ref)}
    if _is_flip(ref):
        fields["flip_margin"] = FLIP_MARGIN
    else:
        del fields["grid"]
    return fields


def _save_plane(plane: np.ndarray, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(plane).save(path)


class InputError(RuntimeError):
    """A plane's input comes from another variant whose cache is missing or incomplete."""


def other_result(variant: str, source: str, key: str) -> Path:
    """The upscaled plane `key` ("texture.plane") of another variant's cache."""
    manifest_path = variant_root(variant) / source / MANIFEST
    hint = f"build it first: uv run python scripts/hd_textures.py --variant {variant} build"
    if not manifest_path.is_file():
        raise InputError(f"no {variant} cache at {manifest_path.parent}; {hint}")
    model = json.loads(manifest_path.read_text())["settings"]["models"].get(key)
    path = manifest_path.parent / "upscaled" / str(model) / f"{key}.png"
    if model is None or not path.is_file():
        raise InputError(f"the {variant} cache has no upscaled {key}; {hint}")
    return path


def split_stage(refs: list[TextureRef], originals: dict[str, Path], work: Path, settings: Settings, force: bool):
    """Write each texture's planes as PNG. Returns {(stem, plane): (model, path)}.

    A plane the variant takes from another variant is that variant's result,
    shrunk. Every other plane is split from the original.
    """
    inputs = variants.VARIANTS[settings.variant].inputs
    planes = {}
    for ref in refs:
        role = roles.ROLES[ref.role]
        source_hash = file_sha256(originals[ref.casc_path])
        stem = stem_of(ref)
        models = {plane.name: settings.model_for(plane, stem) for plane in role.planes}
        targets = {name: work / "planes" / model / f"{stem}.{name}.png" for name, model in models.items()}
        own = [name for name in models if name not in inputs]
        flip = _is_flip(ref)
        if flip and any(name in inputs for name in models):
            raise roles.RoleError(f"{ref.asset}: a flip book cannot take a plane from another variant")
        stamp = _stamp("split", source_hash, ref.role, *((list(ref.grid), FLIP_MARGIN) if flip else ()))
        if own and (force or not all(_fresh(targets[name], stamp) for name in own)):
            _texture, rgba = read_texture(originals[ref.casc_path])
            for name, image in role.split(rgba).items():
                if name in own:
                    _save_plane(explode(image, ref.grid, FLIP_MARGIN) if flip else image, targets[name])
                    _mark(targets[name], stamp)
        for name in models:
            if name not in inputs:
                continue
            given = inputs[name]
            result = other_result(given.variant, work.name, f"{stem}.{name}")
            taken = _stamp("input", given, file_sha256(result))
            if force or not _fresh(targets[name], taken):
                _save_plane(roles.shrink_color(np.asarray(Image.open(result).convert("RGB")), given.shrink), targets[name])
                _mark(targets[name], taken)
        for name, model in models.items():
            planes[stem, name] = (model, targets[name])
    return planes


def upscale_stage(planes: dict, work: Path, settings: Settings, force: bool, tool: str) -> dict:
    """Upscale stale planes, one upscaler run per model. Returns {(stem, plane): path}.

    `tool` is the upscaler's version. A plane made by another version is stale.
    """
    upscaled = {}
    stale: dict[str, list[tuple[Path, Path, str]]] = {}
    for (stem, plane), (model, source) in planes.items():
        target = work / "upscaled" / model / source.name
        stamp = _stamp("upscale", file_sha256(source), model, settings.wrap, tool)
        upscaled[stem, plane] = target
        if force or not _fresh(target, stamp):
            stale.setdefault(model, []).append((source, target, stamp))
    for model, jobs in sorted(stale.items()):
        print(f"hdtex: upscaling {len(jobs)} planes with model {model}", flush=True)
        with tempfile.TemporaryDirectory(prefix="upscale-", dir=work) as scratch:
            inbox, outbox = Path(scratch) / "in", Path(scratch) / "out"
            inbox.mkdir()
            for source, _target, _stamp_value in jobs:
                shutil.copy2(source, inbox / source.name)
            outputs = upscaler.run(inbox, outbox, model, settings.wrap, settings.gpu, settings.tile)
            for source, target, stamp in jobs:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(outputs[source.stem], target)
                _mark(target, stamp)
    return upscaled


def _level(levels: list[np.ndarray], width: int) -> np.ndarray:
    """The mip level of a chain that is `width` wide, or the largest one below it."""
    return next(level for level in levels if level.shape[1] <= width)


def _override_fields(ref: TextureRef) -> list[dict[str, str]]:
    return [override._asdict() for override in ref.overrides]


def encode_texture(
    ref: TextureRef, original: Path, planes: dict[str, np.ndarray], max_size: int, wrap: bool
) -> tuple[bytes, TextureEntry]:
    """Join upscaled planes into a DDS. Returns the file bytes and its manifest entry."""
    source, source_rgba = read_texture(original)
    role = roles.ROLES[ref.role]
    source_planes = role.split(source_rgba)
    levels = roles.limit_size(role.join(planes, source_planes, wrap), max_size)
    reference = role.join(source_planes, None, wrap)
    if ref.role == "normal":
        layout = roles.normal_layout(source_rgba)
        levels = roles.match_layout(levels, layout)
        reference = roles.match_layout(reference, layout)
    height, width = levels[0].shape[:2]
    if width % source.width or height % source.height:
        raise ValueError(f"{ref.asset}: {width}x{height} is not a multiple of the source size")
    if source.format == "DXT1":
        # DXT1 as this tool writes it has no alpha. A source with transparent
        # pixels would lose them.
        if int(source_rgba[:, :, 3].min()) < 255:
            raise roles.RoleError(f"{ref.asset}: DXT1 with transparent pixels is not supported")
        for level in levels:
            level[:, :, 3] = 255
    codec = source.codec
    blobs = [codec.encode(level) for level in levels]
    data = dds.build(width, height, blobs, source.trailer, source.format)
    shrunk = metrics.shrink(levels[0], width // source.width)
    coarse = max(1, source.width // lowfreq.LOW_CELL)
    entry: TextureEntry = {
        "asset": ref.asset,
        "role": ref.role,
        "casc_path": ref.casc_path,
        "map_path": ref.map_path,
        "source_size": [source.width, source.height],
        "source_sha256": file_sha256(original),
        "size": [width, height],
        "mips": len(levels),
        "sha256": hashlib.sha256(data).hexdigest(),
        # Encoding loss: the largest level before and after BC3, per RGBA channel.
        "format": source.format,
        "encode_psnr": metrics.channel_psnr(levels[0], codec.decode(blobs[0], width, height)),
        # Faithfulness: the result shrunk back to the source size, against the source.
        "fidelity_psnr": metrics.channel_psnr(shrunk, source_rgba),
        "fidelity_corr": metrics.channel_correlation(shrunk, source_rgba),
        # Far view: a small mip of the result against the same mip made from the source.
        "coarse_rmse": metrics.rmse(
            _level(levels, coarse), _level(reference, coarse)
        ),
        "seam_source": metrics.seam_ratio(source_rgba),
        "seam": metrics.seam_ratio(levels[0]),
        "overrides": _override_fields(ref),
    }
    return data, entry


def encode_stage(refs, originals, upscaled, work: Path, settings: Settings, force: bool) -> list[TextureEntry]:
    entries: list[TextureEntry] = []
    for ref in refs:
        stem = stem_of(ref)
        role = roles.ROLES[ref.role]
        inputs = {plane.name: upscaled[stem, plane.name] for plane in role.planes}
        target = work / "dds" / ref.map_path.rsplit("\\", 1)[-1]
        entry_file = target.with_name(target.name + ".json")
        stamp = _stamp(
            "encode",
            ENCODER_VERSION,
            _ref_stamp(ref),
            file_sha256(originals[ref.casc_path]),
            {name: file_sha256(path) for name, path in inputs.items()},
            models.max_size(ref.asset, settings.max_size),
            settings.wrap,
        )
        if force or not (_fresh(target, stamp) and entry_file.is_file()):
            print(f"hdtex: encoding {target.name}", flush=True)
            planes = {name: np.asarray(Image.open(path).convert("RGB")) for name, path in inputs.items()}
            # A plane upscaled from a larger input comes out larger than the others.
            width = min(plane.shape[1] for plane in planes.values())
            planes = {
                name: plane if plane.shape[1] == width else roles.shrink_color(plane, plane.shape[1] // width)
                for name, plane in planes.items()
            }
            if _is_flip(ref):
                # The planes were upscaled with a rim around every cell.
                source_width = dds.describe(originals[ref.casc_path].read_bytes()).width
                grown = source_width + 2 * FLIP_MARGIN * ref.grid[0]
                if width % grown:
                    raise ValueError(f"{ref.asset}: an upscaled plane of {width} is not a multiple of {grown}")
                planes = {name: implode(plane, ref.grid, FLIP_MARGIN * (width // grown)) for name, plane in planes.items()}
            data, entry = encode_texture(ref, originals[ref.casc_path], planes, models.max_size(ref.asset, settings.max_size), settings.wrap)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            entry["file"] = f"dds/{target.name}"
            entry_file.write_text(json.dumps(entry, indent=2, sort_keys=True) + "\n")
            _mark(target, stamp)
        entries.append(json.loads(entry_file.read_text()))
    return entries


def _model_layers(path: Path) -> list[m3tex.Layer]:
    return m3tex.layers(m3tex.load(path))


def model_stage(map_dir: Path, casc: Casc, work: Path, entries: list[TextureEntry], force: bool) -> list[ModelEntry]:
    """Write a copy of every wanted model file that names the upscaled textures.

    Returns one manifest entry per CModel. A CModel none of whose files
    names an upscaled texture has no files and gets no override. Otherwise
    every file of it is copied: its variations share one base path.
    """
    paths = {stored_name(entry["asset"]): entry["map_path"] for entry in entries}
    hashes = {entry["map_path"]: entry["sha256"] for entry in entries}
    files = models.model_files(map_dir, casc, work)
    extracted = models.fetch(files, map_dir, casc, work)
    layers = {path: _model_layers(extracted[path]) for path in sorted(extracted)}
    used = {path: sorted({stored_name(layer.path) for layer in found} & set(paths)) for path, found in layers.items()}
    owners: dict[str, str] = {}
    result: dict[str, ModelEntry] = {}
    for file in files:
        entry = result.setdefault(
            file.entry,
            {"entry": file.entry, "actors": list(file.actors), "base": file.base, "map_base": None, "files": []},
        )
        if not any(used[other.casc_path] for other in files if other.entry == file.entry):
            continue
        name = file.asset.replace("/", "\\").rsplit("\\", 1)[-1]
        if owners.setdefault(name.lower(), file.casc_path) != file.casc_path:
            raise SourceError(f"two model files share the name {name}")
        original = extracted[file.casc_path]
        target = work / "m3" / name
        wanted = {asset: paths[asset] for asset in used[file.casc_path]}
        stamp = _stamp("model", MODEL_VERSION, file_sha256(original), wanted)
        if force or not _fresh(target, stamp):
            print(f"hdtex: patching {name}", flush=True)
            m3tex.rewrite(original, target, wanted)
            # The copy is read again. It must name the new textures, and its layers must be the same otherwise.
            expected = [
                layer._replace(path=wanted.get(stored_name(layer.path), layer.path)) for layer in layers[file.casc_path]
            ]
            if _model_layers(target) != expected:
                target.unlink()
                raise m3tex.ModelError(f"{name}: the written copy does not read back with the new texture paths")
            _mark(target, stamp)
        entry["files"].append(
            {
                "asset": file.asset,
                "casc_path": file.casc_path,
                "file": f"m3/{name}",
                "map_path": f"{models.HD_MODEL_DIR}\\{name}",
                "sha256": file_sha256(target),
                "source_sha256": file_sha256(original),
                "textures": {asset: hashes[path] for asset, path in wanted.items()},
            }
        )
        base_name = file.base.replace("/", "\\").rsplit("\\", 1)[-1]
        entry["map_base"] = f"{models.HD_MODEL_DIR}\\{base_name}"
    return [result[key] for key in sorted(result)]


def select(refs: list[TextureRef], only: tuple[str, ...]) -> list[TextureRef]:
    """The refs of the named catalog entries (such as CharLavaCracks). All refs when `only` is empty."""
    if not only:
        return refs
    wanted = {name.lower() for name in only}
    chosen = [ref for ref in refs if any(o.entry.lower() in wanted for o in ref.overrides)]
    found = {o.entry.lower() for ref in chosen for o in ref.overrides}
    if missing := sorted(wanted - found):
        raise roles.RoleError(f"--texture names no entry of this map: {', '.join(missing)}")
    return chosen


def merge_entries(old: list[TextureEntry], new: list[TextureEntry]) -> list[TextureEntry]:
    """The old manifest's entries with the rebuilt ones replaced (matched by map path)."""
    rebuilt = {entry["map_path"] for entry in new}
    return [entry for entry in old if entry["map_path"] not in rebuilt] + new


def build(
    source: str,
    map_dir: Path,
    settings: Settings,
    force: bool = False,
    casc: Casc | None = None,
    only: tuple[str, ...] = (),
) -> Path:
    """Run every stage for one source, or for the entries in `only`. Returns the manifest path.

    A partial build keeps the other textures of the existing manifest.
    """
    work = variant_root(settings.variant) / source
    work.mkdir(parents=True, exist_ok=True)
    casc = casc or Casc()
    every = SOURCES[source](map_dir, casc, work)
    refs = select(every, only)
    print(f"hdtex: {variants.VARIANTS[settings.variant].title}: {source}: {len(refs)} textures", flush=True)
    known = {f"{stem_of(ref)}.{plane.name}" for ref in refs for plane in roles.ROLES[ref.role].planes}
    if unknown := settings.unknown_models(known):
        raise roles.RoleError(f"--model names no plane of {source}: {', '.join(unknown)}")
    originals = casc.extract([ref.casc_path for ref in refs], work / "original")
    planes = split_stage(refs, originals, work, settings, force)
    tool = upscaler.version()
    upscaled = upscale_stage(planes, work, settings, force, tool)
    entries = encode_stage(refs, originals, upscaled, work, settings, force)
    path = work / MANIFEST
    plane_models = {f"{stem}.{name}": model for (stem, name), (model, _path) in sorted(planes.items())}
    if only:
        if not path.is_file():
            raise InputError(f"--texture needs an existing {path}; run a full build first")
        old = json.loads(path.read_text())
        entries = merge_entries(old["textures"], entries)
        plane_models = {**old["settings"]["models"], **plane_models}
    manifest = {
        "format": MANIFEST_FORMAT,
        "variant": settings.variant,
        "source": source,
        "upscaler": tool,
        "settings": {
            "models": plane_models,
            "max_size": settings.max_size,
            "wrap": settings.wrap,
        },
        "textures": entries,
    }
    if source == models.SOURCE:
        manifest["models"] = model_stage(map_dir, casc, work, entries, force)
        manifest["skipped"] = json.loads((work / models.SKIPPED).read_text())
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return path
