"""Host tests on the drop crash zoom (SPEC-HERO-DROP 3a).

The zoom constants are read from the map script (core/hero_drop.galaxy,
data/pod_birth.galaxy, core/constants.galaxy): one source, no copy here.
"""

from __future__ import annotations

import math
import re
import unittest
import xml.etree.ElementTree as ET

from flora import terrain as terrain_mod
from hitvolumes import intro_shots as S
from hitvolumes import pod_birth
from project_root import project_root

SCRIPTS = project_root() / "src" / "SCOBA.SC2Map" / "scripts" / "app"
BUILT = project_root() / "out" / "SCOBA256.SC2Map"
# The Terran lane spawn regions (app/init: gv_sPAWNLOCATIONS[1..3]).
LANE_REGIONS = ("1", "3", "4")
SAMPLES = 41
CLEARANCE = 0.5
CONST_RE = re.compile(r"^const fixed (c_\w+) = ([-0-9.]+);", re.M)


def constants() -> dict[str, float]:
    out: dict[str, float] = {}
    for rel in ("core/constants.galaxy", "data/pod_birth.galaxy", "core/hero_drop.galaxy"):
        for name, value in CONST_RE.findall((SCRIPTS / rel).read_text(encoding="utf-8")):
            out[name] = float(value)
    return out


C = constants()


def ease(t: float) -> float:
    w = min(max(t / C["c_DROP_ZOOM_MOVE"], 0.0), 1.0)
    return 1 - (1 - w) ** 3


def end_arm(clip0: float) -> float:
    """The zoom's end arm (gf_HeroDropZoomBegin): the fall arm at the clip
    time the zoom ends on. The zoom starts once the pod births, clip0 s into
    Birth (operator 2026-11-20)."""
    z = max(pod_birth.world((clip0 + C["c_DROP_ZOOM_LENGTH"]) * 1000.0, 0.0)[2], 0.0)
    return C["c_DROP_POD_ARM"] + z / math.sin(math.radians(C["c_POD_BIRTH_PITCH"]))


# The zoom starts between the Birth start and c_DROP_ARM_MAX into it.
CLIP0S = (0.0, C["c_DROP_ARM_MAX"])


def sample(t: float, clip0: float = 0.0) -> tuple[float, float, float]:
    """Pitch, arm, FOV at t seconds into the zoom (gf_HeroDropZoomApply)."""
    e = ease(t)
    pitch1 = C["c_POD_BIRTH_PITCH"]
    dist1 = end_arm(clip0)
    pitch = C["c_DROP_ZOOM_PITCH"] + (pitch1 - C["c_DROP_ZOOM_PITCH"]) * e
    dist = C["c_DROP_ZOOM_DIST"] + (dist1 - C["c_DROP_ZOOM_DIST"]) * e
    fov = C["c_DROP_ZOOM_FOV0"] + (C["c_DROP_ZOOM_FOV1"] - C["c_DROP_ZOOM_FOV0"]) * e
    return pitch, dist, fov


def times() -> list[float]:
    return [C["c_DROP_ZOOM_LENGTH"] * k / (SAMPLES - 1) for k in range(SAMPLES)]


class ZoomTest(unittest.TestCase):
    def test_constants_found(self) -> None:
        for name in ("c_DROP_ZOOM_LENGTH", "c_DROP_ZOOM_MOVE", "c_DROP_ZOOM_PITCH", "c_DROP_ZOOM_DIST", "c_DROP_ZOOM_FOV0", "c_DROP_ZOOM_FOV1", "c_DROP_YAW", "c_DROP_CAM_SIDE", "c_DROP_POD_ARM", "c_POD_BIRTH_PITCH", "c_POD_BIRTH_START_Z", "c_SCOBA_CAMERA_HEIGHT_OFFSET"):
            self.assertIn(name, C, name)

    def test_length(self) -> None:
        self.assertLessEqual(C["c_DROP_ZOOM_LENGTH"], 0.4)  # R-INTRO-10
        self.assertLess(C["c_DROP_ZOOM_MOVE"], C["c_DROP_ZOOM_LENGTH"])

    def test_ends_on_the_fall_camera(self) -> None:
        for clip0 in CLIP0S:
            pitch, dist, fov = sample(C["c_DROP_ZOOM_LENGTH"], clip0)
            self.assertAlmostEqual(pitch, C["c_POD_BIRTH_PITCH"], places=6)
            self.assertAlmostEqual(dist, end_arm(clip0), places=6)
            self.assertAlmostEqual(fov, C["c_DROP_ZOOM_FOV1"], places=6)

    def test_end_arm_follows_the_pod(self) -> None:
        # At clip 0 + zoom length the pod is below its Birth start: a shorter
        # arm than the start arm. Negative: a later zoom start ends shorter.
        start = C["c_DROP_POD_ARM"] + C["c_POD_BIRTH_START_Z"] / math.sin(math.radians(C["c_POD_BIRTH_PITCH"]))
        self.assertLess(end_arm(0.0), start)
        self.assertLess(end_arm(C["c_DROP_ARM_MAX"]), end_arm(0.0))
        self.assertGreater(end_arm(C["c_DROP_ARM_MAX"]), C["c_DROP_POD_ARM"])

    def test_easing_held_after_the_move(self) -> None:
        self.assertAlmostEqual(ease(C["c_DROP_ZOOM_MOVE"]), 1.0)
        self.assertAlmostEqual(ease(C["c_DROP_ZOOM_LENGTH"]), 1.0)
        # Negative case: halfway through the move it is not done.
        self.assertLess(ease(0.5 * C["c_DROP_ZOOM_MOVE"]), 1.0)
        prev = -1.0
        for t in times():
            self.assertGreaterEqual(ease(t), prev)
            prev = ease(t)

    def test_intro_table_has_no_zoom_row(self) -> None:
        # R-DROP-11: the zoom exists once, in the drop module.
        self.assertFalse(hasattr(S, "ZOOM"))
        self.assertNotIn("c_INTRO_ROW_ZOOM", S.galaxy())
        self.assertNotIn("C", S.EASES)


@unittest.skipUnless((BUILT / "t3HeightMap").is_file() and (BUILT / "Regions").is_file(), "needs the built map (scripts/playtest.sh build)")
class ZoomTerrainTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.t = terrain_mod.load(BUILT)
        root = ET.parse(BUILT / "Regions").getroot()
        cls.regions = {}
        for region in root.iter("region"):
            if region.get("id") in LANE_REGIONS:
                shape = region.find("shape")
                cx, cy = (float(v) for v in shape.find("center").get("value").split(","))
                cls.regions[region.get("id")] = (cx, cy, float(shape.find("radius").get("value")))

    def ground(self, x: float, y: float) -> float:
        return terrain_mod.ground_z(self.t, x, y)

    def surface(self, x: float, y: float) -> float:
        g = self.ground(x, y)
        i, j = int(min(max(y, 0), 255)), int(min(max(x, 0), 255))
        return max(g, self.t.water_level) if self.t.depth[i, j] > 0 else g

    def clearance(self, at: tuple[float, float], pitch_scale: float = 1.0) -> float:
        yaw = C["c_DROP_YAW"]
        # gf_HeroDropSide: the side arm to the right of the travel.
        side = math.radians(yaw - 90.0)
        tx = at[0] + C["c_DROP_CAM_SIDE"] * math.cos(side)
        ty = at[1] + C["c_DROP_CAM_SIDE"] * math.sin(side)
        tz = self.ground(tx, ty) + C["c_SCOBA_CAMERA_HEIGHT_OFFSET"]
        worst = 1e9
        for t in times():
            for clip0 in CLIP0S:
                pitch, dist, _ = sample(t, clip0)
                ex, ey, ez = S.eye(tx, ty, tz, yaw, pitch * pitch_scale, dist)
                worst = min(worst, ez - self.surface(ex, ey))
        return worst

    def points(self, region: tuple[float, float, float]) -> list[tuple[float, float]]:
        cx, cy, r = region
        out = [(cx, cy)]
        for k in range(8):
            a = 2 * math.pi * k / 8
            out.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        return out

    def test_three_lane_regions_found(self) -> None:
        self.assertEqual(sorted(self.regions), sorted(LANE_REGIONS))

    def test_eye_clears_the_ground_over_every_lane_spawn(self) -> None:
        for rid, region in self.regions.items():
            for at in self.points(region):
                self.assertGreaterEqual(self.clearance(at), CLEARANCE, f"region {rid} at {at}")

    def test_clearance_catches_an_eye_in_the_ground(self) -> None:
        # Negative case: the same zoom pitched below the horizon.
        rid = LANE_REGIONS[0]
        cx, cy, _ = self.regions[rid]
        self.assertLess(self.clearance((cx, cy), -1.0), CLEARANCE)


if __name__ == "__main__":
    unittest.main()
