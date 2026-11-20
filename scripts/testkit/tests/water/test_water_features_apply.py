"""Water features: placed objects and the build step on a map folder (split from test_water_features.py)."""

from __future__ import annotations
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
from flora import config as flora_config
from flora import terrain as flora_terrain
from flora.dirt import DIRT_NAME, layer
from flora.hazard_paint import FULL
from mapgen import spore_scale
from mapgen.waterfeatures import build, config, ground, paint, plan as planner, sites as site_finder
from testkit.tests.water.water_fixtures import (
    water_heights,
    MODELS,
    N,
    SCALE,
    RECTS,
    hills,
    unit_xml,
    mouths_of,
    planned,
    OBJECTS_HEAD,
    OBJECTS_TAIL,
    doodad,
    MASK,
    GRASS_SLOT,
    DIRT_SLOT,
    LANE,
    write_map,
)


class ObjectsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.old, self.plan = planned()

    def test_placed_water_doodads_at_the_sites_are_dropped(self) -> None:
        text = OBJECTS_HEAD + doodad(1, "Waterfall", 56, 72, 9) + doodad(2, "RockWaterfall", 70, 60, 9) + doodad(3, "ZerusWaterfall", 5, 120, 9) + doodad(4, "ZerusTree", 56, 72, 9) + OBJECTS_TAIL
        out, dropped = build.drop_placed(text, self.plan.sites)
        self.assertEqual(dropped, 2)
        kinds = [el.get("Type") for el in ET.fromstring(out.encode("utf-8"))]
        self.assertEqual(kinds, ["ZerusWaterfall", "ZerusTree"])  # negative: far water doodad and the tree stay

    def test_trees_follow_the_ground(self) -> None:
        delta = self.plan.ground - self.old
        y, x = np.unravel_index(np.argmin(delta), delta.shape)
        text = (
            OBJECTS_HEAD
            + doodad(1, "ZerusTree", float(x), float(y), 9.0)
            + doodad(2, "ZerusTree", float(x), float(y), 9.0, flags="")
            + doodad(3, "FogMist", float(x), float(y), 9.0)
            + doodad(4, "ZerusTree", 5.0, 5.0, 9.0)
            + OBJECTS_TAIL
        )
        out, moved = build.move_trees(text, self.old, self.plan.ground)
        self.assertEqual(moved, 1)
        z = {el.get("Id"): float(el.get("Position").split(",")[2]) for el in ET.fromstring(out.encode("utf-8"))}
        self.assertAlmostEqual(z["1"], 9.0 + float(delta[y, x]), places=3)
        self.assertEqual((z["2"], z["3"], z["4"]), (9.0, 9.0, 9.0))  # negative: not absolute, not a tree, not on moved ground

    def test_doodads_are_added_with_their_rise(self) -> None:
        text = OBJECTS_HEAD + doodad(7, "ZerusTree", 5, 5, 9) + OBJECTS_TAIL
        out = build.add_doodads(text, self.plan.placements, 0.75)
        added = [el for el in ET.fromstring(out.encode("utf-8")) if el.get("Id") != "7"]
        self.assertEqual(len(added), len(self.plan.placements))
        self.assertEqual(len({el.get("Id") for el in added}), len(added))
        for el, p in zip(added, self.plan.placements):
            self.assertEqual(el.get("Type"), p.kind)
            self.assertAlmostEqual(float(el.get("Position").split(",")[2]), p.z + 0.75, places=3)
            sx, sy, sz = (float(v) for v in el.get("Scale").split(","))
            self.assertEqual(sx, sy)  # one scale on the ground plane
            self.assertAlmostEqual(sz, p.scale, places=3)  # height apart: a fall as wide as its pipe wants
            self.assertAlmostEqual(sx, p.flat, places=3)
            self.assertEqual([f.get("Index") for f in el], list(config.FLAGS))
            self.assertEqual(int(el.get("Variation") or 0), p.variation)
        self.assertNotIn("\n", out.replace("\r\n", ""))  # CRLF kept

    def test_rocks_are_added_after_the_falls(self) -> None:
        text = OBJECTS_HEAD + doodad(7, "ZerusTree", 5, 5, 9) + OBJECTS_TAIL
        out = build.add_doodads(text, self.plan.placements, 0.75, self.plan.rocks)
        added = [el for el in ET.fromstring(out.encode("utf-8")) if el.get("Id") != "7"]
        self.assertEqual(len({el.get("Id") for el in added}), len(self.plan.placements) + len(self.plan.rocks))
        rocks = added[len(self.plan.placements) :]
        self.assertTrue(self.plan.rocks)
        for el, r in zip(rocks, self.plan.rocks):
            self.assertEqual(el.get("Type"), config.ROCK_TYPE)
            self.assertEqual(int(el.get("Variation")), r.variation)
            self.assertAlmostEqual(float(el.get("Position").split(",")[2]), r.z + 0.75, places=3)
            sx, sy, sz = (float(v) for v in el.get("Scale").split(","))
            self.assertEqual((sx, sy), (sz, sz))  # negative: a rock is never stretched
            self.assertEqual([f.get("Index") for f in el], list(config.FLAGS))
        # Preload: the rock with the variations placed.
        folder = Path(tempfile.mkdtemp())
        (folder / "Preload.xml").write_bytes(b"<Preload>\r\n</Preload>\r\n")
        build.update_preload(folder / "Preload.xml", out)
        used = ",".join(str(v) for v in sorted({r.variation for r in self.plan.rocks}))
        self.assertIn(f'<Actor id="{config.ROCK_TYPE}" Variations="{used}"/>', (folder / "Preload.xml").read_bytes().decode("utf-8"))
        # Pathing: the cell under every rock is blocked; without rocks it may be open.
        cells = build.no_path_cells(self.plan, MODELS)
        for r in self.plan.rocks:
            self.assertTrue(cells[int(r.y), int(r.x)])
        self.assertLessEqual(int(build.no_path_cells(self.plan._replace(rocks=()), MODELS).sum()), int(cells.sum()))

    def test_rise_depends_on_the_lift_step(self) -> None:
        folder = Path(tempfile.mkdtemp())
        self.assertAlmostEqual(build.doodad_rise(folder), flora_config.GROUND_LIFT - flora_config.DOODAD_LIFT)
        (folder / ".doodads_lifted").write_text("x", encoding="utf-8")
        self.assertAlmostEqual(build.doodad_rise(folder), flora_config.GROUND_LIFT)

    def test_preload_lists_placed_types(self) -> None:
        folder = Path(tempfile.mkdtemp())
        (folder / "Preload.xml").write_bytes(b'<Preload>\r\n<Actor id="RockWaterfall" Variations="2"/>\r\n<Unit id="X"/>\r\n</Preload>\r\n')
        objects = build.add_doodads(OBJECTS_HEAD + OBJECTS_TAIL, self.plan.placements, 0.0)
        build.update_preload(folder / "Preload.xml", objects)
        pre = (folder / "Preload.xml").read_bytes().decode("utf-8")
        self.assertIn('<Actor id="RockWaterfall" Variations="2"/>', pre)  # negative: none placed, the line is not touched
        self.assertEqual(pre.count('<Actor id="Waterfall"/>'), 1)
        self.assertIn('<Unit id="X"/>', pre)
        self.assertNotIn("ZerusWaterfall", pre)  # negative: not placed, not preloaded
        self.assertNotIn(config.ROCK_TYPE, pre)  # negative: no rock placed, none preloaded


class ApplyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.vz = hills()
        self.map = write_map(Path(tempfile.mkdtemp()) / "map", self.vz, unit_xml())

    def test_apply_writes_the_plan(self) -> None:
        self.assertEqual(spore_scale.PSI_DESTROYER_SCALE, 2.0)  # the pending unit scale the fixtures assume
        text = build.apply_water_features(self.map, MODELS)
        self.assertIn("sites=2", text)
        self.assertEqual((self.map / build.MARKER).read_text(encoding="utf-8"), text)
        # The written ground is the planned ground.
        old = np.rint(self.vz / SCALE) * SCALE
        plan = planner.make(ground.vertex_z(write_map(Path(tempfile.mkdtemp()) / "ref", self.vz, unit_xml())), site_finder.find(RECTS, mouths_of(old)), MODELS)
        self.assertLess(np.abs(ground.vertex_z(self.map) - plan.ground).max(), 0.01)
        # Water height: the planned level, in doodad space.
        water = (self.map / "Base.SC2Data" / "GameData" / "WaterData.xml").read_bytes().decode("utf-8")
        self.assertAlmostEqual(water_heights(water)["Albion"], plan.levels["Albion"] + flora_config.GROUND_LIFT, places=3)
        self.assertEqual(water_heights(water)["BelShir"], 7.15)
        # Doodads: placed ones at the site dropped, the far one kept, the feature added.
        objects = ET.fromstring((self.map / "Objects").read_bytes())
        ids = [el.get("Id") for el in objects]
        self.assertNotIn("30", ids)
        self.assertIn("31", ids)
        self.assertEqual(len(ids), len(set(ids)))
        made = [el for el in objects if el.tag == "ObjectDoodad" and int(el.get("Id")) > 31]
        self.assertEqual(len(made), len(plan.placements) + len(plan.rocks))
        rise = flora_config.GROUND_LIFT - flora_config.DOODAD_LIFT  # the lift step is still to come
        for el, p in zip(made, plan.placements):
            self.assertAlmostEqual(float(el.get("Position").split(",")[2]), p.z + rise, places=3)
        # Pathing: pool cells are painted, the far corner is not.
        pathing = np.frombuffer((self.map / "CellAttribute_Pnp").read_bytes(), dtype=np.uint8, offset=4).reshape(N - 1, N - 1)
        ys, xs = np.nonzero(plan.pools[0])
        deep = [(y, x) for y, x in zip(ys, xs) if plan.ground[y, x] < plan.levels["Albion"] - config.NO_PATH_DEPTH]
        self.assertTrue(deep)
        self.assertTrue(all(pathing[y, x] == ground.NO_PATH for y, x in deep))
        self.assertEqual(int(pathing[2, 2]), 0)  # negative case
        self.assertIn('<Actor id="Waterfall"/>', (self.map / "Preload.xml").read_bytes().decode("utf-8"))
        # No rock waterfall is added (operator 2026-11-20): falls, then plain rocks in the pools.
        self.assertEqual({el.get("Type") for el in made}, {config.FALL_TYPE, config.ROCK_TYPE})
        self.assertNotIn("RockWaterfall", {el.get("Type") for el in made})
        for el, r in zip(made[len(plan.placements) :], plan.rocks):
            self.assertAlmostEqual(float(el.get("Position").split(",")[2]), r.z + rise, places=3)
            self.assertEqual(int(pathing[int(r.y), int(r.x)]), ground.NO_PATH)  # no walking through a rock
        self.assertIn(f'<Actor id="{config.ROCK_TYPE}" Variations="', (self.map / "Preload.xml").read_bytes().decode("utf-8"))
        self.assertIn(f"rock {config.ROCK_TYPE}", text)
        # Flora sees the carved pools (flora/pools.py plants round them): the drawn water, not the rim.
        seen = flora_terrain.load(self.map).pool
        wet = np.zeros(plan.ground.shape, dtype=bool)
        for pool in plan.pools:
            wet |= pool
            whole = pool[:-1, :-1] & pool[1:, :-1] & pool[:-1, 1:] & pool[1:, 1:]  # cells with four wet vertices
            self.assertTrue(whole.any())
            self.assertTrue(seen[whole].all())
        dry = ~(wet[:-1, :-1] | wet[1:, :-1] | wet[:-1, 1:] | wet[1:, 1:])  # cells with no wet vertex
        self.assertFalse(seen[dry].any())  # negative: the rim and the land are no pool
        # Dirt on the pool walls (operator 2026-11-20: the dirt texture we use): the layer only gains.
        self.assertEqual(config.WALL_TEXTURE, DIRT_NAME)
        want = paint.mask_weights(paint.vertex_weights(plan.ground, plan.sites), MASK)
        dirt = layer(self.map, DIRT_SLOT)
        self.assertTrue(np.array_equal(dirt, np.maximum(want, LANE)))
        self.assertGreater(int((want == FULL).sum()), 20)  # there are walls
        self.assertTrue((dirt[want <= LANE] == LANE).all())  # negative: dirt that was there is not weakened
        grass = layer(self.map, GRASS_SLOT)
        self.assertTrue((grass[want == FULL] == 0).all())
        self.assertTrue((grass[want <= LANE] == 15).all())  # negative: no new dirt, no change
        self.assertIn(f"wall texture {config.WALL_TEXTURE}", text)

    def test_palette_without_the_wall_texture_fails(self) -> None:  # negative case
        xml = self.map / "t3Terrain.xml"
        xml.write_text(xml.read_text(encoding="utf-8").replace(f'name="{config.WALL_TEXTURE}"', 'name="Other"'), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "wall texture"):
            build.apply_water_features(self.map, MODELS)
        self.assertFalse((self.map / build.MARKER).exists())

    def test_second_run_changes_nothing(self) -> None:
        build.apply_water_features(self.map, MODELS)
        before = {p.name: p.read_bytes() for p in self.map.iterdir() if p.is_file()}
        self.assertEqual(build.apply_water_features(self.map, MODELS), "")
        self.assertEqual({p.name: p.read_bytes() for p in self.map.iterdir() if p.is_file()}, before)

    def test_no_pipe_unit_fails_and_writes_nothing(self) -> None:  # negative case
        folder = write_map(Path(tempfile.mkdtemp()) / "map", self.vz, unit_xml(kind="SensorTower"))
        before = {p.name: p.read_bytes() for p in folder.iterdir() if p.is_file()}
        with self.assertRaises(ValueError):
            build.apply_water_features(folder, MODELS)
        self.assertEqual({p.name: p.read_bytes() for p in folder.iterdir() if p.is_file()}, before)
        self.assertFalse((folder / build.MARKER).exists())


if __name__ == "__main__":
    unittest.main()
