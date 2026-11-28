#!/usr/bin/env python3
"""Loading screen: its text and the wait for a key (REQ-LOADING-SCREEN).

The text lives in the source map, in the enUS and enGB GameStrings. This
module checks it: the fields, the two locales agree, no word of the old
texts is left, and every control the tip names is bound in the map script.
The game shows the copy in DocumentHeader: the build writes the fields
there from the GameStrings, and the check compares the two.

The wait for a key is one flag in MapInfo. The build sets it; a test map
clears it (testkit/map_builder), so a test run enters the game by itself.

MapInfo header, as the build has read it since 2026-11-07 (version 39 in
the source map): magic, version, an 8 byte check value, width, height,
then strings and numbers by version, then the u32 flags. The check value
is a sum over the description length, the size, the camera bounds and the
count of set flags: a changed flag needs a new check value.
"""

from __future__ import annotations

import re
import struct
from collections import Counter
from pathlib import Path
from typing import NamedTuple

MAGIC = b"IpaM"
HASH_OFF = 8
SIZE_OFF = 16
WAIT_FOR_KEY = 0x02
DOC_MAGIC = b"H2CS"
DOC_VERSION = 8
DOC_DEPS_OFF = 0x2C

# enUS first: the tip is checked against the script in enUS, and every other
# tip against enUS. enGB holds the enUS text; the others a translation.
LOCALES = ("enUS", "enGB", "deDE", "esES", "esMX", "frFR", "itIT", "koKR", "plPL", "ptBR", "ruRU", "zhCN", "zhTW")
SAME_TEXT = {"enGB": "enUS"}
NAME = "SCOBA: StarCraft Online Battle Arena"
AUTHOR = "SCOBA"
TIP = "LoadingScreen/Tip"
# The custom loading layout MapInfo names (R-LOAD-8), as a DescIndex path.
LAYOUT = "UI/Layout/Custom/ScobaLoading.SC2Layout"
FIELDS = ("DocInfo/Name", "DocInfo/Author", "DocInfo/DescShort", "DocInfo/DescLong", TIP)
# Words of the texts before 2026-11-26 (R-LOAD-3).
STALE = (
    "Outbreak", "PAGE UP", "PAGE DOWN", "FPS", "RTS", "E, D, S and F", "G, R, T and A",
    "<CTRL> to zoom", "auto-attack", "Destroy all enemy structures", "Blizzard", "iWaNN",
)
_ORDER_KEY = "TriggerAddEventKeyPressed(gt_OrderKey, c_playerAny, c_keyE, true, c_keyModifierStateIgnore, c_keyModifierStateRequire, c_keyModifierStateIgnore);"
_CANCEL_KEY = "TriggerAddEventKeyPressed(gt_OrderCancel, c_playerAny, c_keyC, true, c_keyModifierStateIgnore, c_keyModifierStateRequire, c_keyModifierStateIgnore);"
_LEFT = "const int gv_mOUSECURSOR = c_mouseButtonLeft;"
_RIGHT = "const int gv_fIRE = c_mouseButtonRight;"
_MIDDLE = "const int gv_aBILITYCAMERA = c_mouseButtonMiddle;"
# Tip phrase -> the script lines that make it true (R-LOAD-4).
BINDINGS: dict[str, tuple[str, ...]] = {
    "W, A, S, D - move": (
        "const int gv_mOVEFORWARD = c_keyW;",
        "const int gv_mOVELEFT = c_keyA;",
        "const int gv_mOVEBACKWARD = c_keyS;",
        "const int gv_mOVERIGHT = c_keyD;",
    ),
    "Shift (hold) - slow walk": ("const int gv_sLOWWALK = c_keyShift;",),
    "Space - deploy at the start, then jump": (
        "const int gv_jUMP = c_keySpace;",
        "TriggerAddEventKeyPressed(gt_IntroDeploy, c_playerAny, c_keySpace, true,",
    ),
    "Z (hold) - zoom": ("const int gv_zOOM = c_keyZ;",),
    "Mouse wheel - camera distance": ("TriggerAddEventMouseWheel(gt_CameraFollowDistance, c_playerAny);",),
    "Ctrl+E - order mode": (_ORDER_KEY,),
    "Ctrl+C - leave it": (_CANCEL_KEY, "gf_OrderExit(lv_player);"),
    "Ctrl+C - cancel the attack": (_CANCEL_KEY, "gf_PncCancel(lv_player);"),
    "Left click - pick a target": (_LEFT,),
    "Right click - attack": (_RIGHT,),
    "Hold a mouse button and drag - turn the camera": (_LEFT, _RIGHT, _MIDDLE),
    "Right hold - aim": (_RIGHT, "gf_AimBegin(lp_player);"),
    "Left click while aiming - shoot": (_LEFT,),
    "Middle click - show or hide the cursor": (_MIDDLE, "gv_mOUSEMIDDLE[lp_player] = !gv_mOUSEMIDDLE[lp_player];"),
    "3 stat points per level": ("gv_availableStatPoints[lp_player] += 3;",),
    "A new ability at levels 3, 6, 9, 12 and 15": (
        "if ((ModI(lp_numberToCheck, 3) == 0)) {",
        "(gv_lEVEL[lp_player] <= 15)",
    ),
    "At level 20, one ultimate from a skill tree with 3 points in it": (
        "(gv_lEVEL[lp_player] == 20)",
        "if ((gv_allocatedAbilityPoints[0][lv_localPlayer] >= 3)) {",
    ),
}
# Tip phrase -> the button names it speaks of (Base.SC2Data ButtonData.xml).
BUTTONS: dict[str, tuple[str, ...]] = {
    "WASD / POINT & CLICK": ("Controls: WASD / Point &amp; Click",),
    "ACTIONS (TPS)": ("Controls: Actions",),
    "Attack button - Single or Auto": ("Attack: Single", "Attack: Auto"),
    "Chase button - Stand or Move": ("Chase: Stand", "Chase: Move"),
}
# What a translated tip keeps from enUS: key names, button labels, numbers.
# The map's buttons are English in every locale.
_TIP_TOKEN = re.compile(
    r"W, A, S, D|Z \(|Ctrl\+[A-Z]|WASD / POINT & CLICK|ACTIONS \(TPS\)"
    r"|(?<![A-Za-z])(?:Shift|Space|Attack|Single|Auto|Chase|Stand|Move)(?![A-Za-z])|\d+"
)
# A key named in the tip outside the phrases above is not proven bound.
_KEY_WORD = re.compile(r"\b(Ctrl|Alt|Shift|Space|Tab|Esc|Enter|Page|Insert|Delete|Home|End|F\d{1,2})\b", re.I)


class Header(NamedTuple):
    version: int
    desc_len: int
    bounds_off: int
    flags_off: int
    # The C string of the custom loading layout (version 35 on).
    layout_off: int


def _skip_cstr(data: bytes, pos: int) -> int:
    return data.index(0, pos) + 1


def _skip_sized(data: bytes, pos: int) -> int:
    return pos + 2 + struct.unpack_from("<H", data, pos)[0]


def header(data: bytes) -> Header:
    """Where the description, the camera bounds and the flags are."""
    if data[:4] != MAGIC:
        raise SystemExit("loading_screen: not a MapInfo file")
    version = struct.unpack_from("<I", data, 4)[0]
    pos = SIZE_OFF + 8
    locale_mode = struct.unpack_from("<I", data, pos)[0]
    pos += 4
    if locale_mode == 2:
        pos = _skip_cstr(data, pos)
    if version >= 22:
        preview_type = struct.unpack_from("<I", data, pos)[0]
        pos += 4
        if preview_type == 2:
            pos = _skip_cstr(data, pos)
    if version >= 28:
        pos = _skip_cstr(data, pos)
    if version >= 37:
        pos = _skip_cstr(data, pos)
    if version >= 29:
        pos += 4
    if version >= 11:
        pos += 4
    if version >= 3:
        pos = _skip_cstr(data, pos)
    desc_end = data.index(0, pos)
    desc_len = desc_end - pos
    bounds_off = desc_end + 1
    pos = bounds_off + 16
    if version >= 19:
        pos += 4
    if version >= 14:
        pos = _skip_cstr(data, pos + 4)
    if version >= 23:
        pos = _skip_sized(data, pos)
    if version >= 20:
        pos += 24
    if version < 35:
        raise SystemExit(f"loading_screen: MapInfo version {version} has no custom loading layout")
    layout_off = pos
    pos = _skip_sized(data, _skip_cstr(data, pos))
    if version >= 39:
        pos = _skip_sized(data, pos)
    if pos + 4 > len(data):
        raise SystemExit("loading_screen: MapInfo ends before its flags")
    return Header(version, desc_len, bounds_off, pos, layout_off)


def map_hash(data: bytes) -> int:
    """The check value of the header as it stands."""
    at = header(data)
    width, height = struct.unpack_from("<II", data, SIZE_OFF)
    left, bottom, right, top = struct.unpack_from("<4i", data, at.bounds_off)
    flags = struct.unpack_from("<I", data, at.flags_off)[0]
    dx, dy = right - left, top - bottom
    return at.desc_len + 7 * height + 2 * (dx * dx + dy * dy) + 3 * width - bin(flags).count("1") - 17


def layout(data: bytes) -> str:
    """The custom loading layout MapInfo names; empty: none."""
    at = header(data).layout_off
    return data[at : data.index(0, at)].decode("utf-8")


def set_layout(data: bytes, path: str) -> bytes:
    """The same MapInfo naming another custom loading layout.

    The check value does not cover the path, so it stays.
    """
    at = header(data).layout_off
    end = data.index(0, at)
    return data[:at] + path.encode("utf-8") + data[end:]


def wait_for_key(data: bytes) -> bool:
    return bool(struct.unpack_from("<I", data, header(data).flags_off)[0] & WAIT_FOR_KEY)


def set_wait_for_key(data: bytes, on: bool) -> bytes:
    """The same MapInfo with the flag on or off and its check value redone."""
    out = bytearray(data)
    at = header(data)
    flags = struct.unpack_from("<I", out, at.flags_off)[0]
    flags = flags | WAIT_FOR_KEY if on else flags & ~WAIT_FOR_KEY
    struct.pack_into("<I", out, at.flags_off, flags)
    struct.pack_into("<Q", out, HASH_OFF, map_hash(bytes(out)))
    return bytes(out)


def read_strings(map_dir: Path, locale: str) -> dict[str, str]:
    path = map_dir / f"{locale}.SC2Data" / "LocalizedData" / "GameStrings.txt"
    out = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        key, sep, value = line.partition("=")
        if sep:
            out[key] = value
    return out


class HeaderEntry(NamedTuple):
    key: str
    locale: str
    value: str


def read_document_header(data: bytes) -> tuple[bytes, list[HeaderEntry]]:
    """The part before the strings, and the strings in file order.

    DocumentHeader version 8: magic, version, ..., at DOC_DEPS_OFF the u32
    count of dependencies, each a C string, then the u32 count of strings.
    Each string: u16 key length, key, the locale reversed (`SUne` is enUS),
    u16 value length, value. The strings run to the end of the file. The
    game shows these on the loading screen, not GameStrings.txt alone.
    """
    if data[:4] != DOC_MAGIC or struct.unpack_from("<I", data, 4)[0] != DOC_VERSION:
        raise SystemExit("loading_screen: not a DocumentHeader of version 8")
    try:
        pos = DOC_DEPS_OFF + 4
        for _ in range(struct.unpack_from("<I", data, DOC_DEPS_OFF)[0]):
            pos = _skip_cstr(data, pos)
        count = struct.unpack_from("<I", data, pos)[0]
        prefix = data[:pos]
        pos += 4
        entries = []
        for _ in range(count):
            size = struct.unpack_from("<H", data, pos)[0]
            key = data[pos + 2 : pos + 2 + size].decode("utf-8")
            pos += 2 + size
            locale = data[pos : pos + 4][::-1].decode("ascii")
            size = struct.unpack_from("<H", data, pos + 4)[0]
            value = data[pos + 6 : pos + 6 + size].decode("utf-8")
            if pos + 6 + size > len(data):
                raise ValueError("a string runs past the end")
            pos += 6 + size
            entries.append(HeaderEntry(key, locale, value))
    except (struct.error, ValueError) as error:
        raise SystemExit(f"loading_screen: DocumentHeader cannot be read: {error}") from error
    if pos != len(data):
        raise SystemExit(f"loading_screen: DocumentHeader has {len(data) - pos} bytes after its strings")
    return prefix, entries


def write_document_header(prefix: bytes, entries: list[HeaderEntry]) -> bytes:
    out = bytearray(prefix)
    out += struct.pack("<I", len(entries))
    for entry in entries:
        key = entry.key.encode("utf-8")
        value = entry.value.encode("utf-8")
        out += struct.pack("<H", len(key)) + key + entry.locale.encode("ascii")[::-1]
        out += struct.pack("<H", len(value)) + value
    return bytes(out)


def sync_document_header(data: bytes, strings: dict[str, dict[str, str]]) -> bytes:
    """The same DocumentHeader with the fields of LOCALES taken from their GameStrings."""
    prefix, entries = read_document_header(data)
    wanted = {(field, locale): strings[locale][field] for locale in LOCALES for field in FIELDS}
    out = []
    for entry in entries:
        value = wanted.pop((entry.key, entry.locale), entry.value)
        out.append(HeaderEntry(entry.key, entry.locale, value))
    out += [HeaderEntry(key, locale, value) for (key, locale), value in wanted.items()]
    return write_document_header(prefix, out)


def check_document_header(data: bytes, strings: dict[str, dict[str, str]]) -> list[str]:
    """R-LOAD-1 to 3 for the copy the game shows."""
    errors = []
    got = {(e.key, e.locale): e.value for e in read_document_header(data)[1]}
    for locale in LOCALES:
        for field in FIELDS:
            value = got.get((field, locale))
            if value != strings[locale].get(field):
                errors.append(f"DocumentHeader {locale} {field} differs from GameStrings")
            for word in STALE:
                if value is not None and word in value:
                    errors.append(f"DocumentHeader {locale} {field}: old text {word!r}")
    return errors


def script_text(map_dir: Path) -> str:
    parts = [p.read_text(encoding="utf-8", errors="replace") for p in sorted((map_dir / "scripts").rglob("*.galaxy"))]
    return "\n".join(parts).replace("\r\n", "\n")


def tip_tokens(tip: str) -> Counter[str]:
    """The key names, button labels and numbers of a tip, and its line count."""
    tokens = Counter(m.group(0) for m in _TIP_TOKEN.finditer(tip))
    tokens["<n/>"] = tip.count("<n/>")
    return tokens


def check_text(strings: dict[str, dict[str, str]]) -> list[str]:
    """R-LOAD-1 to 3: locale -> its strings."""
    errors = []
    first = strings[LOCALES[0]]
    want = tip_tokens(first.get(TIP, ""))
    for locale in LOCALES:
        got = strings[locale]
        for field in FIELDS:
            value = got.get(field, "")
            if not value.strip():
                errors.append(f"{locale} {field}: missing or empty")
            for word in STALE:
                if word in value:
                    errors.append(f"{locale} {field}: old text {word!r}")
        if got.get("DocInfo/Name") != NAME:
            errors.append(f"{locale} DocInfo/Name: {got.get('DocInfo/Name')!r}, want {NAME!r}")
        if got.get("DocInfo/Author") != AUTHOR:
            errors.append(f"{locale} DocInfo/Author: {got.get('DocInfo/Author')!r}, want {AUTHOR!r}")
        if locale == LOCALES[0]:
            continue
        if locale in SAME_TEXT:
            for field in FIELDS:
                if got.get(field) != strings[SAME_TEXT[locale]].get(field):
                    errors.append(f"{field}: {locale} differs from {SAME_TEXT[locale]}")
            continue
        for field in ("DocInfo/DescShort", "DocInfo/DescLong", TIP):
            if got.get(field) == first.get(field):
                errors.append(f"{locale} {field}: the enUS text, not translated")
        if tip_tokens(got.get(TIP, "")) != want:
            errors.append(f"{locale} {TIP}: keys, labels, numbers or lines differ from enUS")
    return errors


def check_bindings(tip: str, script: str, buttons: str) -> list[str]:
    """R-LOAD-4: the tip names only what the map binds."""
    errors = []
    rest = tip
    for table, source, where in ((BINDINGS, script, "script"), (BUTTONS, buttons, "button data")):
        for phrase, lines in table.items():
            if phrase not in tip:
                errors.append(f"tip: phrase missing: {phrase!r}")
            rest = rest.replace(phrase, "")
            for line in lines:
                if line not in source:
                    errors.append(f"tip: {phrase!r} has no {where} line {line!r}")
    for word in sorted({m.group(0) for m in _KEY_WORD.finditer(rest)}):
        errors.append(f"tip: key {word!r} named outside the checked phrases")
    return errors


def check(map_dir: Path) -> list[str]:
    """Validator: the text, its bindings and the wait for a key (R-LOAD-1 to 5)."""
    strings = {locale: read_strings(map_dir, locale) for locale in LOCALES}
    errors = check_text(strings)
    buttons = (map_dir / "Base.SC2Data" / "GameData" / "ButtonData.xml").read_text(encoding="utf-8")
    errors += check_bindings(strings[LOCALES[0]].get(TIP, ""), script_text(map_dir), buttons)
    errors += check_document_header((map_dir / "DocumentHeader").read_bytes(), strings)
    data = (map_dir / "MapInfo").read_bytes()
    if not wait_for_key(data):
        errors.append("MapInfo: the wait for a key is off")
    stored = struct.unpack_from("<Q", data, HASH_OFF)[0]
    if stored != map_hash(data):
        errors.append(f"MapInfo: check value {stored}, want {map_hash(data)}")
    return errors
