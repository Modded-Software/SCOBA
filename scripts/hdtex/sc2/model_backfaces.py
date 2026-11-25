"""Give the solid surfaces of a model a back.

Operator 2026-11-20, on the psi destroyer: "find all culled / missing faces
... insides of pipes, under surfaces, etc.", then "texture from front of
face mirrored on back instead of solid color".

The game draws a triangle from its front only. Where a model is not closed,
or the camera is under or inside it, the eye meets the back of a surface and
sees through it. A third-person camera gets there; the stock top-down
camera never did, so the stock model leaves such faces out.

For every solid, one-sided mesh region this adds a second region: a copy of
its vertices with the normal turned around, and every triangle turned
around. A copied vertex keeps its texture coordinates, so the back shows the
texture of the front, seen mirrored. The back is lit as a surface that
faces the other way. A front face and its back face are never drawn for the
same eye, so they do not fight over depth.

The map ships the changed model at the game's own path, so the catalogs stay
as they are. The HD texture step copies it from there (hdtex.sc2.storage, the dataset's own layer).
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

from character_anim_assets import extract_model
from footfall.fx import clone
from project_root import project_root

ROOT = project_root()
sys.path.insert(0, str(ROOT / "scripts" / "vendor" / "m3addon"))

import m3

MARKER = ".model_backfaces"
# 3: the back shows the texture of the front, lit; 2: a dark gray texture;
# 1: a colour layer, which the game drew in the colour of the owner.
MARKER_VERSION = "3\n"

# (CASC entry, target in the map: the game path of the same model).
MODELS = (
    (
        r"mods\liberty.sc2mod\base.sc2assets\assets\doodads\psidisintegratordoodad\psidisintegratordoodad.m3",
        Path("Assets")
        / "Doodads"
        / "PsiDisintegratorDoodad"
        / "PsiDisintegratorDoodad.m3",
    ),
)

# The material of the backs: that of the fronts, but it casts no shadow (a
# back lies in the plane of its front, and would shade it) and takes no click.
MATERIAL_SUFFIX = " ScobaBackFace"
STANDARD_TYPE = 1  # MATM materialType of a standard material
BLEND_OPAQUE = 0
TWO_SIDED = 0x8
NO_SHADOWS_CAST = 0x20
NO_HIT_TEST = 0x40
WELD = 4  # decimals: vertices this close are one point when edges are counted

# Copies `count` vertices from `first` on with their normals turned; returns the index of the first copy.
CopyVertices = Callable[[object, int, int], int]


class Found(NamedTuple):
    """What one region leaves open."""

    region: int
    triangles: int
    open_edges: int  # edges with one triangle only: the rim of a hole
    parts: int  # connected pieces of the mesh
    open_parts: int  # pieces with such a rim


def solid_regions(model) -> list[tuple[int, int]]:
    """(division, region) of every region drawn solid and from one side."""
    found = []
    for d, division in enumerate(model.divisions):
        for obj in division.objects:
            reference = model.materialReferences[obj.materialReferenceIndex]
            if reference.materialType != STANDARD_TYPE:
                continue
            material = model.standardMaterials[reference.materialIndex]
            if material.blendMode == BLEND_OPAQUE and not material.flags & TWO_SIDED:
                found.append((d, obj.regionIndex))
    return sorted(set(found))


def triangles(division, region) -> list[tuple[int, int, int]]:
    """The triangles of a region, as vertex indices inside the region."""
    faces = division.faces
    start = region.firstFaceVertexIndexIndex
    return [
        (faces[k], faces[k + 1], faces[k + 2])
        for k in range(start, start + region.numberOfFaceVertexIndices, 3)
    ]


def vertex_format(model):
    return m3.structures["VertexFormat" + hex(model.vFlags)].getVersion(0)


def positions(model) -> list[tuple[float, float, float]]:
    description = vertex_format(model)
    vertices = description.createInstances(
        buffer=model.vertices, count=len(model.vertices) // description.size
    )
    return [
        (
            round(v.position.x, WELD),
            round(v.position.y, WELD),
            round(v.position.z, WELD),
        )
        for v in vertices
    ]


def turn(vertex) -> None:
    """Make a vertex face the other way.

    The normal is negated. The tangent stays: the texture runs the same way
    across the surface. The third axis of the normal map is sign x (normal
    cross tangent), so the sign is negated to keep it where it was.
    """
    normal = vertex.normal
    normal.x, normal.y, normal.z = -normal.x, -normal.y, -normal.z
    vertex.sign = -vertex.sign


def copy_turned(model, first: int, count: int) -> int:
    """Append turned copies of `count` vertices from `first` on. Returns the index of the first copy."""
    description = vertex_format(model)
    size = description.size
    copies = description.createInstances(
        buffer=bytes(model.vertices[first * size : (first + count) * size]), count=count
    )
    for vertex in copies:
        turn(vertex)
    start = len(model.vertices) // size
    model.vertices = bytearray(model.vertices) + description.instancesToBytes(copies)
    return start


def survey(
    points: list[tuple[float, float, float]],
    first: int,
    tris: list[tuple[int, int, int]],
    region: int,
) -> Found:
    """Count the open edges of a region and the pieces that have one."""
    parent: dict[tuple, tuple] = {}

    def root(p: tuple) -> tuple:
        while parent.setdefault(p, p) != p:
            parent[p] = parent[parent[p]]
            p = parent[p]
        return p

    edges: Counter = Counter()
    for tri in tris:
        a, b, c = (points[first + i] for i in tri)
        for u, v in ((a, b), (b, c), (c, a)):
            if u != v:
                edges[(u, v) if u < v else (v, u)] += 1
                parent[root(u)] = root(v)
    rims = [edge for edge, count in edges.items() if count == 1]
    return Found(
        region,
        len(tris),
        len(rims),
        len({root(p) for p in parent}),
        len({root(u) for u, _v in rims}),
    )


def back_reference(model, front: int) -> int:
    """The index of a material reference for the backs of material reference `front`: the same look, no shadow, no click."""
    material = clone(
        model.standardMaterials[model.materialReferences[front].materialIndex]
    )
    material.name = material.name + MATERIAL_SUFFIX
    material.flags |= NO_SHADOWS_CAST | NO_HIT_TEST
    model.standardMaterials.append(material)
    reference = clone(model.materialReferences[front])
    reference.materialIndex = len(model.standardMaterials) - 1
    model.materialReferences.append(reference)
    return len(model.materialReferences) - 1


def add_back_faces(
    model,
    points: list[tuple[float, float, float]],
    copy_vertices: CopyVertices = copy_turned,
) -> list[Found]:
    """Give every solid one-sided region a turned copy. Returns what was open.

    `points` holds the position of every vertex of the model (positions).
    """
    if any(
        material.name.endswith(MATERIAL_SUFFIX) for material in model.standardMaterials
    ):
        raise ValueError("the model already has back faces")
    regions = solid_regions(model)
    if not regions:
        raise ValueError("the model has no solid one-sided region")
    references: dict[int, int] = {}
    found = []
    for d, r in regions:
        division = model.divisions[d]
        source = division.regions[r]
        front = next(o for o in division.objects if o.regionIndex == r)
        if front.materialReferenceIndex not in references:
            references[front.materialReferenceIndex] = back_reference(
                model, front.materialReferenceIndex
            )
        tris = triangles(division, source)
        found.append(survey(points, source.firstVertexIndex, tris, r))
        back = clone(source)
        back.firstVertexIndex = copy_vertices(
            model, source.firstVertexIndex, source.numberOfVertices
        )
        back.firstFaceVertexIndexIndex = len(division.faces)
        back.numberOfFaceVertexIndices = 3 * len(tris)
        for a, b, c in tris:
            division.faces.extend((a, c, b))
        division.regions.append(back)
        obj = clone(front)
        obj.regionIndex = len(division.regions) - 1
        obj.materialReferenceIndex = references[front.materialReferenceIndex]
        division.objects.append(obj)
    return found


def generate_model(source: Path, target: Path) -> list[Found]:
    model = m3.loadModel(str(source))
    found = add_back_faces(model, positions(model))
    for item in found:
        print(
            f"{target.name}: region {item.region}: {item.triangles} triangles in {item.parts} pieces; "
            f"{item.open_parts} pieces are open, {item.open_edges} open edges; {item.triangles} back faces added"
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    m3.saveAndInvalidateModel(model, str(target))
    return found


def generate(root: Path, force: bool) -> None:
    marker = root / MARKER
    if marker.exists() and not force and marker.read_text() == MARKER_VERSION:
        return
    temp_root = Path(tempfile.mkdtemp(prefix="backfaces-", dir=root.parent))
    try:
        for entry, target in MODELS:
            generate_model(extract_model(entry, temp_root), root / target)
        marker.write_text(MARKER_VERSION)
    finally:
        shutil.rmtree(temp_root)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    generate(args.map.resolve(), args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
