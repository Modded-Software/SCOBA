#!/usr/bin/env python3
"""Player records and lobby slots (REQ-ROSTER R-ROSTER-2, 3; SPEC-ROSTER 3.2).

Seats 1 to 3 are open Terran user slots. Seats 4 to 6 are locked Zerg
computer slots (humans play Terran only, operator 2026-11-18). The lane
base owners 9, 11, 12 (Terran) and 10, 13, 14 (Zerg) are locked computer
slots. Players 9 to 14 are neutral in the source map. The same table lives
in the map script (core/roster.galaxy); the validator checks both agree.

MapInfo player block (version 39, read from the source map): a u32 count,
then one record per player: id u8, control u8, 7 bytes, race C string,
12 bytes, decal C string. Control: 1 user, 2 computer, 3 neutral, 4 hostile.
"""

from __future__ import annotations

import re
import struct
from pathlib import Path
from typing import NamedTuple

PLAYER_COUNT = 16
CONTROL_USER = 1
CONTROL_COMPUTER = 2
CONTROL_NEUTRAL = 3
# Lane -> (seat, base owner, race). core/roster.galaxy holds the same.
LANES = {
    1: (1, 9, "Terr"),
    2: (2, 11, "Terr"),
    3: (3, 12, "Terr"),
    4: (4, 10, "Zerg"),
    5: (5, 13, "Zerg"),
    6: (6, 14, "Zerg"),
}
HUMAN_SEATS = (1, 2, 3)
BASE_OWNERS = {owner: race for _seat, owner, race in LANES.values()}
# Lobby controller values (Attribute 500): big-endian four-ccs.
ATTR_CONTROLLER = 500
ATTR_COMP = 1131375984   # "Comp"
ATTR_OPEN = 1332766062   # "Open"


class Slot(NamedTuple):
    control: int
    race: str
    lobby: int
    locked: bool


def slots() -> dict[int, Slot]:
    """Wanted state of every patched player."""
    out = {}
    for seat, owner, race in LANES.values():
        if seat in HUMAN_SEATS:
            out[seat] = Slot(CONTROL_USER, race, ATTR_OPEN, False)
        else:
            out[seat] = Slot(CONTROL_COMPUTER, race, ATTR_COMP, True)
        out[owner] = Slot(CONTROL_COMPUTER, race, ATTR_COMP, True)
    return out


class Record(NamedTuple):
    start: int
    end: int
    pid: int
    control: int
    race: bytes


def _cstr_end(data: bytes, pos: int) -> int | None:
    """End of the NUL-terminated string at pos; None past the buffer."""
    if pos >= len(data):
        return None
    nul = data.find(0, pos)
    return None if nul < 0 else nul + 1


def _record(data: bytes, pos: int) -> Record | None:
    """One player record at pos; None when it runs past the buffer."""
    if pos + 9 > len(data):
        return None
    pid, control = data[pos], data[pos + 1]
    race_at = pos + 9
    race_end = _cstr_end(data, race_at)
    if race_end is None:
        return None
    end = _cstr_end(data, race_end + 12)
    if end is None:
        return None
    return Record(pos, end, pid, control, bytes(data[race_at : race_end - 1]))


def find_records(data: bytes) -> list[Record]:
    """The 16 player records: the only spot where a count of 16 is followed
    by records with ids 0..15 in order."""
    count = struct.pack("<I", PLAYER_COUNT)
    pos = data.find(count)
    while pos >= 0:
        records = _walk(data, pos + 4)
        if records is not None:
            return records
        pos = data.find(count, pos + 1)
    raise SystemExit("player_slots: MapInfo player records not found")


def _walk(data: bytes, pos: int) -> list[Record] | None:
    records = []
    for pid in range(PLAYER_COUNT):
        if pos >= len(data) or data[pos] != pid:
            return None
        record = _record(data, pos)
        if record is None or record.control > 4:
            return None
        records.append(record)
        pos = record.end
    return records


def patch_mapinfo(data: bytes) -> bytes:
    records = find_records(data)
    want = slots()
    out = bytearray(data)
    # Back to front, so earlier offsets stay valid while a race changes size.
    for record in reversed(records):
        slot = want.get(record.pid)
        if slot is None:
            continue
        if record.control not in (CONTROL_USER, CONTROL_NEUTRAL, CONTROL_COMPUTER):
            raise SystemExit(f"player_slots: player {record.pid} control {record.control}, want user, neutral or computer")
        if record.race and record.race != slot.race.encode("ascii"):
            raise SystemExit(f"player_slots: player {record.pid} race {record.race!r}, want {slot.race}")
        out[record.start + 1] = slot.control
        race_at = record.start + 9
        out[race_at : race_at + len(record.race)] = slot.race.encode("ascii")
    return bytes(out)


def _default(pad: str, pid: int, slot: Slot) -> str:
    locked = f"{pad}    <Locked/>\n" if slot.locked else ""
    return f"{pad}<Default>\n{pad}    <Slot Id=\"{pid}\"/>\n{pad}    <Value Id=\"{slot.lobby}\"/>\n{locked}{pad}</Default>\n"


def _controller(text: str) -> re.Match[str]:
    block = re.search(rf'<Attribute Namespace="999" Id="{ATTR_CONTROLLER}">(.*?)</Attribute>', text, re.S)
    if block is None:
        raise SystemExit("player_slots: controller attribute not found")
    return block


def lobby(text: str) -> dict[int, tuple[int, bool]]:
    """Slot -> (controller value, locked) from the controller attribute."""
    out = {}
    for m in re.finditer(r'<Default>\s*<Slot Id="(\d+)"/>\s*<Value Id="(\d+)"/>\s*(<Locked/>)?\s*</Default>', _controller(text).group(1)):
        out[int(m.group(1))] = (int(m.group(2)), m.group(3) is not None)
    return out


def patch_attributes(text: str) -> str:
    """Lobby slot defaults: one Default per patched slot, replaced or added."""
    block = _controller(text)
    body = block.group(1)
    indent = re.search(r"\n(\s*)<Default>", body)
    if indent is None:
        raise SystemExit("player_slots: controller defaults not found")
    pad = indent.group(1)
    want = slots()
    for pid in sorted(want):
        new = _default(pad, pid, want[pid])
        old = re.search(rf'{pad}<Default>\n\s*<Slot Id="{pid}"/>\n.*?</Default>\n', body, re.S)
        if old is not None:
            body = body[: old.start()] + new + body[old.end() :]
            continue
        last = body.rfind("</Default>") + len("</Default>\n")
        body = body[:last] + new + body[last:]
    return text[: block.start(1)] + body + text[block.end(1) :]


def apply(map_dir: Path) -> None:
    mapinfo = map_dir / "MapInfo"
    mapinfo.write_bytes(patch_mapinfo(mapinfo.read_bytes()))
    attributes = map_dir / "Attributes"
    raw = attributes.read_bytes()
    newline = "\r\n" if b"\r\n" in raw else "\n"
    text = raw.decode("utf-8").replace("\r\n", "\n")
    attributes.write_bytes(patch_attributes(text).replace("\n", newline).encode("utf-8"))


def check(map_dir: Path) -> list[str]:
    """Validator: player records and lobby slots as the roster wants."""
    errors = []
    records = {r.pid: r for r in find_records((map_dir / "MapInfo").read_bytes())}
    seen = lobby((map_dir / "Attributes").read_bytes().decode("utf-8").replace("\r\n", "\n"))
    for pid, slot in slots().items():
        record = records[pid]
        if record.control != slot.control or record.race != slot.race.encode("ascii"):
            errors.append(f"player {pid}: control {record.control} race {record.race!r}, want {slot.control} {slot.race}")
        if seen.get(pid) != (slot.lobby, slot.locked):
            errors.append(f"slot {pid}: lobby {seen.get(pid)}, want {(slot.lobby, slot.locked)}")
    return errors


def check_script(script: str) -> list[str]:
    """Validator: core/roster.galaxy gives the same seats and owners."""
    errors = []
    body = re.search(r"int gf_RosterOwner \(int lp_lane\) \{\n(.*?)\n\}", script, re.S)
    if body is None:
        return ["roster: gf_RosterOwner not found"]
    for lane, (_seat, owner, _race) in LANES.items():
        m = re.search(rf"if \(lp_lane == {lane}\) {{ return (\d+); }}", body.group(1))
        if m is None or int(m.group(1)) != owner:
            errors.append(f"roster: lane {lane} owner {m.group(1) if m else None}, want {owner}")
    # R-ROSTER-1: no owner outside the table; anything else returns 0.
    owners = {owner for _seat, owner, _race in LANES.values()}
    returns = [int(n) for n in re.findall(r"return (\d+);", body.group(1))]
    for n in returns:
        if n not in owners and n != 0:
            errors.append(f"roster: owner {n} not in the table")
    if not returns or returns[-1] != 0 or returns.count(0) != 1:
        errors.append("roster: gf_RosterOwner must end with one 'return 0;'")
    return errors
