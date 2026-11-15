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
    footprint_xml,
    set_unit_footprint,
    shape_of,
    tree_actor_id,
    tree_actor_xml,
)
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


def write_catalogs(map_dir: Path, trees: list[Blocker], spores: dict[str, Blocker]) -> int:
    """Footprints, tree actors, spore unit footprints, preloads. Returns the footprint count."""
    data_dir = game_data(map_dir)
    shapes = sorted({(b.polygon, b.cells) for b in trees + list(spores.values())})
    append_catalog(data_dir / "FootprintData.xml", "".join(footprint_xml(p, c) for p, c in shapes))
    tree_polygons = sorted({b.polygon for b in trees})
    append_catalog(data_dir / "ActorData.xml", "".join(tree_actor_xml(p) for p in tree_polygons))
    unit_path = data_dir / "UnitData.xml"
    unit_text = unit_path.read_text(encoding="utf-8")
    for unit, blocker in sorted(spores.items()):
        unit_text = set_unit_footprint(unit_text, unit, blocker.footprint)
    unit_path.write_text(unit_text, encoding="utf-8")
    add_preload(map_dir / "Preload.xml", [tree_actor_id(p) for p in tree_polygons])
    return len(shapes)


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


def check_scaled_footprints(map_dir: Path, data: dict | None = None) -> list[str]:
    """Problems with the generated blockers of a built map. Empty when all pass."""
    map_dir = Path(map_dir)
    data = data if data is not None else load_slices()
    data_dir = game_data(map_dir)
    footprints = catalog_bodies(data_dir / "FootprintData.xml", "CFootprint")
    text = (map_dir / "Objects").read_text(encoding="utf-8")
    return check_trees(text, data, footprints, catalog_bodies(data_dir / "ActorData.xml", "CActorDoodad")) + check_spores(
        text, data, footprints, catalog_bodies(data_dir / "UnitData.xml", "CUnit")
    )
