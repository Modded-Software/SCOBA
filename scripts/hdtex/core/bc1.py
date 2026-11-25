"""BC1 (DXT1) block codec.

A BC1 block is 8 bytes for 4x4 pixels: the colour block of BC3 alone.
Endpoint 0 above endpoint 1 gives four colours. Otherwise the block has
three colours, and index 3 is transparent black.

The encoder writes four-colour blocks only, so its output is opaque. A
block of one colour has equal endpoints and index 0, which is opaque too.
"""

from __future__ import annotations

import numpy as np

from . import bc3

BLOCK_BYTES = 8


def encode(image: np.ndarray) -> bytes:
    """Encode an (H, W, 4) uint8 RGBA image as BC1 blocks. Alpha is not stored."""
    if image.ndim != 3 or image.shape[2] != 4 or image.dtype != np.uint8:
        raise ValueError(
            f"encode needs an (H, W, 4) uint8 image, got {image.shape} {image.dtype}"
        )
    blocks = bc3._to_blocks(image)
    out = np.empty((blocks.shape[0], BLOCK_BYTES), dtype=np.uint8)
    for start in range(0, blocks.shape[0], bc3.CHUNK_BLOCKS):
        chunk = blocks[start : start + bc3.CHUNK_BLOCKS].astype(np.float32)
        out[start : start + bc3.CHUNK_BLOCKS] = bc3._encode_color(chunk[:, :, :3])
    return out.tobytes()


def decode(data: bytes, width: int, height: int) -> np.ndarray:
    """Decode BC1 blocks to an (H, W, 4) uint8 RGBA image. Alpha is 255, or 0 for a transparent pixel."""
    count = bc3.block_count(width, height)
    if len(data) != count * BLOCK_BYTES:
        raise ValueError(
            f"{width}x{height} BC1 needs {count * BLOCK_BYTES} bytes, got {len(data)}"
        )
    blocks = np.frombuffer(data, dtype=np.uint8).reshape(count, BLOCK_BYTES)
    packed0 = np.ascontiguousarray(blocks[:, 0:2]).view("<u2")[:, 0]
    packed1 = np.ascontiguousarray(blocks[:, 2:4]).view("<u2")[:, 0]
    wide0 = bc3._expand_565(packed0).astype(np.int32)
    wide1 = bc3._expand_565(packed1).astype(np.int32)
    four = np.stack(
        [wide0, wide1, (2 * wide0 + wide1 + 1) // 3, (wide0 + 2 * wide1 + 1) // 3],
        axis=1,
    )
    three = np.stack([wide0, wide1, (wide0 + wide1) // 2, np.zeros_like(wide0)], axis=1)
    has_four = packed0 > packed1
    palette = np.where(has_four[:, None, None], four, three)
    bits = np.ascontiguousarray(blocks[:, 4:8]).view("<u4")[:, 0]
    shifts = (2 * np.arange(16, dtype=np.uint32))[None, :]
    index = ((bits[:, None] >> shifts) & np.uint32(3)).astype(np.int64)
    pixels = np.empty((count, 16, 4), dtype=np.uint8)
    pixels[:, :, :3] = np.take_along_axis(palette, index[:, :, None], axis=1).astype(
        np.uint8
    )
    pixels[:, :, 3] = np.where(has_four[:, None] | (index != 3), 255, 0)
    return bc3._from_blocks(pixels, width, height)
