"""What the Ghost build's models draw with, by NODExport (SPEC-HD-TEXTURES 6.2, R-HD-151).

The catalog names the models and the templates. `nod` names each model's
materials. One `materials` call finds every material by the lookup of
SPEC-VIEWER-GHOST 4.4. Nothing here reads a NOD, NSA or NOT file: the
lookup is NODExport's alone. The texture coordinates of each model's
export say which of its materials repeat their texture (`repeating`).

The listing is kept in the game's index folder, named by the signature
of the files it read. A listing of another signature is removed.
"""

from __future__ import annotations

import hashlib
import json
import logging
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from ..core.store import write_json
from .build import MODELS, Build, BuildError, by_lower, files, signature

LOG = logging.getLogger(__name__)
FORMAT = 2  # 2: `repeats`, the materials of each model that repeat their texture
# A vertex of `NODExport nod`'s binary: float3 position, float3 normal, float2 uv, uint8[4] bones, float[4] weights.
STRIDE = 52
UV_AT = 24
# How far past a whole number a triangle's u or v may reach and still not repeat the texture: Nova's
# eyelashes reach 1.004 from 0.103 (measured 2026-11-26).
SPAN_SLACK = 0.02
PREFIX = "listing-"
JOBS = 8
# The material keys NODExport exports as texture files (nodexport_materials.cpp).
TEXTURE_KEYS = ("texture", "texture2", "glow", "envmap", "detail")


def _run(build: Build, *args: str) -> bool:
    """One NODExport call. False: it refused, and its JSON says why. Any other end is an error."""
    done = subprocess.run([str(build.exporter), *args], capture_output=True, text=True)
    if done.returncode not in (0, 1):
        raise BuildError(f"NODExport {args[0]} ended with exit status {done.returncode}: {done.stderr.strip()[-400:]}")
    return done.returncode == 0


def _read(path: Path) -> dict:
    """NODExport's JSON. A material with a key twice names its file twice; the last counts, as the viewer's JSON.parse reads it."""
    found = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(found, dict):
        raise BuildError(f"NODExport wrote no object to {path.name}")
    return found


def repeating(answer: dict, binary: bytes, rel: str) -> list[str]:
    """The materials of one exported model whose texture repeats: a triangle of theirs spans a whole-number line of u or v.

    A triangle that spans one samples across the texture's border, so the texture tiles there. A triangle moved
    whole by a whole number does not (SPEC-HD-TEXTURES 6.2).
    """
    try:
        stride, count, offset = answer["vertexStride"], answer["indexCount"], answer["indexOffset"]
        groups, names = answer["groups"], answer["materials"]
    except KeyError as missing:
        raise BuildError(f"{rel}: the export has no {missing}") from missing
    if stride != STRIDE or offset % STRIDE or len(binary) != offset + 4 * count:
        raise BuildError(f"{rel}: the export's binary is {len(binary)} bytes, not {offset} of {STRIDE}-byte vertices and {count} indices")
    data = np.frombuffer(binary, dtype=np.uint8)
    uv = data[:offset].reshape(-1, STRIDE)[:, UV_AT : UV_AT + 8].copy().view(np.float32).reshape(-1, 2)
    indices = data[offset:].copy().view(np.uint32)
    found: set[str] = set()
    for group in groups:
        triangles = indices[group["firstIndex"] : group["firstIndex"] + group["indexCount"]]
        if len(triangles) % 3 or (len(triangles) and int(triangles.max()) >= len(uv)):
            raise BuildError(f"{rel}: a group of the export names indices past its vertices")
        corners = uv[triangles.reshape(-1, 3)]
        low, high = corners.min(axis=1), corners.max(axis=1)
        if (np.floor(high - SPAN_SLACK) > np.floor(low + SPAN_SLACK)).any():
            found.add(names[group["material"]])
    return sorted(found)


def _model_materials(build: Build, rel: str, scratch: Path) -> tuple[list[str] | None, list[str], str]:
    """The material names of one model and those of them that repeat their texture; or None and why NODExport refused it."""
    out = scratch / f"{hashlib.sha256(rel.encode()).hexdigest()}.json"
    binary = out.with_suffix(".bin")
    ok = _run(build, "nod", str(build.root / rel), str(out), str(binary))
    answer = _read(out)
    data = binary.read_bytes() if ok else b""
    binary.unlink(missing_ok=True)
    out.unlink()
    if not ok:
        return None, [], str(answer.get("error"))
    names = answer.get("materials")
    if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
        raise BuildError(f"{rel}: the export names no materials")
    return names, repeating(answer, data, rel), ""


def _materials(build: Build, names: list[str], scratch: Path) -> dict[str, dict]:
    """Each material name: its lookup step, its shader and its texture files (relative to the build; None when missing)."""
    listed, out = scratch / "names.txt", scratch / "materials.json"
    listed.write_text("".join(f"{name}\n" for name in names), encoding="utf-8")
    if not _run(build, "materials", str(build.root), str(listed), str(out)):
        raise BuildError(f"NODExport materials refused: {_read(out).get('error')}")
    found: dict[str, dict] = {}
    for material in _read(out)["materials"]:
        shader = next((value for key, value in material["properties"] if key.lower() == "shader"), "")
        textures = {key: material["textures"].get(key) for key in TEXTURE_KEYS if key in material["textures"]}
        found[material["name"]] = {"step": material["step"], "shader": shader.lower(), "textures": textures}
    return found


def _find(lower: dict[str, str], folder: str, name: str, ext: str) -> str | None:
    """A file named by another file, without regard to case; `ext` appended to a name without one (SPEC-VIEWER-GHOST 4.6)."""
    exact = lower.get(f"{folder}/{name}".lower())
    if exact is not None or "." in name.rsplit("/", 1)[-1]:
        return exact
    return lower.get(f"{folder}/{name}{ext}".lower())


def _make(build: Build, listed: list[str], scratch: Path) -> dict:
    out = scratch / "catalog.json"
    if not _run(build, "catalog", str(build.root), str(out)):
        raise BuildError(f"NODExport catalog refused: {_read(out).get('error')}")
    catalog = _read(out)
    lower = by_lower(listed)
    refused = [{"name": one["name"], "error": one["error"]} for one in catalog["refusedModels"]]
    rels = [f"{MODELS}/{model['file']}" for model in catalog["models"]]
    with ThreadPoolExecutor(max_workers=JOBS) as pool:
        named = list(pool.map(lambda rel: _model_materials(build, rel, scratch), rels))
    models = {}
    repeats = {}
    for rel, (names, repeated, why) in zip(rels, named, strict=True):
        if names is None:
            refused.append({"name": rel, "error": why})
        else:
            models[rel] = names
            repeats[rel] = repeated
    templates = []
    for template in catalog["templates"]:
        model = template["model"]
        rel = _find(lower, MODELS, model, ".nod") if model else None
        if rel in models:
            templates.append({"name": template["name"], "model": rel})
    every = sorted({name for names in models.values() for name in names})
    return {"format": FORMAT, "models": models, "repeats": repeats, "refused": refused, "templates": templates, "materials": _materials(build, every, scratch)}


def listing(build: Build, index: Path) -> tuple[dict, list[str]]:
    """The listing of the build, made when its files changed; and the files it read."""
    listed = files(build.root)
    kept = index / f"{PREFIX}{signature(build.root, listed)}.json"
    if kept.is_file():
        found = _read(kept)
        if found.get("format") == FORMAT:
            return found, listed
    index.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=index, prefix=".export-") as scratch:
        made = _make(build, listed, Path(scratch))
    for old in index.glob(f"{PREFIX}*.json"):
        old.unlink()
    write_json(kept, made)
    LOG.info("ghost: %d models (%d refused), %d templates, %d materials listed by NODExport", len(made["models"]), len(made["refused"]), len(made["templates"]), len(made["materials"]))
    return made, listed
