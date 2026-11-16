from __future__ import annotations

import shutil
import struct
import tempfile
import unittest
from pathlib import Path

import numpy as np

from flora import config
from flora.build import lift_of
from flora.dirt import layer
from flora.hazard_paint import CELLS, FULL, SLOT, TEXTURE, disc_weights, paint, paint_problems, write_layer

SIZE = 512  # 2 mask cells per map cell


def fake_map(root: Path, lava: bool = True) -> Path:
    head = struct.pack("<4sIIII", b"MASK", 102, 0, SIZE, SIZE).ljust(64, b"\0")
    (root / "t3TextureMasks").write_bytes(head + bytes(8 * SIZE * SIZE // 2))
    names = [TEXTURE if (i == SLOT and lava) else f"Zerus{i}" for i in range(8)]
    (root / "t3Terrain.xml").write_text(
        "".join(f'<texture i="{i}" name="{n}"/>\n' for i, n in enumerate(names)), encoding="utf-8"
    )
    return root


class DiscWeightsTest(unittest.TestCase):
    def test_full_inside_zero_beyond_blend(self):
        w = disc_weights(SIZE, [(100.0, 50.0, 2.0)], 3.0)
        k = SIZE // CELLS
        self.assertEqual(w[50 * k, 100 * k], FULL)  # centre
        self.assertEqual(w[50 * k, 106 * k], 0)  # 6 cells out: past half 2 + blend 3

    def test_blend_falls_between(self):
        w = disc_weights(SIZE, [(100.0, 50.0, 2.0)], 3.0)
        k = SIZE // CELLS
        mid = w[50 * k, int(103.5 * k)]
        self.assertTrue(0 < mid < FULL)

    def test_blend_window_is_operator_range(self):
        self.assertTrue(2.0 <= config.HAZARD_PAINT_BLEND <= 4.0)


class PaintTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        fake_map(self.dir)
        self.hazards = [("ZerusTarPit", 40.0, 60.0), ("ZerusLavaGroundCrack", 200.0, 10.0)]

    def tearDown(self):
        shutil.rmtree(self.dir)

    def test_paint_round_trips_and_checks_clean(self):
        paint(self.dir, self.hazards)
        self.assertEqual(paint_problems(self.dir, self.hazards), [])
        self.assertIn(f'<texture i="{SLOT}" name="{TEXTURE}"/>', (self.dir / "t3Terrain.xml").read_text())

    def test_other_layers_untouched(self):
        paint(self.dir, self.hazards)
        for slot in range(8):
            if slot != SLOT:
                self.assertFalse(layer(self.dir, slot).any(), slot)

    def test_used_slot_rejected(self):
        paint(self.dir, self.hazards)
        with self.assertRaises(ValueError):
            paint(self.dir, self.hazards)

    def test_other_layers_cleared_under_solid_lava(self):
        masks = self.dir / "t3TextureMasks"
        write_layer(masks, 4, np.full((SIZE, SIZE), 15, dtype=np.uint8))
        paint(self.dir, self.hazards)
        lava = layer(self.dir, SLOT)
        base = layer(self.dir, 4)
        self.assertFalse(base[lava == FULL].any())
        self.assertTrue((base[lava == 0] == 15).all())  # untouched away from hazards
        self.assertEqual(paint_problems(self.dir, self.hazards), [])

    def test_lane_dirt_layer_untouched(self):
        dirt = 1  # fixture slot 1 is Zerus1, the lane dirt
        write_layer(self.dir / "t3TextureMasks", dirt, np.full((SIZE, SIZE), 15, dtype=np.uint8))
        paint(self.dir, self.hazards)
        self.assertTrue((layer(self.dir, dirt) == 15).all())
        self.assertEqual(paint_problems(self.dir, self.hazards), [])

    def test_check_flags_layer_left_under_lava(self):
        paint(self.dir, self.hazards)
        write_layer(self.dir / "t3TextureMasks", 4, np.full((SIZE, SIZE), 15, dtype=np.uint8))
        self.assertTrue(any("slot 4" in p for p in paint_problems(self.dir, self.hazards)))

    def test_palette_without_lava_rejected(self):
        fake_map(self.dir, lava=False)
        with self.assertRaises(ValueError):
            paint(self.dir, self.hazards)
        self.assertFalse(layer(self.dir, SLOT).any())

    def test_check_flags_missing_paint(self):
        self.assertTrue(paint_problems(self.dir, self.hazards))

    def test_paint_where_planned_only(self):
        paint(self.dir, self.hazards)
        w = layer(self.dir, SLOT)
        self.assertTrue(np.array_equal(w > 0, disc_weights(SIZE, [(40.0, 60.0, 2.0), (200.0, 10.0, 1.5)], config.HAZARD_PAINT_BLEND) > 0))


class LiftTest(unittest.TestCase):
    def test_hazard_lift_above_flora(self):
        self.assertAlmostEqual(lift_of("ZerusTarPit") - lift_of("ZerusFern"), 0.1)


if __name__ == "__main__":
    unittest.main()
