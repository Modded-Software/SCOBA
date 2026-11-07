from __future__ import annotations

from pathlib import Path
import os
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MAP = ROOT / "out" / "SCOBA256.SC2Map"
SPORE_SCALE = 3.0
SPORE_UNITS = {"SporeCannon", "SporeCrawler"}
PROJECTILE_FACTOR = 2.0
MOVER_ID = "MissileDefault"


def scale_projectile(map_dir: Path) -> int:
    path = Path(map_dir) / "Base.SC2Data" / "GameData" / "MoverData.xml"
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(
        r'(<CMoverMissile\b[^>]*\bid="' + re.escape(MOVER_ID) + r'"[^>]*>)(.*?)(</CMoverMissile>)',
        re.S,
    )

    def repl(match: re.Match[str]) -> str:
        body = match.group(2)
        for tag in ("MaxSpeed", "Acceleration"):
            body = re.sub(
                rf'<{tag} value="([0-9.]+)"/>',
                lambda m: f'<{tag} value="{float(m.group(1)) * PROJECTILE_FACTOR:.4f}"/>',
                body,
            )
        return match.group(1) + body + match.group(3)

    path.write_text(pattern.sub(repl, text), encoding="utf-8")
    return 1



def scale_spores(map_dir: Path) -> int:
    map_dir = Path(map_dir)
    marker = map_dir / ".spore_scaled"
    if marker.exists():
        return 0
    path = map_dir / "Objects"
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(r'<ObjectUnit\b[^>]*\bUnitType="([^"]+)"[^>]*>', re.S)
    changed = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal changed
        block = match.group(0)
        if match.group(1) not in SPORE_UNITS:
            return block
        scale_match = re.search(r'\bScale="([^"]+)"', block)
        if not scale_match:
            return block
        values = [float(v) * SPORE_SCALE for v in scale_match.group(1).split(",")]
        new_scale = ",".join(f"{v:.4f}" for v in values)
        changed += 1
        return re.sub(r'\bScale="[^"]+"', f'Scale="{new_scale}"', block, count=1)

    text = pattern.sub(repl, text)
    path.write_text(text, encoding="utf-8")
    scale_projectile(map_dir)
    marker.write_text(f"units={changed} scale={SPORE_SCALE} projectile={PROJECTILE_FACTOR}\n", encoding="utf-8")
    return changed


def revert() -> int:
    env = {**os.environ, "SC2_NO_PROPS": "1"}
    return subprocess.call([sys.executable, str(ROOT / "scripts" / "expand_map.py")], env=env)


def main(argv: list[str]) -> int:
    if "--revert" in argv[1:]:
        return revert()
    map_dir = DEFAULT_MAP
    positional = [a for a in argv[1:] if not a.startswith("--")]
    if positional:
        map_dir = Path(positional[0])
    changed = scale_spores(map_dir)
    print(f"scaled {changed} spore units {SPORE_SCALE}x")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
