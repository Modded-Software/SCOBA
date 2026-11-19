"""Host tests of the engine ground bake (terrain/sync_height.py)."""

from __future__ import annotations

import os
import struct
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from terrain import sync_height as S


def smap(n: int) -> bytes:
    head = bytearray(64)
    struct.pack_into("<4sIII", head, 0, b"SMAP", 102, n, n)
    struct.pack_into("<I", head, 28, 4096)
    return bytes(head) + struct.pack("<HH", 900, 1) * (n * n)


class EncodeTests(unittest.TestCase):
    def test_round_trip(self) -> None:
        z = np.array([[0.0, 1.5], [12.25, 30.0]])
        np.testing.assert_allclose(S.decode(S.encode(z)), z, atol=1.0 / S.SYNC_UNITS)

    def test_clamped(self) -> None:
        self.assertEqual(int(S.encode(np.array([-5.0]))[0]), 0)
        self.assertEqual(int(S.encode(np.array([1e6]))[0]), 65535)


class RenderTests(unittest.TestCase):
    def test_layout(self) -> None:
        z = np.full((S.NEW_VERTS, S.NEW_VERTS), 2.0)
        out = S.render(smap(129), z)
        magic, _v, sx, sy = struct.unpack_from("<4sIII", out, 0)
        self.assertEqual((magic, sx, sy), (b"SMAP", 257, 257))
        n = 257 * 257
        self.assertEqual(len(out), 64 + 4 * n)
        # Header kept past the size; one (height, 1) record per vertex.
        self.assertEqual(struct.unpack_from("<I", out, 28)[0], 4096)
        self.assertEqual(struct.unpack_from("<HH", out, 64), (512, 1))
        self.assertEqual(struct.unpack_from("<HH", out, 64 + 4 * (n - 1)), (512, 1))
        self.assertTrue((S.heights_of(out) == 512).all())

    def test_rejects(self) -> None:
        with self.assertRaises(ValueError):
            S.render(b"HMAP" + smap(129)[4:], np.zeros((257, 257)))
        with self.assertRaises(ValueError):
            S.render(smap(129), np.zeros((129, 129)))
        # Negative: the old u16 grid + two byte grids reading.
        with self.assertRaises(ValueError):
            S.render(smap(129)[:-4], np.zeros((257, 257)))

    def test_editor_map_layout(self) -> None:
        # The committed editor map: every record's second u16 is 1.
        from project_root import project_root

        data = (project_root() / "src" / "SCOBA.SC2Map" / "t3SyncHeightMap").read_bytes()
        _m, _v, sx, sy = struct.unpack_from("<4sIII", data, 0)
        self.assertEqual(len(data), 64 + 4 * sx * sy)
        flags = np.frombuffer(data, dtype="<u2", offset=64, count=sx * sy * 2)[1::2]
        self.assertTrue((flags == 1).all())


class ProblemsTests(unittest.TestCase):
    def test_off_requires_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {S.ENV: "0"}):
            self.assertEqual(S.problems(Path(tmp)), [])
            (Path(tmp) / "t3SyncHeightMap").write_bytes(b"x")
            self.assertTrue(S.problems(Path(tmp)))

    def test_on_requires_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {S.ENV: "1"}):
            self.assertTrue(S.problems(Path(tmp)))

    def test_on_by_default(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(S.ENV, None)
            self.assertTrue(S.enabled())


if __name__ == "__main__":
    unittest.main()
