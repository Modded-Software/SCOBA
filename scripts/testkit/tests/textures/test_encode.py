"""A result keeps its original's layout, and its numbers decide whether it is blocked (R-HD-10 to 13, 52, 90, 91)."""

from __future__ import annotations

import unittest

import numpy as np
from hdtex.core import dds, encode, limits, roles

from testkit.tests.textures.fixtures import (
    SIZE,
    TRAILER,
    colour_rgba,
    invert,
    noise_rgba,
    normal_rgba,
    planes_of,
    repeat,
    smooth,
    texture_file,
)

SOUND = {
    "encode_psnr": [40.0, 41.0, 42.0, 99.0],
    "fidelity_psnr": [30.0, 30.0, 30.0, 30.0],
    "fidelity_corr": [0.9, 0.9, 0.9, 0.9],
    "coarse_rmse": 0.5,
    "seam_source": 1.0,
    "seam": 1.2,
}


def result_of(
    role: str, rgba: np.ndarray, enlarge, format: str = "DXT5", trailer: bytes = b""
) -> encode.Encoded:
    return encode.encode(
        texture_file(role, rgba, format, trailer),
        roles.ROLES.get(role),
        planes_of(role, rgba, enlarge),
    )


class LayoutTest(unittest.TestCase):
    def test_a_result_has_the_format_the_trailer_and_a_full_mip_chain(self) -> None:
        for format in ("DXT5", "DXT1"):
            rgba = colour_rgba()
            rgba[:, :, 3] = 255
            made = result_of("diffuse", rgba, repeat, format, TRAILER)
            self.assertEqual(
                (made.format, made.size, made.source_size),
                (format, (SIZE * 4, SIZE * 4), (SIZE, SIZE)),
            )
            texture = dds.parse(made.files[SIZE * 4])
            self.assertEqual(
                (texture.format, texture.width, texture.height, texture.trailer),
                (format, SIZE * 4, SIZE * 4, TRAILER),
            )
            self.assertEqual(
                len(texture.levels), dds.full_mip_count(SIZE * 4, SIZE * 4)
            )
            self.assertEqual(made.mips, len(texture.levels))

    def test_a_normal_map_keeps_its_channels(self) -> None:
        made = result_of("normal", normal_rgba(), repeat)
        _texture, rgba = encode.read_texture(made.files[SIZE * 4])
        self.assertGreaterEqual(int(rgba[:, :, 0].min()), 247)
        self.assertLessEqual(int(rgba[:, :, 2].max()), 8)
        self.assertGreater(int(rgba[:, :, 3].std()), 0)
        self.assertEqual(limits.missed(made.numbers, tiles=False), [])

    def test_a_smaller_size_is_the_same_chain_without_its_largest_levels(self) -> None:
        rgba = colour_rgba(width=512, height=16)
        made = result_of("diffuse", rgba, repeat)
        self.assertEqual(sorted(made.files), [1024, 2048])
        large, small = dds.parse(made.files[2048]), dds.parse(made.files[1024])
        self.assertEqual(
            (small.width, small.height, len(small.levels)),
            (1024, 32, len(large.levels) - 1),
        )
        for index in range(len(small.levels)):
            self.assertEqual(small.level_bytes(index), large.level_bytes(index + 1))

    def test_a_small_result_is_kept_at_its_own_size_and_its_half(self) -> None:
        self.assertEqual(
            sorted(result_of("diffuse", colour_rgba(), repeat).files),
            [SIZE * 2, SIZE * 4],
            "4x and the 2x a request may ask for; negative: no smaller level",
        )

    def test_transparent_pixels_in_an_opaque_format_are_refused(self) -> None:
        rgba = colour_rgba()
        rgba[:, :, 3] = 255
        original = texture_file("diffuse", rgba, "DXT1")
        self.assertEqual(
            int(
                encode.read_texture(
                    result_of("diffuse", rgba, repeat, "DXT1").files[SIZE * 4]
                )[1][:, :, 3].min()
            ),
            255,
        )
        source, _decoded = encode.read_texture(original)
        blocks = bytearray(original)
        # Endpoint 0 not above endpoint 1 and index 3: a transparent pixel.
        start = source.levels[0].offset
        blocks[start : start + 8] = bytes([0, 0, 0, 0, 255, 255, 255, 255])
        with self.assertRaises(encode.EncodeError):
            encode.encode(
                bytes(blocks),
                roles.ROLES.get("diffuse"),
                planes_of("diffuse", rgba, repeat),
            )

    def test_planes_of_another_shape_are_refused(self) -> None:
        rgba = colour_rgba()
        planes = {
            name: plane[:, : SIZE * 2]
            for name, plane in planes_of("diffuse", rgba, repeat).items()
        }
        with self.assertRaises(encode.EncodeError):
            encode.encode(
                texture_file("diffuse", rgba), roles.ROLES.get("diffuse"), planes
            )


class MeasuredTest(unittest.TestCase):
    def test_a_faithful_result_that_tiles_misses_nothing(self) -> None:
        made = result_of("diffuse", colour_rgba(), smooth)
        self.assertEqual(limits.missed(made.numbers, tiles=True), [])

    def test_a_seam_blocks_a_texture_that_tiles_and_no_other(self) -> None:
        made = result_of("diffuse", colour_rgba(), repeat)
        missed = limits.missed(made.numbers, tiles=True)
        self.assertEqual([miss["limit"] for miss in missed], ["seam"])
        self.assertGreater(missed[0]["value"], missed[0]["bound"])
        self.assertEqual(limits.missed(made.numbers, tiles=False), [])

    def test_another_picture_is_blocked_with_the_number_and_the_bound(self) -> None:
        made = result_of("data", noise_rgba(), invert)
        missed = {
            miss["limit"]: miss for miss in limits.missed(made.numbers, tiles=False)
        }
        self.assertIn("correlation", missed)
        self.assertLess(missed["correlation"]["value"], 0)
        self.assertEqual(missed["correlation"]["bound"], limits.MIN_CORRELATION)


class LimitTest(unittest.TestCase):
    def missed(self, tiles: bool = True, **changed) -> list[str]:
        return [miss["limit"] for miss in limits.missed({**SOUND, **changed}, tiles)]

    def test_sound_numbers_miss_nothing(self) -> None:
        self.assertEqual(self.missed(), [])

    def test_each_limit_is_missed_on_its_own(self) -> None:
        self.assertEqual(
            self.missed(encode_psnr=[40.0, 34.9, 42.0, 99.0]), ["encode_psnr"]
        )
        self.assertEqual(
            self.missed(fidelity_corr=[0.9, 0.69, 0.9, 0.9]), ["correlation"]
        )
        self.assertEqual(self.missed(coarse_rmse=1.51), ["coarse_rmse"])
        self.assertEqual(self.missed(seam=1.51), ["seam"])

    def test_the_bounds_themselves_pass(self) -> None:
        self.assertEqual(
            self.missed(
                encode_psnr=[35.0] * 4,
                fidelity_corr=[0.7] * 4,
                coarse_rmse=1.5,
                seam=1.5,
            ),
            [],
        )

    def test_the_seam_limit_is_for_textures_that_tile(self) -> None:
        self.assertEqual(self.missed(tiles=False, seam=9.0), [])
        self.assertEqual(
            self.missed(tiles=False, seam=9.0, coarse_rmse=2.0), ["coarse_rmse"]
        )

    def test_an_original_with_a_seam_of_its_own_allows_more(self) -> None:
        self.assertEqual(self.missed(seam_source=2.0, seam=2.9), [])
        self.assertEqual(self.missed(seam_source=2.0, seam=3.1), ["seam"])

    def test_a_seam_without_a_ratio(self) -> None:
        self.assertEqual(self.missed(seam=None), ["seam"])
        self.assertEqual(self.missed(seam_source=None, seam=None), [])

    def test_a_flat_channel_is_proven_by_its_error_not_its_correlation(self) -> None:
        self.assertEqual(
            self.missed(
                fidelity_corr=[0.9, 0.09, 0.9, None],
                fidelity_psnr=[30.0, 53.7, 30.0, 99.0],
            ),
            [],
        )
        self.assertEqual(
            self.missed(
                fidelity_corr=[0.9, 0.09, 0.9, None],
                fidelity_psnr=[30.0, 49.0, 30.0, 99.0],
            ),
            ["correlation"],
        )
        self.assertEqual(self.missed(fidelity_corr=[None] * 4), [])
