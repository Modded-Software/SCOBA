"""baseai gas group: the radius scan data patch (SC2_BA_GAS_SCAN, SPEC-BASE-AI 8).

The engine takes a structure's radius from its footprint Shape, so a radius is set by a Shape:
the stock built octagon (FootprintGeyserRoundedBuilt, radius 1.6772) scaled. Layers stay the
map's 6x6 ones. Pure text functions, so host tests run them on the map's own data
(scripts/testkit/tests/test_resources.py)."""

from __future__ import annotations

import math
import os
import re
from pathlib import Path

SCAN_ENV = "SC2_BA_GAS_SCAN"
SCAN_GAS = (("Refinery", "BgBuiltFootT"), ("Extractor", "BgBuiltFootZ"))
SCAN_GEYSERS = (("BgGeyserA", "BgGeyserFootA"), ("BgGeyserB", "BgGeyserFootB"))
SCAN_BUILT_ON_FROM = 3     # stock Refinery and Extractor name three geysers (index 0 to 2)
OCTAGON = ((-0.75, -1.5), (0.75, -1.5), (-0.75, 1.5), (0.75, 1.5), (-1.5, -0.75), (-1.5, 0.75), (1.5, -0.75), (1.5, 0.75))
OCTAGON_BORDERS = "0,4,2;1,0,2;2,3,2;3,7,2;4,5,2;5,2,2;6,1,2;7,6,2"
OCTAGON_RADIUS = 1.6772
SQUARE_HALF = 3.0
CUT_SQUARE_BORDERS = "7,0,2;0,1,2;1,2,2;2,3,2;3,4,2;4,5,2;5,6,2;6,7,2"


def gas_scan() -> tuple[str, ...] | None:
    """SC2_BA_GAS_SCAN=<refinery>,<extractor>,<geyser A>,<geyser B>: four
    footprint Shapes for the probe map. Each is "map" (the map's 6x6
    square), a radius (the stock built octagon scaled to it) or "sq<cut>"
    (the 6x6 square with its corners cut by <cut> on each side) or "none"
    (no Shape), with an optional "@<radius>" that sets the unit Radius
    field (default: the map's 3). The
    Refinery and the Extractor get their own built footprint; two probe
    geyser types BgGeyserA and BgGeyserB are added, which both build on.
    The gas harness then places one probe geyser per AI lane (A: the Terran
    lanes 2 and 3, B: the Zerg lanes 5 and 6). Default: no scan."""
    raw = os.environ.get(SCAN_ENV)
    if not raw:
        return None
    parts = tuple(raw.split(","))
    if len(parts) != 4:
        raise SystemExit(f"{SCAN_ENV} must be four shapes, comma separated, got {raw}")
    for part in parts:
        scan_shape(part)
    return parts


def octagon_shape(radius: float) -> str:
    """A footprint Shape: the stock built octagon scaled to the radius."""
    scale = radius / OCTAGON_RADIUS
    offsets = ";".join(f"{x * scale:.4f},{y * scale:.4f}" for x, y in OCTAGON)
    return (f'<Shape>\n            <Radius value="{radius:.4f}"/>\n            <Offsets value="{offsets}"/>\n'
            f'            <Borders value="{OCTAGON_BORDERS}"/>\n        </Shape>')


def cut_square_shape(cut: float) -> str:
    """A footprint Shape: the 6x6 square, each corner cut by cut along both sides. Its radius
    is hypot(3, 3 - cut); the centre of the corner 0.5 sub-cell (2.75, 2.75) stays inside up
    to cut 0.5."""
    if not 0 < cut < SQUARE_HALF:
        raise SystemExit(f"{SCAN_ENV}: corner cut {cut} is not between 0 and {SQUARE_HALF}")
    h, k = SQUARE_HALF, SQUARE_HALF - cut
    points = ((-h, -k), (-h, k), (-k, h), (k, h), (h, k), (h, -k), (k, -h), (-k, -h))
    offsets = ";".join(f"{x:.4f},{y:.4f}" for x, y in points)
    return (f'<Shape>\n            <Radius value="{math.hypot(h, k):.4f}"/>\n            <Offsets value="{offsets}"/>\n'
            f'            <Borders value="{CUT_SQUARE_BORDERS}"/>\n        </Shape>')


def split_spec(spec: str) -> tuple[str, float | None]:
    """A scan spec is <shape>[@<unit radius>]: the shape part, and the unit Radius field the
    unit gets (None: it keeps the map's)."""
    shape, mark, radius = spec.partition("@")
    if not mark:
        return shape, None
    try:
        value = float(radius)
    except ValueError as error:
        raise SystemExit(f"{SCAN_ENV}: {spec}: {radius} is not a unit radius") from error
    if value <= 0:
        raise SystemExit(f"{SCAN_ENV}: {spec}: the unit radius must be above 0")
    return shape, value


def scan_shape(spec: str) -> str | None:
    """The Shape text of one scan spec; None for "map" (the Shape stays) and for "none" (the
    footprint gets no Shape)."""
    spec = split_spec(spec)[0]
    if spec in ("map", "none"):
        return None
    try:
        return cut_square_shape(float(spec[2:])) if spec.startswith("sq") else octagon_shape(float(spec))
    except ValueError as error:
        raise SystemExit(f"{SCAN_ENV}: {spec} is not map, none, a radius or sq<cut>") from error


def footprint_copy(text: str, source: str, name: str, spec: str) -> str:
    """The CFootprint source of a FootprintData text under a new name, its Shape that of the
    scan spec ("map": the Shape stays; "none": the Shape is removed)."""
    found = re.search(rf'<CFootprint id="{source}">.*?</CFootprint>', text, re.S)
    if not found:
        raise SystemExit(f"FootprintData.xml: no {source}")
    body = found.group(0).replace(f'id="{source}"', f'id="{name}"', 1)
    shape = scan_shape(spec)
    spec = split_spec(spec)[0]
    if spec == "map":
        return body
    if spec == "none":
        body, count = re.subn(r"\n\s*<Shape>.*?</Shape>", "", body, count=1, flags=re.S)
    else:
        body, count = re.subn(r"<Shape>.*?</Shape>", lambda _m: shape, body, count=1, flags=re.S)
    if count != 1:
        raise SystemExit(f"FootprintData.xml: {source} has no Shape")
    return body


def scan_footprints(text: str, scan: tuple[str, ...]) -> str:
    """FootprintData text with the four scan footprints added."""
    made = [footprint_copy(text, "FootprintScobaGeyser6x6Built", foot, spec)
            for (_unit, foot), spec in zip(SCAN_GAS, scan[:2])]
    made += [footprint_copy(text, "FootprintScobaGeyser6x6", foot, spec)
             for (_unit, foot), spec in zip(SCAN_GEYSERS, scan[2:])]
    if text.count("</Catalog>") != 1:
        raise SystemExit("FootprintData.xml: expected one </Catalog>")
    return text.replace("</Catalog>", "".join(f"    {body}\n" for body in made) + "</Catalog>")


def scan_units(text: str, scan: tuple[str, ...] = ("map", "map", "map", "map")) -> str:
    """UnitData text for the scan: the Refinery and the Extractor name their scan footprint and
    build on the probe geysers too; the probe geyser types are added. A spec with @<radius>
    sets the unit Radius field of its unit."""
    built_on = "".join(f'        <BuiltOn index="{SCAN_BUILT_ON_FROM + n}" value="{unit}"/>\n'
                       for n, (unit, _foot) in enumerate(SCAN_GEYSERS))
    for (unit, foot), spec in zip(SCAN_GAS, scan[:2]):
        found = re.search(rf'<CUnit id="{unit}">.*?</CUnit>', text, re.S)
        if not found or found.group(0).count('<Footprint value="FootprintScobaGeyser6x6Built"/>') != 1:
            raise SystemExit(f"UnitData.xml: expected one {unit} entry with the 6x6 built footprint")
        body = found.group(0).replace("FootprintScobaGeyser6x6Built", foot)
        body = body.replace("    </CUnit>", built_on + "    </CUnit>")
        radius = split_spec(spec)[1]
        if radius is not None:
            body, count = re.subn(r'<Radius value="[^"]+"/>', f'<Radius value="{radius:g}"/>', body, count=1)
            if count != 1:
                raise SystemExit(f"UnitData.xml: {unit} has no Radius")
        text = text.replace(found.group(0), body)
    geysers = ""
    for (unit, foot), spec in zip(SCAN_GEYSERS, scan[2:]):
        radius = split_spec(spec)[1]
        own = f'        <Radius value="{radius:g}"/>\n' if radius is not None else ""
        geysers += f'    <CUnit id="{unit}" parent="VespeneGeyser">\n{own}        <Footprint value="{foot}"/>\n    </CUnit>\n'
    if text.count("</Catalog>") != 1:
        raise SystemExit("UnitData.xml: expected one </Catalog>")
    return text.replace("</Catalog>", geysers + "</Catalog>")


def _rewrite(path: Path, change) -> None:
    """Rewrite a map XML through change(text); the file keeps its line ends."""
    raw = path.read_bytes()
    crlf = b"\r\n" in raw
    text = change(raw.decode("utf-8").replace("\r\n", "\n"))
    path.write_bytes(text.replace("\n", "\r\n").encode("utf-8") if crlf else text.encode("utf-8"))


def patch_scan(map_dir: Path, scan: tuple[str, ...]) -> None:
    data = map_dir / "Base.SC2Data" / "GameData"
    _rewrite(data / "FootprintData.xml", lambda text: scan_footprints(text, scan))
    _rewrite(data / "UnitData.xml", lambda text: scan_units(text, scan))
    print(f"baseai: probe map gas radius scan, {SCAN_ENV}={os.environ[SCAN_ENV]}")
