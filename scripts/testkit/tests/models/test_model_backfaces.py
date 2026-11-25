"""Host tests for scripts/hdtex/sc2/model_backfaces.py: which faces get a back, and what the back looks like."""

from __future__ import annotations

import unittest
from types import SimpleNamespace as Part

from hdtex.sc2 import model_backfaces as B

# A square of two triangles, and a closed tetrahedron beside it.
POINTS = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0), (5.0, 0.0, 0.0), (6.0, 0.0, 0.0), (5.0, 1.0, 0.0), (5.0, 0.0, 1.0)]
SQUARE = [(0, 1, 2), (0, 2, 3)]
SOLID = [(4, 6, 5), (4, 5, 7), (5, 6, 7), (6, 4, 7)]
COPIES_AT = 100  # where the stand-in for the vertex copy says the copies begin


def material(name: str, blend: int = 0, flags: int = 0x4000) -> Part:
    return Part(name=name, flags=flags, blendMode=blend, diffuseLayer=[Part(imagePath="Assets/Textures/Hull.dds")])


def region(first_face: int, count: int) -> Part:
    return Part(firstVertexIndex=0, numberOfVertices=len(POINTS), firstFaceVertexIndexIndex=first_face, numberOfFaceVertexIndices=count, rootBoneIndex=0)


def model() -> Part:
    """Region 0: the hull (solid). Region 1: glass (blended). Region 2: a two-sided sheet."""
    hull = [i for tri in SQUARE + SOLID for i in tri]
    faces = hull + [0, 1, 2] + [0, 2, 3]
    division = Part(
        faces=faces,
        regions=[region(0, len(hull)), region(len(hull), 3), region(len(hull) + 3, 3)],
        objects=[Part(regionIndex=0, materialReferenceIndex=0), Part(regionIndex=1, materialReferenceIndex=1), Part(regionIndex=2, materialReferenceIndex=2)],
    )
    return Part(
        divisions=[division],
        materialReferences=[Part(materialType=1, materialIndex=0), Part(materialType=1, materialIndex=1), Part(materialType=1, materialIndex=2)],
        standardMaterials=[material("hull"), material("glass", blend=1), material("sheet", flags=0x4000 | B.TWO_SIDED)],
    )


class SurveyTest(unittest.TestCase):
    def test_an_open_sheet_has_a_rim_and_a_closed_body_has_none(self) -> None:
        self.assertEqual(B.survey(POINTS, 0, SQUARE, 0), B.Found(0, 2, 4, 1, 1))
        self.assertEqual(B.survey(POINTS, 0, SOLID, 0), B.Found(0, 4, 0, 1, 0))

    def test_pieces_are_counted_apart(self) -> None:
        self.assertEqual(B.survey(POINTS, 0, SQUARE + SOLID, 3), B.Found(3, 6, 4, 2, 1))

    def test_vertices_at_one_point_are_one_point(self) -> None:
        # The same square with its second triangle on vertices of its own.
        points = [*POINTS[:4], POINTS[0], POINTS[2], POINTS[3]]
        self.assertEqual(B.survey(points, 0, [(0, 1, 2), (4, 5, 6)], 0).open_edges, 4)


class TurnTest(unittest.TestCase):
    def test_a_turned_vertex_faces_the_other_way_and_keeps_its_texture(self) -> None:
        vertex = Part(normal=Part(x=0.0, y=0.6, z=0.8), sign=1.0, tangent=Part(x=1.0, y=0.0, z=0.0), uv0=Part(x=3, y=4), position=Part(x=1.0, y=2.0, z=3.0))
        B.turn(vertex)
        self.assertEqual((vertex.normal.x, vertex.normal.y, vertex.normal.z), (0.0, -0.6, -0.8))
        # sign x (normal cross tangent) is the third axis of the normal map: it stays.
        self.assertEqual(vertex.sign, -1.0)
        # Negative: nothing else moves.
        self.assertEqual((vertex.tangent.x, vertex.uv0.x, vertex.uv0.y, vertex.position.z), (1.0, 3, 4, 3.0))


class BackFaceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.model = model()
        self.before = list(self.model.divisions[0].faces)
        self.copied: list[tuple[int, int]] = []

        def copy_vertices(_model, first: int, count: int) -> int:
            self.copied.append((first, count))
            return COPIES_AT

        self.copy = copy_vertices
        self.found = B.add_back_faces(self.model, POINTS, copy_vertices)
        self.division = self.model.divisions[0]

    def test_only_the_solid_one_sided_region_gets_backs(self) -> None:
        self.assertEqual([item.region for item in self.found], [0])
        self.assertEqual(len(self.division.regions), 4)
        self.assertEqual((self.division.objects[-1].regionIndex, self.division.objects[-1].materialReferenceIndex), (3, 3))

    def test_every_triangle_is_there_once_more_turned_around(self) -> None:
        back = self.division.regions[-1]
        faces = self.division.faces
        got = [tuple(faces[k : k + 3]) for k in range(back.firstFaceVertexIndexIndex, back.firstFaceVertexIndexIndex + back.numberOfFaceVertexIndices, 3)]
        self.assertEqual(got, [(a, c, b) for a, b, c in SQUARE + SOLID])

    def test_the_backs_stand_on_turned_copies_of_the_vertices(self) -> None:
        back = self.division.regions[-1]
        self.assertEqual(self.copied, [(0, len(POINTS))])
        self.assertEqual((back.firstVertexIndex, back.numberOfVertices), (COPIES_AT, len(POINTS)))
        # Negative: the fronts keep their own vertices.
        self.assertEqual(self.division.regions[0].firstVertexIndex, 0)

    def test_the_faces_the_model_had_are_untouched(self) -> None:
        self.assertEqual(self.division.faces[: len(self.before)], self.before)
        self.assertEqual(self.division.regions[0].numberOfFaceVertexIndices, 3 * len(SQUARE + SOLID))

    def test_the_back_shows_the_texture_of_the_front(self) -> None:
        reference = self.model.materialReferences[-1]
        back = self.model.standardMaterials[reference.materialIndex]
        self.assertEqual((reference.materialType, back.name, back.blendMode), (1, "hull" + B.MATERIAL_SUFFIX, 0))
        self.assertEqual(back.diffuseLayer[0].imagePath, "Assets/Textures/Hull.dds")
        self.assertTrue(back.flags & B.NO_SHADOWS_CAST)
        self.assertTrue(back.flags & B.NO_HIT_TEST)
        # Negative: it is not drawn from both sides, and it is lit (0x10 is unshaded).
        self.assertFalse(back.flags & B.TWO_SIDED)
        self.assertFalse(back.flags & 0x10)

    def test_the_material_of_the_front_keeps_its_flags(self) -> None:
        hull = self.model.standardMaterials[0]
        self.assertEqual((hull.name, hull.flags), ("hull", 0x4000))
        self.assertEqual(len(self.model.standardMaterials), 4)

    def test_a_second_run_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            B.add_back_faces(self.model, POINTS, self.copy)

    def test_a_model_without_a_solid_region_is_refused(self) -> None:
        glass = model()
        glass.standardMaterials[0].blendMode = 1
        with self.assertRaises(ValueError):
            B.add_back_faces(glass, POINTS, self.copy)


if __name__ == "__main__":
    unittest.main()
