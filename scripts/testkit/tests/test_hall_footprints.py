"""Hall footprints (R-FP-10, R-BASE-30): mapgen/footprints/hall.py."""

from __future__ import annotations

import math
import re
import tempfile
import unittest
from pathlib import Path

from mapgen.footprints.build import apply_scaled_footprints, check_scaled_footprints
from mapgen.footprints.hall import (
    actor_scale,
    hall_angle,
    hall_cells,
    hall_footprint_id,
    hall_footprint_xml,
    hall_polygons,
    hall_scale,
    hall_shape,
    hall_sub_rows,
)
from mapgen.footprints.slices import load_slices

from testkit.tests.test_scaled_footprints import DATA, make_map


def blocked(cells: tuple[str, ...]) -> set[tuple[int, int]]:
    h = len(cells) // 2
    return {(i - h, h - k) for k, row in enumerate(cells) for i, c in enumerate(row) if c == "x"}


class ActorScaleTests(unittest.TestCase):
    def test_reads_the_x_scale(self) -> None:
        text = '<CActorUnit id="CommandCenter">\n<Scale value="3.600000,3.600000,4.200000"/>\n</CActorUnit>'
        self.assertEqual(actor_scale(text, "CommandCenter"), 3.6)

    def test_no_entry_or_no_scale_is_one(self) -> None:
        self.assertEqual(actor_scale("<Catalog/>", "CommandCenter"), 1.0)
        self.assertEqual(actor_scale('<CActorUnit id="CommandCenter"><On/></CActorUnit>', "CommandCenter"), 1.0)

    def test_uneven_xy_scale_fails(self) -> None:
        with self.assertRaises(ValueError):
            actor_scale('<CActorUnit id="CommandCenter"><Scale value="3,2,1"/></CActorUnit>', "CommandCenter")


class HallScaleTests(unittest.TestCase):
    """Drawn scale = actor Scale x ModelData ScaleMax (the CC model is 0.8)."""

    ACTOR = '<CActorUnit id="CommandCenter"><Scale value="3.6,3.6,4.2"/></CActorUnit>'

    def test_actor_times_model(self) -> None:
        data = {"model_scale": {"CommandCenter": [0.8, 0.8, 0.8]}}
        self.assertAlmostEqual(hall_scale(data, self.ACTOR, "CommandCenter", "CommandCenter"), 2.88)

    def test_committed_model_scale_is_the_stock_0_8(self) -> None:
        self.assertEqual(load_slices()["model_scale"]["CommandCenter"], [0.8, 0.8, 0.8])

    def test_missing_or_uneven_model_scale_fails(self) -> None:
        with self.assertRaises(ValueError):
            hall_scale({}, self.ACTOR, "CommandCenter", "CommandCenter")
        with self.assertRaises(ValueError):
            hall_scale({"model_scale": {"CommandCenter": [1, 2, 1]}}, self.ACTOR, "CommandCenter", "CommandCenter")


class SyntheticHallTests(unittest.TestCase):
    def test_four_legs_and_an_open_middle(self) -> None:
        cells = hall_cells(DATA, "CommandCenter", 1.0, 0.0)
        self.assertEqual(len(cells) % 2, 1)
        got = blocked(cells)
        for sx in (1, -1):
            for sy in (1, -1):
                self.assertIn((3 * sx, 3 * sy), got)
        # Negative: nothing in the middle, nothing on the axes between the legs.
        for i in range(-1, 2):
            for j in range(-1, 2):
                self.assertNotIn((i, j), got)
        self.assertNotIn((0, 3), got)
        self.assertNotIn((3, 0), got)

    def test_xml_area_puts_the_origin_on_a_cell_centre(self) -> None:
        hall = hall_shape(DATA, "CommandCenter", 1.0)
        cells = hall.cells
        h = len(cells) // 2
        xml = hall_footprint_xml(hall)
        self.assertEqual(xml.count(f'Area="{-h},{-h},{h + 1},{h + 1}"'), 2)
        self.assertEqual(xml.count(f'<Rows value="{cells[0]}"/>'), 2 * cells.count(cells[0]))
        self.assertIn(f'id="{hall_footprint_id(hall)}"', xml)
        # The Shape blocks unit pathing (Place cells alone do not): one closed
        # loop per leg, every point an edge start.
        polygons = hall_polygons(hall.sub)
        self.assertEqual(len(polygons), 4)
        offsets = re.search(r'<Offsets value="([^"]+)"/>', xml).group(1).split(";")
        borders = re.search(r'<Borders value="([^"]+)"/>', xml).group(1).split(";")
        self.assertEqual(len(offsets), sum(len(p) for p in polygons))
        self.assertEqual(sorted(int(b.split(",")[0]) for b in borders), list(range(len(offsets))))

    def test_build_links_the_cc_and_the_check_catches_a_missing_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_map(Path(tmp))
            apply_scaled_footprints(root, DATA)
            game = root / "Base.SC2Data" / "GameData"
            units = (game / "UnitData.xml").read_text(encoding="utf-8")
            want = hall_footprint_id(hall_shape(DATA, "CommandCenter", 1.0))
            self.assertRegex(units, r'<CUnit id="CommandCenter">\s*<Footprint value="' + want + '"/>')
            self.assertIn(f'<CFootprint id="{want}">', (game / "FootprintData.xml").read_text(encoding="utf-8"))
            self.assertEqual(check_scaled_footprints(root, DATA), [])
            # Negative: the link back to the 1x1 is flagged.
            (game / "UnitData.xml").write_text(units.replace(want, "FootprintSCOBAHall1x1"), encoding="utf-8")
            self.assertTrue(any("CommandCenter has no measured hall footprint" in p for p in check_scaled_footprints(root, DATA)))


class MeasuredHallTests(unittest.TestCase):
    """The committed slices of CommandCenterEx1.m3 at the drawn scale 2.88
    (actor 3.6 x model 0.8). Foot bones at ±1.6 model units: ±4.6.
    """

    def test_unturned_legs_at_about_five_and_the_middle_open(self) -> None:
        got = blocked(hall_cells(load_slices(), "CommandCenter", 2.88, 0.0))
        for sx in (1, -1):
            for sy in (1, -1):
                self.assertIn((5 * sx, 5 * sy), got)
        # Negative: the middle is open, and nothing at the actor-only
        # leg centres (±6, ±6) beyond the drawn legs.
        for i in range(-2, 3):
            for j in range(-2, 3):
                self.assertNotIn((i, j), got)
        for sx in (1, -1):
            for sy in (1, -1):
                self.assertNotIn((7 * sx, 7 * sy), got)
        # Open from east and west between the legs.
        for j in range(-2, 3):
            self.assertNotIn((6, j), got)
            self.assertNotIn((-6, j), got)
        # Negative: no bar between the feet at y ±3 (body triangles and a
        # fill across feet once blocked x -2..2 there).
        for i in range(-2, 3):
            self.assertNotIn((i, 3), got)
            self.assertNotIn((i, -3), got)

    def test_shape_follows_the_half_grid_not_whole_cells(self) -> None:
        # As trees: the Shape is the 0.5 outline. Four feet, each within its
        # pad's vertex box (x and y 2.56..6.65 at 2.88), none in the middle.
        sub = hall_sub_rows(load_slices(), "CommandCenter", 2.88, 0.0)
        self.assertEqual(len(sub) % 2, 0)
        polygons = hall_polygons(sub)
        self.assertEqual(len(polygons), 4)
        for polygon in polygons:
            for x, y in polygon:
                self.assertTrue(2.5 <= abs(x) <= 7.0 and 2.5 <= abs(y) <= 7.0, (x, y))
        # Negative: a point off the whole-cell grid exists (not 1x1 squares).
        self.assertTrue(any(x % 1 or y % 1 for polygon in polygons for x, y in polygon))

    def test_feet_are_turned_by_the_unit_facing(self) -> None:
        # CC facing 225 in game, model drawn as authored at 270: turned -45 degrees.
        # Foot bones at (±1.6, ±1.6) x 2.88 land on the axes at 6.5
        # (operator 2026-11-19: the unturned feet sat 45 degrees off).
        self.assertAlmostEqual(math.degrees(hall_angle("CommandCenter")), -45.0)
        sub = hall_sub_rows(load_slices(), "CommandCenter", 2.88)
        polygons = hall_polygons(sub)
        self.assertEqual(len(polygons), 4)
        centres = sorted((round(sum(x for x, _ in q) / len(q)), round(sum(y for _, y in q) / len(q))) for q in polygons)
        self.assertEqual(centres, [(-6, 0), (0, -6), (0, 6), (6, 0)])
        for polygon in polygons:
            for x, y in polygon:
                self.assertTrue(4.5 <= max(abs(x), abs(y)) <= 8.5 and min(abs(x), abs(y)) <= 2.0, (x, y))
        # Negative: nothing at the unturned leg centres or in the middle.
        got = blocked(hall_cells(load_slices(), "CommandCenter", 2.88))
        for sx in (1, -1):
            for sy in (1, -1):
                self.assertNotIn((5 * sx, 5 * sy), got)
        for i in range(-3, 4):
            for j in range(-3, 4):
                self.assertNotIn((i, j), got)

    def test_slices_are_per_foot_bone(self) -> None:
        parts = load_slices()["models"]["CommandCenter"]
        self.assertEqual(sorted(parts), [f"Bldg_Terran_CommandCenter_Foot_0{k}" for k in range(1, 5)])


if __name__ == "__main__":
    unittest.main()

