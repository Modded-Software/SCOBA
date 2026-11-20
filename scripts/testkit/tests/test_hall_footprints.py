"""Hall footprints (R-FP-10, R-BASE-30): mapgen/footprints/hall.py."""

from __future__ import annotations

import math
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mapgen.footprints import config
from mapgen.footprints.build import apply_scaled_footprints, check_scaled_footprints
from mapgen.footprints.hall import (
    actor_scale,
    check_halls,
    hall_angle,
    hall_cells,
    hall_footprint_id,
    hall_footprint_xml,
    hall_footprints,
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

    @mock.patch.object(config, "HALL_FOOTPRINTS_ON", False)
    def test_switched_off_the_cc_keeps_the_footprint_of_the_map(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            map_dir = make_map(Path(tmp))
            game = map_dir / "Base.SC2Data" / "GameData"
            before = (game / "UnitData.xml").read_text(encoding="utf-8")
            apply_scaled_footprints(map_dir, DATA)
            self.assertNotIn("FootprintScobaHall", (game / "UnitData.xml").read_text(encoding="utf-8"))
            self.assertNotIn("FootprintScobaHall", before)
            self.assertNotIn("FootprintScobaHall", (game / "FootprintData.xml").read_text(encoding="utf-8"))
            self.assertEqual(check_scaled_footprints(map_dir, DATA), [])

    @mock.patch.object(config, "HALL_FOOTPRINTS_ON", True)
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
    """The committed slices of CommandCenter_Remastered.m3 at the drawn scale
    2.88 (actor 3.6 x model 0.8). It stands on three round legs (Leg1..3)
    and two side plates (LegPlate, LegPlate2).
    """

    LEGS = [(-4, -4), (0, 6), (3, -4)]  # unturned leg centres, world units

    def legs(self, polygons) -> list:
        """The loops of the round legs: 3 world units wide and deep."""
        return [q for q in polygons if max(x for x, _ in q) - min(x for x, _ in q) >= 2.5 and max(y for _, y in q) - min(y for _, y in q) >= 2.5]

    def centres(self, polygons) -> list[tuple[int, int]]:
        return sorted((round((min(x for x, _ in q) + max(x for x, _ in q)) / 2), round((min(y for _, y in q) + max(y for _, y in q)) / 2)) for q in polygons)

    def test_unturned_legs_and_the_middle_open(self) -> None:
        got = blocked(hall_cells(load_slices(), "CommandCenter", 2.88, 0.0))
        for cell in self.LEGS:
            self.assertIn(cell, got)
        # Negative: the middle is open, and no bar joins two legs.
        for i in range(-2, 3):
            for j in range(-2, 3):
                self.assertNotIn((i, j), got)
        for i in range(-2, 2):
            self.assertNotIn((i, -4), got)

    def test_shape_follows_the_half_grid_not_whole_cells(self) -> None:
        # As trees: the Shape is the 0.5 outline. Three legs, the plates in
        # smaller loops, none in the middle.
        sub = hall_sub_rows(load_slices(), "CommandCenter", 2.88, 0.0)
        self.assertEqual(len(sub) % 2, 0)
        polygons = hall_polygons(sub)
        self.assertEqual(self.centres(self.legs(polygons)), self.LEGS)
        for polygon in polygons:
            for x, y in polygon:
                self.assertTrue(max(abs(x), abs(y)) >= 2.5 and max(abs(x), abs(y)) <= 7.5, (x, y))
        # Negative: a point off the whole-cell grid exists (not 1x1 squares).
        self.assertTrue(any(x % 1 or y % 1 for polygon in polygons for x, y in polygon))

    def test_feet_are_turned_by_the_unit_facing(self) -> None:
        # CC facing 225 in game, model drawn as authored at 270: turned -45 degrees
        # (operator 2026-11-19: the unturned feet sat 45 degrees off).
        self.assertAlmostEqual(math.degrees(hall_angle("CommandCenter")), -45.0)
        polygons = hall_polygons(hall_sub_rows(load_slices(), "CommandCenter", 2.88))
        want = sorted((round((x + y) * math.sqrt(0.5)), round((y - x) * math.sqrt(0.5))) for x, y in self.LEGS)
        got = self.centres(self.legs(polygons))
        self.assertEqual(len(got), 3)
        for (gx, gy), (wx, wy) in zip(got, want):
            self.assertTrue(abs(gx - wx) <= 1 and abs(gy - wy) <= 1, (got, want))
        # Negative: nothing at the unturned leg centres or in the middle.
        cells = blocked(hall_cells(load_slices(), "CommandCenter", 2.88))
        for cell in self.LEGS[:1] + self.LEGS[2:]:
            self.assertNotIn(cell, cells)
        for i in range(-3, 4):
            for j in range(-3, 4):
                self.assertNotIn((i, j), cells)

    def test_every_town_hall_form_links_the_footprint_at_one_scale(self) -> None:
        # R-FP-10 (operator 2026-11-20): CC, Orbital Command, Planetary Fortress.
        self.assertEqual(sorted(config.HALL_UNITS), ["CommandCenter", "OrbitalCommand", "PlanetaryFortress"])
        actors = "".join(f'<CActorUnit id="{u}"><Scale value="3.6,3.6,4.2"/></CActorUnit>' for u in config.HALL_UNITS)
        halls = hall_footprints(load_slices(), actors)
        self.assertEqual(len({hall_footprint_id(h) for h in halls.values()}), 1)
        self.assertEqual(sorted(halls), sorted(config.HALL_UNITS))
        units = {u: f'<Footprint value="{hall_footprint_id(h)}"/>' for u, h in halls.items()}
        prints = {hall_footprint_id(h): hall_footprint_xml(h) for h in halls.values()}
        self.assertEqual(check_halls(prints, units, load_slices(), actors), [])
        # Negative: an Orbital Command left at scale 1 or on the 1x1 is flagged.
        small = actors.replace('id="OrbitalCommand"><Scale value="3.6,3.6,4.2"/>', 'id="OrbitalCommand">')
        self.assertTrue(any("different actor scales" in p for p in check_halls(prints, units, load_slices(), small)))
        units["OrbitalCommand"] = '<Footprint value="FootprintSCOBAHall1x1"/>'
        self.assertIn("OrbitalCommand has no measured hall footprint", check_halls(prints, units, load_slices(), actors))

    def test_slices_are_per_leg_bone(self) -> None:
        parts = load_slices()["models"]["CommandCenter"]
        self.assertEqual(sorted(parts), ["Leg1", "Leg2", "Leg3", "LegPlate", "LegPlate2"])


if __name__ == "__main__":
    unittest.main()
