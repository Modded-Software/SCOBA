"""Whether an SC2 model texture tiles (m3tex.spanning, m3tex.moves, modelindex.repeating)."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

import numpy as np

from hdtex.sc2 import m3tex
from hdtex.sc2.modelindex import repeating

FLAGS = 0x182007D  # a vertex format of the game: position, weights, normal, uv0, tangent
STANDARD, COMPOSITE = 1, 3


def fields(*names: str) -> SimpleNamespace:
    """A structure description that has the named fields (the vendored reader's `hasField`)."""
    return SimpleNamespace(hasField=lambda name: name in names)


def vertices(uvs: list[tuple[int, int]]) -> bytearray:
    """Vertices of the format FLAGS, zero but their stored uv0."""
    form = m3tex.m3.structures[f"VertexFormat{hex(FLAGS)}"].getVersion(0)
    offset = 0
    for field in form.fields:
        if field.name == "uv0":
            break
        offset += field.size
    rows = np.zeros((len(uvs), form.size), dtype=np.uint8)
    rows[:, offset : offset + 4] = np.asarray(uvs, dtype="<i2").view(np.uint8).reshape(len(uvs), 4)
    return bytearray(rows.tobytes())


def region(first: int, mult: float = 16.0) -> SimpleNamespace:
    """One triangle: vertices first to first + 2, faces 3 * (first // 3) on."""
    return SimpleNamespace(
        firstVertexIndex=first, firstFaceVertexIndexIndex=first, numberOfFaceVertexIndices=3, uvwMult=mult, uvwOffset=0.0,
        structureDescription=fields("uvwMult", "uvwOffset"),  # a region of version 5 or later
    )  # fmt: skip


def model(uvs: list[tuple[int, int]], regions: list[SimpleNamespace], batches: list[tuple[int, int]], references: list[tuple[int, int]], composites=()) -> SimpleNamespace:
    return SimpleNamespace(
        structureDescription=fields("vertices", "compositeMaterials"),
        vFlags=FLAGS,
        vertices=vertices(uvs),
        divisions=[SimpleNamespace(
            faces=[0, 1, 2] * len(regions),
            regions=regions,
            objects=[SimpleNamespace(regionIndex=r, materialReferenceIndex=m) for r, m in batches],
        )],
        materialReferences=[SimpleNamespace(materialType=t, materialIndex=i) for t, i in references],
        compositeMaterials=[SimpleNamespace(sections=[SimpleNamespace(materialReferenceIndex=s) for s in one]) for one in composites],
    )  # fmt: skip


def stored(u: float, v: float, mult: float = 16.0) -> tuple[int, int]:
    """A texture coordinate as a region of that scale stores it."""
    return round(u * 2048 * 16 / mult), round(v * 2048 * 16 / mult)


def animation(x: float = 1.0, y: float = 1.0, flags: int = 8) -> SimpleNamespace:
    return SimpleNamespace(initValue=SimpleNamespace(x=x, y=y), header=SimpleNamespace(animFlags=flags))


def layer(tiling=None, offset=None, wraps: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        structureDescription=fields("uvTiling"), uvTiling=tiling or animation(), uvOffset=offset or animation(0.0, 0.0),
        getNamedBit=lambda field, bit: field == "flags" and bit in m3tex.WRAP_BITS and wraps,
    )  # fmt: skip


INSIDE = [stored(0.1, 0.1), stored(0.9, 0.1), stored(0.5, 0.9)]
ACROSS = [stored(0.5, 0.5), stored(1.5, 0.5), stored(1.0, 0.9)]


class SpanningTest(unittest.TestCase):
    def test_a_triangle_across_a_whole_number_line_counts_for_its_material_and_one_inside_does_not(self) -> None:
        found = m3tex.spanning(model(INSIDE + ACROSS, [region(0), region(3)], [(0, 0), (1, 1)], [(STANDARD, 0), (STANDARD, 1)]))
        self.assertEqual(found, {(0, 0): (0, 1), (1, 0): (1, 1)})

    def test_a_triangle_that_reaches_past_a_line_by_less_than_the_slack_does_not_span_it(self) -> None:
        edge = [stored(0.005, 0.2), stored(0.014, 0.2), stored(0.01, 0.3)]
        past = [stored(0.95, 0.2), stored(1.01, 0.2), stored(0.97, 0.3)]
        found = m3tex.spanning(model(edge + past, [region(0), region(3)], [(0, 0), (1, 1)], [(STANDARD, 0), (STANDARD, 1)]))
        self.assertEqual(found, {(0, 0): (0, 1), (1, 0): (0, 1)})

    def test_a_triangle_of_no_area_counts_for_nothing(self) -> None:
        line = [stored(0.5, 0.5), stored(1.5, 0.5), stored(0.5, 0.5)]
        self.assertEqual(m3tex.spanning(model(line, [region(0)], [(0, 0)], [(STANDARD, 0)])), {(0, 0): (0, 0)})

    def test_the_regions_scale_applies(self) -> None:
        # Stored 600 to 1400: 0.29 to 0.68 at the scale 16, 0.59 to 1.37 at 32.
        uvs = [(600, 600), (1400, 600), (1000, 700)]
        self.assertEqual(m3tex.spanning(model(uvs, [region(0, 16.0)], [(0, 0)], [(STANDARD, 0)])), {(0, 0): (0, 1)})
        self.assertEqual(m3tex.spanning(model(uvs, [region(0, 32.0)], [(0, 0)], [(STANDARD, 0)])), {(0, 0): (1, 1)})

    def test_a_composite_batch_counts_for_the_materials_of_its_sections(self) -> None:
        found = m3tex.spanning(model(ACROSS, [region(0)], [(0, 2)], [(STANDARD, 0), (STANDARD, 1), (COMPOSITE, 0)], composites=[[1]]))
        # Negative: the standard material no section names counts nothing.
        self.assertEqual(found, {(1, 0): (1, 1)})


class MovesTest(unittest.TestCase):
    def test_a_layer_repeats_by_itself_when_it_scrolls_or_tiles_and_wraps(self) -> None:
        self.assertEqual(
            [
                m3tex.moves(layer()),
                m3tex.moves(layer(offset=animation(0.0, 0.0, flags=14))),
                m3tex.moves(layer(tiling=animation(1.0, 1.0, flags=14))),
                m3tex.moves(layer(tiling=animation(2.0, 1.0))),
                m3tex.moves(layer(tiling=animation(1.01, 1.0))),
                m3tex.moves(layer(tiling=animation(2.0, 1.0), offset=animation(0.0, 0.0, flags=14), wraps=False)),
            ],
            # Negative: still and 1 to 1; a tiling within the slack of 1; a layer that clamps, however it runs.
            [False, True, True, True, False, False],
        )


class TextureTest(unittest.TestCase):
    """modelindex.repeating: over every layer of every model file that names the texture."""

    @staticmethod
    def one(moves: bool = False, spans: int = 0, triangles: int = 0) -> m3tex.Layer:
        return m3tex.Layer("standardMaterials", 0, "diffuseLayer", "a.dds", False, False, True, None, moves, spans, triangles)

    def test_a_texture_tiles_at_the_share_of_spanning_triangles_or_when_a_layer_moves(self) -> None:
        share = int(m3tex.TILE_SHARE * 1000)
        self.assertEqual(
            [
                repeating([self.one(spans=share, triangles=1000)]),
                repeating([self.one(spans=share - 1, triangles=1000)]),
                # thorbirth's 3 of 4152 stray triangles beside thorex1, which spans none: not tiled.
                repeating([self.one(spans=3, triangles=4152), self.one(triangles=5938)]),
                repeating([self.one(moves=True), self.one(triangles=5938)]),
                repeating([self.one()]),
            ],
            [True, False, False, True, False],
        )


if __name__ == "__main__":
    unittest.main()
