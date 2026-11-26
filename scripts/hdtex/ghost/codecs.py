"""The formats StarCraft: Ghost needs past the core's: DXT3, and 32-bit RGBA without compression (SPEC-HD-TEXTURES 6.3).

A DXT3 block is 16 bytes for 4x4 pixels: 4 bits of alpha per pixel, row by
row, the low nibble first; then a colour block read in four-colour mode
always, as the colour block of BC3.

The uncompressed layout keeps B, G, R, A in memory: the masks FF0000,
FF00, FF and FF000000 of the DDS header.
"""

from __future__ import annotations

import numpy as np

from ..core import bc3
from ..core.registry import CODECS

DXT3_BLOCK = 16
RGBA32_MASKS = (0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000)


class Dxt3:
    id = "DXT3"
    opaque = False
    masks = None  # named by a FourCC

    def level_size(self, width: int, height: int) -> int:
        return bc3.block_count(width, height) * DXT3_BLOCK

    def decode(self, data: bytes, width: int, height: int) -> np.ndarray:
        count = bc3.block_count(width, height)
        if len(data) != count * DXT3_BLOCK:
            raise ValueError(f"{width}x{height} DXT3 needs {count * DXT3_BLOCK} bytes, got {len(data)}")
        blocks = np.frombuffer(data, dtype=np.uint8).reshape(count, DXT3_BLOCK)
        nibbles = np.empty((count, 16), dtype=np.uint8)
        nibbles[:, 0::2] = blocks[:, 0:8] & 0x0F
        nibbles[:, 1::2] = blocks[:, 0:8] >> 4
        pixels = np.empty((count, 16, 4), dtype=np.uint8)
        pixels[:, :, 3] = nibbles * 17
        pixels[:, :, :3] = bc3._decode_color(blocks[:, 8:16])
        return bc3._from_blocks(pixels, width, height)

    def encode(self, rgba: np.ndarray) -> bytes:
        if rgba.ndim != 3 or rgba.shape[2] != 4 or rgba.dtype != np.uint8:
            raise ValueError(f"encode needs an (H, W, 4) uint8 image, got {rgba.shape} {rgba.dtype}")
        blocks = bc3._to_blocks(rgba)
        out = np.empty((blocks.shape[0], DXT3_BLOCK), dtype=np.uint8)
        for start in range(0, blocks.shape[0], bc3.CHUNK_BLOCKS):
            chunk = blocks[start : start + bc3.CHUNK_BLOCKS]
            alpha = ((chunk[:, :, 3].astype(np.uint16) * 15 + 127) // 255).astype(np.uint8)
            out[start : start + bc3.CHUNK_BLOCKS, 0:8] = alpha[:, 0::2] | (alpha[:, 1::2] << 4)
            out[start : start + bc3.CHUNK_BLOCKS, 8:16] = bc3._encode_color(chunk[:, :, :3].astype(np.float32))
        return out.tobytes()


class Rgba32:
    id = "RGBA32"
    opaque = False
    masks = RGBA32_MASKS

    def level_size(self, width: int, height: int) -> int:
        return width * height * 4

    def decode(self, data: bytes, width: int, height: int) -> np.ndarray:
        if len(data) != width * height * 4:
            raise ValueError(f"{width}x{height} RGBA32 needs {width * height * 4} bytes, got {len(data)}")
        bgra = np.frombuffer(data, dtype=np.uint8).reshape(height, width, 4)
        return bgra[:, :, [2, 1, 0, 3]].copy()

    def encode(self, rgba: np.ndarray) -> bytes:
        if rgba.ndim != 3 or rgba.shape[2] != 4 or rgba.dtype != np.uint8:
            raise ValueError(f"encode needs an (H, W, 4) uint8 image, got {rgba.shape} {rgba.dtype}")
        return np.ascontiguousarray(rgba[:, :, [2, 1, 0, 3]]).tobytes()


DXT3 = CODECS.add(Dxt3.id, Dxt3())
RGBA32 = CODECS.add(Rgba32.id, Rgba32())
