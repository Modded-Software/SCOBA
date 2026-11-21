"""R-INTRO-17: no map tree overlaps the two trees placed for intro shot S2.

The placed trees are model actors made at map init
(systems/visual_tuning.galaxy) at s2_tree() and s2_tree2(). The map trees
are ObjectDoodad ZerusTree* in Objects. Overlap: trunk distance below the
sum of both canopies, canopy = CANOPY_PER_SCALE * scale (the estimate of
flora/treevary.py). An overlapping map tree is removed from Objects.

The step runs before the footprints and flora (expand_map.py): a removed
tree gets no blocker, and flora plans with the same trees its validator
re-plans from. Flora's seeded scatter re-rolls when the tree set changes
(about 2,400 doodads, operator 2026-11-21: accepted). problems() is the
validator on the built map.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import NamedTuple

from flora.treevary import CANOPY_PER_SCALE

from . import intro_shots

TREE_PREFIX = "ZerusTree"
_TAG = re.compile(r"<ObjectDoodad\b[^>]*>")
_CLOSE = "</ObjectDoodad>"


class Placed(NamedTuple):
    name: str
    x: float
    y: float
    canopy: float


class Hit(NamedTuple):
    start: int  # element span in the Objects text
    end: int
    ident: str
    x: float
    y: float
    scale: float
    placed: str
    distance: float

    def line(self) -> str:
        return f"tree {self.ident} at ({self.x:.2f},{self.y:.2f}) scale {self.scale:.2f}: {self.distance:.2f} from the intro {self.placed}"


def placed() -> tuple[Placed, Placed]:
    x1, y1 = intro_shots.s2_tree()
    x2, y2 = intro_shots.s2_tree2()
    actor = intro_shots.TREE_ACTOR_SCALE
    return (
        Placed("tree 1", x1, y1, CANOPY_PER_SCALE * intro_shots.TREE_DOODAD_SCALE * actor),
        Placed("tree 2", x2, y2, CANOPY_PER_SCALE * intro_shots.TREE2_DOODAD_SCALE * actor),
    )


def _attr(tag: str, name: str) -> str | None:
    found = re.search(r"\b" + name + r'="([^"]*)"', tag)
    return found.group(1) if found else None


def _span(text: str, tag: re.Match[str]) -> tuple[int, int]:
    """The whole element with its own line: indent before, line end after."""
    end = tag.end()
    if not tag.group(0).endswith("/>"):
        close = text.find(_CLOSE, end)
        if close < 0:
            raise ValueError(f"unclosed ObjectDoodad at offset {tag.start()}")
        end = close + len(_CLOSE)
    start = tag.start()
    while start > 0 and text[start - 1] in " \t":
        start -= 1
    while end < len(text) and text[end] in " \t\r":
        end += 1
    if end < len(text) and text[end] == "\n":
        end += 1
    return start, end


def overlapping(text: str) -> list[Hit]:
    """Map trees whose canopy overlaps a placed tree's canopy, in file order."""
    spots = placed()
    hits: list[Hit] = []
    for tag in _TAG.finditer(text):
        body = tag.group(0)
        if not (_attr(body, "Type") or "").startswith(TREE_PREFIX):
            continue
        x, y = (float(v) for v in (_attr(body, "Position") or "0,0").split(",")[:2])
        scale = float((_attr(body, "Scale") or "1").split(",")[0])
        for spot in spots:
            distance = math.hypot(x - spot.x, y - spot.y)
            if distance < spot.canopy + CANOPY_PER_SCALE * scale:
                start, end = _span(text, tag)
                hits.append(Hit(start, end, _attr(body, "Id") or "?", x, y, scale, spot.name, distance))
                break
    return hits


def clear(text: str) -> tuple[str, list[Hit]]:
    hits = overlapping(text)
    pieces, last = [], 0
    for hit in hits:
        pieces.append(text[last : hit.start])
        last = hit.end
    pieces.append(text[last:])
    return "".join(pieces), hits


def apply_intro_tree_clearing(map_dir: Path) -> int:
    """Remove the overlapping map trees from Objects. Returns the count."""
    objects = Path(map_dir) / "Objects"
    text, hits = clear(objects.read_text(encoding="utf-8"))
    for hit in hits:
        print(f"intro trees: removed {hit.line()}")
    print(f"intro trees: removed={len(hits)}")
    if hits:
        objects.write_text(text, encoding="utf-8")
    return len(hits)


def problems(map_dir: Path) -> list[str]:
    text = (Path(map_dir) / "Objects").read_text(encoding="utf-8")
    return [f"intro trees: {hit.line()} overlaps it" for hit in overlapping(text)]
