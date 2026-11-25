"""The texture formats, the roles, the measures and the flip book cells of the core (R-HD-10 to 13, R-HD-56)."""

from __future__ import annotations

import unittest

import numpy as np
from hdtex.core import bc1, bc3, dds, flipbook, lowfreq, metrics, registry, roles


def smooth_rgba(size: int, seed: int = 1, contrast: int = 90) -> np.ndarray:
    """A tiling picture with soft detail in every channel."""
    rng = np.random.default_rng(seed)
    angle = np.arange(size) * (2 * np.pi / size)
    wave = np.sin(angle)[:, None] * np.cos(angle * 2)[None, :]
    planes = [
        128 + contrast * np.roll(wave, shift, axis=1)
        for shift in (0, size // 4, size // 2, size // 8)
    ]
    image = np.stack(planes, axis=2) + rng.normal(0, 2, (size, size, 4))
    return np.clip(np.rint(image), 0, 255).astype(np.uint8)


def swizzled_normal(size: int) -> np.ndarray:
    """A normal map in the game's layout: X in alpha, Y in green, red 255, blue 0."""
    angle = np.arange(size) * (2 * np.pi / size)
    x = 0.4 * np.sin(angle)[None, :] * np.ones((size, 1))
    y = 0.3 * np.cos(angle)[:, None] * np.ones((1, size))
    rgba = np.zeros((size, size, 4), dtype=np.uint8)
    rgba[:, :, 0] = 255
    rgba[:, :, 1] = np.rint((y * 0.5 + 0.5) * 255)
    rgba[:, :, 3] = np.rint((x * 0.5 + 0.5) * 255)
    return rgba


def free_red_normal(size: int) -> np.ndarray:
    """A normal map with an amount of its own in red."""
    rgba = swizzled_normal(size)
    rgba[:, :, 0] = np.arange(size, dtype=np.uint8)[None, :] * 3
    return rgba


class Bc3Test(unittest.TestCase):
    def test_size_is_sixteen_bytes_per_block(self) -> None:
        self.assertEqual(len(bc3.encode(smooth_rgba(16))), 16 * bc3.BLOCK_BYTES)
        self.assertEqual(bc3.block_count(1024, 1024), 256 * 256)

    def test_flat_block_is_exact(self) -> None:
        image = np.zeros((8, 8, 4), dtype=np.uint8)
        image[:, :, :3] = 255
        image[:, :, 3] = 77
        decoded = bc3.decode(bc3.encode(image), 8, 8)
        self.assertTrue(np.array_equal(decoded, image))

    def test_smooth_picture_survives(self) -> None:
        image = smooth_rgba(64)
        decoded = bc3.decode(bc3.encode(image), 64, 64)
        self.assertEqual(decoded.shape, image.shape)
        self.assertGreater(min(metrics.channel_psnr(image, decoded)), 35.0)

    def test_alpha_does_not_leak_into_colour(self) -> None:
        image = smooth_rgba(32)
        other = image.copy()
        other[:, :, 3] = 255 - other[:, :, 3]
        first = bc3.decode(bc3.encode(image), 32, 32)
        second = bc3.decode(bc3.encode(other), 32, 32)
        self.assertTrue(np.array_equal(first[:, :, :3], second[:, :, :3]))
        self.assertFalse(np.array_equal(first[:, :, 3], second[:, :, 3]))

    def test_levels_smaller_than_a_block(self) -> None:
        for size in (2, 1):
            image = np.full((size, size, 4), 255, dtype=np.uint8)
            data = bc3.encode(image)
            self.assertEqual(len(data), bc3.BLOCK_BYTES)
            self.assertTrue(np.array_equal(bc3.decode(data, size, size), image))


class Bc1Test(unittest.TestCase):
    def test_a_block_is_eight_bytes(self) -> None:
        self.assertEqual(
            len(bc1.encode(smooth_rgba(64))), (64 // 4) ** 2 * bc1.BLOCK_BYTES
        )

    def test_flat_colours_come_back_exact_and_opaque(self) -> None:
        image = np.zeros((8, 8, 4), dtype=np.uint8)
        image[:, :, :3] = (255, 0, 255)
        image[:, 4:, :3] = (0, 0, 0)
        decoded = bc1.decode(bc1.encode(image), 8, 8)
        self.assertTrue(np.array_equal(decoded[:, :, :3], image[:, :, :3]))
        self.assertEqual(int(decoded[:, :, 3].min()), 255)

    def test_a_smooth_picture_survives(self) -> None:
        image = smooth_rgba(64, seed=4)
        decoded = bc1.decode(bc1.encode(image), 64, 64)
        error = np.abs(
            decoded[:, :, :3].astype(int) - image[:, :, :3].astype(int)
        ).mean()
        self.assertLess(error, 3.0)
        self.assertEqual(int(decoded[:, :, 3].min()), 255)

    def test_a_three_colour_block_decodes_its_transparent_pixel(self) -> None:
        # Endpoint 0 below endpoint 1: three colours, index 3 is transparent black.
        block = bytes([0x00, 0x00, 0xFF, 0xFF]) + (3).to_bytes(4, "little")
        decoded = bc1.decode(block, 4, 4)
        self.assertEqual(decoded[0, 0].tolist(), [0, 0, 0, 0])
        self.assertEqual(decoded[0, 1].tolist(), [0, 0, 0, 255])

    def test_the_container_reads_and_writes_dxt1(self) -> None:
        levels = registry.ROLES.get("data").join(
            roles.split_data(smooth_rgba(64)), None, True
        )
        data = dds.build(64, 64, [bc1.encode(level) for level in levels], b"", "DXT1")
        parsed = dds.parse(data)
        self.assertEqual(
            (parsed.format, parsed.width, len(parsed.levels)),
            ("DXT1", 64, dds.full_mip_count(64, 64)),
        )
        self.assertEqual(parsed.levels[0].size, (64 // 4) ** 2 * 8)
        self.assertEqual(dds.describe(data).format, "DXT1")
        self.assertEqual(
            dds.describe(
                dds.build(
                    16,
                    16,
                    [bytes(dds.level_size(size, size)) for size in (16, 8, 4, 2, 1)],
                )
            ).format,
            "DXT5",
        )


class DdsTest(unittest.TestCase):
    def chain(self, size: int) -> list[bytes]:
        blobs = []
        while size >= 1:
            blobs.append(bytes(dds.level_size(size, size)))
            size //= 2
        return blobs

    def test_round_trip_keeps_size_levels_and_trailer(self) -> None:
        blobs = self.chain(16)
        texture = dds.parse(dds.build(16, 16, blobs, b"_NXD"))
        self.assertEqual((texture.width, texture.height), (16, 16))
        self.assertEqual(len(texture.levels), 5)
        self.assertEqual(texture.trailer, b"_NXD")
        self.assertEqual(texture.level_bytes(1), blobs[1])

    def test_full_mip_count(self) -> None:
        self.assertEqual(dds.full_mip_count(1024, 1024), 11)
        self.assertEqual(dds.full_mip_count(4096, 4096), 13)

    def test_wrong_level_size_is_rejected(self) -> None:
        blobs = self.chain(16)
        blobs[1] = blobs[1] + b"\0"
        with self.assertRaises(dds.DdsError):
            dds.build(16, 16, blobs)

    def test_truncated_file_is_rejected(self) -> None:
        data = dds.build(16, 16, self.chain(16))
        with self.assertRaises(dds.DdsError):
            dds.parse(data[:-1])

    def test_other_format_is_rejected(self) -> None:
        data = bytearray(dds.build(16, 16, self.chain(16)))
        data[84:88] = b"DXT3"
        with self.assertRaises(dds.DdsError):
            dds.parse(bytes(data))

    def test_not_a_dds_is_rejected(self) -> None:
        with self.assertRaises(dds.DdsError):
            dds.parse(b"PNG " + bytes(200))


class DiffuseRoleTest(unittest.TestCase):
    def test_split_and_join_give_the_picture_back(self) -> None:
        image = smooth_rgba(32)
        levels = roles.join_diffuse(roles.split_diffuse(image))
        self.assertEqual(len(levels), 6)
        self.assertEqual(levels[-1].shape, (1, 1, 4))
        self.assertLessEqual(
            int(np.abs(levels[0].astype(int) - image.astype(int)).max()), 1
        )

    def test_colour_mips_average_in_linear_light(self) -> None:
        image = np.zeros((2, 2, 4), dtype=np.uint8)
        image[0, :, :3] = 255
        image[0, :, 3] = 200
        small = roles.join_diffuse(roles.split_diffuse(image))[1][0, 0]
        # Half the light is 186 at gamma 2.2. Averaging the bytes would give 128.
        for channel in range(3):
            self.assertAlmostEqual(int(small[channel]), 186, delta=1)
        # The mask is not light. It averages as it is.
        self.assertEqual(int(small[3]), 100)

    def test_grey_planes_from_the_upscaler_are_accepted(self) -> None:
        image = smooth_rgba(16)
        planes = roles.split_diffuse(image)
        planes["alpha"] = np.repeat(planes["alpha"][:, :, None], 3, axis=2)
        level = roles.join_diffuse(planes)[0]
        self.assertTrue(np.array_equal(level[:, :, 3], image[:, :, 3]))

    def test_drift_against_the_source_is_removed(self) -> None:
        def light(color: np.ndarray) -> float:
            """Mean in linear light, the domain the match works in."""
            return float(((color.astype(np.float64) / 255.0) ** roles.GAMMA).mean())

        source = roles.split_diffuse(smooth_rgba(64, contrast=40))
        enlarged = {
            name: np.repeat(np.repeat(plane, 4, axis=0), 4, axis=1)
            for name, plane in source.items()
        }
        drifted = dict(
            enlarged, color=(enlarged["color"].astype(int) + 12).astype(np.uint8)
        )
        wanted = light(source["color"])
        plain = light(roles.join_diffuse(drifted)[0][:, :, :3])
        matched = light(roles.join_diffuse(drifted, source)[0][:, :, :3])
        self.assertGreater(plain - wanted, 0.03)
        self.assertLess(abs(matched - wanted), 0.003)

    def test_planes_of_different_size_are_rejected(self) -> None:
        planes = roles.split_diffuse(smooth_rgba(16))
        planes["alpha"] = planes["alpha"][:8, :8]
        with self.assertRaises(roles.RoleError):
            roles.join_diffuse(planes)


class NormalRoleTest(unittest.TestCase):
    def test_split_rebuilds_a_plain_normal_map(self) -> None:
        plane = roles.split_normal(swizzled_normal(32))["normal"]
        self.assertEqual(plane.shape, (32, 32, 3))
        # Z points out of the surface, so blue is the strong channel.
        self.assertGreater(int(plane[:, :, 2].min()), 200)

    def test_join_packs_the_game_layout_on_every_level(self) -> None:
        image = swizzled_normal(32)
        levels = roles.join_normal(roles.split_normal(image))
        self.assertEqual(len(levels), 6)
        for level in levels:
            self.assertTrue((level[:, :, 0] == roles.NORMAL_RED).all())
            self.assertTrue((level[:, :, 2] == roles.NORMAL_BLUE).all())
        difference = np.abs(levels[0].astype(int) - image.astype(int))
        self.assertLessEqual(int(difference.max()), 2)

    def test_flat_average_stays_unit_length(self) -> None:
        # Opposite tilts cancel. The small level must be flat, not a short vector.
        small = roles.join_normal(roles.split_normal(swizzled_normal(32)))[-1][0, 0]
        self.assertAlmostEqual(int(small[1]), 128, delta=2)
        self.assertAlmostEqual(int(small[3]), 128, delta=2)

    def test_a_texture_that_is_not_swizzled_is_rejected(self) -> None:
        image = swizzled_normal(16)
        image[:, :, 0] = 128
        with self.assertRaises(roles.RoleError):
            roles.split_normal(image)
        image = swizzled_normal(16)
        image[:, :, 2] = 200
        with self.assertRaises(roles.RoleError):
            roles.split_normal(image)


class NormalLayoutTest(unittest.TestCase):
    """The game fills red and blue of a normal map in two ways: red 255 and blue 0, or both a copy of green."""

    def copied(self, size: int = 16) -> np.ndarray:
        rgba = swizzled_normal(size)
        rgba[:, :, 0] = rgba[:, :, 2] = rgba[:, :, 1]
        return rgba

    def test_both_fillers_are_recognised(self) -> None:
        self.assertEqual(roles.normal_layout(swizzled_normal(16)), "fixed")
        self.assertEqual(roles.normal_layout(self.copied()), "copy")

    def test_the_split_does_not_depend_on_the_filler(self) -> None:
        self.assertTrue(
            np.array_equal(
                roles.split_normal(swizzled_normal(16))["normal"],
                roles.split_normal(self.copied())["normal"],
            )
        )

    def test_another_filler_is_rejected(self) -> None:
        rgba = swizzled_normal(16)
        rgba[:, :, 0] = (
            np.arange(16, dtype=np.uint8)[None, :] * 7
        )  # red is neither 255 nor a copy of green
        with self.assertRaises(roles.RoleError):
            roles.normal_layout(rgba)

    def test_a_copy_filler_is_written_back_and_a_fixed_one_is_left(self) -> None:
        level = swizzled_normal(16)
        out = roles.match_layout([level], "copy")[0]
        self.assertTrue(np.array_equal(out[:, :, 0], out[:, :, 1]))
        self.assertTrue(np.array_equal(out[:, :, 2], out[:, :, 1]))
        self.assertIs(roles.match_layout([level], "fixed")[0], level)


class DataRoleTest(unittest.TestCase):
    def test_data_keeps_every_channel(self) -> None:
        rgba = smooth_rgba(64, seed=5)
        role = registry.ROLES.get("data")
        levels = role.join(role.split(rgba), None, True)
        self.assertTrue(np.array_equal(levels[0], rgba))
        self.assertEqual(levels[-1].shape[:2], (1, 1))

    def test_data_mips_average_the_bytes(self) -> None:
        rgba = np.zeros((2, 2, 4), dtype=np.uint8)
        rgba[0, 0] = 200
        levels = roles.join_data(roles.split_data(rgba), None, True)
        self.assertEqual(levels[1][0, 0].tolist(), [50, 50, 50, 50])

    def test_a_free_red_normal_keeps_red_and_blue_and_the_tilt(self) -> None:
        rgba = free_red_normal(64)
        self.assertTrue(roles.has_free_red(rgba))
        with self.assertRaises(roles.RoleError):
            roles.normal_layout(rgba)
        role = registry.ROLES.get("normal_red")
        level = role.join(role.split(rgba), role.split(rgba), True)[0]
        self.assertTrue(np.array_equal(level[:, :, 0], rgba[:, :, 0]))
        self.assertEqual(int(level[:, :, 2].max()), 0)
        for channel in (1, 3):
            self.assertLessEqual(
                int(
                    np.abs(
                        level[:, :, channel].astype(int)
                        - rgba[:, :, channel].astype(int)
                    ).max()
                ),
                1,
            )

    def test_a_picture_with_blue_is_not_a_free_red_normal(self) -> None:
        with self.assertRaises(roles.RoleError):
            roles.split_normal_red(smooth_rgba(64))


class ShrinkTest(unittest.TestCase):
    def test_shrink_color_averages_in_linear_light(self) -> None:
        image = np.zeros((4, 4, 3), dtype=np.uint8)
        image[::2, ::2] = 255
        half = roles.shrink_color(image, 2)
        self.assertEqual(half.shape, (2, 2, 3))
        # A quarter of the light, not a quarter of the bytes (64).
        self.assertEqual(int(half[0, 0, 0]), round(255 * 0.25 ** (1 / roles.GAMMA)))
        self.assertTrue(np.array_equal(roles.shrink_color(image, 1), image))
        with self.assertRaises(roles.RoleError):
            roles.shrink_color(image, 3)


class FlipCellTest(unittest.TestCase):
    def picture(self) -> np.ndarray:
        # Four cells of 4x4, each of one value: 10, 20, 30, 40.
        return np.kron(
            np.array([[10, 20], [30, 40]], dtype=np.uint8),
            np.ones((4, 4), dtype=np.uint8),
        )

    def test_the_rim_of_a_cell_holds_only_that_cell(self) -> None:
        grown = flipbook.explode(self.picture(), (2, 2), 3)
        self.assertEqual(grown.shape, (20, 20))
        for row, column, value in ((0, 0, 10), (0, 1, 20), (1, 0, 30), (1, 1, 40)):
            cell = grown[row * 10 : (row + 1) * 10, column * 10 : (column + 1) * 10]
            self.assertEqual(set(cell.ravel().tolist()), {value})

    def test_cutting_the_rim_gives_the_picture_back(self) -> None:
        picture = np.arange(8 * 12 * 3, dtype=np.uint8).reshape(8, 12, 3)
        grown = flipbook.explode(picture, (3, 2), 2)
        self.assertEqual(grown.shape, (16, 24, 3))
        self.assertTrue(np.array_equal(flipbook.implode(grown, (3, 2), 2), picture))

    def test_a_picture_upscaled_whole_would_mix_the_cells(self) -> None:
        # The reason for the rim: without it, the edge of a cell borders the next cell.
        picture = self.picture()
        self.assertNotEqual(int(picture[0, 3]), int(picture[0, 4]))
        grown = flipbook.explode(picture, (2, 2), 3)
        self.assertEqual(int(grown[3, 9]), int(grown[3, 6]))


class LowFrequencyTest(unittest.TestCase):
    def source(self) -> np.ndarray:
        return smooth_rgba(64).astype(np.float32) / 255.0

    def enlarged(self, image: np.ndarray) -> np.ndarray:
        return np.repeat(np.repeat(image, 4, axis=0), 4, axis=1)

    def cell_error(self, result: np.ndarray, source: np.ndarray) -> float:
        cells = source.shape[0] // lowfreq.LOW_CELL
        wanted = lowfreq.cell_means(source, cells, cells)
        return float(np.abs(lowfreq.cell_means(result, cells, cells) - wanted).max())

    def test_a_uniform_shift_is_removed(self) -> None:
        source = self.source()
        result = self.enlarged(source) + 0.05
        self.assertGreater(self.cell_error(result, source), 0.04)
        self.assertLess(
            self.cell_error(lowfreq.match(result, source, True), source), 1e-4
        )

    def test_a_slow_drift_is_removed(self) -> None:
        # One wave over the whole texture, as a model that drifts by region gives.
        source = smooth_rgba(256).astype(np.float32) / 255.0
        wave = (
            0.1
            * np.sin(np.arange(1024, dtype=np.float32) * (2 * np.pi / 1024))[
                None, :, None
            ]
        )
        result = self.enlarged(source) + wave
        before = self.cell_error(result, source)
        after = self.cell_error(lowfreq.match(result, source, True), source)
        self.assertGreater(before, 0.08)
        self.assertLess(after, before / 20)

    def test_a_matching_result_is_left_alone(self) -> None:
        source = self.source()
        result = self.enlarged(source)
        self.assertLess(
            float(np.abs(lowfreq.match(result, source, True) - result).max()), 1e-5
        )

    def test_detail_inside_a_cell_is_kept(self) -> None:
        source = self.source()
        result = self.enlarged(source)
        detail = np.zeros_like(result)
        detail[::2, ::2] = 0.04
        detail[1::2, 1::2] = -0.04
        matched = lowfreq.match(result + detail + 0.05, source, True)
        # The checker pattern has no cell average, so it must come through whole.
        self.assertAlmostEqual(
            float((matched - result)[::2, ::2].mean()), 0.04, delta=0.005
        )
        self.assertAlmostEqual(
            float((matched - result)[1::2, 1::2].mean()), -0.04, delta=0.005
        )

    def test_a_side_that_does_not_divide_uses_one_cell(self) -> None:
        source = np.full((48, 48, 1), 0.5, dtype=np.float32)
        result = np.full((192, 192, 1), 0.7, dtype=np.float32)
        matched = lowfreq.match(result, source, False)
        self.assertAlmostEqual(float(matched.mean()), 0.5, delta=1e-4)


class MetricsTest(unittest.TestCase):
    def test_identical_pictures(self) -> None:
        image = smooth_rgba(16)
        self.assertEqual(metrics.channel_psnr(image, image), [99.0] * 4)
        self.assertEqual(metrics.rmse(image, image), 0.0)
        self.assertEqual(metrics.channel_correlation(image, image), [1.0] * 4)

    def test_inverted_and_constant_channels(self) -> None:
        image = smooth_rgba(16)
        other = image.copy()
        other[:, :, 0] = 255 - other[:, :, 0]
        other[:, :, 1] = 7
        correlation = metrics.channel_correlation(image, other)
        self.assertLess(correlation[0], -0.9)
        self.assertIsNone(correlation[1])

    def test_shrink_averages_blocks(self) -> None:
        image = np.zeros((4, 4, 1), dtype=np.uint8)
        image[:2, :2] = 200
        image[0, 2] = 100
        self.assertEqual(
            metrics.shrink(image, 2)[:, :, 0].tolist(), [[200, 25], [0, 0]]
        )

    def test_seam_ratio_tells_a_tiling_picture_from_a_ramp(self) -> None:
        self.assertLess(metrics.seam_ratio(smooth_rgba(64)), 2.0)
        ramp = np.repeat(np.arange(64, dtype=np.uint8)[None, :, None] * 4, 64, axis=0)
        self.assertGreater(metrics.seam_ratio(ramp), 10.0)


if __name__ == "__main__":
    unittest.main()
