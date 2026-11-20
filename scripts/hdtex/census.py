"""Count the textures of the map's models: format, size, slots, users, verdict.

The census changes nothing. It says what the model source handles and what
it leaves alone, before a texture is upscaled.
"""

from __future__ import annotations

from pathlib import Path

from . import dds
from .casc import Casc
from .models import judged
from .sources import map_archives

REDUCTION_TABLE = "\\base.sc2data\\texturereduction\\texturereductionvalues.txt"


def reduction_names(casc: Casc, archives: tuple[str, ...], work: Path) -> set[str]:
    """File names the game's texture size table holds, lower case."""
    present = set(casc.find([REDUCTION_TABLE]))
    stored = [archive + REDUCTION_TABLE for archive in archives if archive + REDUCTION_TABLE in present]
    names: set[str] = set()
    for path in casc.extract(stored, work / "catalogs").values():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            name = line.partition(":")[0].strip().lower()
            if name:
                names.add(name)
    return names


def report(map_dir: Path, casc: Casc, work: Path) -> list[str]:
    found = judged(map_dir, casc, work)
    table = reduction_names(casc, map_archives(map_dir), work)
    lines = [f"textures: {len(found)}"]
    formats: dict[str, int] = {}
    verdicts: dict[str, int] = {}
    for use, verdict in found:
        info = None
        if use.casc_path is not None and use.asset.endswith(".dds"):
            path = work / "original" / Path(*use.casc_path.split("\\"))
            info = dds.describe(path.read_bytes())
        kind = info.format if info else "-"
        formats[kind] = formats.get(kind, 0) + 1
        outcome = verdict.role or f"skip: {verdict.reason}"
        if verdict.role and use.flipbook and use.grid:
            outcome += f" in {use.grid[0]}x{use.grid[1]} cells"
        verdicts[outcome] = verdicts.get(outcome, 0) + 1
        size = f"{info.width}x{info.height} mips {info.mips}" if info else "-"
        marks = "".join(
            mark
            for mark, on in (
                ("V", use.video),
                ("F", use.flipbook),
                ("W", use.wrap),
                ("T", use.asset.rsplit("\\", 1)[-1] in table),
            )
            if on
        )
        lines.append(
            f"  {kind:5s} {size:20s} {marks:4s} {use.asset}  [{', '.join(use.slots)}]"
            f"  <- {', '.join(use.entries)}  => {outcome}"
        )
    lines.append("marks: V video, F flip book, W the layers wrap on both axes, T in the size table")
    lines.append("formats: " + ", ".join(f"{kind} {count}" for kind, count in sorted(formats.items())))
    lines.append("verdicts: " + "; ".join(f"{kind} {count}" for kind, count in sorted(verdicts.items())))
    return lines
