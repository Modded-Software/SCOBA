"""Footprint and actor ids, and the XML edits of the map's game data."""

from __future__ import annotations

import hashlib
import math
import re
from pathlib import Path

from . import config
from .raster import Polygon


def attr(block: str, name: str) -> str | None:
    match = re.search(rf'\b{name}="([^"]*)"', block)
    return match.group(1) if match else None


def footprint_id(polygon: Polygon, cells: tuple[str, ...] = ()) -> str:
    key = repr(polygon) + (repr(cells) if cells else "")
    digest = hashlib.sha1(key.encode("ascii")).hexdigest()[:10]
    return f"{config.FOOTPRINT_PREFIX}{digest}"


def tree_actor_id(polygon: Polygon) -> str:
    return config.ACTOR_PREFIX + footprint_id(polygon)[len(config.FOOTPRINT_PREFIX) :]


def footprint_xml(polygon: Polygon, cells: tuple[str, ...] = ()) -> str:
    """A CFootprint with the Shape polygon; Place/Check rows for units, 1x1 for doodads."""
    offsets = ";".join(f"{x:g},{y:g}" for x, y in polygon)
    count = len(polygon)
    borders = ";".join(f"{(k - 1) % count},{k},2" for k in range(count))
    radius = max(math.hypot(x, y) for x, y in polygon)
    if cells:
        half = len(cells) // 2
        area = f"{-half},{-half},{half},{half}"
        rows = "".join(f'            <Rows value="{row}"/>\n' for row in cells)
    else:
        area = "0,0,1,1"
        rows = '            <Rows value="x"/>\n'
    layers = "".join(f'        <Layers index="{name}" Area="{area}">\n{rows}        </Layers>\n' for name in ("Check", "Place"))
    return (
        f'    <CFootprint id="{footprint_id(polygon, cells)}">\n'
        + layers
        + "        <Shape>\n"
        f'            <Radius value="{radius:.4f}"/>\n'
        f'            <Offsets value="{offsets}"/>\n'
        f'            <Borders value="{borders}"/>\n'
        "        </Shape>\n"
        "    </CFootprint>\n"
    )


def tree_actor_xml(polygon: Polygon) -> str:
    return (
        f'    <CActorDoodad id="{tree_actor_id(polygon)}" parent="{config.TREE_TYPE}">\n'
        f'        <Model value="{config.TREE_TYPE}"/>\n'
        f'        <Footprint value="{footprint_id(polygon)}"/>\n'
        "    </CActorDoodad>\n"
    )


def set_unit_footprint(text: str, unit: str, footprint: str) -> str:
    block = re.compile(r'(<CUnit\b[^>]*\bid="' + unit + r'"[^>]*>)(.*?)(\s*</CUnit>)', re.S)
    match = block.search(text)
    line = f'<Footprint value="{footprint}"/>'
    if match is None:
        entry = f'    <CUnit id="{unit}">\n        {line}\n    </CUnit>\n'
        return text.replace("</Catalog>", entry + "</Catalog>", 1)
    body = match.group(2)
    if re.search(r'<Footprint value="[^"]*"/>', body):
        body = re.sub(r'<Footprint value="[^"]*"/>', line, body, count=1)
    else:
        body = body + f"\n        {line}"
    return text[: match.start()] + match.group(1) + body + match.group(3) + text[match.end() :]


def append_catalog(path: Path, entries: str) -> None:
    if path.exists():
        text = path.read_text(encoding="utf-8")
        if "</Catalog>" not in text:
            raise ValueError(f"{path} has no </Catalog>")
        text = text.replace("</Catalog>", entries + "</Catalog>", 1)
    else:
        text = '<?xml version="1.0" encoding="us-ascii"?>\n<Catalog>\n' + entries + "</Catalog>\n"
    path.write_text(text, encoding="utf-8")


def add_preload(path: Path, actor_ids: list[str]) -> None:
    """Preload each actor with the stock tree's variations."""
    text = path.read_text(encoding="utf-8")
    line = re.search(r'<Actor id="' + config.TREE_TYPE + r'"[^>]*/>', text)
    if line is None:
        raise ValueError(f"{path} has no {config.TREE_TYPE} actor preload")
    variations = attr(line.group(0), "Variations")
    suffix = f' Variations="{variations}"' if variations else ""
    extra = "".join(f'\n<Actor id="{actor}"{suffix}/>' for actor in actor_ids)
    path.write_text(text[: line.end()] + extra + text[line.end() :], encoding="utf-8")


def catalog_bodies(path: Path, tag: str) -> dict[str, str]:
    """Entry id to inner XML for every `tag` entry of a catalog file."""
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(r"<" + tag + r'\b[^>]*\bid="([^"]+)"[^>]*>(.*?)</' + tag + r">", re.S)
    return {m.group(1): m.group(2) for m in pattern.finditer(text)}


def shape_of(body: str) -> Polygon:
    match = re.search(r'<Offsets value="([^"]+)"/>', body)
    if match is None:
        return ()
    return tuple((float(a), float(b)) for a, b in (pair.split(",") for pair in match.group(1).split(";")))
