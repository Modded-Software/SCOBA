from __future__ import annotations

from pathlib import Path
import os
import random
import re
import struct
import subprocess
import sys

from project_root import project_root

ROOT = project_root()
DEFAULT_MAP = ROOT / "out" / "SCOBA256.SC2Map"
TREE_TYPE = "ZerusTree"
TREE_COUNT_FACTOR = 1.5
FLUFF_COUNT_FACTOR = 2
TREE_OLD_MIN = 2.0
TREE_OLD_MAX = 5.0
TREE_NEW_MIN = 2.0
TREE_NEW_MAX = 8.0
SEED = 20261107
MARKER = ".props_expanded"


def _vec(value: str) -> list[float]:
    return [float(part) for part in value.split(",")]


def _fmt(values: list[float]) -> str:
    return ",".join(f"{v:.4f}" for v in values)


def _remap_scale(value: float) -> float:
    span = TREE_OLD_MAX - TREE_OLD_MIN
    if span <= 0:
        return TREE_NEW_MAX
    t = (value - TREE_OLD_MIN) / span
    t = max(0.0, min(1.0, t))
    return TREE_NEW_MIN + t * (TREE_NEW_MAX - TREE_NEW_MIN)


def expand_objects(path: Path, rng: random.Random) -> int:
    text = path.read_text(encoding="utf-8")
    used = {int(value) for value in re.findall(r'\bId="(\d+)"', text)}
    next_id = max(used) + 1 if used else 1
    pattern = re.compile(
        r'<ObjectDoodad\b(?=[^>]*\bType="' + re.escape(TREE_TYPE) + r'")[^>]*>.*?</ObjectDoodad>',
        re.S,
    )
    matches = list(pattern.finditer(text))
    total = len(matches)
    target = round(total * TREE_COUNT_FACTOR)
    need = max(0, target - total)
    duplicates = {min(total - 1, (i * total) // need) for i in range(need)} if need else set()

    out: list[str] = []
    last = 0
    added = 0
    for index, match in enumerate(matches):
        block = match.group(0)
        pos_match = re.search(r'\bPosition="([^"]+)"', block)
        scale_match = re.search(r'\bScale="([^"]+)"', block)
        rot_match = re.search(r'\bRotation="([^"]+)"', block)
        if scale_match:
            scale = [_remap_scale(v) for v in _vec(scale_match.group(1))]
            block = re.sub(r'\bScale="[^"]+"', f'Scale="{_fmt(scale)}"', block, count=1)
        out.append(text[last : match.start()])
        out.append(block)
        if index in duplicates and pos_match:
            pos = _vec(pos_match.group(1))
            copy = re.sub(r'\bId="\d+"', f'Id="{next_id}"', block, count=1)
            next_id += 1
            new_pos = f"{pos[0] + rng.uniform(-4.0, 4.0):.4f},{pos[1] + rng.uniform(-4.0, 4.0):.4f},{pos[2]:.4f}"
            copy = re.sub(r'\bPosition="[^"]+"', f'Position="{new_pos}"', copy, count=1)
            if rot_match:
                copy = re.sub(
                    r'\bRotation="[^"]+"',
                    f'Rotation="{rng.uniform(0.0, 6.2832):.4f}"',
                    copy,
                    count=1,
                )
            out.append("\n" + copy)
            added += 1
        last = match.end()
    out.append(text[last:])
    path.write_text("".join(out), encoding="utf-8")
    return added


def expand_fluff(path: Path, rng: random.Random) -> int:
    data = path.read_bytes()
    count = struct.unpack_from("<I", data, 24)[0]
    assert len(data) == 28 + count * 9, (len(data), count)
    out = bytearray(data[:28])
    copies = int(count * (FLUFF_COUNT_FACTOR - 1))
    duplicate = set()
    if copies:
        duplicate = {min(count - 1, (i * count) // copies) for i in range(copies)}
    added = 0
    for index in range(count):
        off = 28 + index * 9
        record = data[off : off + 9]
        out += record
        if index in duplicate:
            x, y, flag = struct.unpack_from("<2fB", record, 0)
            out += struct.pack("<2fB", x + rng.uniform(-1.5, 1.5), y + rng.uniform(-1.5, 1.5), flag)
            added += 1
    struct.pack_into("<I", out, 24, count + added)
    path.write_bytes(bytes(out))
    return added


def expand_props(map_dir: Path, force: bool = False) -> bool:
    map_dir = Path(map_dir)
    marker = map_dir / MARKER
    if marker.exists() and not force:
        return False
    rng = random.Random(SEED)
    trees = expand_objects(map_dir / "Objects", rng)
    fluff = expand_fluff(map_dir / "t3FluffDoodad", rng)
    marker.write_text(f"trees_added={trees} fluff_added={fluff}\n", encoding="utf-8")
    return True


def revert(map_dir: Path) -> int:
    env = {**os.environ, "SC2_NO_PROPS": "1"}
    return subprocess.call([sys.executable, str(ROOT / "scripts" / "expand_map.py")], env=env)


def main(argv: list[str]) -> int:
    map_dir = DEFAULT_MAP
    args = argv[1:]
    if "--revert" in args:
        return revert(map_dir)
    force = "--force" in args
    positional = [a for a in args if not a.startswith("--")]
    if positional:
        map_dir = Path(positional[0])
    applied = expand_props(map_dir, force=force)
    print("props expanded" if applied else "props already expanded (skipped)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
