"""Host tests of the rim waterfalls (REQ-RIM-FALLS, scripts/mapgen/rimfalls)."""

from __future__ import annotations

import math
import struct
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

from flora.terrain import bilinear
from mapgen.rimfalls import build, carve, compose, config, models as models_mod, sites as site_finder
from mapgen.waterfeatures import build as water_build
from mapgen.waterfeatures import ground
from mapgen.waterfeatures.models import rotation_facing, turned

MODELS = models_mod.load()
N = 257  # vertices per side of the synthetic map
SCALE = 0.001
WALL = 20.0  # width of the wall of the synthetic bowl
STEEP = 0.8
NONE = np.zeros((0, 3))
HEAD = '<?xml version="1.0" encoding="utf-8"?>\r\n<PlacedObjects Version="27">\r\n'
TAIL = "</PlacedObjects>\r\n"
ABSOLUTE = '        <Flag Index="HeightAbsolute" Value="1"/>\r\n'


def bowl() -> np.ndarray:
    """A flat floor at z 5 and a wall rising STEEP per unit over the last WALL units to the edge."""
    ys, xs = np.mgrid[0:N, 0:N]
    edge = np.minimum(np.minimum(xs, N - 1 - xs), np.minimum(ys, N - 1 - ys))
    return 5.0 + STEEP * np.maximum(0.0, WALL - edge)


def inward(x: float, y: float) -> tuple[float, float]:
    """True downhill direction of the synthetic wall at a point off the corners."""
    n = N - 1
    edge = min(x, y, n - x, n - y)
    if edge == x:
        return (1.0, 0.0)
    if edge == n - x:
        return (-1.0, 0.0)
    return (0.0, 1.0) if edge == y else (0.0, -1.0)


def off_corner(s: site_finder.Site) -> bool:
    n = N - 1
    return sorted((s.x, s.y, n - s.x, n - s.y))[1] > WALL + 2 * config.NORMAL_RADIUS


def gap(a: float, b: float) -> float:
    return build.turn_gap(a, b)


def tree(oid: int, x: float, y: float, z: float) -> str:
    return f'    <ObjectDoodad Id="{oid}" Position="{x},{y},{z}" Rotation="1" Scale="2,2,2" Type="ZerusTree">\r\n{ABSOLUTE}    </ObjectDoodad>\r\n'


def write_map(folder: Path, vz: np.ndarray, extra: str = "") -> Path:
    """A synthetic built map: what apply_rim_falls reads and writes."""
    folder.mkdir(parents=True)
    records = np.zeros((N, N, 3), dtype="<u2")
    records[..., 0] = np.rint(vz / SCALE).astype("<u2")
    (folder / "t3HeightMap").write_bytes(struct.pack("<4sIII", b"HMAP", 101, N, N) + bytes(16) + records.tobytes())
    (folder / "t3Terrain.xml").write_text(
        f'<terrain><vertData quantizeBias="1" quantizeScale="{SCALE}" standardHeight="8" name="t3HeightMap"/></terrain>\n', encoding="utf-8"
    )
    (folder / "t3Water").write_bytes(b"WATR" + struct.pack("<II", 110, 0) + bytes(20))
    game = folder / "Base.SC2Data" / "GameData"
    game.mkdir(parents=True)
    (game / "ActorData.xml").write_text('<?xml version="1.0" encoding="us-ascii"?>\n<Catalog>\n</Catalog>\n', encoding="utf-8")
    (folder / "Preload.xml").write_bytes(b"<Preload>\r\n</Preload>\r\n")
    (folder / "CellAttribute_Pnp").write_bytes(struct.pack("<I", (N - 1) * (N - 1) * 8) + bytes((N - 1) * (N - 1)))
    # Trees on the floor calibrate the height offset (flora/terrain.py).
    trees = "".join(tree(10 + k, x, y, round(float(vz[y, x]), 4)) for k, (x, y) in enumerate([(100, 100), (150, 120), (128, 160), (90, 140)]))
    (folder / "Objects").write_bytes((HEAD + trees + extra + TAIL).encode("utf-8"))
    return folder


class SitesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.vz = bowl()
        self.sites = site_finder.find(self.vz, NONE, [])

    def test_the_bowl_gives_twelve_to_twenty_four_sites_on_the_wall(self) -> None:
        self.assertEqual(site_finder.problems(self.sites), [])
        self.assertTrue(config.MIN_SITES <= len(self.sites) <= config.MAX_SITES, len(self.sites))
        n = N - 1
        for s in self.sites:
            edge = min(s.x, s.y, n - s.x, n - s.y)
            self.assertTrue(config.EDGE_MIN <= edge <= WALL, (s, edge))  # on the wall, not on the floor
            # Raised terrain behind, lower ground ahead.
            self.assertGreater(bilinear(self.vz, s.x - s.dir[0] * 4, s.y - s.dir[1] * 4), self.vz[int(s.y), int(s.x)] + 1.0)
            self.assertLess(bilinear(self.vz, s.x + s.dir[0] * 4, s.y + s.dir[1] * 4), self.vz[int(s.y), int(s.x)])

    def test_the_site_direction_is_the_wall_normal(self) -> None:
        straight = [s for s in self.sites if off_corner(s)]
        self.assertGreaterEqual(len(straight), 8)
        for s in straight:
            want = inward(s.x, s.y)
            self.assertAlmostEqual(math.hypot(*s.dir), 1.0, places=6)
            self.assertGreater(s.dir[0] * want[0] + s.dir[1] * want[1], 0.99, s)

    def test_one_site_a_sector_and_sites_apart(self) -> None:
        self.assertEqual(len({s.sector for s in self.sites}), len(self.sites))
        for i, a in enumerate(self.sites):
            for b in self.sites[i + 1 :]:
                self.assertGreaterEqual(math.hypot(a.x - b.x, a.y - b.y), config.MIN_SPACING)

    def test_flat_ground_has_no_site(self) -> None:  # negative: no wall, no fall
        flat = np.full((N, N), 5.0)
        self.assertEqual(site_finder.find(flat, NONE, []), [])
        self.assertTrue(site_finder.problems([]))

    def test_a_wall_falling_to_the_edge_has_no_site(self) -> None:  # negative: a dome is no bowl
        self.assertEqual(site_finder.find(30.0 - bowl(), NONE, []), [])

    def test_sites_keep_clear_of_placed_objects(self) -> None:
        target = self.sites[0]
        placed = np.array([(target.x, target.y, 0.0)])
        moved = site_finder.find(self.vz, placed, [])
        for s in moved:
            self.assertGreaterEqual(math.hypot(s.x - target.x, s.y - target.y), config.CLEAR)
        # A crowded wall: nothing fits anywhere.
        ys, xs = np.mgrid[0:N:4, 0:N:4]
        crowd = np.stack([xs.ravel(), ys.ravel(), 0 * xs.ravel()], axis=1).astype(float)
        self.assertEqual(site_finder.find(self.vz, crowd, []), [])

    def test_a_change_only_reaches_the_sectors_near_it(self) -> None:
        # Objects all over the floor, so every site has a nearest object of its own.
        ys, xs = np.mgrid[32 : N - 32 : 16, 32 : N - 32 : 16]
        floor = np.stack([xs.ravel(), ys.ravel(), 0 * xs.ravel()], axis=1).astype(float)
        before = site_finder.find(self.vz, floor, [])
        target = before[0]
        after = {s.sector: s for s in site_finder.find(self.vz, np.vstack([floor, [(target.x, target.y, 0.0)]]), [])}
        self.assertNotEqual(after.get(target.sector), target)  # the change is real
        near = {(target.sector + k) % config.SECTORS for k in (-2, -1, 0, 1, 2)}
        far = [s for s in before if s.sector not in near]
        self.assertGreaterEqual(len(far), 6)
        for s in far:
            self.assertEqual(after[s.sector], s)

    def test_sites_keep_clear_of_water(self) -> None:
        target = self.sites[0]
        rect = (target.x - 2, target.y - 2, target.x + 2, target.y + 2)
        for s in site_finder.find(self.vz, NONE, [rect]):
            self.assertGreaterEqual(math.hypot(max(rect[0] - s.x, 0, s.x - rect[2]), max(rect[1] - s.y, 0, s.y - rect[3])), config.WATER_MARGIN)

    def test_placed_points_reads_doodads_units_and_points(self) -> None:
        text = HEAD + tree(1, 3, 4, 5) + '    <ObjectUnit Id="2" Position="7.5,8,0" UnitType="X"/>\r\n    <ObjectPoint Id="3" Position="9,10,0" Type="Normal"/>\r\n' + TAIL
        # The tree (scale 2) reaches TREE_REACH per unit of scale; the others are points.
        self.assertEqual(site_finder.placed_points(text).tolist(), [[3.0, 4.0, 2 * config.TREE_REACH], [7.5, 8.0, 0.0], [9.0, 10.0, 0.0]])

    def test_sites_keep_away_from_geysers(self) -> None:  # operator 2026-11-20: never near geysers
        target = self.sites[0]
        geyser = f'    <ObjectUnit Id="2" Position="{target.x},{target.y},0" UnitType="VespeneGeyser"/>\r\n'
        other = f'    <ObjectUnit Id="2" Position="{target.x},{target.y},0" UnitType="Marine"/>\r\n'
        placed = site_finder.placed_points(HEAD + geyser + TAIL)
        self.assertEqual(placed.tolist(), [[target.x, target.y, config.GEYSER_REACH]])

        def near(found) -> float:
            return min(math.hypot(s.x - target.x, s.y - target.y) for s in found)

        self.assertGreaterEqual(near(site_finder.find(self.vz, placed, [])), config.CLEAR + config.GEYSER_REACH)
        # Control: another unit there is a point, with no extra reach.
        self.assertEqual(site_finder.placed_points(HEAD + other + TAIL).tolist(), [[target.x, target.y, 0.0]])

    def test_sites_are_close_to_the_rim(self) -> None:  # operator 2026-11-20: closer to the rim
        n = N - 1
        self.assertLessEqual(config.EDGE_MAX, 20.0)
        for s in self.sites:
            self.assertLessEqual(min(s.x, s.y, n - s.x, n - s.y), config.EDGE_MAX)

    def test_a_big_tree_keeps_sites_further_away(self) -> None:
        target = self.sites[0]
        reach = 4.0
        for s in site_finder.find(self.vz, np.array([(target.x, target.y, reach)]), []):
            self.assertGreaterEqual(math.hypot(s.x - target.x, s.y - target.y), config.CLEAR + reach)


class CarveTest(unittest.TestCase):
    def setUp(self) -> None:
        self.vz = bowl()
        self.site = site_finder.find(self.vz, NONE, [])[0]
        self.edge = carve.basin_edge(self.vz, self.site)
        self.cut = carve.cut(self.vz, self.site, self.edge)

    def test_the_ground_is_only_lowered_and_only_near_the_basin(self) -> None:
        delta = self.cut - self.vz
        self.assertLessEqual(delta.max(), 0.0)  # negative: nothing raised
        self.assertLess(delta.min(), -config.BASIN_DEPTH * 0.5)
        cx, cy = carve.basin_centre(self.site)
        ys, xs = np.mgrid[0:N, 0:N]
        far = np.hypot(xs - cx, ys - cy) > config.BASIN_RADIUS + config.BASIN_BLEND
        self.assertEqual(float(np.abs(delta[far]).max()), 0.0)  # negative: nothing changes outside the reach
        self.assertLessEqual(-delta.min(), config.MAX_CUT)

    def test_the_basin_is_a_bowl_below_its_edge(self) -> None:
        cx, cy = carve.basin_centre(self.site)
        self.assertAlmostEqual(bilinear(self.cut, cx, cy), self.edge - config.BASIN_DEPTH, delta=0.25)
        ys, xs = np.mgrid[0:N, 0:N]
        inside = np.hypot(xs - cx, ys - cy) <= config.BASIN_RADIUS
        self.assertLessEqual(float(self.cut[inside].max()), self.edge + 1e-9)

    def test_the_notch_leaves_raised_terrain_behind(self) -> None:
        cx, cy = carve.basin_centre(self.site)
        reach = config.BASIN_RADIUS + config.BASIN_BLEND
        behind = bilinear(self.cut, cx - self.site.dir[0] * reach, cy - self.site.dir[1] * reach)
        self.assertGreater(behind, self.edge + 2.0)


class ComposeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.vz = bowl()
        self.sites = site_finder.find(self.vz, NONE, [])
        self.plan = build.make(self.vz, self.sites, MODELS)

    def test_the_plan_has_no_problem(self) -> None:
        self.assertEqual(build.problems(self.vz, self.plan), [])

    def test_every_group_layers_rock_and_normal_waterfalls(self) -> None:
        for g in self.plan.groups:
            rock = [p for p in g.falls if p.kind == config.ROCK_FALL]
            plain = [p for p in g.falls if p.kind == config.FALL]
            self.assertTrue(config.ROCK_FALLS[0] <= len(rock) <= config.ROCK_FALLS[1])
            self.assertTrue(config.FALLS[0] <= len(plain) <= config.FALLS[1])
            self.assertEqual(len({p.variation for p in rock}), len(rock))
            for p in rock:
                self.assertIn(p.variation, MODELS.falls[config.ROCK_FALL])
            # Layered: every normal waterfall stands in front of the first rock waterfall.
            for p in plain:
                ahead = (p.x - rock[0].x) * g.site.dir[0] + (p.y - rock[0].y) * g.site.dir[1]
                self.assertGreater(ahead, 0.0)
                self.assertLess(compose_top(p), compose_top(rock[0]) + 1e-6)

    def test_every_fall_faces_the_wall_normal(self) -> None:
        for g in self.plan.groups:
            for p in g.falls:
                self.assertLessEqual(gap(p.rotation, rotation_facing(g.site.dir)), config.TURN_JITTER + 1e-9)
                # The model's front (-y), turned, points downhill: away from the raised terrain.
                front = turned((0.0, -1.0), p.rotation)
                self.assertGreater(front[0] * g.site.dir[0] + front[1] * g.site.dir[1], math.cos(config.TURN_JITTER) - 1e-9)
                step = 3.0
                self.assertGreater(bilinear(self.vz, g.site.x - front[0] * step, g.site.y - front[1] * step), bilinear(self.vz, g.site.x + front[0] * step, g.site.y + front[1] * step))

    def test_rock_waterfalls_are_embedded_in_the_wall(self) -> None:  # operator 2026-11-20: not floating in front of it
        for g in self.plan.groups:
            for p in g.falls:
                if p.kind != config.ROCK_FALL:
                    continue
                share = compose.embedded(self.plan.ground, MODELS, p, g.surface)
                self.assertGreaterEqual(share, config.EMBED[0] - 0.02, (g.site, p))
                # The wall behind it is higher still, and it stands uphill of the basin.
                self.assertGreater(bilinear(self.plan.ground, p.x - g.site.dir[0], p.y - g.site.dir[1]), bilinear(self.plan.ground, p.x, p.y))
                self.assertLess((p.x - g.basin[0]) * g.site.dir[0] + (p.y - g.basin[1]) * g.site.dir[1], 0.0)

    def test_a_floating_rock_waterfall_is_a_problem(self) -> None:  # negative
        g = self.plan.groups[0]
        out = g.falls[0]._replace(x=g.basin[0], y=g.basin[1])  # in the basin: nothing covers it
        bad = build.Plan(self.plan.ground, (g._replace(falls=(out,) + g.falls[1:]),) + self.plan.groups[1:])
        self.assertTrue(any("is embedded" in line for line in build.problems(self.vz, bad, MODELS)))
        self.assertEqual(build.problems(self.vz, self.plan, MODELS), [])

    def test_a_fall_turned_off_the_normal_is_a_problem(self) -> None:  # negative
        g = self.plan.groups[0]
        wrong = g.falls[0]._replace(rotation=(g.falls[0].rotation + 1.0) % math.tau)
        bad = build.Plan(self.plan.ground, (g._replace(falls=(wrong,) + g.falls[1:]),) + self.plan.groups[1:])
        self.assertTrue(any("off the wall normal" in line for line in build.problems(self.vz, bad)))

    def test_sizes_and_turns_vary(self) -> None:
        rock = [p for g in self.plan.groups for p in g.falls if p.kind == config.ROCK_FALL]
        plain = [p for g in self.plan.groups for p in g.falls if p.kind == config.FALL]
        for falls in (rock, plain):
            self.assertGreater(max(p.flat for p in falls) / min(p.flat for p in falls), 1.3)
            self.assertGreater(max(p.scale for p in falls) / min(p.scale for p in falls), 1.3)
        self.assertGreater(len({p.variation for p in rock}), 3)
        low, high = config.ROCK_FALL_SCALE
        for p in rock:
            self.assertTrue(low * 0.75 - 1e-9 <= p.flat <= high + 1e-9)

    def test_rocks_lie_on_the_basin_floor(self) -> None:
        for g in self.plan.groups:
            self.assertTrue(config.ROCKS[0] <= len(g.rocks) <= config.ROCKS[1], len(g.rocks))
            wet = [q for p in g.falls if p.kind == config.ROCK_FALL for q in compose.landings(MODELS, p)]
            for r in g.rocks:
                self.assertEqual(r.kind, config.ROCK)
                self.assertLessEqual(math.hypot(r.x - g.basin[0], r.y - g.basin[1]), config.ROCK_SPREAD * config.BASIN_RADIUS + 1e-9)
                self.assertAlmostEqual(r.z, bilinear(self.plan.ground, r.x, r.y) - config.ROCK_SINK, places=6)
                self.assertLessEqual(r.z, g.edge)  # in the basin, not on the wall
                for q in wet:
                    self.assertGreaterEqual(math.hypot(r.x - q[0], r.y - q[1]), config.ROCK_FALL_CLEAR)

    def test_the_falls_stand_on_the_basin_water_surface(self) -> None:
        for g in self.plan.groups:
            self.assertLess(g.surface, g.edge)
            for p in g.falls:
                self.assertAlmostEqual(p.z + MODELS.falls[p.kind][p.variation].base_z * p.scale, g.surface, places=6)

    def test_same_input_same_plan(self) -> None:
        again = build.make(self.vz, site_finder.find(self.vz, NONE, []), MODELS)
        self.assertEqual(again.groups, self.plan.groups)

    def test_a_group_does_not_depend_on_the_other_sites(self) -> None:
        alone = build.make(self.vz, [self.sites[3]], MODELS).groups[0]
        held = self.plan.groups[3]
        self.assertEqual([p._replace(site=0) for p in held.falls], list(alone.falls))
        self.assertEqual([r._replace(site=0) for r in held.rocks], list(alone.rocks))


def compose_top(p) -> float:
    return p.z + MODELS.falls[p.kind][p.variation].hi[2] * p.scale


class ModelsTest(unittest.TestCase):
    def test_the_rock_waterfalls_are_measured(self) -> None:
        shapes = MODELS.falls[config.ROCK_FALL]
        self.assertEqual(sorted(shapes), list(range(7)))
        for shape in shapes.values():
            self.assertTrue(shape.splashes)
            self.assertLess(shape.base_z, 0.0)  # the water surface is at the model's foot
            self.assertGreater(shape.hi[2], 2.0)
            # Front is -y: the streams land in front of the rock's back.
            self.assertLess(min(s[1] for s in shape.splashes), 0.0)
        self.assertIn(config.FALL, MODELS.falls)
        self.assertIn(config.ROCK_SOURCE, MODELS.rocks)


class ApplyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.vz = bowl()
        self.map = write_map(Path(tempfile.mkdtemp()) / "map", self.vz)
        self.pathing = (self.map / "CellAttribute_Pnp").read_bytes()
        self.text = build.apply_rim_falls(self.map, MODELS)

    def test_apply_writes_the_plan(self) -> None:
        self.assertEqual((self.map / config.MARKER).read_text(encoding="utf-8"), self.text)
        ref = write_map(Path(tempfile.mkdtemp()) / "ref", self.vz)
        old = ground.vertex_z(ref)
        objects = (ref / "Objects").read_text(encoding="utf-8")
        plan = build.make(old, site_finder.find(old, site_finder.placed_points(objects), []), MODELS)
        self.assertIn(f"groups={len(plan.groups)} ", self.text)
        self.assertLess(np.abs(ground.vertex_z(self.map) - plan.ground).max(), 0.01)
        placed = ET.fromstring((self.map / "Objects").read_bytes())
        ids = [el.get("Id") for el in placed]
        self.assertEqual(len(ids), len(set(ids)))
        kinds = [el.get("Type") for el in placed]
        self.assertEqual(kinds.count(config.ROCK_FALL), sum(1 for g in plan.groups for p in g.falls if p.kind == config.ROCK_FALL))
        self.assertEqual(kinds.count(config.FALL), sum(1 for g in plan.groups for p in g.falls if p.kind == config.FALL))
        self.assertEqual(kinds.count(config.ROCK), sum(len(g.rocks) for g in plan.groups))
        self.assertNotIn(config.ROCK_SOURCE, kinds)  # negative: no rock with the stock footprint
        rise = water_build.doodad_rise(self.map)
        written = {(el.get("Type"), el.get("Position")) for el in placed}
        for g in plan.groups:
            for p in g.falls:
                self.assertIn((p.kind, f"{p.x:.4f},{p.y:.4f},{p.z + rise:.4f}"), written)

    def test_written_falls_face_the_wall(self) -> None:
        for el in ET.fromstring((self.map / "Objects").read_bytes()):
            if el.get("Type") not in (config.ROCK_FALL, config.FALL):
                continue
            x, y, _z = (float(v) for v in el.get("Position").split(","))
            front = turned((0.0, -1.0), float(el.get("Rotation")))
            # Behind the fall the ground is higher than in front of it (the uncut bowl).
            self.assertGreater(bilinear(self.vz, x - front[0] * 5, y - front[1] * 5), bilinear(self.vz, x + front[0] * 5, y + front[1] * 5))
            self.assertEqual({f.get("Index") for f in el.findall("Flag")}, {"HeightAbsolute", "ForcePlacement"})

    def test_the_rim_stays_walkable(self) -> None:
        self.assertEqual((self.map / "CellAttribute_Pnp").read_bytes(), self.pathing)  # negative: no pathing painted
        actors = (self.map / "Base.SC2Data" / "GameData" / "ActorData.xml").read_text(encoding="utf-8")
        entry = ET.fromstring(actors).find(f"CActorDoodad[@id='{config.ROCK}']")
        self.assertEqual(entry.get("parent"), config.ROCK_SOURCE)
        self.assertEqual(entry.find("Footprint").get("value"), config.NONE_FOOTPRINT)
        self.assertEqual(entry.find("Model").get("value"), config.ROCK_SOURCE)
        footprint = ET.fromstring((self.map / "Base.SC2Data" / "GameData" / "FootprintData.xml").read_text(encoding="utf-8")).find(f"CFootprint[@id='{config.NONE_FOOTPRINT}']")
        self.assertEqual({row.get("value") for row in footprint.iter("Rows")}, {"."})  # no blocked cell

    def test_preload_lists_what_was_placed(self) -> None:
        pre = (self.map / "Preload.xml").read_text(encoding="utf-8")
        for kind in (config.ROCK_FALL, config.ROCK):
            self.assertRegex(pre, rf'<Actor id="{kind}" Variations="[\d,]+"/>')
        self.assertIn(f'<Actor id="{config.FALL}"/>', pre)
        ET.fromstring(pre)

    def test_a_second_run_changes_nothing(self) -> None:
        before = (self.map / "Objects").read_bytes(), (self.map / "t3HeightMap").read_bytes()
        self.assertEqual(build.apply_rim_falls(self.map, MODELS), "")
        self.assertEqual(((self.map / "Objects").read_bytes(), (self.map / "t3HeightMap").read_bytes()), before)

    def test_two_builds_are_identical(self) -> None:
        other = write_map(Path(tempfile.mkdtemp()) / "other", self.vz)
        build.apply_rim_falls(other, MODELS)
        for name in ("Objects", "t3HeightMap", config.MARKER, "Preload.xml"):
            self.assertEqual((other / name).read_bytes(), (self.map / name).read_bytes(), name)

    def test_a_map_without_a_rim_fails_and_writes_nothing(self) -> None:  # negative
        flat = write_map(Path(tempfile.mkdtemp()) / "flat", np.full((N, N), 5.0))
        before = (flat / "Objects").read_bytes()
        with self.assertRaisesRegex(ValueError, "rim falls failed"):
            build.apply_rim_falls(flat, MODELS)
        self.assertEqual((flat / "Objects").read_bytes(), before)
        self.assertFalse((flat / config.MARKER).exists())


if __name__ == "__main__":
    unittest.main()
