"""DDS container for compressed textures with a mip chain.

Only one layout is supported: a 124-byte header, a FourCC that names a
registered codec, and a mip chain. Anything else is rejected, so a texture
in another format is reported instead of converted wrongly.

Bytes after the last mip are kept as `trailer`. Some games end a file in a
tag of their own, and it is written back unchanged.
"""

from __future__ import annotations

import struct
from typing import NamedTuple

from .interfaces import Codec
from .codecs import CODECS  # loading it registers the codecs

MAGIC = b"DDS "
HEADER_SIZE = 124
DATA_OFFSET = 4 + HEADER_SIZE

# DDSD_CAPS | HEIGHT | WIDTH | PIXELFORMAT | MIPMAPCOUNT | LINEARSIZE
HEADER_FLAGS = 0x1 | 0x2 | 0x4 | 0x1000 | 0x20000 | 0x80000
PIXEL_FORMAT_SIZE = 32
PIXEL_FORMAT_FOURCC = 0x4
# DDSCAPS_COMPLEX | TEXTURE | MIPMAP
CAPS = 0x8 | 0x1000 | 0x400000


class DdsError(ValueError):
    """The file is not a DDS this tool can read."""


class Level(NamedTuple):
    width: int
    height: int
    offset: int
    size: int


class Dds(NamedTuple):
    width: int
    height: int
    levels: tuple[Level, ...]
    trailer: bytes
    data: bytes
    format: str = "DXT5"

    @property
    def codec(self) -> Codec:
        return CODECS.get(self.format)

    def level_bytes(self, index: int) -> bytes:
        level = self.levels[index]
        return self.data[level.offset : level.offset + level.size]


def full_mip_count(width: int, height: int) -> int:
    return max(width, height).bit_length()


def level_size(width: int, height: int, format: str = "DXT5") -> int:
    return CODECS.get(format).level_size(width, height)


class Info(NamedTuple):
    """What the header of any DDS file says, whether or not this tool can decode it."""

    format: str  # FourCC such as DXT1, or RGB<bits>/RGBA<bits> for uncompressed data
    width: int
    height: int
    mips: int
    cube: bool


def describe(data: bytes) -> Info:
    if len(data) < DATA_OFFSET or data[:4] != MAGIC:
        raise DdsError("not a DDS file")
    _size, _flags, height, width, _linear, _depth, mips = struct.unpack_from(
        "<7I", data, 4
    )
    _pf_size, pf_flags, fourcc, bits, _red, _green, _blue, alpha_mask = (
        struct.unpack_from("<II4s5I", data, 76)
    )
    caps2 = struct.unpack_from("<I", data, 112)[0]
    if pf_flags & PIXEL_FORMAT_FOURCC:
        name = fourcc.decode("ascii", errors="replace")
    else:
        name = f"{'RGBA' if alpha_mask else 'RGB'}{bits}"
    return Info(name, width, height, max(1, mips), bool(caps2 & 0x200))


def parse(data: bytes) -> Dds:
    if len(data) < DATA_OFFSET or data[:4] != MAGIC:
        raise DdsError("not a DDS file")
    size, _flags, height, width, _linear, _depth, mips = struct.unpack_from(
        "<7I", data, 4
    )
    if size != HEADER_SIZE:
        raise DdsError(f"unexpected DDS header size {size}")
    pf_size, pf_flags, fourcc = struct.unpack_from("<II4s", data, 76)
    name = fourcc.decode("ascii", errors="replace")
    if (
        pf_size != PIXEL_FORMAT_SIZE
        or not pf_flags & PIXEL_FORMAT_FOURCC
        or not CODECS.has(name)
    ):
        raise DdsError(
            f"unsupported pixel format {fourcc!r}; only {' and '.join(CODECS.ids())} are supported"
        )
    if width <= 0 or height <= 0:
        raise DdsError(f"bad size {width}x{height}")
    mips = max(1, mips)
    levels = []
    offset = DATA_OFFSET
    level_w, level_h = width, height
    for _ in range(mips):
        size = level_size(level_w, level_h, name)
        levels.append(Level(level_w, level_h, offset, size))
        offset += size
        level_w, level_h = max(1, level_w // 2), max(1, level_h // 2)
    if offset > len(data):
        raise DdsError(
            f"truncated DDS: {mips} mips need {offset} bytes, file has {len(data)}"
        )
    return Dds(width, height, tuple(levels), data[offset:], data, name)


def build(
    width: int,
    height: int,
    mips: list[bytes],
    trailer: bytes = b"",
    format: str = "DXT5",
) -> bytes:
    """Assemble a DDS from encoded mip levels, largest first."""
    if not CODECS.has(format):
        raise DdsError(f"unsupported pixel format {format!r}")
    if not mips:
        raise DdsError("a DDS needs at least one mip level")
    level_w, level_h = width, height
    for index, blob in enumerate(mips):
        expected = level_size(level_w, level_h, format)
        if len(blob) != expected:
            raise DdsError(
                f"mip {index} is {len(blob)} bytes, {level_w}x{level_h} needs {expected}"
            )
        level_w, level_h = max(1, level_w // 2), max(1, level_h // 2)
    header = bytearray(HEADER_SIZE)
    struct.pack_into(
        "<7I",
        header,
        0,
        HEADER_SIZE,
        HEADER_FLAGS,
        height,
        width,
        len(mips[0]),
        0,
        len(mips),
    )
    struct.pack_into(
        "<II4s",
        header,
        72,
        PIXEL_FORMAT_SIZE,
        PIXEL_FORMAT_FOURCC,
        format.encode("ascii"),
    )
    struct.pack_into("<I", header, 104, CAPS)
    return MAGIC + bytes(header) + b"".join(mips) + trailer
