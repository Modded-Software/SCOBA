"""Water features: the in-game profile, its points and its checks (split from test_water_features.py)."""

from __future__ import annotations
import math
import tempfile
import unittest
from unittest import mock
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from flora.terrain import bilinear
from mapgen.waterfeatures import build, carve, config, ground


class ProfileTest(unittest.TestCase):
    """The in-game profile (testkit/profiles/waterfeat.py) on the built map: its points and its checks."""

    @classmethod
    def setUpClass(cls) -> None:
        from testkit.profiles import waterfeat

        cls.wf = waterfeat
        if not (waterfeat.BUILT / build.MARKER).exists():
            raise unittest.SkipTest("the built map has no water features (SC2_NO_WATER_FEATURES)")
        cls.scene = waterfeat.scene()
        cls.samples = [waterfeat.samples(cls.scene, i) for i in range(len(cls.scene.sites))]

    def bank(self) -> dict:
        """What a game that agrees with the build would write."""
        sc, wf = self.scene, self.wf
        data: dict = {"meta": {"done": 1, "realClicks": 0, "count": 1}}
        for k, (_kind, x, y) in enumerate(sc.pipes):
            data[f"pipe{k}"] = {"count": 1, "x": x, "y": y, "facing": 270.0, "height": 0.0, "ground": bilinear(sc.vz, x, y)}
        for i, site in enumerate(sc.sites):
            s = self.samples[i]
            for name, points in (("pool", s.pool), ("dry", s.dry), ("far", s.far), ("cells", s.cells)):
                row = data.setdefault(f"s{i}_{name}", {})
                for k, (x, y) in enumerate(points):
                    row[f"s{k}Ground"] = bilinear(sc.vz, x, y)
                    row[f"s{k}Pass"] = name == "far"
            data[f"s{i}_stand"] = {"x": s.stand[0], "y": s.stand[1], "marineH": 0.0, "ground": bilinear(sc.vz, *s.stand), "alive": True}
            # The Marine walks toward the pool and stops where the water starts.
            path = []
            for k in range(200):
                t = k / 199
                p = (s.start[0] + (s.end[0] - s.start[0]) * t, s.start[1] + (s.end[1] - s.start[1]) * t)
                if wf.water_depth(sc, site, p) > 0.0:
                    break
                path.append(p)
            walk = {"startPass": True, "endPass": False, "moveIssued": True, "alive": True, "endOrders": 0, "pathCount": len(path)}
            walk.update({f"path{k:03d}": f"{int(x * 100)},{int(y * 100)}" for k, (x, y) in enumerate(path)})
            data[f"s{i}_walk"] = walk
            (x, y), yaw = wf.orbit(sc, i)
            row = {"seconds": wf.ORBIT_SECONDS + 0.05, "followsHero": False, "scene": True}
            for tag, share in (("start", 0.0), ("mid", 0.5), ("end", 1.0)):
                row.update({tag + "X": x, tag + "Y": y, tag + "Yaw": (yaw + wf.ORBIT_TURN * share) % 360.0, tag + "Pitch": wf.ORBIT_PITCH, tag + "Dist": wf.ORBIT_DIST})
            data[f"s{i}_orbit"] = row
        for i, rim in enumerate(wf.rim_groups()):
            data[f"r{i}_basin"] = {"s0Ground": bilinear(sc.vz, *rim.basin), "s0Pass": True}
            data[f"r{i}_rocks"] = {f"s{k}Pass": True for k in range(len(rim.rocks))}
        return data

    def shots(self) -> SimpleNamespace:
        """A host that took every screenshot on time."""
        folder = Path(tempfile.mkdtemp())
        taken = {}
        for i in range(len(self.scene.sites)):
            rows = [(k * self.wf.SHOT_GAP_S + 0.01 * k, f"s{i}_orbit-{k:04d}.png") for k in range(self.wf.SHOTS)]
            for _t, name in rows:
                (folder / name).write_bytes(b"png")
            taken[f"s{i}_orbit"] = rows
        return SimpleNamespace(errors=[], frames=SimpleNamespace(dir=folder), orbit_shots=taken)

    def failed(self, data: dict, ctx: SimpleNamespace | None = None) -> list[str]:
        import contextlib
        import io
        from unittest import mock

        from testkit.checks import Checks

        checks = Checks(data)
        with mock.patch.object(self.wf, "scene", return_value=self.scene), contextlib.redirect_stdout(io.StringIO()):
            self.wf.check(ctx or self.shots(), data, checks)
        names = [str(r["section"]) for r in checks.results if r["status"] == "FAIL"]
        self.assertEqual(len(names), checks.failures)
        return names

    def test_points_are_what_they_are_named(self) -> None:
        sc = self.scene
        self.assertEqual(len(sc.sites), 2)
        self.assertEqual(len(sc.pipes), 1)
        for i, site in enumerate(sc.sites):
            s, level = self.samples[i], sc.levels[site.water]
            self.assertGreaterEqual(len(s.pool), 10)
            self.assertGreaterEqual(len(s.dry), 10)
            self.assertGreaterEqual(len(s.far), 4)
            self.assertGreaterEqual(len(s.cells), 5)
            for x, y in s.pool:
                self.assertLess(sc.vz[int(y), int(x)], level)
            for x, y in s.dry:
                self.assertGreater(sc.vz[int(y), int(x)], level)
                self.assertGreaterEqual(abs(sc.vz[int(y), int(x)] - sc.before[int(y), int(x)]), self.wf.MOVED)
            for x, y in s.far:
                self.assertEqual(sc.vz[int(y), int(x)], sc.before[int(y), int(x)])  # negative: not moved
            for x, y in s.cells:
                self.assertTrue(sc.painted[int(y), int(x)])
                self.assertGreaterEqual(self.wf.water_depth(sc, site, (x, y)), config.NO_PATH_DEPTH)
            self.assertTrue(sc.open[int(s.start[1]), int(s.start[0])])
            self.assertLessEqual(self.wf.water_depth(sc, site, s.start), 0.0)  # the walk starts dry
            self.assertGreaterEqual(self.wf.water_depth(sc, site, s.end), config.NO_PATH_DEPTH)  # and aims into the pool
        text = self.wf.points_galaxy(sc)
        for call in ('gf_WfPipe("pipe0", "PsiDecimator")', 'gf_WfStand("s0_stand"', 'gf_WfWalk("s1_walk"', 'gf_WfSample("s1_cells", 0,'):
            self.assertIn(call, text)

    def test_helpers(self) -> None:
        wf = self.wf
        self.assertEqual(wf.thin([(float(k), 0.0) for k in range(10)], 5), [(0.0, 0.0), (2.0, 0.0), (4.0, 0.0), (6.0, 0.0), (8.0, 0.0)])
        self.assertEqual(len(wf.thin([(1.0, 1.0)], 5)), 1)
        self.assertEqual(wf.path_points({"pathCount": 2, "path000": "150,275", "path001": "200,300", "path002": "9,9"}), [(1.5, 2.75), (2.0, 3.0)])
        self.assertEqual(wf.water_depth(self.scene, self.scene.sites[0], (5.0, 5.0)), 0.0)  # no water outside the rectangle

    def test_agreeing_game_passes(self) -> None:
        self.assertEqual(self.failed(self.bank()), [])

    def test_rim_points_are_what_they_are_named(self) -> None:
        from mapgen.rimfalls import config as rim_config

        sc, rims = self.scene, self.wf.rim_groups()
        if not rims:
            self.skipTest("the built map has no rim falls (SC2_NO_RIM_FALLS)")
        self.assertTrue(rim_config.MIN_SITES <= len(rims) <= rim_config.MAX_SITES)
        for rim in rims:
            self.assertGreaterEqual(sc.before[int(rim.basin[1]), int(rim.basin[0])] - sc.vz[int(rim.basin[1]), int(rim.basin[0])], self.wf.MOVED)
            self.assertTrue(rim.rocks)
            for x, y in rim.rocks:
                self.assertLessEqual(math.dist((x, y), rim.basin), rim_config.BASIN_RADIUS + 1.0)
                self.assertFalse(sc.painted[int(y), int(x)])  # negative: the build painted no pathing there
        text = self.wf.points_galaxy(sc)
        self.assertEqual(text.count('_basin", 0,'), len(rims))
        self.assertEqual(text.count("_rocks\","), sum(len(r.rocks) for r in rims))

    def test_rim_faults_fail(self) -> None:  # negative cases
        if not self.wf.rim_groups():
            self.skipTest("the built map has no rim falls (SC2_NO_RIM_FALLS)")
        sc, wf, rims = self.scene, self.wf, self.wf.rim_groups()
        # A rock and a basin on ground the map left walkable, and a point it did not.
        rock = next((i, k) for i, r in enumerate(rims) for k, p in enumerate(r.rocks) if wf.was_open(sc, p))
        basin = next(i for i, r in enumerate(rims) if wf.was_open(sc, r.basin))
        data = self.bank()
        data[f"r{rock[0]}_rocks"][f"s{rock[1]}Pass"] = False  # a rock blocks
        self.assertEqual(self.failed(data), [f"r{rock[0]}_walk basin and rocks block no walkable ground"])
        data = self.bank()
        data[f"r{basin}_basin"]["s0Pass"] = False  # the basin blocks
        self.assertEqual(self.failed(data), [f"r{basin}_walk basin and rocks block no walkable ground"])
        data = self.bank()
        data["r0_basin"]["s0Ground"] = bilinear(sc.before, *rims[0].basin)  # the cut did not reach the engine
        self.assertEqual(self.failed(data), ["r0_basin engine ground = built ground", "r0_basin basin is cut, the uncut ground is absent"])
        data = self.bank()
        del data["r1_basin"]
        self.assertEqual(self.failed(data), ["r1_basin sample read"])
        data = self.bank()
        del data["r1_rocks"]
        self.assertEqual(self.failed(data), ["r1_walk every sample read"])
        # Ground the map blocks itself is not held against the step.
        shut = [(i, k) for i, r in enumerate(rims) for k, p in enumerate(r.rocks) if not wf.was_open(sc, p)]
        if shut:
            data = self.bank()
            data[f"r{shut[0][0]}_rocks"][f"s{shut[0][1]}Pass"] = False
            self.assertEqual(self.failed(data), [])
        # Negative: with nothing on walkable ground the check is empty, and that fails.
        blind = sc._replace(prior=np.full_like(sc.prior, 255))
        with mock.patch.object(type(self), "scene", blind):
            self.assertEqual(self.failed(self.bank()), ["rim points on ground the map left walkable"])

    def test_was_open(self) -> None:
        sc, wf = self.scene, self.wf
        prior = np.zeros_like(sc.prior)
        prior[50, 60] = 128
        bare = sc._replace(prior=prior, things=((100.0, 100.0, 3.0),))
        self.assertTrue(wf.was_open(bare, (70.5, 50.5)))
        self.assertFalse(wf.was_open(bare, (60.5, 50.5)))  # painted cell
        self.assertFalse(wf.was_open(bare, (61.5, 51.5)))  # beside a painted cell
        self.assertTrue(wf.was_open(bare, (62.5, 50.5)))
        self.assertFalse(wf.was_open(bare, (102.0, 100.0)))  # under a tree
        self.assertTrue(wf.was_open(bare, (104.0, 100.0)))
        self.assertFalse(wf.was_open(sc._replace(prior=None), (70.5, 50.5)))

    def test_old_ground_in_the_game_fails(self) -> None:  # negative: the carve did not reach the engine
        sc, data = self.scene, self.bank()
        for k, (x, y) in enumerate(self.samples[0].pool):
            data["s0_pool"][f"s{k}Ground"] = bilinear(sc.before, x, y)
        names = self.failed(data)
        self.assertIn("s0_pool engine ground = built ground", names)
        self.assertIn("s0_pool ground from before the step is absent", names)
        self.assertNotIn("s1_pool engine ground = built ground", names)

    def test_moved_ground_beside_the_site_fails(self) -> None:
        data = self.bank()
        data["s1_far"]["s0Ground"] += 1.0
        self.assertIn("s1_far ground beside the site did not move", self.failed(data))

    def test_passable_pool_cell_fails(self) -> None:
        data = self.bank()
        data["s1_cells"]["s0Pass"] = True
        self.assertEqual(self.failed(data), ["s1_cells painted pool cells are not passable"])
        data = self.bank()
        del data["s0_cells"]["s0Pass"]  # a value the game did not write is no pass
        self.assertEqual(self.failed(data), ["s0_cells painted pool cells are not passable"])

    def test_marine_in_the_pool_fails(self) -> None:
        data = self.bank()
        s = self.samples[0]
        walk = data["s0_walk"]
        count = walk["pathCount"]
        walk[f"path{count:03d}"] = f"{int(s.end[0] * 100)},{int(s.end[1] * 100)}"
        walk["pathCount"] = count + 1
        self.assertEqual(self.failed(data), ["s0_walk the marine never stands in the pool"])

    def test_marine_that_did_not_walk_fails(self) -> None:
        data = self.bank()
        walk = data["s1_walk"]
        for k in range(walk["pathCount"]):
            walk[f"path{k:03d}"] = walk["path000"]
        self.assertEqual(self.failed(data), ["s1_walk the marine walked"])
        data = self.bank()
        data["s1_walk"]["startPass"] = False
        self.assertEqual(self.failed(data), ["s1_walk start is passable"])

    def test_marine_off_the_ground_fails(self) -> None:
        data = self.bank()
        data["s0_stand"]["marineH"] = 1.5
        self.assertEqual(self.failed(data), ["s0_stand marine stands on the engine ground"])

    def test_turned_or_moved_pipe_unit_fails(self) -> None:
        data = self.bank()
        data["pipe0"]["facing"] = 225.0
        self.assertEqual(self.failed(data), ["pipe0 faces 270: the model is drawn as authored"])
        data = self.bank()
        data["pipe0"]["height"] = 2.0
        self.assertEqual(self.failed(data), ["pipe0 stands on the built ground"])
        data = self.bank()
        data["pipe0"]["count"] = 0
        self.assertEqual(self.failed(data), ["pipe0 one PsiDecimator in the game"])

    def test_orbit_plan(self) -> None:
        wf, sc = self.wf, self.scene
        self.assertEqual((wf.ORBIT_SECONDS, wf.SHOTS, wf.SHOT_GAP_S), (15.0, 5, 3.0))  # operator 2026-11-20
        self.assertLess((wf.SHOTS - 1) * wf.SHOT_GAP_S, wf.ORBIT_SECONDS)
        for i, site in enumerate(sc.sites):
            target, yaw = wf.orbit(sc, i)
            self.assertGreaterEqual(wf.water_depth(sc, site, target), 0.0)  # the pool
            # The middle screenshot looks from the pool at the pipe mouths.
            middle = math.radians(yaw + wf.ORBIT_TURN / wf.ORBIT_SECONDS * (wf.SHOTS - 1) * wf.SHOT_GAP_S / 2)
            for mouth in site.mouths:
                self.assertLess(math.cos(middle) * mouth.dx + math.sin(middle) * mouth.dy, -0.7)
        self.assertEqual(wf.points_galaxy(sc).count("gf_WfOrbit("), len(sc.sites))

    def test_orbit_faults_fail(self) -> None:  # negative cases
        data = self.bank()
        data["s0_orbit"]["endYaw"] = data["s0_orbit"]["startYaw"]  # the camera did not turn
        self.assertEqual(self.failed(data), ["s0_orbit camera yaw follows the orbit"])
        data = self.bank()
        data["s1_orbit"]["midX"] += 30.0  # pulled off the site
        self.assertEqual(self.failed(data), ["s1_orbit camera target stays on the site"])
        data = self.bank()
        data["s1_orbit"]["followsHero"] = True
        self.assertEqual(self.failed(data), ["s1_orbit camera does not follow the hero"])
        data = self.bank()
        data["s0_orbit"]["seconds"] = 10.7  # game seconds, not real ones
        self.assertEqual(self.failed(data), ["s0_orbit orbit lasts 15 s of real time"])
        data = self.bank()
        del data["s0_orbit"]["midYaw"]
        self.assertEqual(self.failed(data), ["s0_orbit camera read"])

    def test_missing_or_late_screenshots_fail(self) -> None:  # negative cases
        name = "s1_orbit 5 screenshots 3 s apart, inside the orbit"
        ctx = self.shots()
        ctx.orbit_shots["s1_orbit"].pop()
        self.assertEqual(self.failed(self.bank(), ctx), [name])
        ctx = self.shots()
        (ctx.frames.dir / ctx.orbit_shots["s1_orbit"][2][1]).unlink()
        self.assertEqual(self.failed(self.bank(), ctx), [name])
        ctx = self.shots()
        ctx.orbit_shots["s1_orbit"] = [(t * 2, n) for t, n in ctx.orbit_shots["s1_orbit"]]
        self.assertEqual(self.failed(self.bank(), ctx), [name])
        ctx = self.shots()
        del ctx.orbit_shots  # the host hook never ran
        self.assertEqual(len(self.failed(self.bank(), ctx)), 2)

    def test_real_click_fails(self) -> None:
        data = self.bank()
        data["meta"]["realClicks"] = 1
        self.assertEqual(self.failed(data), ["meta"])


if __name__ == "__main__":
    unittest.main()
