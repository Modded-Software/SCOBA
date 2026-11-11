#!/usr/bin/env python3
"""Double a 128x128 SC2 map into a uniform 256x256 component folder."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import struct
from pathlib import Path

from bootstrap_galaxy import write_bootstrap
from character_anim_assets import generate as generate_character_anim
from control_mode_icons import generate as generate_control_icons
from doodad_occlusion import disable_doodad_occlusion
from expand_helpers import clone_cells, read, upsample_grid, write
from project_root import project_root
from props_expand import expand_props
from spore_scale import scale_spores
from strip_gui_triggers import strip_triggers

SCALE = 2
OLD_CELLS = 128
NEW_CELLS = 256
OLD_VERTS = 129
NEW_VERTS = 257


def expand_heightmap(src: Path, dst: Path) -> None:
    data = read(src)
    magic, version, sx, sy = struct.unpack_from("<4sIII", data, 0)
    assert magic == b"HMAP" and sx == OLD_VERTS and sy == OLD_VERTS
    records = [struct.unpack_from("<HHH", data, 32 + i * 6) for i in range(sx * sy)]
    base = upsample_grid([r[0] for r in records], sx, NEW_VERTS)
    adj = upsample_grid([r[1] for r in records], sy, NEW_VERTS)
    out = bytearray(32 + NEW_VERTS * NEW_VERTS * 6)
    struct.pack_into("<4sIII", out, 0, magic, version, NEW_VERTS, NEW_VERTS)
    for y in range(NEW_VERTS):
        for x in range(NEW_VERTS):
            i = y * NEW_VERTS + x
            old = (min(y // 2, OLD_VERTS - 1) * OLD_VERTS + min(x // 2, OLD_VERTS - 1))
            struct.pack_into(
                "<HHH",
                out,
                32 + i * 6,
                max(0, min(65535, round(base[i]))),
                max(0, min(65535, round(adj[i]))),
                records[old][2],
            )
    write(dst, bytes(out))


def expand_sync_heightmap(src: Path, dst: Path) -> None:
    data = read(src)
    magic, version, sx, sy = struct.unpack_from("<4sIII", data, 0)
    assert magic == b"SMAP" and sx == OLD_VERTS and sy == OLD_VERTS
    count = sx * sy
    primary = list(struct.unpack_from("<" + "H" * count, data, 64))
    off = 64 + count * 2
    secondary = data[off : off + count]
    tertiary = data[off + count : off + count * 2]
    assert len(tertiary) == count, (len(secondary), len(tertiary))
    new_primary = upsample_grid(primary, sx, NEW_VERTS)
    out = bytearray(64 + NEW_VERTS * NEW_VERTS * 4)
    out[:64] = data[:64]
    struct.pack_into("<4sIII", out, 0, magic, version, NEW_VERTS, NEW_VERTS)
    for i, value in enumerate(new_primary):
        struct.pack_into("<H", out, 64 + i * 2, max(0, min(65535, round(value))))

    def up8(grid: bytes, old_n: int) -> bytes:
        out8 = bytearray(NEW_VERTS * NEW_VERTS)
        for y in range(NEW_VERTS):
            oy = min(y // 2, old_n - 1)
            row = oy * old_n
            base = y * NEW_VERTS
            for x in range(NEW_VERTS):
                out8[base + x] = grid[row + min(x // 2, old_n - 1)]
        return bytes(out8)

    nsec = up8(secondary, sx)
    nter = up8(tertiary, sy)
    noff = 64 + NEW_VERTS * NEW_VERTS * 2
    out[noff : noff + len(nsec)] = nsec
    out[noff + len(nsec) : noff + len(nsec) + len(nter)] = nter
    write(dst, bytes(out))


def expand_cell_flags(src: Path, dst: Path) -> None:
    data = read(src)
    magic, version = struct.unpack_from("<4sI", data, 0)
    w, h = struct.unpack_from("<II", data, 24)
    assert magic == b"LFCT" and w == OLD_CELLS and h == OLD_CELLS
    grid = data[32 : 32 + w * h]
    out = bytearray(32 + NEW_CELLS * NEW_CELLS)
    struct.pack_into("<4sI", out, 0, magic, version)
    struct.pack_into("<II", out, 24, NEW_CELLS, NEW_CELLS)
    out[32:] = clone_cells(grid, w, h, 1)
    write(dst, bytes(out))


def expand_cell_attributes(src: Path, dst: Path) -> None:
    data = read(src)
    assert len(data) == 4 + OLD_CELLS * OLD_CELLS
    bit_count = struct.unpack_from("<I", data, 0)[0]
    assert bit_count == OLD_CELLS * OLD_CELLS * 8
    out = bytearray(4 + NEW_CELLS * NEW_CELLS)
    struct.pack_into("<I", out, 0, NEW_CELLS * NEW_CELLS * 8)
    out[4:] = clone_cells(data[4:], OLD_CELLS, OLD_CELLS, 1)
    write(dst, bytes(out))


def expand_cliff_level(src: Path, dst: Path) -> None:
    data = read(src)
    w, h = struct.unpack_from("<II", data, 8)
    assert w == OLD_CELLS and h == OLD_CELLS
    out = bytearray(32 + NEW_CELLS * NEW_CELLS * 2)
    out[:32] = data[:32]
    struct.pack_into("<II", out, 8, NEW_CELLS, NEW_CELLS)
    out[32:] = clone_cells(data[32:], w, h, 2)
    write(dst, bytes(out))


def expand_sync_texture_info(src: Path, dst: Path) -> None:
    data = read(src)
    magic, version, w, h, sets = struct.unpack_from("<4sIIII", data, 0)
    assert magic == b"RTXT" and w == OLD_CELLS and h == OLD_CELLS
    pos = 20
    for _ in range(sets * 8):
        pos = data.index(0, pos) + 1
    names = data[20:pos]
    cell_size = 8 if version >= 101 else 4
    body = data[pos:]
    assert len(body) == w * h * cell_size
    out = bytearray(20 + len(names) + NEW_CELLS * NEW_CELLS * cell_size)
    struct.pack_into("<4sIIII", out, 0, magic, version, NEW_CELLS, NEW_CELLS, sets)
    out[20 : 20 + len(names)] = names
    out[20 + len(names) :] = clone_cells(body, w, h, cell_size)
    write(dst, bytes(out))


def unpack_tile(tile: bytes) -> list[int]:
    cells = []
    for row in range(64):
        for col in range(32):
            b = tile[row * 32 + col]
            cells.append(b >> 4)
            cells.append(b & 0x0F)
    return cells


def pack_tile(cells: list[int]) -> bytes:
    out = bytearray(2048)
    for row in range(64):
        for col in range(32):
            a = cells[row * 64 + col * 2]
            b = cells[row * 64 + col * 2 + 1]
            out[row * 32 + col] = ((a & 0x0F) << 4) | (b & 0x0F)
    return bytes(out)


def expand_texture_masks(src: Path, dst: Path) -> None:
    data = read(src)
    magic, version, reserved, w, h = struct.unpack_from("<4sIIII", data, 0)
    assert magic == b"MASK" and version == 102 and w == 1024 and h == 1024
    old_tiles = 16
    new_tiles = 32
    tile_size = 2048
    layer_size = old_tiles * old_tiles * tile_size
    out = bytearray(64 + 8 * new_tiles * new_tiles * tile_size)
    out[:64] = data[:64]
    struct.pack_into("<4sIIII", out, 0, magic, version, reserved, 2048, 2048)
    write_pos = 64
    for layer in range(8):
        base = 64 + layer * layer_size
        for ty in range(new_tiles):
            for tx in range(new_tiles):
                old_tx = tx // 2
                old_ty = ty // 2
                old_tile = data[
                    base
                    + (old_ty * old_tiles + old_tx) * tile_size :
                    base
                    + (old_ty * old_tiles + old_tx + 1) * tile_size
                ]
                cells = unpack_tile(old_tile)
                dx = (tx % 2) * 32
                dy = (ty % 2) * 32
                scaled = [0] * (64 * 64)
                for y in range(64):
                    for x in range(64):
                        sx = dx + x // 2
                        sy = dy + y // 2
                        scaled[y * 64 + x] = cells[sy * 64 + sx]
                out[write_pos : write_pos + tile_size] = pack_tile(scaled)
                write_pos += tile_size
    write(dst, bytes(out))


def expand_vertcol(src: Path, dst: Path) -> None:
    data = read(src)
    magic, version, count = struct.unpack_from("<4sII", data, 0)
    assert magic == b"VTCL" and version == 104
    out = bytearray(32)
    out[:32] = data[:32]
    pos = 32
    for _ in range(count):
        entry = data[pos : pos + 36]
        tex, layer, x1, y1, x2, y2, enabled, blend = struct.unpack_from("<ii4fii", entry, 0)
        size = struct.unpack_from("<I", data, pos + 32)[0]
        sub = data[pos + 36 : pos + 36 + size]
        assert size == 25
        old_grid = list(sub)
        new_n = int((x2 - x1) * SCALE) + 1
        new_sub = bytearray(new_n * new_n)
        for y in range(new_n):
            for x in range(new_n):
                sx = min(int(x / SCALE), 4)
                sy = min(int(y / SCALE), 4)
                new_sub[y * new_n + x] = old_grid[sy * 5 + sx]
        out += struct.pack(
            "<ii4fiiI",
            tex,
            layer,
            x1 * SCALE,
            y1 * SCALE,
            x2 * SCALE,
            y2 * SCALE,
            enabled,
            blend,
            len(new_sub),
        )
        out += new_sub
        pos += 36 + size
    assert pos == len(data)
    write(dst, bytes(out))


def expand_fluff(src: Path, dst: Path) -> None:
    data = read(src)
    magic, version = struct.unpack_from("<4sI", data, 0)
    count = struct.unpack_from("<I", data, 24)[0]
    assert magic == b"DLFT" and version == 103
    assert len(data) == 28 + count * 9
    out = bytearray(28)
    out[:28] = data[:28]
    for i in range(count):
        off = 28 + i * 9
        x, y = struct.unpack_from("<2f", data, off)
        out += struct.pack("<2fB", x * SCALE, y * SCALE, data[off + 8])
    write(dst, bytes(out))


def expand_water(src: Path, dst: Path) -> None:
    data = read(src)
    magic, version, amount = struct.unpack_from("<4sII", data, 0)
    assert magic == b"WATR"
    assert len(data) == 32 + amount * 56
    out = bytearray(data[:32])
    for i in range(amount):
        off = 32 + i * 56
        out += data[off : off + 40]
        start_x, start_y, end_x, end_y = struct.unpack_from("<4f", data, off + 40)
        out += struct.pack("<4f", start_x * SCALE, start_y * SCALE, end_x * SCALE, end_y * SCALE)
    write(dst, bytes(out))


def expand_mapinfo(src: Path, dst: Path) -> None:
    data = bytearray(read(src))
    assert data[:4] == b"IpaM"
    version = struct.unpack_from("<I", data, 4)[0]
    pos = 8
    hash_off = pos
    pos += 8
    width, height = struct.unpack_from("<II", data, pos)
    assert width == OLD_CELLS and height == OLD_CELLS
    struct.pack_into("<II", data, pos, NEW_CELLS, NEW_CELLS)
    pos += 8
    locale_mode = struct.unpack_from("<I", data, pos)[0]
    pos += 4
    if locale_mode == 2:
        pos = data.index(0, pos) + 1
    if version >= 22:
        preview_type = struct.unpack_from("<I", data, pos)[0]
        pos += 4
        if preview_type == 2:
            pos = data.index(0, pos) + 1
    if version >= 28:
        pos = data.index(0, pos) + 1
    if version >= 37:
        pos = data.index(0, pos) + 1
    if version >= 29:
        pos += 4
    if version >= 11:
        pos += 4
    if version >= 3:
        pos = data.index(0, pos) + 1
    desc_start = pos
    desc_end = data.index(0, pos)
    desc_len = desc_end - desc_start
    pos = desc_end + 1
    bounds_off = pos
    struct.pack_into("<4i", data, bounds_off, 2, 3, 254, 254)
    pos += 16
    if version >= 19:
        pos += 4
    if version >= 14:
        pos += 4
        pos = data.index(0, pos) + 1
    if version >= 23:
        bar_len = struct.unpack_from("<H", data, pos)[0]
        pos += 2 + bar_len
    if version >= 20:
        pos += 24
    if version >= 35:
        pos = data.index(0, pos) + 1
        locale_len = struct.unpack_from("<H", data, pos)[0]
        pos += 2 + locale_len
    if version >= 39:
        str_len = struct.unpack_from("<H", data, pos)[0]
        pos += 2 + str_len
    flags = struct.unpack_from("<I", data, pos)[0] & ~0x02
    struct.pack_into("<I", data, pos, flags)
    popcount = bin(flags).count("1")
    dx, dy = 254 - 2, 254 - 3
    hash_value = desc_len + 7 * NEW_CELLS + 2 * (dx * dx + dy * dy) + 3 * NEW_CELLS - popcount - 17
    struct.pack_into("<Q", data, hash_off, hash_value)
    write(dst, bytes(data))


def scale_xml_objects(src: Path, dst: Path) -> None:
    text = src.read_text(encoding="utf-8")
    pattern = re.compile(r'Position="([^"]+)"')
    def repl(match: re.Match[str]) -> str:
        parts = match.group(1).split(",")
        parts[0] = format(float(parts[0]) * SCALE, ".10g")
        parts[1] = format(float(parts[1]) * SCALE, ".10g")
        return 'Position="' + ",".join(parts) + '"'
    dst.write_text(pattern.sub(repl, text), encoding="utf-8")


def scale_xml_regions(src: Path, dst: Path) -> None:
    text = src.read_text(encoding="utf-8")
    center = re.compile(r'<center value="([^"]+)"/>')
    radius = re.compile(r'<radius value="([^"]+)"/>')
    def center_repl(match: re.Match[str]) -> str:
        x, y = match.group(1).split(",")
        return '<center value="{},{}"/>'.format(
            format(float(x) * SCALE, ".10g"),
            format(float(y) * SCALE, ".10g"),
        )
    def radius_repl(match: re.Match[str]) -> str:
        return '<radius value="{}"/>'.format(format(float(match.group(1)) * SCALE, ".10g"))
    text = center.sub(center_repl, text)
    text = radius.sub(radius_repl, text)
    dst.write_text(text, encoding="utf-8")


def write_pathing_info(dst: Path) -> None:
    out = bytearray(32 + NEW_CELLS * NEW_CELLS * 2)
    struct.pack_into("<4sIII", out, 0, b"PATH", 100, NEW_CELLS, NEW_CELLS)
    write(dst, bytes(out))


def expand_terrain_xml(src: Path, dst: Path) -> None:
    text = src.read_text(encoding="utf-8")
    text = re.sub(r'dim="\d+ \d+ "', 'dim="257 257 "', text, count=1)
    text = re.sub(
        r"<blockTextureSetList num=\"\d+\">.*?</blockTextureSetList>",
        lambda _: block_texture_sets(),
        text,
        flags=re.S,
    )
    text = re.sub(
        r"<cliffCellList num=\"\d+\" numOccupied=\"\d+\">.*?</cliffCellList>",
        lambda _: cliff_cells(src),
        text,
        flags=re.S,
    )
    dst.write_text(text, encoding="utf-8")


def block_texture_sets() -> str:
    lines = ['        <blockTextureSetList num="1024">']
    for y in range(32):
        for x in range(32):
            i = y * 32 + x
            lines.append(f'            <blockTextureSet i="{i}" tileSet="0"/>')
    lines.append("        </blockTextureSetList>")
    return "\n".join(lines)


def cliff_cells(src: Path) -> str:
    text = src.read_text(encoding="utf-8")
    cells = {}
    for match in re.finditer(r'<cc i="(\d+)" f="(\d+)" cid="(\d+)" cvar="(\d+)"/>', text):
        cells[int(match.group(1))] = match.groups()[1:]
    out = []
    for y in range(128):
        for x in range(128):
            src_index = (y // 2) * 64 + (x // 2)
            if src_index in cells:
                i = y * 128 + x
                f, cid, cvar = cells[src_index]
                out.append(f'            <cc i="{i}" f="{f}" cid="{cid}" cvar="{cvar}"/>')
    lines = [f'        <cliffCellList num="16384" numOccupied="{len(out)}">']
    lines.extend(out)
    lines.append("        </cliffCellList>")
    return "\n".join(lines)


def expand_minimap(src: Path, dst: Path) -> None:
    data = read(src)
    id_len, cmap, image_type = data[0], data[1], data[2]
    assert image_type == 2
    width, height = struct.unpack_from("<HH", data, 12)
    depth = data[16]
    desc = data[17]
    assert width == OLD_CELLS and height == OLD_CELLS and depth == 24
    offset = 18 + id_len + cmap
    pixel_size = 3
    old = data[offset : offset + width * height * pixel_size]
    footer = data[offset + width * height * pixel_size :]
    new_w = width * SCALE
    new_h = height * SCALE
    out = bytearray(data[:offset])
    struct.pack_into("<HH", out, 12, new_w, new_h)
    for y in range(new_h):
        sy = y // SCALE
        for x in range(new_w):
            sx = x // SCALE
            p = (sy * width + sx) * pixel_size
            out += old[p : p + pixel_size]
    out += footer
    write(dst, bytes(out))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, help="Build into this folder without swapping")
    args = parser.parse_args()
    root = project_root()
    src = root / "src" / "SCOBA.SC2Map"
    final = root / "out" / "SCOBA256.SC2Map"
    dst = args.out if args.out is not None else root / "out" / ".build-tmp"
    if not src.is_dir():
        raise SystemExit(f"source not found: {src}")
    if dst.exists():
        shutil.rmtree(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst)
    (dst / "t3SyncHeightMap").unlink(missing_ok=True)
    expand_mapinfo(src / "MapInfo", dst / "MapInfo")
    expand_terrain_xml(src / "t3Terrain.xml", dst / "t3Terrain.xml")
    expand_heightmap(src / "t3HeightMap", dst / "t3HeightMap")
    expand_cell_flags(src / "t3CellFlags", dst / "t3CellFlags")
    for path in sorted(src.glob("CellAttribute_*")):
        expand_cell_attributes(path, dst / path.name)
    expand_cliff_level(src / "t3SyncCliffLevel", dst / "t3SyncCliffLevel")
    expand_sync_texture_info(src / "t3SyncTextureInfo", dst / "t3SyncTextureInfo")
    expand_texture_masks(src / "t3TextureMasks", dst / "t3TextureMasks")
    expand_vertcol(src / "t3VertCol", dst / "t3VertCol")
    expand_fluff(src / "t3FluffDoodad", dst / "t3FluffDoodad")
    shutil.copy2(src / "t3HardTile", dst / "t3HardTile")
    expand_water(src / "t3Water", dst / "t3Water")
    scale_xml_objects(src / "Objects", dst / "Objects")
    scale_xml_regions(src / "Regions", dst / "Regions")
    strip_triggers(dst)
    write_bootstrap(dst)
    expand_minimap(src / "Minimap.tga", dst / "Minimap.tga")
    disable_doodad_occlusion(dst)
    generate_character_anim(dst, False)
    generate_control_icons(dst, False)
    if os.environ.get("SC2_NO_PROPS") != "1":
        expand_props(dst)
    if os.environ.get("SC2_NO_SPORES") != "1":
        scale_spores(dst)
    if args.out is None:
        old = root / "out" / ".build-old"
        if old.exists():
            shutil.rmtree(old)
        if final.exists():
            final.rename(old)
        dst.rename(final)
        if old.exists():
            shutil.rmtree(old)
        dst = final
    print(dst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
