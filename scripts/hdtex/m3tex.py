"""The textures a model file names, and a copy of the model that names others.

A model keeps its texture paths in the layers of its materials. A layer
sits in a slot of a material, such as `diffuseLayer`. The slot says what
the texture means.
"""

from __future__ import annotations

import sys
from pathlib import Path
from collections.abc import Callable, Iterator
from typing import NamedTuple

from project_root import project_root

sys.path.insert(0, str(project_root() / "scripts" / "vendor" / "m3addon"))

import m3

VIDEO_BIT = "isVideo"
FLIPBOOK_BIT = "useParticleFlipBook"
WRAP_BITS = ("textureWrapX", "textureWrapY")
# A particle system names its material by a reference: a type and an index.
STANDARD_TYPE = 1
STANDARD_LIST = "standardMaterials"


class ModelError(RuntimeError):
    """The model file could not be read or written."""


class Layer(NamedTuple):
    material: str  # material list of the model, such as standardMaterials
    index: int  # position in that list
    slot: str  # field of the material, such as diffuseLayer
    path: str  # texture path as the model spells it
    video: bool
    flipbook: bool
    wrap: bool  # the layer repeats the texture on both axes
    # Flip book: (columns, rows) of its cells. None: no flip book, or the cells are not known.
    grid: tuple[int, int] | None = None


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
            ("ambientOcclussionLayer", lambda material: material.ambientOcclussionLayer),
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
        (
            ("terrainLayer", lambda material: material.terrainLayer),
        ),
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
        (
            ("creepLayer", lambda material: material.creepLayer),
        ),
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
        if not 0 <= index < len(references) or references[index].materialType != STANDARD_TYPE:
            continue
        cells = (max(1, system.numberOfColumns), max(1, system.numberOfRows))
        found.setdefault((STANDARD_LIST, references[index].materialIndex), set()).add(cells)
    return {key: next(iter(cells)) if len(cells) == 1 else None for key, cells in found.items()}


def layers(model) -> list[Layer]:
    """The layers of a loaded model that name a texture."""
    found = []
    grids = flip_grids(model)
    for material, index, slot, layer in _slots(model):
        path = layer.imagePath or ""
        if not path:
            continue
        found.append(
            Layer(
                material,
                index,
                slot,
                path,
                bool(layer.getNamedBit("flags", VIDEO_BIT)),
                bool(layer.getNamedBit("flags", FLIPBOOK_BIT)),
                all(layer.getNamedBit("flags", bit) for bit in WRAP_BITS),
                grids.get((material, index)) if layer.getNamedBit("flags", FLIPBOOK_BIT) else None,
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
