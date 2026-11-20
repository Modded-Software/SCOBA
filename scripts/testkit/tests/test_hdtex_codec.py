from __future__ import annotations

import unittest

import numpy as np

from hdtex import bc3, dds, lowfreq, metrics, roles, variants


def smooth_rgba(size: int, seed: int = 1, contrast: int = 90) -> np.ndarray:
    """A tiling picture with soft detail in every channel."""
    rng = np.random.default_rng(seed)
    angle = np.arange(size) * (2 * np.pi / size)
    wave = np.sin(angle)[:, None] * np.cos(angle * 2)[None, :]
    planes = [128 + contrast * np.roll(wave, shift, axis=1) for shift in (0, size // 4, size // 2, size // 8)]
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
        self.assertLessEqual(int(np.abs(levels[0].astype(int) - image.astype(int)).max()), 1)

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
        enlarged = {name: np.repeat(np.repeat(plane, 4, axis=0), 4, axis=1) for name, plane in source.items()}
        drifted = dict(enlarged, color=(enlarged["color"].astype(int) + 12).astype(np.uint8))
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


class RoleTableTest(unittest.TestCase):
    def test_limit_size_drops_the_largest_levels(self) -> None:
        levels = roles.join_diffuse(roles.split_diffuse(smooth_rgba(32)))
        kept = roles.limit_size(levels, 8)
        self.assertEqual(kept[0].shape[:2], (8, 8))
        self.assertEqual(len(kept), 4)
        self.assertEqual(len(roles.limit_size(levels, 4096)), len(levels))

    def test_limit_size_needs_a_positive_size(self) -> None:
        with self.assertRaises(ValueError):
            roles.limit_size([np.zeros((4, 4, 4), dtype=np.uint8)], 0)

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

    def test_every_variant_input_names_a_built_variant_and_a_plane(self) -> None:
        planes = {plane.name for role in roles.ROLES.values() for plane in role.planes}
        for key, variant in variants.VARIANTS.items():
            for plane, given in variant.inputs.items():
                self.assertIn(plane, planes, key)
                self.assertIn(given.variant, variants.VARIANTS, key)
                self.assertNotEqual(given.variant, key)
                self.assertFalse(variants.VARIANTS[given.variant].inputs, "inputs must not chain")
        self.assertEqual(variants.VARIANTS["generative"].inputs, {"color": variants.Input("upscale", 2)})

    def test_every_variant_gives_every_plane_a_model(self) -> None:
        planes = {plane.name for role in roles.ROLES.values() for plane in role.planes}
        for key, variant in variants.VARIANTS.items():
            self.assertEqual(set(variant.planes), planes, key)
            for texture in variant.textures:
                self.assertIn(texture.rsplit(".", 1)[-1], planes, texture)


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
        self.assertLess(self.cell_error(lowfreq.match(result, source, True), source), 1e-4)

    def test_a_slow_drift_is_removed(self) -> None:
        # One wave over the whole texture, as a model that drifts by region gives.
        source = smooth_rgba(256).astype(np.float32) / 255.0
        wave = 0.1 * np.sin(np.arange(1024, dtype=np.float32) * (2 * np.pi / 1024))[None, :, None]
        result = self.enlarged(source) + wave
        before = self.cell_error(result, source)
        after = self.cell_error(lowfreq.match(result, source, True), source)
        self.assertGreater(before, 0.08)
        self.assertLess(after, before / 20)

    def test_a_matching_result_is_left_alone(self) -> None:
        source = self.source()
        result = self.enlarged(source)
        self.assertLess(float(np.abs(lowfreq.match(result, source, True) - result).max()), 1e-5)

    def test_detail_inside_a_cell_is_kept(self) -> None:
        source = self.source()
        result = self.enlarged(source)
        detail = np.zeros_like(result)
        detail[::2, ::2] = 0.04
        detail[1::2, 1::2] = -0.04
        matched = lowfreq.match(result + detail + 0.05, source, True)
        # The checker pattern has no cell average, so it must come through whole.
        self.assertAlmostEqual(float((matched - result)[::2, ::2].mean()), 0.04, delta=0.005)
        self.assertAlmostEqual(float((matched - result)[1::2, 1::2].mean()), -0.04, delta=0.005)

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
        self.assertEqual(metrics.shrink(image, 2)[:, :, 0].tolist(), [[200, 25], [0, 0]])

    def test_seam_ratio_tells_a_tiling_picture_from_a_ramp(self) -> None:
        self.assertLess(metrics.seam_ratio(smooth_rgba(64)), 2.0)
        ramp = np.repeat(np.arange(64, dtype=np.uint8)[None, :, None] * 4, 64, axis=0)
        self.assertGreater(metrics.seam_ratio(ramp), 10.0)


if __name__ == "__main__":
    unittest.main()
