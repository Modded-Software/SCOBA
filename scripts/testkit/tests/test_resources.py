"""Host tests for scripts/mapgen/resources (REQ-BASE-AI R-BASE-3, 8, 26, 31, 32)."""

from __future__ import annotations

import math
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from project_root import project_root
from mapgen.resources import config, fit, sites
from mapgen.resources.build import PILE

ROOT = project_root()
APP = ROOT / "src" / "SCOBA.SC2Map" / "scripts" / "app"
BUILT = ROOT / "out" / "SCOBA256.SC2Map"
# The files sites.plan reads (terrain.load, Regions, Objects).
INPUTS = ("Objects", "Regions", "t3HeightMap", "t3Terrain.xml", "t3CellFlags", "t3Water",
          "Base.SC2Data/GameData/WaterData.xml", ".doodads_lifted", ".trees_sunk")


def _stage(src: Path, work: Path) -> None:
    """The built map's plan inputs, without its placed piles."""
    for name in INPUTS:
        if (src / name).exists():
            (work / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src / name, work / name)
    (work / "Objects").write_text(PILE.sub("", (src / "Objects").read_text(encoding="utf-8")), encoding="utf-8")


class ShapeTest(unittest.TestCase):
    def test_same_name_same_shape(self) -> None:
        self.assertEqual(sites.shape("main9", (177, 174)), sites.shape("main9", (177, 174)))

    def test_shape_is_organic(self) -> None:
        # R-BASE-32: radii and angle steps vary; two lines differ.
        a = sites.shape("main9", (177, 174))
        fields = [(ang, r) for kind, ang, r in a if kind == "field"]
        self.assertEqual(len(fields), config.FIELDS)
        self.assertEqual(sum(1 for kind, *_ in a if kind == "geyser"), config.GEYSERS)
        radii = [r for _a, r in fields]
        steps = [fields[i + 1][0] - fields[i][0] for i in range(len(fields) - 1)]
        self.assertGreater(max(radii) - min(radii), 0.5)
        self.assertGreater(max(steps) - min(steps), 1.0)
        self.assertNotEqual(a, sites.shape("main10", (177, 174)))

    def test_line_keeps_hall_gap_and_no_overlap(self) -> None:
        free = np.ones((256, 256), dtype=bool)
        taken: set = set()
        line = sites.line_at(free, "TerranJungleLeftA", (120, 60), taken)
        self.assertIsNotNone(line)
        near = set(sites.hall_cells(line.hall, sites.HALL_GAP))
        used = set(sites.hall_cells(line.hall))
        for size, ps in ((config.FIELD_SIZE, line.fields), (config.GEYSER_SIZE, line.geysers)):
            for p in ps:
                cs = set(sites.cells(*p, size))
                self.assertFalse(cs & near, p)
                self.assertFalse(cs & used, p)
                used |= cs

    def test_blocked_spot_fails(self) -> None:
        # Negative: no line on blocked ground.
        free = np.zeros((256, 256), dtype=bool)
        self.assertIsNone(sites.line_at(free, "x", (120, 60), set()))


class AnchorTest(unittest.TestCase):
    LURKERS = "".join(
        f'<ObjectUnit Id="{i}" Position="{x},{y},0" Scale="1,1,1" UnitType="LurkerMPBurrowed" Player="8"/>\n'
        for i, (x, y) in enumerate(((10, 10), (12, 10), (11, 12), (100, 100), (102, 100), (101, 102)), 1))

    def test_two_groups(self) -> None:
        got = sorted(sites.lurker_anchors(self.LURKERS))
        self.assertAlmostEqual(got[0][0], 11.0, places=3)
        self.assertAlmostEqual(got[1][0], 101.0, places=3)

    def test_moved_lurker_moves_anchor(self) -> None:
        # R-BASE-3: the anchor follows the source.
        moved = self.LURKERS.replace('Position="100,100,0"', 'Position="106,100,0"')
        self.assertNotEqual(sorted(sites.lurker_anchors(self.LURKERS)), sorted(sites.lurker_anchors(moved)))

    def test_too_few_lurkers_fails(self) -> None:
        with self.assertRaises(ValueError):
            sites.lurker_anchors(self.LURKERS.splitlines()[0])


class FitTest(unittest.TestCase):
    def _objects(self) -> str:
        return ("<PlacedObjects>\n"
                '<ObjectDoodad Id="1" Position="50,50,3" Scale="2,2,2" Type="ZerusTree"/>\n'
                '<ObjectDoodad Id="2" Position="200,200,3" Scale="2,2,2" Type="ZerusTree"/>\n'
                '<ObjectUnit Id="3" Position="52,50,0" Scale="1,1,1" UnitType="Zergling" Player="15"/>\n'
                '<ObjectUnit Id="4" Position="150,150,0" Scale="1,1,1" UnitType="Zergling" Player="15"/>\n'
                "</PlacedObjects>\n")

    def test_moves_only_what_is_inside(self) -> None:
        keep = np.zeros((256, 256), dtype=bool)
        keep[45:56, 45:56] = True
        terrain = SimpleNamespace(height=np.zeros((256, 256)))
        text, moved, problems = fit.fit(self._objects(), keep, np.ones((256, 256), dtype=bool), terrain)
        self.assertEqual(problems, [])
        self.assertEqual(sorted((m.kind, m.ident) for m in moved), [("tree", "1"), ("unit", "3")])
        self.assertIn('Position="200,200,3"', text)
        self.assertIn('Position="150,150,0"', text)
        self.assertEqual(fit.inside(text, keep), [])
        # Negative: the unfitted text has both inside.
        self.assertEqual(len(fit.inside(self._objects(), keep)), 2)


@unittest.skipUnless((BUILT / "Objects").exists(), "needs a built map")
class PlanTest(unittest.TestCase):
    def setUp(self) -> None:
        self.work = Path(tempfile.mkdtemp())
        _stage(BUILT, self.work)

    def tearDown(self) -> None:
        shutil.rmtree(self.work)

    def test_plan_is_stable_and_complete(self) -> None:
        # R-BASE-8: the same map gives the same lines.
        a, b = sites.plan(self.work), sites.plan(self.work)
        self.assertEqual(a.problems, [])
        self.assertEqual(a.lines(), b.lines())
        self.assertEqual(len(a.mains), config.MAIN_COUNT)
        self.assertEqual(len(a.sites), config.SITE_COUNT)
        names = [ln.name for ln in a.sites]
        for camp in ("Brakk", "InfestedTank"):
            self.assertIn(camp + "Front", names)
            self.assertIn(camp + "Back", names)

    def test_camp_sites_either_side_of_camp(self) -> None:
        p = sites.plan(self.work)
        objects = (self.work / "Objects").read_text(encoding="utf-8")
        halls = {ln.name: ln.hall for ln in p.sites}
        for name, kind in config.GUARDS:
            camp = sites.units_of(objects, kind)[0]
            cen = config.CENTRE
            front, back = math.dist(halls[name + "Front"], cen), math.dist(halls[name + "Back"], cen)
            self.assertLess(front, math.dist(camp, cen))
            self.assertGreater(back, math.dist(camp, cen))


class ScriptTest(unittest.TestCase):
    def test_no_script_makes_a_resource(self) -> None:
        # R-BASE-26.
        text = "\n".join(p.read_text(encoding="utf-8") for p in sorted(APP.rglob("*.galaxy")))
        self.assertIsNone(re.search(r'UnitCreate\([^;]*"(?:MineralField|VespeneGeyser)"', text))
        self.assertIn("gf_BaseSitesLoad();", text)


GAME = ROOT / "src" / "SCOBA.SC2Map" / "Base.SC2Data" / "GameData"
GAS_BUILDINGS = ("Refinery", "AutomatedRefinery", "Extractor", "AutomatedExtractor")


def _entry(name: str, tag: str, ident: str) -> str:
    text = (GAME / name).read_text(encoding="utf-8")
    found = re.findall(rf'<{tag} id="{ident}">(.*?)</{tag}>', text, re.S)
    if len(found) != 1:
        raise AssertionError(f"{name}: {len(found)} {tag} entries of {ident}")
    return found[0]


def _solid(footprint: str, layer: str) -> list[str]:
    """The rows of one layer of a footprint, cut to their solid ("x") cells."""
    body = re.search(rf'<Layers index="{layer}"[^>]*>(.*?)</Layers>', _entry("FootprintData.xml", "CFootprint", footprint), re.S).group(1)
    rows = re.findall(r'<Rows value="([^"]+)"/>', body)
    return [row.strip(".o") for row in rows if "x" in row]


class GasSizeTest(unittest.TestCase):
    """R-BASE-35: the geyser and the gas buildings are 6x6, twice stock, in every place that says a size."""

    def test_the_site_generator_places_6x6_geysers_on_cell_corners(self) -> None:
        self.assertEqual(config.GEYSER_SIZE, (6, 6))
        line = sites.line_at(np.ones((256, 256), dtype=bool), "TerranJungleLeftA", (120, 60), set())
        for x, y in line.geysers:
            self.assertEqual((x, y), (round(x), round(y)))
            self.assertEqual(len(set(sites.cells(x, y, config.GEYSER_SIZE))), 36)
        # Negative: a field keeps its 2x1 snap (half y).
        self.assertTrue(all(y != round(y) for _x, y in line.fields))

    def test_a_sibling_site_keeps_its_piles_to_itself(self) -> None:
        # Two halls 20 apart, as a double site: 6x6 geysers reach across.
        free = np.ones((256, 256), dtype=bool)
        taken: set = set()
        first = sites.line_at(free, "TerranJungleLeftA", (185, 132), taken)
        second = sites.search(free, "TerranJungleLeftB", (185.0, 112.0), taken, [first])
        self.assertIsNotNone(second)
        for mine, other in ((first, second), (second, first)):
            gap = set(sites.hall_cells(other.hall, sites.HALL_GAP))
            self.assertFalse(gap & sites.pile_cells(mine), mine.name)
            for pile in mine.fields + mine.geysers:
                self.assertLess(math.dist(pile, mine.hall), math.dist(pile, other.hall), (mine.name, pile))
        # Negative: a hall on top of the first line's piles is refused.
        x, y = first.geysers[0]
        self.assertIsNone(sites.line_at(free, "x", (int(x), int(y) + 8), set(), others=[first]))

    def test_every_footprint_blocks_a_6x6_square(self) -> None:
        for footprint in ("FootprintScobaGeyser6x6", "FootprintScobaGeyser6x6Built", "FootprintScoba6x6CappedGeyser"):
            for layer in ("Check", "Place"):
                self.assertEqual(_solid(footprint, layer), ["xxxxxx"] * 6, (footprint, layer))

    def test_the_no_hall_ring_keeps_its_stock_width(self) -> None:
        # Negative: the ring is not doubled. 3 cells each side of the 6.
        body = _entry("FootprintData.xml", "CFootprint", "FootprintScobaGeyser6x6")
        self.assertEqual(body.count('<Rows value="oooxxxxxxooo"/>'), 12)
        self.assertEqual(body.count('Area="-6,-6,6,6"'), 2)

    def test_the_units_name_the_footprints_and_twice_the_stock_radius(self) -> None:
        geyser = _entry("UnitData.xml", "CUnit", "VespeneGeyser")
        self.assertIn('<Footprint value="FootprintScobaGeyser6x6"/>', geyser)
        self.assertNotIn("PlacementFootprint", geyser)
        for unit in GAS_BUILDINGS:
            body = _entry("UnitData.xml", "CUnit", unit)
            self.assertIn('<Footprint value="FootprintScobaGeyser6x6Built"/>', body, unit)
            self.assertIn('<PlacementFootprint value="FootprintScoba6x6CappedGeyser"/>', body, unit)
        for unit in ("VespeneGeyser", *GAS_BUILDINGS):
            body = _entry("UnitData.xml", "CUnit", unit)
            for field in ("Radius", "SeparationRadius", "MinimapRadius"):
                self.assertIn(f'<{field} value="3"/>', body, (unit, field))

    def test_the_models_are_drawn_at_twice_the_size(self) -> None:
        for actor in ("VespeneGeyser", *GAS_BUILDINGS):
            self.assertIn('<Scale value="2.000000"/>', _entry("ActorData.xml", "CActorUnit", actor), actor)
        self.assertIn('<Scale value="2.000000"/>', _entry("ActorData.xml", "CActorSplat", "VespeneGeyserSplat"))


if __name__ == "__main__":
    unittest.main()
