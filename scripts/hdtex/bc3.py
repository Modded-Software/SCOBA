"""BC3 (DXT5) block codec.

A BC3 block is 16 bytes for 4x4 pixels: an 8-byte alpha block, then an
8-byte colour block. The encoder fits each block twice: a range fit along
the principal colour axis, then one least-squares refit of the endpoints.
The better of the two is kept per block.
"""

from __future__ import annotations

import numpy as np

BLOCK_BYTES = 16
CHUNK_BLOCKS = 1 << 16  # blocks encoded per pass, bounds peak memory

# Share of endpoint 0 in each palette entry, by index.
COLOR_WEIGHTS = np.array([1.0, 0.0, 2.0 / 3.0, 1.0 / 3.0], dtype=np.float32)
ALPHA_WEIGHTS = np.array([1.0, 0.0, 6 / 7, 5 / 7, 4 / 7, 3 / 7, 2 / 7, 1 / 7], dtype=np.float32)


def padded_size(length: int) -> int:
    return max(4, (length + 3) // 4 * 4)


def block_count(width: int, height: int) -> int:
    return (padded_size(width) // 4) * (padded_size(height) // 4)


def _to_blocks(image: np.ndarray) -> np.ndarray:
    """(H, W, 4) to (N, 16, 4). Edges are repeated up to a multiple of four."""
    height, width = image.shape[:2]
    pad_h, pad_w = padded_size(height) - height, padded_size(width) - width
    if pad_h or pad_w:
        image = np.pad(image, ((0, pad_h), (0, pad_w), (0, 0)), mode="edge")
    height, width = image.shape[:2]
    blocks = image.reshape(height // 4, 4, width // 4, 4, 4).swapaxes(1, 2)
    return blocks.reshape(-1, 16, 4)


def _from_blocks(blocks: np.ndarray, width: int, height: int) -> np.ndarray:
    full_h, full_w = padded_size(height), padded_size(width)
    image = blocks.reshape(full_h // 4, full_w // 4, 4, 4, 4).swapaxes(1, 2)
    return image.reshape(full_h, full_w, 4)[:height, :width]


def _quantize_565(color: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Round (N, 3) colours to RGB565. Returns the packed value and the 8-bit colour."""
    color = np.clip(color, 0.0, 255.0)
    r = np.rint(color[:, 0] * (31.0 / 255.0)).astype(np.uint16)
    g = np.rint(color[:, 1] * (63.0 / 255.0)).astype(np.uint16)
    b = np.rint(color[:, 2] * (31.0 / 255.0)).astype(np.uint16)
    packed = (r << 11) | (g << 5) | b
    return packed, _expand_565(packed)


def _expand_565(packed: np.ndarray) -> np.ndarray:
    r = (packed >> 11) & 31
    g = (packed >> 5) & 63
    b = packed & 31
    wide = np.stack([(r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)], axis=-1)
    return wide.astype(np.float32)


def _nearest(pixels: np.ndarray, palette: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Nearest palette entry per pixel. Returns indices (N, 16) and block error (N,)."""
    distance = ((pixels[:, :, None, :] - palette[:, None, :, :]) ** 2).sum(axis=3)
    index = distance.argmin(axis=2)
    error = np.take_along_axis(distance, index[:, :, None], axis=2)[:, :, 0].sum(axis=1)
    return index, error


def _refit(pixels: np.ndarray, weight: np.ndarray, fallback0: np.ndarray, fallback1: np.ndarray):
    """Least-squares endpoints for fixed indices. `weight` is the share of endpoint 0."""
    other = 1.0 - weight
    aa = (weight * weight).sum(axis=1)
    bb = (other * other).sum(axis=1)
    ab = (weight * other).sum(axis=1)
    det = aa * bb - ab * ab
    solvable = det > 1e-4
    safe = np.where(solvable, det, 1.0)
    pa = (weight[:, :, None] * pixels).sum(axis=1)
    pb = (other[:, :, None] * pixels).sum(axis=1)
    end0 = (bb[:, None] * pa - ab[:, None] * pb) / safe[:, None]
    end1 = (aa[:, None] * pb - ab[:, None] * pa) / safe[:, None]
    end0 = np.where(solvable[:, None], end0, fallback0)
    end1 = np.where(solvable[:, None], end1, fallback1)
    return end0, end1


def _color_fit(pixels: np.ndarray, end0: np.ndarray, end1: np.ndarray):
    packed0, wide0 = _quantize_565(end0)
    packed1, wide1 = _quantize_565(end1)
    palette = (
        wide0[:, None, :] * COLOR_WEIGHTS[None, :, None]
        + wide1[:, None, :] * (1.0 - COLOR_WEIGHTS)[None, :, None]
    )
    index, error = _nearest(pixels, palette)
    return packed0, packed1, index, error


def _encode_color(pixels: np.ndarray) -> np.ndarray:
    """(N, 16, 3) float32 to (N, 8) uint8 colour blocks, always in four-colour mode."""
    mean = pixels.mean(axis=1)
    centred = pixels - mean[:, None, :]
    covariance = np.einsum("nij,nik->njk", centred, centred)
    axis = pixels.max(axis=1) - pixels.min(axis=1)
    for _ in range(4):
        axis = np.einsum("njk,nk->nj", covariance, axis)
        norm = np.linalg.norm(axis, axis=1, keepdims=True)
        axis = np.where(norm > 1e-6, axis / np.maximum(norm, 1e-6), 0.0)
    along = np.einsum("nij,nj->ni", centred, axis)
    end0 = mean + axis * along.max(axis=1, keepdims=True)
    end1 = mean + axis * along.min(axis=1, keepdims=True)

    packed0, packed1, index, error = _color_fit(pixels, end0, end1)
    refit0, refit1 = _refit(pixels, COLOR_WEIGHTS[index], end0, end1)
    again0, again1, again_index, again_error = _color_fit(pixels, refit0, refit1)
    better = again_error < error
    packed0 = np.where(better, again0, packed0)
    packed1 = np.where(better, again1, packed1)
    index = np.where(better[:, None], again_index, index)

    # Four-colour mode needs endpoint 0 above endpoint 1. Swapping the
    # endpoints swaps index 0 with 1 and index 2 with 3.
    swap = packed0 < packed1
    packed0, packed1 = np.where(swap, packed1, packed0), np.where(swap, packed0, packed1)
    index = np.where(swap[:, None], index ^ 1, index)
    index = np.where((packed0 == packed1)[:, None], 0, index)

    shifts = (2 * np.arange(16, dtype=np.uint32))[None, :]
    bits = (index.astype(np.uint32) << shifts).sum(axis=1, dtype=np.uint32)
    out = np.empty((pixels.shape[0], 8), dtype=np.uint8)
    out[:, 0:2] = packed0.astype("<u2").view(np.uint8).reshape(-1, 2)
    out[:, 2:4] = packed1.astype("<u2").view(np.uint8).reshape(-1, 2)
    out[:, 4:8] = bits.astype("<u4").view(np.uint8).reshape(-1, 4)
    return out


def _alpha_fit(values: np.ndarray, high: np.ndarray, low: np.ndarray):
    high = np.clip(np.rint(high), 0, 255)
    low = np.clip(np.rint(low), 0, 255)
    high, low = np.maximum(high, low), np.minimum(high, low)
    palette = high[:, None] * ALPHA_WEIGHTS[None, :] + low[:, None] * (1.0 - ALPHA_WEIGHTS)[None, :]
    index, error = _nearest(values[:, :, None], palette[:, :, None])
    return high, low, index, error


def _encode_alpha(values: np.ndarray) -> np.ndarray:
    """(N, 16) float32 to (N, 8) uint8 alpha blocks in eight-value mode."""
    high, low, index, error = _alpha_fit(values, values.max(axis=1), values.min(axis=1))
    refit_high, refit_low = _refit(values[:, :, None], ALPHA_WEIGHTS[index], high[:, None], low[:, None])
    again_high, again_low, again_index, again_error = _alpha_fit(values, refit_high[:, 0], refit_low[:, 0])
    better = again_error < error
    high = np.where(better, again_high, high)
    low = np.where(better, again_low, low)
    index = np.where(better[:, None], again_index, index)
    # Equal endpoints put the decoder in six-value mode. Index 0 is still the endpoint.
    index = np.where((high == low)[:, None], 0, index)

    shifts = (3 * np.arange(16, dtype=np.uint64))[None, :]
    bits = (index.astype(np.uint64) << shifts).sum(axis=1, dtype=np.uint64)
    out = np.empty((values.shape[0], 8), dtype=np.uint8)
    out[:, 0] = high.astype(np.uint8)
    out[:, 1] = low.astype(np.uint8)
    out[:, 2:8] = bits.astype("<u8").view(np.uint8).reshape(-1, 8)[:, :6]
    return out


def encode(image: np.ndarray) -> bytes:
    """Encode an (H, W, 4) uint8 RGBA image as BC3 blocks, row by row."""
    if image.ndim != 3 or image.shape[2] != 4 or image.dtype != np.uint8:
        raise ValueError(f"encode needs an (H, W, 4) uint8 image, got {image.shape} {image.dtype}")
    blocks = _to_blocks(image)
    out = np.empty((blocks.shape[0], BLOCK_BYTES), dtype=np.uint8)
    for start in range(0, blocks.shape[0], CHUNK_BLOCKS):
        chunk = blocks[start : start + CHUNK_BLOCKS].astype(np.float32)
        out[start : start + CHUNK_BLOCKS, 0:8] = _encode_alpha(chunk[:, :, 3])
        out[start : start + CHUNK_BLOCKS, 8:16] = _encode_color(chunk[:, :, :3])
    return out.tobytes()


def _decode_alpha(blocks: np.ndarray) -> np.ndarray:
    high = blocks[:, 0].astype(np.int32)
    low = blocks[:, 1].astype(np.int32)
    steps = np.arange(1, 7, dtype=np.int32)[None, :]
    eight = ((7 - steps) * high[:, None] + steps * low[:, None] + 3) // 7
    four = ((5 - steps[:, :4]) * high[:, None] + steps[:, :4] * low[:, None] + 2) // 5
    six = np.concatenate([four, np.zeros_like(four[:, :1]), np.full_like(four[:, :1], 255)], axis=1)
    middle = np.where((high > low)[:, None], eight, six)
    palette = np.concatenate([high[:, None], low[:, None], middle], axis=1)
    packed = np.zeros((blocks.shape[0], 8), dtype=np.uint8)
    packed[:, :6] = blocks[:, 2:8]
    bits = packed.view("<u8")[:, 0]
    shifts = (3 * np.arange(16, dtype=np.uint64))[None, :]
    index = ((bits[:, None] >> shifts) & np.uint64(7)).astype(np.int64)
    return np.take_along_axis(palette, index, axis=1).astype(np.uint8)


def _decode_color(blocks: np.ndarray) -> np.ndarray:
    packed0 = np.ascontiguousarray(blocks[:, 0:2]).view("<u2")[:, 0]
    packed1 = np.ascontiguousarray(blocks[:, 2:4]).view("<u2")[:, 0]
    wide0 = _expand_565(packed0).astype(np.int32)
    wide1 = _expand_565(packed1).astype(np.int32)
    palette = np.stack(
        [wide0, wide1, (2 * wide0 + wide1 + 1) // 3, (wide0 + 2 * wide1 + 1) // 3], axis=1
    )
    bits = np.ascontiguousarray(blocks[:, 4:8]).view("<u4")[:, 0]
    shifts = (2 * np.arange(16, dtype=np.uint32))[None, :]
    index = ((bits[:, None] >> shifts) & np.uint32(3)).astype(np.int64)
    return np.take_along_axis(palette, index[:, :, None], axis=1).astype(np.uint8)


def decode(data: bytes, width: int, height: int) -> np.ndarray:
    """Decode BC3 blocks to an (H, W, 4) uint8 RGBA image."""
    count = block_count(width, height)
    if len(data) != count * BLOCK_BYTES:
        raise ValueError(f"{width}x{height} BC3 needs {count * BLOCK_BYTES} bytes, got {len(data)}")
    blocks = np.frombuffer(data, dtype=np.uint8).reshape(count, BLOCK_BYTES)
    pixels = np.empty((count, 16, 4), dtype=np.uint8)
    pixels[:, :, 3] = _decode_alpha(blocks[:, 0:8])
    pixels[:, :, :3] = _decode_color(blocks[:, 8:16])
    return _from_blocks(pixels, width, height)
