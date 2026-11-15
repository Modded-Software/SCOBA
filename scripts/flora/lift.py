"""Raise every non-flora doodad that has an absolute height by DOODAD_LIFT.

Operator, 2026-11-15: all props looked sunk into the ground. Flora gets its
lift in build.py (GROUND_LIFT); this step covers the editor-placed doodads.
Doodads without HeightAbsolute are placed by the engine and are left alone.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import config

MARKER = ".doodads_lifted"
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
