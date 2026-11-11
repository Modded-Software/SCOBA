from __future__ import annotations

import argparse
import math
import re
from pathlib import Path

MARKER = ".skybox_rotate"
MARKER_VERSION = "2\n"
ACTOR_DATA = Path("Base.SC2Data") / "GameData" / "ActorData.xml"
TERRAIN_DATA = Path("Base.SC2Data") / "GameData" / "TerrainData.xml"
FIXED_ACTOR = "SCOBAFixedSkybox"
ROTATION_OP = "SCOBASkyboxFlip"
ANGLE_DEG = 190.0
AXIS = "roll"


def _rotation_vectors() -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    angle = math.radians(ANGLE_DEG)
    sin = math.sin(angle)
    cos = math.cos(angle)
    if AXIS == "yaw":
        return (sin, -cos, 0.0), (0.0, 0.0, 1.0)
    if AXIS == "pitch":
        return (0.0, -1.0, 0.0), (sin, 0.0, cos)
    return (0.0, -1.0, 0.0), (sin, 0.0, -cos)


def _actor_block() -> str:
    forward, up = _rotation_vectors()
    return (
        f'    <CActorSiteOpRotationExplicit id="{ROTATION_OP}">\n'
        '        <EditorCategories value=""/>\n'
        f'        <Forward value="{forward[0]:.6f},{forward[1]:.6f},{forward[2]:.6f}"/>\n'
        f'        <Up value="{up[0]:.6f},{up[1]:.6f},{up[2]:.6f}"/>\n'
        '        <IsLocal value="1"/>\n'
        '    </CActorSiteOpRotationExplicit>\n'
        f'    <CActorModel id="{FIXED_ACTOR}">\n'
        f'        <HostSiteOps Ops="SOpGameCameraFollow {ROTATION_OP}"/>\n'
        '        <Model value="AiurSkybox"/>\n'
        '        <ModelFlags index="AutomateGlobalLoops" value="1"/>\n'
        '    </CActorModel>\n'
    )


def _apply_actors(path: Path) -> None:
    text = path.read_text()
    if f'id="{FIXED_ACTOR}"' in text:
        return
    text = text.replace("</Catalog>", _actor_block() + "</Catalog>")
    path.write_text(text)


def _apply_terrain(path: Path) -> None:
    text = path.read_text()
    field = f'        <FixedSkyboxActor value="{FIXED_ACTOR}"/>\n'
    if f'<FixedSkyboxActor value="{FIXED_ACTOR}"/>' in text:
        return
    text = re.sub(r"[ \t]*<FixedSkyboxActor value=\"[^\"]*\"/>\n", "", text)
    text = text.replace("    </CTerrain>", field + "    </CTerrain>")
    path.write_text(text)


def revert(root: Path) -> None:
    actor_path = root / ACTOR_DATA
    text = actor_path.read_text()
    for actor_id in (ROTATION_OP, FIXED_ACTOR):
        pattern = re.compile(
            rf'    <CActor(?:SiteOpRotationExplicit|Model) id="{re.escape(actor_id)}">.*?    </CActor(?:SiteOpRotationExplicit|Model)>\n',
            re.S,
        )
        text = pattern.sub("", text)
    actor_path.write_text(text)

    terrain_path = root / TERRAIN_DATA
    text = terrain_path.read_text()
    text = re.sub(r"[ \t]*<FixedSkyboxActor value=\"[^\"]*\"/>\n", "", text)
    terrain_path.write_text(text)
    (root / MARKER).unlink(missing_ok=True)


def generate(root: Path, force: bool) -> None:
    marker = root / MARKER
    if marker.exists() and not force and marker.read_text() == MARKER_VERSION:
        return
    _apply_actors(root / ACTOR_DATA)
    _apply_terrain(root / TERRAIN_DATA)
    marker.write_text(MARKER_VERSION)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--map", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--revert", action="store_true")
    args = parser.parse_args()
    root = args.map.resolve()
    if args.revert:
        revert(root)
        return 0
    generate(root, args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())