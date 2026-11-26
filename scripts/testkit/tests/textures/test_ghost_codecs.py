"""DXT3 and uncompressed RGBA32, the formats StarCraft: Ghost adds (R-HD-152, SPEC-HD-TEXTURES 6.3)."""

from __future__ import annotations

import struct
import unittest

import numpy as np
from hdtex.core import dds, registry
from hdtex.ghost import codecs

from testkit.tests.textures.fixtures import colour_rgba


class Dxt3Test(unittest.TestCase):
    def test_round_trip_is_close(self) -> None:
        rgba = colour_rgba(3)
        back = codecs.DXT3.decode(codecs.DXT3.encode(rgba), 64, 64)
        self.assertEqual(back.shape, rgba.shape)
        # Alpha has 4 bits: within half a step of 17.
        self.assertLessEqual(int(np.abs(back[:, :, 3].astype(int) - rgba[:, :, 3]).max()), 9)
        self.assertLess(float(np.abs(back[:, :, :3].astype(int) - rgba[:, :, :3]).mean()), 6)

    def test_known_block(self) -> None:
        # Alpha nibbles 0..15, low nibble first; colour0 white, colour1 black, every index 0.
        alpha = bytes((2 * i) | ((2 * i + 1) << 4) for i in range(8))
        block = alpha + struct.pack("<HHI", 0xFFFF, 0x0000, 0)
        pixels = codecs.DXT3.decode(block, 4, 4)
        self.assertEqual(pixels[:, :, 3].flatten().tolist(), [17 * i for i in range(16)])
        self.assertTrue((pixels[:, :, :3] == 255).all())

    def test_colour_block_is_four_colour_always(self) -> None:
        # colour0 < colour1 makes DXT1 transparent at index 3; DXT3 draws the colour.
        block = bytes([0xFF] * 8) + struct.pack("<HHI", 0x0000, 0xFFFF, 0xFFFFFFFF)
        pixels = codecs.DXT3.decode(block, 4, 4)
        self.assertTrue((pixels[:, :, 3] == 255).all())
        self.assertTrue((pixels[:, :, :3] > 0).all())

    def test_size(self) -> None:
        self.assertEqual(codecs.DXT3.level_size(64, 64), 16 * 16 * 16)
        with self.assertRaises(ValueError):
            codecs.DXT3.decode(b"\0" * 15, 4, 4)


class Rgba32Test(unittest.TestCase):
    def test_round_trip_is_exact(self) -> None:
        rgba = colour_rgba(4)
        self.assertTrue((codecs.RGBA32.decode(codecs.RGBA32.encode(rgba), 64, 64) == rgba).all())

    def test_memory_order_is_bgra(self) -> None:
        rgba = np.array([[[1, 2, 3, 4]]], dtype=np.uint8)
        self.assertEqual(codecs.RGBA32.encode(rgba), bytes([3, 2, 1, 4]))

    def test_dds_header_masks(self) -> None:
        data = dds.build(64, 64, [codecs.RGBA32.encode(colour_rgba(5))], b"", "RGBA32")
        flags, _fourcc, bits, *masks = struct.unpack_from("<I4s5I", data, 80)
        self.assertEqual(bits, 32)
        self.assertEqual(tuple(masks), codecs.RGBA32_MASKS)
        self.assertEqual(flags & dds.PIXEL_FORMAT_FOURCC, 0)
        parsed = dds.parse(data)
        self.assertEqual((parsed.format, parsed.width), ("RGBA32", 64))

    def test_other_masks_are_refused(self) -> None:
        data = bytearray(dds.build(64, 64, [codecs.RGBA32.encode(colour_rgba(5))], b"", "RGBA32"))
        # Red and blue swapped: RGBA in memory, which no codec here reads.
        struct.pack_into("<II", data, 92, 0x000000FF, 0x0000FF00)
        struct.pack_into("<I", data, 100, 0x00FF0000)
        with self.assertRaisesRegex(dds.DdsError, "masks"):
            dds.parse(bytes(data))

    def test_registered(self) -> None:
        self.assertIs(registry.CODECS.get("DXT3"), codecs.DXT3)
        self.assertIs(registry.CODECS.get("RGBA32"), codecs.RGBA32)
        self.assertFalse(registry.CODECS.has("DXT2"))


if __name__ == "__main__":
    unittest.main()
