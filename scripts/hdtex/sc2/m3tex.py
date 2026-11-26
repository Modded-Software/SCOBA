"""The textures a model file names, and a copy of the model that names others.

A model keeps its texture paths in the layers of its materials. A layer
sits in a slot of a material, such as `diffuseLayer`. The slot says what
the texture means.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import NamedTuple

import numpy as np
from project_root import project_root

sys.path.insert(0, str(project_root() / "scripts" / "vendor" / "m3addon"))

import m3

VIDEO_BIT = "isVideo"
FLIPBOOK_BIT = "useParticleFlipBook"
WRAP_BITS = ("textureWrapX", "textureWrapY")
# A particle system names its material by a reference: a type and an index.
STANDARD_TYPE = 1
STANDARD_LIST = "standardMaterials"
COMPOSITE_TYPE = 3  # a composite draws the materials its sections name, on the same batch
# MATM materialType -> the model's list of that type (structures.xml MODL; the viewer's model.ts MATERIAL_TYPES).
MATERIAL_TYPES = {
    1: "standardMaterials", 2: "displacementMaterials", 3: "compositeMaterials", 4: "terrainMaterials",
    5: "volumeMaterials", 7: "creepMaterials", 8: "volumeNoiseMaterials", 9: "splatTerrainBakeMaterials",
    10: "reflectionMaterial", 11: "lensFlareMaterial",
}  # fmt: skip
ANIMATED = 6  # animFlags of an animation reference that names an animation (structures.xml)
UV_FIELDS = ("uv0", "uv1", "uv2", "uv3")  # a layer's uvSource 0 to 3 reads these; other sources are no coordinates
SPAN_SLACK = 0.02  # as Ghost (ghost/export.py): a triangle that reaches past a line by less does not span it
NO_AREA = 1e-9  # a triangle whose texture-space area is at most this shows nothing
# A texture tiles when at least this share of the triangles that draw it, over all its model files, span a line
# (modelindex.uses). Chosen 2026-11-26: of the 3426 batches of the cache with a spanning triangle (uv0), 430 have a
# share of at most 1%, 2996 more; thorbirth.m3 spans 3 of 4152, and Thor_Diffuse 3 of 10090 over Thor's two files.
TILE_SHARE = 0.01


class ModelError(RuntimeError):
    """The model file could not be read or written."""


class Layer(NamedTuple):
    material: str  # material list of the model, such as standardMaterials
    index: int  # position in that list
    slot: str  # field of the material, such as diffuseLayer
    path: str  # texture path as the model spells it
    video: bool
    flipbook: bool
    wrap: bool  # the layer's sampler wraps on both axes: the default, set on 97% of layers; no sign that it repeats
    # Flip book: (columns, rows) of its cells. None: no flip book, or the cells are not known.
    grid: tuple[int, int] | None = None
    moves: bool = False  # it repeats the texture by itself: it tiles or scrolls (`moves`)
    spans: int = 0  # triangles drawn with it that span a whole-number line of its coordinates; 0 when it clamps
    triangles: int = 0  # triangles drawn with it that show something (`spanning`)


# Reads one field of a structure of the model.
Reader = Callable[[m3.M3Structure], list[m3.M3Structure]]

# Every material list of a model, and every slot of its materials that holds
# layers, as scripts/vendor/m3addon/structures.xml lists them. An older
# model lacks the newer ones; the description of a structure says which.
MATERIAL_LISTS: tuple[tuple[str, Reader, tuple[tuple[str, Reader], ...]], ...] = (
    (
        "standardMaterials",
        lambda model: model.standardMaterials,
        (
            ("diffuseLayer", lambda material: material.diffuseLayer),
            ("decalLayer", lambda material: material.decalLayer),
            ("specularLayer", lambda material: material.specularLayer),
            ("glossLayer", lambda material: material.glossLayer),
            ("emissiveLayer", lambda material: material.emissiveLayer),
            ("emissive2Layer", lambda material: material.emissive2Layer),
            ("evioLayer", lambda material: material.evioLayer),
            ("evioMaskLayer", lambda material: material.evioMaskLayer),
            ("alphaMaskLayer", lambda material: material.alphaMaskLayer),
            ("alphaMask2Layer", lambda material: material.alphaMask2Layer),
            ("normalLayer", lambda material: material.normalLayer),
            ("heightLayer", lambda material: material.heightLayer),
            ("lightMapLayer", lambda material: material.lightMapLayer),
            (
                "ambientOcclussionLayer",
                lambda material: material.ambientOcclussionLayer,
            ),
            ("normalBlendMask1", lambda material: material.normalBlendMask1),
            ("normalBlendMask2", lambda material: material.normalBlendMask2),
            ("normalBlendNormal1", lambda material: material.normalBlendNormal1),
            ("normalBlendNormal2", lambda material: material.normalBlendNormal2),
        ),
    ),
    (
        "displacementMaterials",
        lambda model: model.displacementMaterials,
        (
            ("normalLayer", lambda material: material.normalLayer),
            ("strengthLayer", lambda material: material.strengthLayer),
        ),
    ),
    (
        "terrainMaterials",
        lambda model: model.terrainMaterials,
        (("terrainLayer", lambda material: material.terrainLayer),),
    ),
    (
        "volumeMaterials",
        lambda model: model.volumeMaterials,
        (
            ("colorDefiningLayer", lambda material: material.colorDefiningLayer),
            ("unknownLayer1", lambda material: material.unknownLayer1),
            ("unknownLayer2", lambda material: material.unknownLayer2),
        ),
    ),
    (
        "creepMaterials",
        lambda model: model.creepMaterials,
        (("creepLayer", lambda material: material.creepLayer),),
    ),
    (
        "volumeNoiseMaterials",
        lambda model: model.volumeNoiseMaterials,
        (
            ("colorLayer", lambda material: material.colorLayer),
            ("noise1Layer", lambda material: material.noise1Layer),
            ("noise2Layer", lambda material: material.noise2Layer),
        ),
    ),
    (
        "splatTerrainBakeMaterials",
        lambda model: model.splatTerrainBakeMaterials,
        (
            ("diffuseLayer", lambda material: material.diffuseLayer),
            ("normalLayer", lambda material: material.normalLayer),
            ("specularLayer", lambda material: material.specularLayer),
        ),
    ),
    (
        "reflectionMaterial",
        lambda model: model.reflectionMaterial,
        (
            ("normalLayer", lambda material: material.normalLayer),
            ("strengthLayer", lambda material: material.strengthLayer),
            ("blurLayer", lambda material: material.blurLayer),
        ),
    ),
    (
        "lensFlareMaterial",
        lambda model: model.lensFlareMaterial,
        (
            ("colorLayer", lambda material: material.colorLayer),
            ("unknownLayer1", lambda material: material.unknownLayer1),
        ),
    ),
)


def _slots(model) -> Iterator[tuple[str, int, str, object]]:
    """Every filled layer of every material: (material list, index, slot, layer)."""
    for name, materials_of, slots in MATERIAL_LISTS:
        if not model.structureDescription.hasField(name):
            continue
        for index, material in enumerate(materials_of(model) or []):
            for slot, layers_of in slots:
                if not material.structureDescription.hasField(slot):
                    continue
                for layer in layers_of(material) or []:
                    yield name, index, slot, layer


def load(path: Path):
    try:
        return m3.loadModel(str(path))
    except Exception as error:  # the vendored reader raises plain Exception
        raise ModelError(f"{path.name}: {error}") from error


def flip_grids(model) -> dict[tuple[str, int], tuple[int, int] | None]:
    """(material list, index) -> the cells of the flip book the particle systems draw from it.

    A flip book layer does not hold its cells. The particle system that
    draws the material does. None: two systems name different cells.
    """
    references = model.materialReferences or []
    found: dict[tuple[str, int], set[tuple[int, int]]] = {}
    for system in model.particles or []:
        index = system.materialReferenceIndex
        if (
            not 0 <= index < len(references)
            or references[index].materialType != STANDARD_TYPE
        ):
            continue
        cells = (max(1, system.numberOfColumns), max(1, system.numberOfRows))
        found.setdefault((STANDARD_LIST, references[index].materialIndex), set()).add(
            cells
        )
    return {
        key: next(iter(cells)) if len(cells) == 1 else None
        for key, cells in found.items()
    }


def _animated(reference) -> bool:
    """An animation reference that names an animation: `animFlags` holds 6 then (structures.xml)."""
    return reference.header.animFlags & ANIMATED == ANIMATED


def _uvs(model) -> dict[int, np.ndarray]:
    """Source -> the texture coordinates of every vertex, as stored (int16 pairs). Only the sources the vertices hold."""
    if not model.structureDescription.hasField("vertices") or not model.vertices:
        return {}
    name = f"VertexFormat{hex(model.vFlags)}"
    if name not in m3.structures:
        return {}
    form = m3.structures[name].getVersion(0)
    raw = np.frombuffer(bytes(model.vertices), dtype=np.uint8)
    rows = raw[: len(raw) // form.size * form.size].reshape(-1, form.size)
    found, offset = {}, 0
    for field in form.fields:
        if field.name in UV_FIELDS:
            found[UV_FIELDS.index(field.name)] = rows[:, offset : offset + 4].copy().view("<i2").astype(np.float64)
        offset += field.size
    return found


def spanning(model) -> dict[tuple[int, int], tuple[int, int]]:
    """(material reference, UV source) -> (triangles that span a whole-number line of u or v, triangles), over the
    batches that draw the material. A triangle of no area in texture space shows nothing and counts for nothing."""
    uvs = _uvs(model)
    found: dict[tuple[int, int], tuple[int, int]] = {}
    if not uvs:
        return found
    references = model.materialReferences or []
    composites = model.compositeMaterials if model.structureDescription.hasField("compositeMaterials") else []

    def drawn(position: int) -> list[int]:
        """The material references a batch of this reference draws: it, or the sections of its composite."""
        reference = references[position]
        if reference.materialType != COMPOSITE_TYPE or not 0 <= reference.materialIndex < len(composites or []):
            return [position]
        return [section.materialReferenceIndex for section in composites[reference.materialIndex].sections or []]

    for division in model.divisions or []:
        faces = np.asarray(division.faces or [], dtype=np.int64)
        for batch in division.objects or []:
            region = division.regions[batch.regionIndex]
            # A region version without these fields stores plain coordinates: a multiplier of 16, no offset.
            fields = region.structureDescription
            scale = (region.uvwMult if fields.hasField("uvwMult") else 16.0) / 16 / 2048
            shift = region.uvwOffset if fields.hasField("uvwOffset") else 0.0
            start = region.firstFaceVertexIndexIndex
            corners = faces[start : start + region.numberOfFaceVertexIndices // 3 * 3] + region.firstVertexIndex
            if not len(corners):
                continue
            for source, stored in uvs.items():
                tri = (stored[corners] * scale + shift).reshape(-1, 3, 2)
                a, b, c = tri[:, 0], tri[:, 1], tri[:, 2]
                shows = np.abs((b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (c[:, 0] - a[:, 0]) * (b[:, 1] - a[:, 1])) > NO_AREA
                low, high = tri.min(axis=1), tri.max(axis=1)
                spans = int(((np.floor(high - SPAN_SLACK) > np.floor(low + SPAN_SLACK)).any(axis=1) & shows).sum())
                for one in drawn(batch.materialReferenceIndex):
                    before = found.get((one, source), (0, 0))
                    found[(one, source)] = (before[0] + spans, before[1] + int(shows.sum()))
    return found


def _references(model) -> dict[tuple[str, int], list[int]]:
    """(material list, index) -> the material references that name it."""
    found: dict[tuple[str, int], list[int]] = {}
    for position, reference in enumerate(model.materialReferences or []):
        name = MATERIAL_TYPES.get(reference.materialType)
        if name is not None:
            found.setdefault((name, reference.materialIndex), []).append(position)
    return found


def wraps(layer) -> bool:
    """Whether a layer's sampler wraps on an axis. One that wraps on none clamps: it shows the texture once,
    however its coordinates run."""
    return any(layer.getNamedBit("flags", bit) for bit in WRAP_BITS)


def moves(layer) -> bool:
    """Whether a layer repeats its texture by itself: it wraps, and its tiling is above 1 or animated, or its
    offset is animated (it scrolls).

    Measured 2026-11-26 on battlecruiser_remastered.m3: WarpLine2_Orange and FireTile4 scroll; grad3 has a
    tiling of 3; BigWaves 2 by 5 and scrolls; the hull and the particle textures do neither.
    """
    if not wraps(layer) or not layer.structureDescription.hasField("uvTiling"):
        return False
    tiling = layer.uvTiling
    tiled = max(abs(tiling.initValue.x), abs(tiling.initValue.y)) > 1 + SPAN_SLACK
    return tiled or _animated(tiling) or _animated(layer.uvOffset)


def layers(model) -> list[Layer]:
    """The layers of a loaded model that name a texture."""
    found = []
    grids = flip_grids(model)
    spans = spanning(model)
    references = _references(model)
    for material, index, slot, layer in _slots(model):
        path = layer.imagePath or ""
        if not path:
            continue
        source = layer.uvSource if layer.structureDescription.hasField("uvSource") else 0
        counted = [spans.get((reference, source), (0, 0)) for reference in references.get((material, index), [])]
        # A layer that clamps shows no line it spans.
        spanned = sum(one[0] for one in counted) if wraps(layer) else 0
        found.append(
            Layer(
                material,
                index,
                slot,
                path,
                bool(layer.getNamedBit("flags", VIDEO_BIT)),
                bool(layer.getNamedBit("flags", FLIPBOOK_BIT)),
                all(layer.getNamedBit("flags", bit) for bit in WRAP_BITS),
                grids.get((material, index))
                if layer.getNamedBit("flags", FLIPBOOK_BIT)
                else None,
                moves(layer),
                spanned,
                sum(one[1] for one in counted),
            )
        )
    return found


def rewrite(source: Path, target: Path, paths: dict[str, str]) -> int:
    """Write a copy of `source` whose layers name `paths[old lower-case path]`. Returns the layers changed."""
    model = load(source)
    changed = 0
    for _material, _index, _slot, layer in _slots(model):
        new = paths.get((layer.imagePath or "").replace("/", "\\").lower())
        if new is not None:
            layer.imagePath = new
            changed += 1
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        m3.saveAndInvalidateModel(model, str(target))
    except Exception as error:
        raise ModelError(f"{target.name}: {error}") from error
    return changed
