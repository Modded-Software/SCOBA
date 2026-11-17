"""Raise every non-flora doodad that has an absolute height by DOODAD_LIFT.

Operator, 2026-11-15: all props looked sunk into the ground. Flora gets its
lift in build.py (GROUND_LIFT); this step covers the editor-placed doodads.
Doodads without HeightAbsolute are placed by the engine and are left alone.

Operator, 2026-11-16: large trees float. sink_trees lowers every absolute
ZerusTree* doodad (editor and border trees) by TREE_SINK by its final scale.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import config

MARKER = ".doodads_lifted"
SINK_MARKER = ".trees_sunk"
_BLOCK = re.compile(r'<ObjectDoodad\b[^>]*>.*?</ObjectDoodad>', re.S)


def lift_text(text: str, lift: float) -> tuple[str, int]:
    flora = set(config.FAMILIES) | set(config.HAZARD_VARIATIONS)
    count = 0

    def repl(m: re.Match[str]) -> str:
        nonlocal count
        block = m.group(0)
        kind = re.search(r'\bType="([^"]+)"', block)
        if kind is None or kind.group(1) in flora or 'Index="HeightAbsolute" Value="1"' not in block:
            return block
        pos = re.search(r'\bPosition="([^",]+),([^",]+),([^"]+)"', block)
        if pos is None:
            raise ValueError(f"absolute doodad without a 3D Position: {block[:120]}")
        count += 1
        z = float(pos.group(3)) + lift
        return block.replace(pos.group(0), f'Position="{pos.group(1)},{pos.group(2)},{z:.4f}"', 1)

    return _BLOCK.sub(repl, text), count


def tree_sink(scale: float) -> float:
    """How far a tree of this scale is lowered (operator 2026-11-16)."""
    for above, sink in config.TREE_SINK:
        if scale > above:
            return sink
    return 0.0


def sink_text(text: str) -> tuple[str, int]:
    """Lower every absolute ZerusTree* doodad by tree_sink(scale)."""
    count = 0

    def repl(m: re.Match[str]) -> str:
        nonlocal count
        block = m.group(0)
        kind = re.search(r'\bType="([^"]+)"', block)
        if kind is None or not kind.group(1).startswith("ZerusTree") or 'Index="HeightAbsolute" Value="1"' not in block:
            return block
        scale = re.search(r'\bScale="([^",]+)', block)
        if scale is None:
            raise ValueError(f"tree without a Scale: {block[:120]}")
        sink = tree_sink(float(scale.group(1)))
        if sink == 0.0:
            return block
        pos = re.search(r'\bPosition="([^",]+),([^",]+),([^"]+)"', block)
        if pos is None:
            raise ValueError(f"absolute tree without a 3D Position: {block[:120]}")
        count += 1
        z = float(pos.group(3)) - sink
        return block.replace(pos.group(0), f'Position="{pos.group(1)},{pos.group(2)},{z:.4f}"', 1)

    return _BLOCK.sub(repl, text), count


def sink_trees(map_dir: Path) -> int:
    """Run after every step that places or moves trees."""
    map_dir = Path(map_dir)
    marker = map_dir / SINK_MARKER
    if marker.exists():
        return 0
    objects = map_dir / "Objects"
    text, count = sink_text(objects.read_text(encoding="utf-8"))
    objects.write_text(text, encoding="utf-8")
    marker.write_text(f"sunk={count} steps={config.TREE_SINK}\n", encoding="utf-8")
    return count


def lift_doodads(map_dir: Path) -> int:
    map_dir = Path(map_dir)
    marker = map_dir / MARKER
    if marker.exists():
        return 0
    objects = map_dir / "Objects"
    text, count = lift_text(objects.read_text(encoding="utf-8"), config.DOODAD_LIFT)
    objects.write_text(text, encoding="utf-8")
    marker.write_text(f"lifted={count} by={config.DOODAD_LIFT}\n", encoding="utf-8")
    return count
