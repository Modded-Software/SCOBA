"""Steps: fitting, four times larger, flip-book cells (R-HD-56)."""

from __future__ import annotations

import unittest

import numpy as np
from hdtex.core import steps

from testkit.tests.textures.fixtures import repeat


def smear(image: np.ndarray, reach: int = 8) -> np.ndarray:
    """An upscaler that reaches `reach` input pixels sideways, as a real one does."""
    wide = image.astype(np.float32)
    total = sum(np.roll(wide, shift, axis=1) for shift in range(-reach, reach + 1))
    return repeat(np.rint(total / (2 * reach + 1)).astype(np.uint8))


class FitTest(unittest.TestCase):
    def test_a_plane_within_the_limit_is_left_alone(self) -> None:
        plane = np.zeros((2048, 8, 3), dtype=np.uint8)
        self.assertIs(steps.fit(plane, 2048, True), plane)

    def test_a_larger_plane_is_halved_until_it_fits(self) -> None:
        plane = np.zeros((8192, 16, 3), dtype=np.uint8)
        self.assertEqual(steps.fit(plane, 2048, True).shape, (2048, 4, 3))
        self.assertEqual(steps.fitted(8192, 2048), 2048)
        self.assertEqual(steps.fitted(3000, 2048), 1500)

    def test_colour_is_averaged_in_linear_light_and_data_as_it_is(self) -> None:
        checker = np.zeros((4, 4), dtype=np.uint8)
        checker[::2, ::2] = 255
        checker[1::2, 1::2] = 255
        colour = np.stack([checker] * 3, axis=2)
        self.assertEqual(int(steps.fit(checker, 2, False)[0, 0]), 128)
        self.assertGreater(int(steps.fit(colour, 2, True)[0, 0, 0]), 180)

    def test_a_grey_plane_stays_grey(self) -> None:
        self.assertEqual(
            steps.fit(np.zeros((8, 8), dtype=np.uint8), 4, False).shape, (4, 4)
        )

    def test_an_odd_side_cannot_be_halved(self) -> None:
        with self.assertRaises(steps.StepError):
            steps.fit(np.zeros((6, 5, 3), dtype=np.uint8), 4, True)


class StepTest(unittest.TestCase):
    def test_a_step_enlarges_four_times(self) -> None:
        plane = np.arange(64 * 64 * 3, dtype=np.uint8).reshape(64, 64, 3)
        given = steps.prepare(plane, True, steps.SINGLE)
        self.assertIs(given, plane)
        self.assertEqual(
            steps.conclude(plane, repeat(given), True, steps.SINGLE).shape,
            (256, 256, 3),
        )

    def test_an_input_above_2048_is_halved_first(self) -> None:
        plane = np.zeros((4096, 8, 3), dtype=np.uint8)
        given = steps.prepare(plane, True, steps.SINGLE)
        self.assertEqual(given.shape, (2048, 4, 3))
        self.assertEqual(
            steps.conclude(plane, repeat(given), True, steps.SINGLE).shape, (4096, 8, 3)
        )

    def test_an_output_above_4096_is_halved(self) -> None:
        plane = np.zeros((2048, 4), dtype=np.uint8)
        kept = steps.conclude(
            plane, np.zeros((8192, 16), dtype=np.uint8), False, steps.SINGLE
        )
        self.assertEqual(kept.shape, (4096, 8))
        self.assertEqual(steps.after(2048, False), 4096)
        self.assertEqual(steps.after(256, True), 1024)

    def test_a_full_size_data_plane_is_passed_on_and_colour_is_not(self) -> None:
        data = np.zeros((4096, 8), dtype=np.uint8)
        self.assertIsNone(steps.prepare(data, False, steps.SINGLE))
        self.assertIs(steps.conclude(data, None, False, steps.SINGLE), data)
        self.assertEqual(steps.after(4096, False), 4096)
        self.assertIsNotNone(
            steps.prepare(np.zeros((4096, 8, 3), dtype=np.uint8), True, steps.SINGLE)
        )
        self.assertIsNotNone(
            steps.prepare(np.zeros((2048, 4), dtype=np.uint8), False, steps.SINGLE)
        )

    def test_an_output_of_another_size_is_refused(self) -> None:
        plane = np.zeros((64, 64, 3), dtype=np.uint8)
        with self.assertRaises(steps.StepError):
            steps.conclude(
                plane, np.zeros((128, 128, 3), dtype=np.uint8), True, steps.SINGLE
            )


class FlipBookTest(unittest.TestCase):
    def setUp(self) -> None:
        # Two cells side by side: the left one black, the right one white.
        self.plane = np.zeros((64, 128), dtype=np.uint8)
        self.plane[:, 64:] = 255
        self.grid = (2, 1)

    def test_no_cell_takes_pixels_from_the_next(self) -> None:
        given = steps.prepare(self.plane, False, self.grid)
        self.assertEqual(given.shape, (64 + 32, 128 + 64))
        kept = steps.conclude(self.plane, smear(given), False, self.grid)
        self.assertEqual(kept.shape, (256, 512))
        self.assertEqual(int(kept[:, :256].max()), 0)
        self.assertEqual(int(kept[:, 256:].min()), 255)

    def test_without_cells_the_same_upscaler_mixes_them(self) -> None:
        given = steps.prepare(self.plane, False, steps.SINGLE)
        kept = steps.conclude(self.plane, smear(given), False, steps.SINGLE)
        self.assertGreater(int(kept[:, :256].max()), 0)
        self.assertLess(int(kept[:, 256:].min()), 255)
