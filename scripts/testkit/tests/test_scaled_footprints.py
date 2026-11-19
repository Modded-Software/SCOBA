from __future__ import annotations

import math
import re
import tempfile
import unittest
from pathlib import Path

from unittest import mock

import numpy as np

from mapgen.footprints import config
from mapgen.footprints.build import apply_scaled_footprints, check_scaled_footprints
from mapgen.footprints.blocker import build_blocker
from mapgen.footprints.catalog import tree_actor_id
from mapgen.footprints.config import MARKER, REPORT
from mapgen.footprints.raster import close_pinches, trace
from mapgen.footprints.slices import engine_quarter_turns, feet_slices, residual_rotation, segments_world

STEP = 0.0025
COUNT = 80


def rect(x0: float, y0: float, x1: float, y1: float) -> list[list[float]]:
    return [[x0, y0, x1, y0], [x1, y0, x1, y1], [x1, y1, x0, y1], [x0, y1, x0, y0]]


def ell() -> list[list[float]]:
    """L outline: arm along +x (y 0..0.1, x 0..0.4) and arm along +y (x 0..0.1, y 0..0.4)."""
    pts = [(0, 0), (0.4, 0), (0.4, 0.1), (0.1, 0.1), (0.1, 0.4), (0, 0.4)]
    return [[*pts[i], *pts[(i + 1) % len(pts)]] for i in range(len(pts))]


SQUARE = rect(-0.25, -0.25, 0.25, 0.25)  # 0.5 model units wide
THIN = rect(-0.02, -0.02, 0.02, 0.02)
DATA = {
    "slice_step": STEP,
    "slice_count": COUNT,
    "models": {
        "ZerusTree": {str(v): [SQUARE] * COUNT for v in range(15)} | {"1": [ell()] * COUNT, "3": [THIN] * COUNT},
        "SporeCannon": {"0": [rect(-1, -1, 1, 1)] * COUNT},
        "SporeCrawler": {"0": [rect(-0.5, -0.5, 0.5, 0.5)] * COUNT},
    },
}

OBJECTS = """<?xml version="1.0" encoding="utf-8"?>
<PlacedObjects Version="27">
    <ObjectUnit Id="1" Position="10,10,0" Rotation="0.7851" Scale="3,3,3" UnitType="SporeCannon" Player="8"/>
    <ObjectUnit Id="2" Position="20,20,0" Rotation="2.1" Scale="3,3,3" UnitType="SporeCrawler" Player="8"/>
    <ObjectUnit Id="3" Position="30,30,0" Scale="1,1,1" UnitType="Marine" Player="1"/>
    <ObjectDoodad Id="4" Variation="1" Position="101.3,67.6,7" Rotation="1.5708" Scale="8.0000,8.0000,8.0000" Type="ZerusTree">
        <Flag Index="HeightOffset" Value="1"/>
    </ObjectDoodad>
    <ObjectDoodad Id="5" Position="40.4,51.6,3" Scale="4,4,4" Type="ZerusTree"/>
    <ObjectDoodad Id="6" Variation="3" Position="12,12,3" Scale="2,2,2" Type="ZerusTree"/>
    <ObjectDoodad Id="7" Variation="1" Position="50,50,3" Rotation="0" Scale="8,8,8" Type="ZerusTree"/>
    <ObjectDoodad Id="8" Position="9,9,0" Scale="1,1,1" Type="Waterfall"/>
</PlacedObjects>
"""

UNITS = """<?xml version="1.0" encoding="us-ascii"?>
<Catalog>
    <CUnit id="SporeCannon">
        <LifeMax value="6000"/>
        <Footprint value="Footprint5x5Contour"/>
    </CUnit>
</Catalog>
"""

ACTORS = """<?xml version="1.0" encoding="us-ascii"?>
<Catalog>
    <CActorDoodad id="ZerusTree">
        <RandomScaleRange value="4.000000,6.000000"/>
    </CActorDoodad>
</Catalog>
"""

PRELOAD = """<Preload>
<Actor id="ZerusTree" Variations="0,1,2"/>
<Model id="AiurSkybox"/>
</Preload>
"""


def make_map(root: Path) -> Path:
    game = root / "Base.SC2Data" / "GameData"
    game.mkdir(parents=True)
    (root / "Objects").write_text(OBJECTS, encoding="utf-8")
    (game / "UnitData.xml").write_text(UNITS, encoding="utf-8")
    (game / "ActorData.xml").write_text(ACTORS, encoding="utf-8")
    (root / "Preload.xml").write_text(PRELOAD, encoding="utf-8")
    return root


def blocker_for(segments: list[list[float]], scale: float, angle: float = 0.0):
    outline = segments_world(segments, scale, angle)
    return build_blocker("t", [outline])


class RotationTests(unittest.TestCase):
    def test_quarter_turns_match_probe(self) -> None:
        # fprot runs 20261115-132159 and 20261115-132312.
        for degrees, want in ((0, 0), (30, 0), (45, 0), (60, 1), (90, 1), (100, 1), (135, 1),
                              (180, 2), (225, 2), (270, 3), (315, 3), (359, 0)):
            self.assertEqual(engine_quarter_turns(math.radians(degrees)), want, degrees)

    def test_residual_is_what_the_engine_leaves(self) -> None:
        for degrees in (0, 30, 45, 60, 135, 200, 300):
            r = math.radians(degrees)
            total = engine_quarter_turns(r) * 90 + math.degrees(residual_rotation(r))
            self.assertAlmostEqual(total % 360, degrees % 360, places=6)
            self.assertLessEqual(abs(math.degrees(residual_rotation(r))), 45 + 1e-6)


class FeetSliceTests(unittest.TestCase):
    def test_slices_scale_down_with_scale(self) -> None:
        low = feet_slices(DATA, 8.0)
        high = feet_slices(DATA, 2.0)
        self.assertLess(max(low), max(high))
        self.assertTrue(all(0 <= i < COUNT for i in low + high))


class TraceTests(unittest.TestCase):
    def test_square_is_clockwise_four_corners(self) -> None:
        mask = np.ones((2, 2), dtype=bool)
        poly = trace(mask, 0.0, 0.0)
        self.assertEqual(len(poly), 4)
        area = sum(poly[i - 1][0] * poly[i][1] - poly[i][0] * poly[i - 1][1] for i in range(4)) / 2
        self.assertLess(area, 0)  # clockwise, like the stock footprints and the probe shapes
        self.assertAlmostEqual(abs(area), 1.0)

    def test_concave_keeps_notch(self) -> None:
        mask = np.array([[1, 1, 1], [1, 0, 0], [1, 0, 0]], dtype=bool)
        self.assertEqual(len(trace(mask, 0.0, 0.0)), 6)

    def test_pinch_is_closed(self) -> None:
        mask = np.array([[1, 0], [0, 1]], dtype=bool)
        self.assertEqual(int(close_pinches(mask).sum()), 3)


class BlockerTests(unittest.TestCase):
    def test_square_trunk_fills_exactly(self) -> None:
        with mock.patch.object(config, "ERODE", 0.0):
            b = blocker_for(SQUARE, 4.0)  # 2 x 2 world
        self.assertAlmostEqual(b.fit.blocked_area, 4.0)
        self.assertGreater(b.fit.covered, 0.99)
        self.assertLess(b.fit.offset, 0.01)

    def test_square_trunk_is_eroded_by_unit_radius(self) -> None:
        # 2 x 2 world minus ERODE on each side is 1.25 wide: the inner 1 x 1 blocks.
        b = blocker_for(SQUARE, 4.0)
        self.assertAlmostEqual(b.fit.blocked_area, 1.0)
        # Negative case: nothing past the eroded edge.
        self.assertLessEqual(max(abs(v) for p in b.polygon for v in p), 0.5)

    def test_blocker_grows_with_scale(self) -> None:
        self.assertGreater(blocker_for(SQUARE, 8.0).fit.blocked_area, blocker_for(SQUARE, 4.0).fit.blocked_area * 3.5)

    def test_partial_cells_below_coverage_stay_open(self) -> None:
        # 0.6 x 0.5 from the origin: the second sub-cell column is 20% mesh; it must not block.
        with mock.patch.object(config, "ERODE", 0.0):
            b = blocker_for(rect(0.0, 0.0, 0.6, 0.5), 1.0)
        self.assertAlmostEqual(b.fit.blocked_area, 0.25)

    def test_thin_trunk_still_blocks_one_cell(self) -> None:
        b = blocker_for(THIN, 2.0)
        self.assertAlmostEqual(b.fit.blocked_area, 1.0)

    def test_rotated_ell_differs(self) -> None:
        plain = blocker_for(ell(), 8.0, 0.0)
        turned = blocker_for(ell(), 8.0, math.pi / 4)
        self.assertNotEqual(plain.polygon, turned.polygon)
        # Negative case: the notch of the L is not blocked.
        self.assertLess(plain.fit.blocked_area, 0.55 * (3.2 * 3.2))

    def test_offset_mesh_gives_offset_blocker(self) -> None:
        b = blocker_for(rect(0.5, 0.5, 1.0, 1.0), 2.0)
        xs = [x for x, _ in b.polygon]
        self.assertGreaterEqual(min(xs), 1.0)


class ApplyTests(unittest.TestCase):
    def test_retypes_and_generates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_map(Path(tmp))
            self.assertTrue(apply_scaled_footprints(root, DATA))
            objects = (root / "Objects").read_text(encoding="utf-8")
            self.assertNotIn('Type="ZerusTree"', objects)
            self.assertIn('Type="Waterfall"', objects)
            # Positions are not snapped.
            self.assertIn('Position="101.3,67.6,7"', objects)
            types = dict(re.findall(r'Id="(\d+)"[^>]*Type="(ZerusTreeFp[0-9a-f]+)"', objects))
            self.assertEqual(len(types), 4)
            # Same L at 90 (engine turns it) and 0: same baked shape.
            self.assertEqual(types["4"], types["7"])
            game = root / "Base.SC2Data" / "GameData"
            footprints = (game / "FootprintData.xml").read_text(encoding="utf-8")
            for actor in set(types.values()):
                self.assertIn(f'<CActorDoodad id="{actor}" parent="ZerusTree">', (game / "ActorData.xml").read_text(encoding="utf-8"))
            # One per tree shape, plus the two spores.
            self.assertEqual(footprints.count("<CFootprint "), len(set(types.values())) + 2)
            units = (game / "UnitData.xml").read_text(encoding="utf-8")
            self.assertNotIn("Footprint5x5Contour", units)
            self.assertIn('<LifeMax value="6000"/>', units)
            self.assertRegex(units, r'<CUnit id="SporeCrawler">\s*<Footprint value="FootprintScoba[0-9a-f]+"/>')
            preload = (root / "Preload.xml").read_text(encoding="utf-8")
            self.assertIn(f'<Actor id="{types["5"]}" Variations="0,1,2"/>', preload)
            self.assertTrue((root / REPORT).exists())
            self.assertTrue((root / MARKER).exists())
            self.assertEqual(check_scaled_footprints(root, DATA), [])

    def test_second_run_is_a_no_op(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_map(Path(tmp))
            apply_scaled_footprints(root, DATA)
            path = root / "Base.SC2Data" / "GameData" / "FootprintData.xml"
            before = path.read_text(encoding="utf-8")
            self.assertFalse(apply_scaled_footprints(root, DATA))
            self.assertEqual(before, path.read_text(encoding="utf-8"))

    def test_check_flags_wrong_and_stock_footprints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_map(Path(tmp))
            apply_scaled_footprints(root, DATA)
            objects = root / "Objects"
            text = objects.read_text(encoding="utf-8")
            text = re.sub(r'(Id="5" [^>]*)Scale="4,4,4"', r'\1Scale="6,6,6"', text)
            text = text.replace('Type="Waterfall"', 'Type="ZerusTree"')
            objects.write_text(text, encoding="utf-8")
            problems = check_scaled_footprints(root, DATA)
            self.assertTrue(any("stock ZerusTree" in p for p in problems), problems)
            self.assertTrue(any("tree 5 footprint does not match" in p for p in problems), problems)

    def test_check_flags_stock_spore_footprint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_map(Path(tmp))
            apply_scaled_footprints(root, DATA)
            units = root / "Base.SC2Data" / "GameData" / "UnitData.xml"
            text = re.sub(r'(<CUnit id="SporeCannon">.*?)FootprintScoba[0-9a-f]+', r"\1Footprint5x5Contour", units.read_text(encoding="utf-8"), flags=re.S)
            units.write_text(text, encoding="utf-8")
            self.assertIn("SporeCannon has no generated footprint", check_scaled_footprints(root, DATA))

    def test_fails_without_trees(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_map(Path(tmp))
            (root / "Objects").write_text("<PlacedObjects/>", encoding="utf-8")
            with self.assertRaises(ValueError):
                apply_scaled_footprints(root, DATA)

    def test_actor_id_follows_polygon(self) -> None:
        poly = ((0.0, 0.0), (0.0, 1.0), (1.0, 1.0), (1.0, 0.0))
        self.assertTrue(tree_actor_id(poly).startswith("ZerusTreeFp"))
        self.assertNotEqual(tree_actor_id(poly), tree_actor_id(poly[::-1]))


if __name__ == "__main__":
    unittest.main()
