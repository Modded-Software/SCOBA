"""The formats the core brings: DXT1 and DXT5, both 4x4 block codecs."""

from __future__ import annotations

from types import ModuleType

import numpy as np

from . import bc1, bc3
from .registry import CODECS


class BlockCodec:
    def __init__(self, key: str, blocks: ModuleType, opaque: bool) -> None:
        self.id = key
        self.opaque = opaque
        self.blocks = blocks

    def level_size(self, width: int, height: int) -> int:
        return bc3.block_count(width, height) * self.blocks.BLOCK_BYTES

    def decode(self, data: bytes, width: int, height: int) -> np.ndarray:
        return self.blocks.decode(data, width, height)

    def encode(self, rgba: np.ndarray) -> bytes:
        return self.blocks.encode(rgba)


# DXT1 as bc1 writes it has no alpha.
DXT1 = CODECS.add("DXT1", BlockCodec("DXT1", bc1, opaque=True))
DXT5 = CODECS.add("DXT5", BlockCodec("DXT5", bc3, opaque=False))
