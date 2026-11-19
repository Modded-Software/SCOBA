"""Melee map data for the stock AI (REQ-BASE-AI 3.5, SPEC-BASE-AI 4.7a).

Start locations: one `StartLoc` point per base owner at the centre of its
lane spawn region, and the owner's `MapInfo` player record pointing at it.
The record layout (race, then u32, then the start location object id, then
u32) was read from the Void campaign map pkorhal01 (MapInfo version 39).

Depots: the six placed Supply Depots belong to the Terran owners, two each.

Runs on the built map, after Objects and Regions are scaled.
"""
from __future__ import annotations

import re
import struct
from pathlib import Path

from mapgen.player_slots import LANES, find_records

# Lane -> spawn region id (app/init.galaxy gv_sPAWNLOCATIONS).
LANE_REGION = {1: 1, 2: 3, 3: 4, 4: 2, 5: 5, 6: 6}
# Object ids of the start points; above every id the map source uses.
START_ID_BASE = 2100000000
# Placed depot id -> owner (R-BASE-29).
DEPOT_OWNERS = {
    "1689533396": 9, "1971666357": 9,
    "352867994": 11, "1559950947": 11,
    "1455266132": 12, "1424795256": 12,
}
START_FIELD = 4  # bytes after the race terminator


def start_id(owner: int) -> int:
    return START_ID_BASE + owner


def region_centres(regions_xml: str) -> dict[int, tuple[float, float]]:
    out = {}
    for m in re.finditer(r'<region id="(\d+)">.*?<center value="([^"]+)"/>', regions_xml, re.S):
        x, y = m.group(2).split(",")
        out[int(m.group(1))] = (float(x), float(y))
    return out


def start_points(regions_xml: str) -> dict[int, tuple[int, int]]:
    """Owner -> start point. Whole cells: the 8x8 hall centres on a cell corner."""
    centres = region_centres(regions_xml)
    out = {}
    for lane, (_seat, owner, _race) in LANES.items():
        x, y = centres[LANE_REGION[lane]]
        out[owner] = (round(x), round(y))
    return out


def _point_xml(owner: int, at: tuple[int, int]) -> str:
    return (f'    <ObjectPoint Id="{start_id(owner)}" Position="{at[0]},{at[1]},0" Scale="1,1,1" '
            f'Type="StartLoc" Name="Start Location P{owner:02d}" Color="0,0,0,0"/>\n')


def patch_objects(objects_xml: str, points: dict[int, tuple[int, int]]) -> str:
    if 'Type="StartLoc"' in objects_xml:
        raise SystemExit("melee_map: Objects already has start locations")
    for oid in DEPOT_OWNERS:
        if f'Id="{oid}"' not in objects_xml:
            raise SystemExit(f"melee_map: depot {oid} missing")
    for owner in points:
        if f'Id="{start_id(owner)}"' in objects_xml:
            raise SystemExit(f"melee_map: object id {start_id(owner)} already used")
    end = objects_xml.rindex("</PlacedObjects>")
    block = "".join(_point_xml(owner, points[owner]) for owner in sorted(points))
    return objects_xml[:end] + block + objects_xml[end:]


def _start_at(data: bytes, record) -> int:
    race_end = data.index(0, record.start + 9) + 1
    return race_end + START_FIELD


def patch_mapinfo(data: bytes, owners: list[int]) -> bytes:
    out = bytearray(data)
    records = {r.pid: r for r in find_records(data)}
    for owner in owners:
        struct.pack_into("<I", out, _start_at(data, records[owner]), start_id(owner))
    return bytes(out)


def apply(map_dir: Path) -> None:
    regions = (map_dir / "Regions").read_text(encoding="utf-8")
    points = start_points(regions)
    objects = map_dir / "Objects"
    raw = objects.read_bytes()
    newline = "\r\n" if b"\r\n" in raw else "\n"
    text = raw.decode("utf-8").replace("\r\n", "\n")
    objects.write_bytes(patch_objects(text, points).replace("\n", newline).encode("utf-8"))
    mapinfo = map_dir / "MapInfo"
    mapinfo.write_bytes(patch_mapinfo(mapinfo.read_bytes(), sorted(points)))


def check(map_dir: Path) -> list[str]:
    """Validator: start points, record pointers, depot owners."""
    errors = []
    objects = (map_dir / "Objects").read_text(encoding="utf-8")
    regions = (map_dir / "Regions").read_text(encoding="utf-8")
    want = start_points(regions)
    found = {}
    for m in re.finditer(r'<ObjectPoint Id="(\d+)" Position="([^"]+)"[^>]*Type="StartLoc"', objects):
        x, y = m.group(2).split(",")[:2]
        found[int(m.group(1))] = (float(x), float(y))
    if len(found) != len(want):
        errors.append(f"start locations: {len(found)}, want {len(want)}")
    data = (map_dir / "MapInfo").read_bytes()
    records = {r.pid: r for r in find_records(data)}
    for owner, at in want.items():
        sid = start_id(owner)
        if found.get(sid) != (float(at[0]), float(at[1])):
            errors.append(f"start location of {owner}: {found.get(sid)}, want {at}")
        got = struct.unpack_from("<I", data, _start_at(data, records[owner]))[0]
        if got != sid:
            errors.append(f"MapInfo player {owner} start location {got}, want {sid}")
    for pid, record in records.items():
        if pid in want:
            continue
        got = struct.unpack_from("<I", data, _start_at(data, record))[0]
        if got != 0:
            errors.append(f"MapInfo player {pid} start location {got}, want 0")
    depots = dict(re.findall(r'<ObjectUnit Id="(\d+)" [^>]*UnitType="SupplyDepot" Player="(\d+)"', objects))
    for oid, owner in DEPOT_OWNERS.items():
        if depots.get(oid) != str(owner):
            errors.append(f"depot {oid}: owner {depots.get(oid)}, want {owner}")
    extra = sorted(set(depots) - set(DEPOT_OWNERS))
    if extra:
        errors.append(f"unexpected placed depots: {extra}")
    return errors
