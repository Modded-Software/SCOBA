"""The registry: ids, and a texture format that plugs in with no edit to the core (R-HD-109, R-HD-110)."""

from __future__ import annotations

import unittest

import numpy as np
from hdtex.core import dds, registry, roles
from hdtex.core.registry import RegistryError, Table


class PlainCodec:
    """A second format: every pixel as four bytes."""

    id = "RAW4"
    opaque = False
    masks = None  # named by a FourCC

    def level_size(self, width: int, height: int) -> int:
        return width * height * 4

    def decode(self, data: bytes, width: int, height: int) -> np.ndarray:
        return np.frombuffer(data, dtype=np.uint8).reshape(height, width, 4).copy()

    def encode(self, rgba: np.ndarray) -> bytes:
        return rgba.tobytes()


class TableTest(unittest.TestCase):
    def test_an_unknown_id_is_refused_and_the_known_ones_are_named(self) -> None:
        table: Table[int] = Table("thing")
        table.add("b", 2)
        table.add("a", 1)
        with self.assertRaises(RegistryError) as caught:
            table.get("c")
        self.assertEqual(str(caught.exception), "unknown thing c; known: a, b")
        self.assertFalse(table.has("c"))
        self.assertEqual(table.ids(), ("a", "b"))

    def test_an_id_cannot_be_taken_twice(self) -> None:
        table: Table[object] = Table("thing")
        first = table.add("a", object())
        self.assertIs(table.add("a", first), first)
        with self.assertRaises(RegistryError):
            table.add("a", object())


class CoreFormatsTest(unittest.TestCase):
    def test_the_core_brings_dxt1_and_dxt5_and_the_four_roles(self) -> None:
        # A game may register more formats from its own package (Ghost: SPEC-HD-TEXTURES 6.3).
        core = sorted(key for key, codec in registry.CODECS.items.items() if type(codec).__module__ == "hdtex.core.codecs")
        self.assertEqual(core, ["DXT1", "DXT5"])
        self.assertEqual(
            roles.ROLES.ids(), ("data", "diffuse", "normal", "normal_red")
        )
        self.assertTrue(registry.CODECS.get("DXT1").opaque)
        self.assertFalse(registry.CODECS.get("DXT5").opaque)

    def test_only_the_colour_plane_of_a_role_is_colour(self) -> None:
        colour = {
            role: [
                plane.name for plane in roles.ROLES.get(role).planes if plane.colour
            ]
            for role in roles.ROLES.ids()
        }
        self.assertEqual(
            colour, {"data": [], "diffuse": ["color"], "normal": [], "normal_red": []}
        )


class SecondFormatTest(unittest.TestCase):
    def setUp(self) -> None:
        registry.CODECS.add(PlainCodec.id, PlainCodec())
        self.addCleanup(registry.CODECS.items.pop, PlainCodec.id)
        rng = np.random.default_rng(3)
        self.levels = [
            rng.integers(0, 256, (size, size, 4), dtype=np.uint8) for size in (4, 2, 1)
        ]

    def test_a_registered_format_is_written_and_read_back(self) -> None:
        codec = registry.CODECS.get(PlainCodec.id)
        data = dds.build(
            4, 4, [codec.encode(level) for level in self.levels], b"tail", PlainCodec.id
        )
        texture = dds.parse(data)
        self.assertEqual(
            (texture.format, texture.width, len(texture.levels), texture.trailer),
            ("RAW4", 4, 3, b"tail"),
        )
        for index, level in enumerate(self.levels):
            decoded = texture.codec.decode(
                texture.level_bytes(index), level.shape[1], level.shape[0]
            )
            self.assertTrue(np.array_equal(decoded, level))

    def test_a_format_nobody_registered_is_refused(self) -> None:
        codec = registry.CODECS.get(PlainCodec.id)
        data = dds.build(
            4, 4, [codec.encode(level) for level in self.levels], b"", PlainCodec.id
        )
        registry.CODECS.items.pop(PlainCodec.id)
        self.addCleanup(registry.CODECS.add, PlainCodec.id, codec)
        with self.assertRaises(dds.DdsError):
            dds.parse(data)
        with self.assertRaises(dds.DdsError):
            dds.build(4, 4, [b""], b"", PlainCodec.id)
