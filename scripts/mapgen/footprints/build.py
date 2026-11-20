"""Apply the blockers to a built map, check a built map, write the fit report.

Entry point of the footprints package: pathing blockers for scaled trees and
spores, shaped like their mesh at the feet. A placed Scale only scales the
mesh; the footprint stays stock size. See docs/specifications/SPEC-SCALED-FOOTPRINTS.md.

Modules, in dependency order: config (knobs), slices (mesh slices, scale,
engine rotation), raster (0.5 grid sampling, erosion, tracing), catalog
(ids, XML edits), blocker (shape and fit), placement (placed objects),
build (this). Tools, run from scripts/: `uv run python -m footprints.measure`
slices the models; `uv run python -m footprints.preview` prints ASCII views.

Runs on the built map after props_expand and scale_spores. Idempotent: a
marker file makes a second run a no-op.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import config
from .blocker import Blocker, fit_problems
from .catalog import (
    add_preload,
    append_catalog,
    attr,
    catalog_bodies,
    footprint_id,
    footprint_xml,
    set_unit_footprint,
    shape_of,
    tree_actor_id,
    tree_actor_xml,
)
from .hall import check_halls, hall_footprint_id, hall_footprint_xml, hall_footprints
from .placement import size_spores, size_trees, tree_blocker, tree_pattern
from .slices import load_slices


def game_data(map_dir: Path) -> Path:
    return map_dir / "Base.SC2Data" / "GameData"


def report_lines(blockers: list[Blocker]) -> list[str]:
    lines = ["section footprint vertices mesh_area blocked_area covered ratio offset"]
    for b in blockers:
        f = b.fit
        lines.append(
            f"{b.section} {b.footprint} {len(b.polygon)} {f.mesh_area:.2f} {f.blocked_area:.2f}"
            f" {f.covered:.2f} {f.ratio:.2f} {f.offset:.2f}"
        )
    return lines


def square_shape(side: int) -> tuple[tuple[tuple[float, float], ...], tuple[str, ...]]:
    """A side x side cell square centred on the unit: Shape polygon and Place rows."""
    h = side / 2
    # Clockwise, like the stock footprints and the traced shapes.
    polygon = ((-h, -h), (-h, h), (h, h), (h, -h))
    return polygon, tuple("x" * side for _ in range(side))


def square_footprints() -> dict[str, tuple[tuple[tuple[float, float], ...], tuple[str, ...]]]:
    return {unit: square_shape(side) for unit, side in sorted(config.SQUARE_UNITS.items())}


def flatten_events(unit: str) -> list[str]:
    return [f'<On Terms="{terms.format(u=unit)}" Send="{send}"/>' for terms, send in config.FLATTEN_EVENTS]


def add_flatten_events(text: str, unit: str) -> str:
    """Add the terrain flatten events to the unit's CActorUnit entry.

    An existing entry (an earlier build step may have one) gets the events
    appended. Without one, a new entry with no parent merges into the stock actor.
    """
    lines = flatten_events(unit)
    entry = re.compile(r'(<CActorUnit\b[^>]*\bid="' + re.escape(unit) + r'"[^>]*>)(.*?)(\n?[ \t]*</CActorUnit>)', re.DOTALL)
    found = list(entry.finditer(text))
    if len(found) > 1:
        raise ValueError(f"ActorData.xml has {len(found)} CActorUnit {unit} entries")
    if not found:
        body = "".join(f"        {line}\n" for line in lines)
        if "</Catalog>" not in text:
            raise ValueError("ActorData.xml has no </Catalog>")
        return text.replace("</Catalog>", f'    <CActorUnit id="{unit}">\n{body}    </CActorUnit>\n</Catalog>', 1)
    m = found[0]
    missing = [line for line in lines if line not in m.group(2)]
    extra = "".join(f"\n        {line}" for line in missing)
    return text[: m.end(2)] + extra + text[m.end(2) :]


def write_catalogs(map_dir: Path, trees: list[Blocker], spores: dict[str, Blocker]) -> int:
    """Footprints, tree actors, spore and square unit footprints, preloads. Returns the footprint count."""
    data_dir = game_data(map_dir)
    squares = square_footprints()
    shapes = sorted({(b.polygon, b.cells) for b in trees + list(spores.values())} | set(squares.values()))
    append_catalog(data_dir / "FootprintData.xml", "".join(footprint_xml(p, c) for p, c in shapes))
    tree_polygons = sorted({b.polygon for b in trees})
    actor_path = data_dir / "ActorData.xml"
    append_catalog(actor_path, "".join(tree_actor_xml(p) for p in tree_polygons))
    actor_text = actor_path.read_text(encoding="utf-8")
    for unit in (*squares, *config.FLATTEN_UNITS):
        actor_text = add_flatten_events(actor_text, unit)
    actor_path.write_text(actor_text, encoding="utf-8")
    unit_path = data_dir / "UnitData.xml"
    unit_text = unit_path.read_text(encoding="utf-8")
    for unit, blocker in sorted(spores.items()):
        unit_text = set_unit_footprint(unit_text, unit, blocker.footprint)
    for unit, (polygon, cells) in squares.items():
        unit_text = set_unit_footprint(unit_text, unit, footprint_id(polygon, cells))
    unit_path.write_text(unit_text, encoding="utf-8")
    add_preload(map_dir / "Preload.xml", [tree_actor_id(p) for p in tree_polygons])
    return len(shapes)


def write_halls(map_dir: Path, data: dict) -> str:
    """Measured hall footprints (R-FP-10) linked as the hall units' Footprint. Returns a note."""
    data_dir = game_data(map_dir)
    halls = hall_footprints(data, (data_dir / "ActorData.xml").read_text(encoding="utf-8"))
    append_catalog(data_dir / "FootprintData.xml", "".join(hall_footprint_xml(c) for c in sorted(set(halls.values()))))
    unit_path = data_dir / "UnitData.xml"
    unit_text = unit_path.read_text(encoding="utf-8")
    for unit, hall in halls.items():
        unit_text = set_unit_footprint(unit_text, unit, hall_footprint_id(hall))
    unit_path.write_text(unit_text, encoding="utf-8")
    return "".join(f" {u}={hall_footprint_id(c)}" for u, c in halls.items())


def apply_scaled_footprints(map_dir: Path, data: dict | None = None) -> bool:
    """Give every placed tree and spore its blocker. False when already applied."""
    map_dir = Path(map_dir)
    marker = map_dir / config.MARKER
    if marker.exists():
        return False
    data = data if data is not None else load_slices()
    objects = map_dir / "Objects"
    text, trees = size_trees(objects.read_text(encoding="utf-8"), data)
    if not trees:
        raise ValueError(f"no placed {config.TREE_TYPE} in {objects}")
    spores = size_spores(text, data)
    (map_dir / config.REPORT).write_text("\n".join(report_lines(trees + list(spores.values()))) + "\n", encoding="utf-8")
    # Spore fit is reported, not enforced: their mesh fill is noisy (disk_blocker).
    problems = [p for b in trees for p in fit_problems(b)]
    if problems:
        raise ValueError("footprint fit failed:\n" + "\n".join(problems))
    objects.write_text(text, encoding="utf-8")
    count = write_catalogs(map_dir, trees, spores)
    spore_note = " ".join(f"{u}={b.footprint}" for u, b in sorted(spores.items()))
    spore_note += "".join(f" {u}={footprint_id(p, c)}" for u, (p, c) in square_footprints().items())
    spore_note += write_halls(map_dir, data)
    marker.write_text(f"trees={len(trees)} footprints={count} {spore_note}\n", encoding="utf-8")
    return True


def check_trees(text: str, data: dict, footprints: dict[str, str], actors: dict[str, str]) -> list[str]:
    problems = []
    if tree_pattern(config.TREE_TYPE).search(text):
        problems.append(f"a placed tree still uses the stock {config.TREE_TYPE} footprint")
    trees = tree_pattern(config.ACTOR_PREFIX + "[0-9a-f]+").findall(text)
    if not trees:
        problems.append("no placed tree uses a generated footprint type")
    for block in trees:
        actor = attr(block, "Type") or ""
        body = actors.get(actor)
        fp = re.search(r'<Footprint value="([^"]+)"/>', body or "")
        if body is None or fp is None or fp.group(1) not in footprints:
            problems.append(f"{actor} has no generated footprint")
            continue
        want = tree_blocker(data, block)
        if shape_of(footprints[fp.group(1)]) != want.polygon:
            problems.append(f"tree {attr(block, 'Id')} footprint does not match its mesh")
        problems.extend(fit_problems(want))
    return problems


def check_spores(text: str, data: dict, footprints: dict[str, str], units: dict[str, str]) -> list[str]:
    problems = []
    for unit, blocker in size_spores(text, data).items():
        fp = re.search(r'<Footprint value="([^"]+)"/>', units.get(unit, ""))
        if fp is None or fp.group(1) not in footprints or fp.group(1) != blocker.footprint:
            problems.append(f"{unit} has no generated footprint")
    return problems


def flatten_problems(unit: str, actors: dict[str, str] | None) -> list[str]:
    body = (actors or {}).get(unit, "")
    return [f"{unit} actor does not flatten terrain ({line})" for line in flatten_events(unit) if line not in body]


def check_squares(text: str, footprints: dict[str, str], units: dict[str, str], actors: dict[str, str] | None = None) -> list[str]:
    """Every placed square unit links its square footprint and flattens the terrain."""
    problems = []
    for unit, (polygon, cells) in square_footprints().items():
        if f'UnitType="{unit}"' not in text:
            continue
        want = footprint_id(polygon, cells)
        fp = re.search(r'<Footprint value="([^"]+)"/>', units.get(unit, ""))
        if fp is None or fp.group(1) != want or want not in footprints:
            problems.append(f"{unit} has no generated square footprint")
        elif shape_of(footprints[want]) != polygon or footprints[want].count('<Rows value="' + "x" * len(cells) + '"/>') != 2 * len(cells):
            problems.append(f"{unit} square footprint has the wrong shape")
        problems += flatten_problems(unit, actors)
    for unit in config.FLATTEN_UNITS:
        if f'UnitType="{unit}"' in text:
            problems += flatten_problems(unit, actors)
    return problems


def check_scaled_footprints(map_dir: Path, data: dict | None = None) -> list[str]:
    """Problems with the generated blockers of a built map. Empty when all pass."""
    map_dir = Path(map_dir)
    data = data if data is not None else load_slices()
    data_dir = game_data(map_dir)
    footprints = catalog_bodies(data_dir / "FootprintData.xml", "CFootprint")
    text = (map_dir / "Objects").read_text(encoding="utf-8")
    units = catalog_bodies(data_dir / "UnitData.xml", "CUnit")
    actor_text = (data_dir / "ActorData.xml").read_text(encoding="utf-8")
    return (
        check_trees(text, data, footprints, catalog_bodies(data_dir / "ActorData.xml", "CActorDoodad"))
        + check_spores(text, data, footprints, units)
        + check_squares(text, footprints, units, catalog_bodies(data_dir / "ActorData.xml", "CActorUnit"))
        + check_halls(footprints, units, data, actor_text)
    )
