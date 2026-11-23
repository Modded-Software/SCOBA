"""Operator probe: labeled rows of plants beside the hero spawn, one height/variation format per row.

Usage: PYTHONPATH=scripts uv run python -m flora.probe  -> out/SCOBA256_heightprobe.SC2Map
Launch: SC2_PLAYTEST_ACTIVE=1 SC2_MAP_SOURCE=<that path> bash scripts/launch-scoba.sh
Every row and prop has floating text; the camera pans to the rows at start.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path


from flora import terrain as terrain_mod
from project_root import project_root

KINDS = ("ZerusBrambles", "ZerusPlant", "ZerusPlantClusterMedium", "ZerusTallGrassCluster", "ZerusPlantlife")
ORIGIN = (197.0, 178.0)  # east of the hero spawn (188, 186)
ROW_GAP = 3.0
COL_GAP = 3.0
ABS = ("HeightOffset", "HeightAbsolute")


class Row:
    def __init__(self, name: str, label: str, flags: tuple[str, ...], dz: float | None, variation: int | None) -> None:
        self.name, self.label, self.flags, self.dz, self.variation = name, label, flags, dz, variation


# Operator 2026-11-15: row "ground +1.0, absolute" chosen; "z 0, no flags"
# buried props (the engine ground was flat then). 2026-11-23: small plants
# look underground at ground + 2.6 (GROUND_LIFT); the engine ground is baked
# from the terrain since 2026-11-19. These rows decide the new rule.
ROWS = (
    Row("A", "z 0, no flags (engine places it)", (), None, None),
    Row("B", "ground +2.6, absolute (now)", ABS, 2.6, None),
    Row("C", "ground +3.0, absolute", ABS, 3.0, None),
    Row("D", "ground +3.4, absolute", ABS, 3.4, None),
)


def entry(ident: int, kind: str, x: float, y: float, z: float, row: Row) -> str:
    var = "" if row.variation is None else f' Variation="{row.variation}"'
    body = "".join(f'        <Flag Index="{f}" Value="1"/>\n' for f in row.flags)
    head = f'    <ObjectDoodad Id="{ident}"{var} Position="{x:g},{y:g},{z:.4f}" Rotation="0" Scale="1,1,1" Type="{kind}"'
    return head + (">\n" + body + "    </ObjectDoodad>\n" if body else "/>\n")


def add_labels(map_dir: Path) -> None:
    lines = ["", "trigger gt_HeightProbe;", "bool gt_HeightProbe_Func (bool c, bool a) {", "    Wait(2.0, c_timeGame);"]
    cx = ORIGIN[0] + (len(KINDS) - 1) * COL_GAP / 2
    for r, row in enumerate(ROWS):
        y = ORIGIN[1] + r * ROW_GAP
        lines.append(f'    TextTagCreate(StringToText("ROW {row.name}: {row.label}"), 22, Point({ORIGIN[0] - 4:.2f}, {y:.2f}), 1.5, true, false, PlayerGroupAll());')
        for c in range(len(KINDS)):
            x = ORIGIN[0] + c * COL_GAP
            lines.append(f'    TextTagCreate(StringToText("{row.name}{c + 1}"), 16, Point({x:.2f}, {y:.2f}), 0.2, true, false, PlayerGroupAll());')
    mid = ORIGIN[1] + (len(ROWS) - 1) * ROW_GAP / 2
    lines += [
        f"    CameraPan(1, Point({cx:.2f}, {mid:.2f}), 0.5, -1, 10, false);",
        "    return true;",
        "}",
        "void gt_HeightProbe_Init () {",
        '    gt_HeightProbe = TriggerCreate("gt_HeightProbe_Func");',
        "    TriggerAddEventMapInit(gt_HeightProbe);",
        "}",
    ]
    script = map_dir / "MapScript.galaxy"
    text = script.read_text(encoding="utf-8")
    hook = "void InitTriggers () { main(); }"
    if hook not in text:
        raise ValueError(f"{script}: unexpected bootstrap")
    script.write_text(text.replace(hook, "\n".join(lines) + "\nvoid InitTriggers () { main(); gt_HeightProbe_Init(); }", 1), encoding="utf-8")


def main() -> int:
    root = project_root()
    src = root / "out" / "SCOBA256.SC2Map"
    dst = root / "out" / "SCOBA256_heightprobe.SC2Map"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    terrain = terrain_mod.load(dst)
    objects = dst / "Objects"
    text = objects.read_text(encoding="utf-8")
    ident = max(int(i) for i in re.findall(r'\bId="(\d+)"', text)) + 1
    out = []
    for r, row in enumerate(ROWS):
        y = ORIGIN[1] + r * ROW_GAP
        for c, kind in enumerate(KINDS):
            x = ORIGIN[0] + c * COL_GAP
            z = 0.0 if row.dz is None else terrain_mod.ground_z(terrain, x, y) + row.dz
            out.append(entry(ident, kind, x, y, z, row))
            ident += 1
        print(f"row {row.name}: y {y} {row.label}")
    objects.write_text(text.replace("</PlacedObjects>", "".join(out) + "</PlacedObjects>", 1), encoding="utf-8")
    add_labels(dst)
    print(f"wrote {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
