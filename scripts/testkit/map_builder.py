"""Build instrumented test maps from declarative profile specifications."""

from __future__ import annotations

import shutil
import struct
from pathlib import Path
from types import MappingProxyType
from typing import Mapping, NamedTuple

from .profiles.registry import PROFILE_OUTPUTS
from .profiles.registry import PROFILE_BANKS


class TestMapSpec(NamedTuple):
    profile: str
    source: Path
    output: Path
    bank_names: tuple[str, ...]
    galaxy_files: tuple[Path, ...]
    galaxy_includes: tuple[str, ...]
    init_calls: tuple[str, ...]
    options: Mapping[str, bool] = MappingProxyType({})


def _read_cstr(data: bytes, pos: int) -> tuple[bytes, int]:
    end = data.index(b"\x00", pos)
    return data[pos:end], end + 1


def patch_mapinfo(path: Path) -> None:
    data = bytearray(path.read_bytes())
    version = struct.unpack_from("<I", data, 4)[0]
    pos = 8 + 8
    struct.unpack_from("<II", data, pos)
    pos += 8
    locale_mode = struct.unpack_from("<I", data, pos)[0]
    pos += 4
    if locale_mode == 2:
        pos = data.index(b"\x00", pos) + 1
    if version >= 22:
        preview_type = struct.unpack_from("<I", data, pos)[0]
        pos += 4
        if preview_type == 2:
            pos = data.index(b"\x00", pos) + 1
    if version >= 28:
        pos = data.index(b"\x00", pos) + 1
    if version >= 37:
        pos = data.index(b"\x00", pos) + 1
    if version >= 29:
        pos += 4
    if version >= 11:
        pos += 4
    if version >= 3:
        pos = data.index(b"\x00", pos) + 1
    desc, pos = _read_cstr(data, pos)
    bounds_off = pos
    left, bottom, right, top = struct.unpack_from("<4i", data, bounds_off)
    pos += 16
    if version >= 19:
        pos += 4
    if version >= 14:
        pos += 4
        pos = data.index(b"\x00", pos) + 1
    if version >= 23:
        bar_len = struct.unpack_from("<H", data, pos)[0]
        pos += 2 + bar_len
    if version >= 20:
        pos += 24
    if version >= 35:
        pos = data.index(b"\x00", pos) + 1
        locale_len = struct.unpack_from("<H", data, pos)[0]
        pos += 2 + locale_len
    if version >= 39:
        str_len = struct.unpack_from("<H", data, pos)[0]
        pos += 2 + str_len
    flags_off = pos
    flags = struct.unpack_from("<I", data, flags_off)[0]
    flags &= ~0x02
    struct.pack_into("<I", data, flags_off, flags)
    popcount = bin(flags).count("1")
    dx, dy = right - left, top - bottom
    width, height = struct.unpack_from("<II", data, 16)
    hash_value = (
        len(desc)
        + 7 * height
        + 2 * (dx * dx + dy * dy)
        + 3 * width
        - popcount
        - 17
    )
    struct.pack_into("<Q", data, 8, hash_value)
    path.write_bytes(bytes(data))


def patch_banklist(path: Path, bank_names: tuple[str, ...]) -> None:
    text = path.read_text()
    for name in bank_names:
        if f'<Bank Name="{name}"' in text:
            continue
        text = text.replace("</BankList>", f'    <Bank Name="{name}" Player="1"/>\n</BankList>')
    path.write_text(text)


def patch_map_options(root: Path, options: Mapping[str, bool]) -> None:
    if options.get("zero_pnp"):
        for path in root.glob("CellAttribute_*"):
            data = bytearray(path.read_bytes())
            if len(data) <= 4:
                continue
            struct.pack_into("<I", data, 0, (len(data) - 4) * 8)
            data[4:] = b"\x00" * (len(data) - 4)
            path.write_bytes(bytes(data))
    if options.get("add_pathing"):
        n = 256
        body = bytearray(n * n * 2)
        for y in range(n):
            for x in range(n):
                v = 0x23 if (x < 2 or y < 2 or x >= n - 2 or y >= n - 2) else 0
                struct.pack_into("<H", body, (y * n + x) * 2, v)
        header = struct.pack("<4sIII", b"PATH", 100, n, n) + b"\x00" * 16
        (root / "t3SyncPathingInfo").write_bytes(header + bytes(body))
    if options.get("zero_flags"):
        path = root / "t3CellFlags"
        data = bytearray(path.read_bytes())
        data[32:] = b"\x00" * (len(data) - 32)
        path.write_bytes(bytes(data))


def _insert_includes(text: str, includes: tuple[str, ...]) -> str:
    marker = "\nvoid main ()"
    if marker not in text:
        raise SystemExit("main entry point not found")
    block = "".join(f'\ninclude "{name}"' for name in includes)
    return text.replace(marker, block + marker, 1)


def _insert_init_calls(text: str, calls: tuple[str, ...]) -> str:
    start = text.find("void main () {")
    if start < 0:
        raise SystemExit("main function not found")
    pos = text.find("{", start) + 1
    depth = 1
    while pos < len(text) and depth:
        if text[pos] == "{":
            depth += 1
        elif text[pos] == "}":
            depth -= 1
        pos += 1
    if depth:
        raise SystemExit("main function is not closed")
    end = pos - 1
    block = "".join(f"    {call}\n" for call in calls)
    return text[:end] + block + text[end:]


def build_instrumented_map(spec: TestMapSpec) -> Path:
    expected = PROFILE_OUTPUTS.get(spec.profile)
    if expected is None:
        raise SystemExit(f"unknown test profile: {spec.profile}")
    if spec.output != expected:
        raise SystemExit(f"profile {spec.profile} must write {expected}")
    if tuple(PROFILE_BANKS.get(spec.profile, ())) != tuple(spec.bank_names):
        raise SystemExit(f"profile {spec.profile} bank names do not match registry")
    if not spec.source.is_dir():
        raise SystemExit(f"missing expanded map: {spec.source}")
    if spec.output.exists():
        shutil.rmtree(spec.output)
    shutil.copytree(spec.source, spec.output)
    patch_map_options(spec.output, spec.options)
    patch_mapinfo(spec.output / "MapInfo")
    patch_banklist(spec.output / "BankList.xml", spec.bank_names + ("SCOBACLIPMETRICS",))
    harness_root = spec.output / "scripts" / "test" / spec.profile
    harness_root.mkdir(parents=True, exist_ok=True)
    for source in spec.galaxy_files:
        shutil.copy2(source, harness_root / source.name)
    main_path = spec.output / "scripts" / "app" / "main.galaxy"
    if not main_path.is_file():
        raise SystemExit(f"missing module entry point: {main_path}")
    text = main_path.read_text(encoding="utf-8")
    text = _insert_includes(text, spec.galaxy_includes)
    text = _insert_init_calls(text, spec.init_calls)
    main_path.write_text(text, encoding="utf-8")
    return spec.output
