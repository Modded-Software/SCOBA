"""Double the placed water doodads of the 256 map, with variation.

The 2x map expansion spreads every placed object apart, so waterfall runs
that were dense in the 128 source look sparse (REQ-WATER-DOODADS). This step
runs on the built map after positions are scaled and adds one copy per
placed water doodad:

- R-WD-01: count x DENSITY_FACTOR per type.
- R-WD-02: a copy fills the gap to the nearest unpaired water doodad within
  NEIGHBOR_RADIUS (midpoint, height averaged). Without one, the copy sits
  beside the source, across its facing (along the cliff lip).
- R-WD-03: copies vary: scale x [1-SCALE_JITTER, 1+SCALE_JITTER], rotation
  +- ROTATION_JITTER (waterfalls keep their flow direction), and a different
  model variation where the model has more than one.
- Copies keep the source's flags (HeightOffset, HeightAbsolute,
  ForcePlacement), so they sit like the source.

Deterministic: fixed seed, objects visited in Id order.
"""

from __future__ import annotations

import math
import random
import re
from pathlib import Path
from typing import NamedTuple

# Model VariationCount from liberty.sc2mod ModelData (no entry = 1).
WATER_TYPES = {"Waterfall": 1, "RockWaterfall": 7, "ZerusWaterfall": 1}
DENSITY_FACTOR = 2
NEIGHBOR_RADIUS = 6.0  # 256-map units
SIDE_OFFSET = 1.5  # x placed scale, 256-map units, when no neighbour
POSITION_JITTER = 0.25
SCALE_JITTER = 0.15
ROTATION_JITTER = 0.2  # radians
SEED = 20261119
MARKER = ".water_doodads"

BLOCK_RE = re.compile(r'([ \t]*)<ObjectDoodad\b[^>]*?(?:/>|>.*?</ObjectDoodad>)[ \t]*\r?\n', re.S)


class Doodad(NamedTuple):
    oid: int
    kind: str
    pos: tuple[float, float, float]
    rot: float
    scale: float
    variation: int
    block: str


def _attr(block: str, name: str) -> str | None:
    m = re.search(rf'\b{name}="([^"]*)"', block.split(">", 1)[0])
    return m.group(1) if m else None


def _set(block: str, name: str, value: str) -> str:
    head, sep, rest = block.partition(">")
    if re.search(rf'\b{name}="', head):
        head = re.sub(rf'\b{name}="[^"]*"', f'{name}="{value}"', head, count=1)
    else:
        head = re.sub(r'(<ObjectDoodad\b)', rf'\1 {name}="{value}"', head, count=1)
    return head + sep + rest


def parse(text: str) -> list[Doodad]:
    out = []
    for m in BLOCK_RE.finditer(text):
        block = m.group(0)
        kind = _attr(block, "Type")
        if kind not in WATER_TYPES:
            continue
        x, y, z = (float(v) for v in _attr(block, "Position").split(","))
        scale = float((_attr(block, "Scale") or "1").split(",")[0])
        out.append(Doodad(int(_attr(block, "Id")), kind, (x, y, z), float(_attr(block, "Rotation") or 0.0), scale, int(_attr(block, "Variation") or 0), block))
    return sorted(out, key=lambda d: d.oid)


def plan_copy(src: Doodad, others: list[Doodad], used: set[frozenset[int]], rng: random.Random) -> tuple[float, float, float]:
    best = None
    for o in others:
        if o.oid == src.oid or frozenset((src.oid, o.oid)) in used:
            continue
        d = math.dist(src.pos[:2], o.pos[:2])
        if d <= NEIGHBOR_RADIUS and (best is None or d < best[0]):
            best = (d, o)
    if best:
        o = best[1]
        used.add(frozenset((src.oid, o.oid)))
        x, y, z = ((a + b) / 2 for a, b in zip(src.pos, o.pos))
    else:
        side = src.rot + math.pi / 2 * (1 if rng.random() < 0.5 else -1)
        step = SIDE_OFFSET * src.scale
        x, y, z = src.pos[0] + math.cos(side) * step, src.pos[1] + math.sin(side) * step, src.pos[2]
    return (x + rng.uniform(-POSITION_JITTER, POSITION_JITTER), y + rng.uniform(-POSITION_JITTER, POSITION_JITTER), z)


def make_copy(src: Doodad, oid: int, pos: tuple[float, float, float], rng: random.Random) -> str:
    block = _set(src.block, "Id", str(oid))
    block = _set(block, "Position", ",".join(f"{v:.4f}" for v in pos))
    block = _set(block, "Rotation", f"{(src.rot + rng.uniform(-ROTATION_JITTER, ROTATION_JITTER)) % math.tau:.4f}")
    s = src.scale * rng.uniform(1 - SCALE_JITTER, 1 + SCALE_JITTER)
    block = _set(block, "Scale", f"{s:.4f},{s:.4f},{s:.4f}")
    count = WATER_TYPES[src.kind]
    if count > 1:
        block = _set(block, "Variation", str(rng.choice([v for v in range(count) if v != src.variation])))
    return block


def densify_text(text: str, seed: int = SEED) -> tuple[str, dict[str, int]]:
    rng = random.Random(seed)
    doodads = parse(text)
    next_id = max(int(v) for v in re.findall(r'\bId="(\d+)"', text)) + 1
    used: set[frozenset[int]] = set()
    copies, added = [], {k: 0 for k in WATER_TYPES}
    for src in doodads:
        for _ in range(DENSITY_FACTOR - 1):
            copies.append(make_copy(src, next_id, plan_copy(src, doodads, used, rng), rng))
            next_id += 1
            added[src.kind] += 1
    close = text.rfind("</PlacedObjects>")
    if close < 0:
        raise ValueError("no </PlacedObjects> in Objects")
    newline = "\r\n" if "\r\n" in text else "\n"
    body = "".join(c.replace("\r\n", "\n").replace("\n", newline) for c in copies)
    return text[:close] + body + text[close:], added


def update_preload(path: Path, text: str) -> None:
    """Preload every placed water type, with every variation now placed."""
    if not path.is_file():
        return
    pre = path.read_bytes().decode("utf-8")
    newline = "\r\n" if "\r\n" in pre else "\n"
    placed = parse(text)
    for kind, count in WATER_TYPES.items():
        used = sorted({int(_attr(d.block, "Variation") or 0) for d in placed if d.kind == kind})
        if not used:
            continue
        line = f'<Actor id="{kind}" Variations="{",".join(map(str, used))}"/>' if count > 1 else f'<Actor id="{kind}"/>'
        entry = re.compile(rf'<Actor id="{kind}"( Variations="[^"]*")?/>')
        if entry.search(pre):
            pre = entry.sub(line, pre, count=1)
            continue
        actors = list(re.finditer(r'<Actor id="[^"]*"[^>]*/>', pre))
        at = actors[-1].end() if actors else pre.rfind("</Preload>")
        if at < 0:
            raise ValueError(f"no place for {kind} in {path}")
        pre = pre[:at] + (newline + line if actors else line + newline) + pre[at:]
    path.write_bytes(pre.encode("utf-8"))


def apply_water_doodads(map_dir: Path) -> dict[str, int]:
    map_dir = Path(map_dir)
    marker = map_dir / MARKER
    if marker.exists():
        return {}
    objects = map_dir / "Objects"
    before = {k: len([d for d in parse(objects.read_text(encoding="utf-8")) if d.kind == k]) for k in WATER_TYPES}
    text, added = densify_text(objects.read_text(encoding="utf-8"))
    after = {k: len([d for d in parse(text) if d.kind == k]) for k in WATER_TYPES}
    for k in WATER_TYPES:
        if after[k] != before[k] * DENSITY_FACTOR:
            raise ValueError(f"water doodads: {k} {before[k]} -> {after[k]}, want x{DENSITY_FACTOR}")
    objects.write_text(text, encoding="utf-8")
    update_preload(map_dir / "Preload.xml", text)
    marker.write_text(" ".join(f"{k}={before[k]}->{after[k]}" for k in WATER_TYPES) + "\n", encoding="utf-8")
    return added
