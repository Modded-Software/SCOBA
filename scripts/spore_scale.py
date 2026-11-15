from __future__ import annotations

from pathlib import Path
import os
import re
import subprocess
import sys

from project_root import project_root

ROOT = project_root()
DEFAULT_MAP = ROOT / "out" / "SCOBA256.SC2Map"
SPORE_SCALE = 3.0
SPORE_UNITS = {"SporeCannon", "SporeCrawler"}
PROJECTILE_FACTOR = 1.5
MOVER_ID = "MissileDefault"
# The map's psi destroyer is the placed PsiDecimator unit.
PSI_DESTROYER_SCALE = 2.0
PSI_DESTROYER_UNITS = {"PsiDecimator"}
PSI_DESTROYER_MARKER = ".psi_destroyer_scaled"
# Its animations run this many times slower: the unit model and its death model.
PSI_DESTROYER_ANIM_SLOWDOWN = 2.0
PSI_DESTROYER_MODELS = ("PsiDecimator", "PsiDecimatorDeath")
PSI_DESTROYER_ANIM_MARKER = ".psi_destroyer_slowed"
# AnimSpeed of a CModel that does not set one.
DEFAULT_ANIM_SPEED = 1.0


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


def scale_unit_instances(text: str, unit_types: set[str], factor: float) -> tuple[str, int]:
    """Multiply the placed Scale of every ObjectUnit whose type is in unit_types."""
    pattern = re.compile(r'<ObjectUnit\b[^>]*\bUnitType="([^"]+)"[^>]*>', re.S)
    changed = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal changed
        block = match.group(0)
        if match.group(1) not in unit_types:
            return block
        scale_match = re.search(r'\bScale="([^"]+)"', block)
        if not scale_match:
            raise ValueError(f"{match.group(1)} instance has no Scale attribute")
        values = [float(v) * factor for v in scale_match.group(1).split(",")]
        new_scale = ",".join(f"{v:.4f}" for v in values)
        changed += 1
        return re.sub(r'\bScale="[^"]+"', f'Scale="{new_scale}"', block, count=1)

    return pattern.sub(repl, text), changed


def scale_psi_destroyer(map_dir: Path) -> int:
    """Scale the placed psi destroyer. Visual only: footprint and radius are unchanged."""
    map_dir = Path(map_dir)
    marker = map_dir / PSI_DESTROYER_MARKER
    if marker.exists():
        return 0
    path = map_dir / "Objects"
    text, changed = scale_unit_instances(
        path.read_text(encoding="utf-8"), PSI_DESTROYER_UNITS, PSI_DESTROYER_SCALE
    )
    if changed == 0:
        raise ValueError(f"no placed unit of type {sorted(PSI_DESTROYER_UNITS)} in {path}")
    path.write_text(text, encoding="utf-8")
    marker.write_text(f"units={changed} scale={PSI_DESTROYER_SCALE}\n", encoding="utf-8")
    return changed


def slow_model_animations(text: str, model_ids: tuple[str, ...], slowdown: float) -> tuple[str, int]:
    """Divide the AnimSpeed of each CModel by slowdown. Missing entries are added."""
    if slowdown <= 0:
        raise ValueError(f"slowdown must be positive, got {slowdown}")
    changed = 0
    for model_id in model_ids:
        # A self-closing entry has no body to edit and would be mistaken for the next block.
        if re.search(r'<CModel\b[^>]*\bid="' + re.escape(model_id) + r'"[^>]*/>', text):
            raise ValueError(f"CModel {model_id} is self-closing; give it a body first")
        block_pattern = re.compile(
            r'(<CModel\b[^>]*\bid="' + re.escape(model_id) + r'"[^>]*>)(.*?)([ \t]*</CModel>)',
            re.S,
        )
        match = block_pattern.search(text)
        if match is None:
            if "</Catalog>" not in text:
                raise ValueError("ModelData has no </Catalog> to add a CModel to")
            speed = DEFAULT_ANIM_SPEED / slowdown
            entry = (
                f'    <CModel id="{model_id}">\n'
                f'        <AnimSpeed value="{speed:.6f}"/>\n'
                f"    </CModel>\n"
            )
            text = text.replace("</Catalog>", entry + "</Catalog>", 1)
            changed += 1
            continue
        body = match.group(2)
        speed_match = re.search(r'<AnimSpeed value="([^"]+)"/>', body)
        if speed_match:
            speed = float(speed_match.group(1)) / slowdown
            body = body.replace(speed_match.group(0), f'<AnimSpeed value="{speed:.6f}"/>', 1)
        else:
            speed = DEFAULT_ANIM_SPEED / slowdown
            body = body + f'        <AnimSpeed value="{speed:.6f}"/>\n'
        text = text[: match.start()] + match.group(1) + body + match.group(3) + text[match.end() :]
        changed += 1
    return text, changed


def slow_psi_destroyer_animations(map_dir: Path) -> int:
    """Slow the psi destroyer's animations. Keyframes only: particle emitters keep their own rate."""
    map_dir = Path(map_dir)
    marker = map_dir / PSI_DESTROYER_ANIM_MARKER
    if marker.exists():
        return 0
    path = map_dir / "Base.SC2Data" / "GameData" / "ModelData.xml"
    text, changed = slow_model_animations(
        path.read_text(encoding="utf-8"), PSI_DESTROYER_MODELS, PSI_DESTROYER_ANIM_SLOWDOWN
    )
    path.write_text(text, encoding="utf-8")
    marker.write_text(f"models={changed} slowdown={PSI_DESTROYER_ANIM_SLOWDOWN}\n", encoding="utf-8")
    return changed


def revert() -> int:
    env = {**os.environ, "SC2_NO_SPORES": "1"}
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
