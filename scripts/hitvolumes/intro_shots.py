"""Intro shot table (SPEC-INTRO 3.4). Single source for the map and the host tests.

Writes src/SCOBA.SC2Map/scripts/app/data/intro_shots.galaxy. The build
validator checks that the file equals this output.

Run from scripts/: uv run python -m hitvolumes.intro_shots [--check]
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import NamedTuple

DATA_FILE = Path("scripts") / "app" / "data" / "intro_shots.galaxy"

WATER = 7.15
BOUNDS = 254.0
TICK = 0.0625

# Easing codes, shared with core/intro.galaxy.
EASES = {"E": 0, "L": 1, "S": 2, "A": 3, "O": 4, "Z": 5, "C": 6}
ARC_RAMP = 0.1  # A: smoothstep share at each end
CRASH_MOVE = 0.3  # C: eased part, then held
DOLLY_DIST = 42.0  # Z: distance at the start FOV (3x: the Psi Destroyer is huge)
DOLLY_FOV = 70.0
# z is the camera height offset: above the ground under the target. The
# engine has no usable ground getter (SPEC-INTRO F13: WorldHeight Ground
# reads 0, Air reads the cliff level), so shots meant at an absolute height
# (over the river) take their offset from the survey ground, and the host
# test pins the absolute height (ABSOLUTE).
# Variants on odd passes.
VAR_NONE, VAR_TARGET, VAR_YAW = 0, 1, 2


class Shot(NamedTuple):
    name: str
    length: float
    ease: str
    x0: float
    y0: float
    x1: float
    y1: float
    z0: float
    z1: float
    yaw0: float
    yaw1: float
    pitch0: float
    pitch1: float
    dist0: float
    dist1: float
    fov0: float
    fov1: float
    dof: bool
    variant: int
    # Per-shot DOF (operator 2026-11-17). near: near-blur strength (1 =
    # default, lower = weaker). far: 0 = no far blur, else far blur from
    # far x arm past the focus, full at 3 x that (lower = stronger).
    near: float = 1.0
    far: float = 0.0


def dolly_k() -> float:
    return DOLLY_DIST * math.tan(math.radians(DOLLY_FOV / 2))


def dolly_dist(fov: float) -> float:
    return dolly_k() / math.tan(math.radians(fov / 2))


BC = (103.8, 153.2)
X = (125.3, 118.8)
HYBRID = (194.4, 193.1)
HIVE = (21.0, 9.0)
NYDUS = (59.0, 59.0)
PSI = (240.0, 248.0)
# S8 start: the placed Predator nearest the Tosh spawn (Terran jungle).
PREDATOR = (177.84, 135.15)
# S8 roams (operator 2026-11-17: not attached to the Predator): from the
# Predator spot north through the jungle, looking along the path.
# Third jungle spot (operator 2026-11-17): the Predator pair at (117.7,
# 157.1) and (116.1, 166.5), passed on the east, north, 8 s at 2.5 cells/s.
JUNGLE_START = (120.0, 150.0)
JUNGLE_END = (120.0, 170.0)
BRAMBLE = (194.85, 162.8)  # S4 eye: survey spot 3 cells back along the yaw (operator 2026-11-17)
# S1: the eye sits at the Brakk mob boss (Objects) and looks at the
# battlecruiser (operator 2026-11-17). Target = eye + arm along the yaw.
BRAKK = (14.9558, 113.3615)
BRAKK_YAW = round(math.degrees(math.atan2(BC[1] - BRAKK[1], BC[0] - BRAKK[0])), 2)
S1_D0, S1_D1 = 8.0, 14.0
S1_Z = 14.0  # target height: the eye looks up from below it and must clear the ridge


def _ahead(d: float, pitch: float) -> tuple[float, float]:
    h = d * math.cos(math.radians(pitch))
    return (round(BRAKK[0] + h * math.cos(math.radians(BRAKK_YAW)), 2), round(BRAKK[1] + h * math.sin(math.radians(BRAKK_YAW)), 2))


# Pitched far up to show the battlecruiser overhead (operator 2026-11-17).
S1_P0, S1_P1 = -25.0, -45.0
S1_T0 = _ahead(S1_D0, S1_P0)
S1_T1 = _ahead(S1_D1, S1_P1)

# Survey ground (out/SCOBA256.SC2Map, scripts/flora/terrain.py) under the
# S1 and S2 targets, all under water.
S1_GROUND = (5.67, 5.59)
S2_GROUND = (4.16, 4.17)
# Absolute heights SPEC-INTRO 3.4 asks for: z start, z end.
ABSOLUTE = {"S2 Line": (WATER + 1.2, WATER + 1.2)}

SHOTS: tuple[Shot, ...] = (
    Shot("S1 Pride", 12, "E", *S1_T0, *S1_T1, S1_Z, S1_Z, BRAKK_YAW, BRAKK_YAW, S1_P0, S1_P1, S1_D0, S1_D1, 50, 40, False, VAR_NONE),
    Shot("S2 Line", 12, "L", 119.6, 113.1, 131.0, 124.5, round(WATER + 1.2 - S2_GROUND[0], 2), round(WATER + 1.2 - S2_GROUND[1], 2), 135, 135, 6, 6, 16, 16, 50, 50, True, VAR_TARGET),
    Shot("S3 Map", 10, "E", *X, *X, 0, 0, 45, 75, 80, 80, 150, 150, 22, 22, False, VAR_NONE, 1.3),
    Shot("S4 Brambles", 6, "E", *HYBRID, *HYBRID, 3, 3, 90.8, 90.8, -6.0, -6.0, 30.5, 30.5, 70, 45, False, VAR_NONE),
    Shot("S5 Shackled", 4, "E", *HYBRID, *HYBRID, 4, 4, 90.8, 90.8, 8, 8, 18, 12, 48, 44, False, VAR_NONE, 0.3, 0.15),
    Shot("S6 Overmind", 6, "A", *HIVE, *HIVE, 3, 3, 205, 245, 18, 18, 66, 66, 55, 55, False, VAR_YAW, 0.1, 0.3),
    Shot("S7 Worm", 3, "O", *NYDUS, *NYDUS, 6, 12, 225, 225, -20, -35, 9, 9, 80, 80, False, VAR_NONE, 2.0),
    Shot("S8 Jungle", 8, "L", *JUNGLE_START, *JUNGLE_END, 2, 2, 90, 90, 12, 12, 6, 6, 60, 60, False, VAR_NONE, 2.0, 1.5),
    Shot("S9 Decimator", 8, "Z", *PSI, *PSI, 4, 4, 45, 45, 10, 10, DOLLY_DIST, round(dolly_dist(24), 1), 70, 24, False, VAR_NONE, 2.0),
)
# The crash zoom. Its target is the hero drop point, set at SPACE.
# Ends on the hero drop chase camera: pitch = pod descent, arm 20.
ZOOM = Shot("Zoom", 0.35, "C", 0, 0, 0, 0, 0, 0, 225, 225, 55, 54.32, 60, 20, 60, 12, False, VAR_NONE)
LOOP_LENGTH = sum(s.length for s in SHOTS)


def smooth(u: float) -> float:
    return u * u * (3 - 2 * u)


def ease(code: str, u: float, length: float = 1.0) -> float:
    """Eased progress at u = time in shot / length, in [0, 1]."""
    u = min(max(u, 0.0), 1.0)
    if code in ("E", "Z"):
        return smooth(u)
    if code == "L":
        return u
    if code == "S":
        return 0.0
    if code == "A":
        r = ARC_RAMP
        v = 1 / (1 - r)
        if u < r:
            return v * u * u / (2 * r)
        if u > 1 - r:
            return 1 - v * (1 - u) * (1 - u) / (2 * r)
        return v * (u - r / 2)
    if code == "O":
        return 1 - (1 - u) ** 3
    if code == "C":
        w = min(u * length / CRASH_MOVE, 1.0)
        return 1 - (1 - w) ** 3
    raise ValueError(code)


class Sample(NamedTuple):
    x: float
    y: float
    z: float  # height offset above the ground under the target
    yaw: float
    pitch: float
    dist: float
    fov: float


def sample(shot: Shot, u: float, odd: bool = False) -> Sample:
    e = ease(shot.ease, u, shot.length)
    x0, y0, x1, y1 = shot.x0, shot.y0, shot.x1, shot.y1
    yaw0, yaw1 = shot.yaw0, shot.yaw1
    if odd and shot.variant == VAR_TARGET:
        x0, y0, x1, y1 = x1, y1, x0, y0
    if odd and shot.variant == VAR_YAW:
        yaw0, yaw1 = yaw1, yaw0

    def lerp(a: float, b: float) -> float:
        return a + (b - a) * e

    fov = lerp(shot.fov0, shot.fov1)
    dist = dolly_dist(fov) if shot.ease == "Z" else lerp(shot.dist0, shot.dist1)
    return Sample(lerp(x0, x1), lerp(y0, y1), lerp(shot.z0, shot.z1), lerp(yaw0, yaw1), lerp(shot.pitch0, shot.pitch1), dist, fov)


def eye(tx: float, ty: float, tz: float, yaw: float, pitch: float, dist: float) -> tuple[float, float, float]:
    c = dist * math.cos(math.radians(pitch))
    return (tx - c * math.cos(math.radians(yaw)), ty - c * math.sin(math.radians(yaw)), tz + dist * math.sin(math.radians(pitch)))


def _f(v: float) -> str:
    return f"{v:.4f}"


def galaxy() -> str:
    rows = list(SHOTS) + [ZOOM]
    n = len(rows)
    lines = [
        "// Generated by scripts/hitvolumes/intro_shots.py. Do not edit.",
        f"// Rows 0..{len(SHOTS) - 1}: shots S1..S{len(SHOTS)}. Row {len(SHOTS)}: the crash zoom.",
        f"const int c_INTRO_SHOTS = {len(SHOTS)};",
        f"const int c_INTRO_ROW_ZOOM = {len(SHOTS)};",
        f"const fixed c_INTRO_LOOP_LENGTH = {_f(LOOP_LENGTH)};",
        f"const fixed c_INTRO_DOLLY_K = {_f(dolly_k())};",
        f"const fixed c_INTRO_ARC_RAMP = {_f(ARC_RAMP)};",
        f"const fixed c_INTRO_CRASH_MOVE = {_f(CRASH_MOVE)};",
    ]
    for code, value in EASES.items():
        lines.append(f"const int c_INTRO_EASE_{code} = {value};")
    lines += [
        f"const int c_INTRO_VAR_NONE = {VAR_NONE};",
        f"const int c_INTRO_VAR_TARGET = {VAR_TARGET};",
        f"const int c_INTRO_VAR_YAW = {VAR_YAW};",
    ]
    fields = ("length", "x0", "y0", "x1", "y1", "z0", "z1", "yaw0", "yaw1", "pitch0", "pitch1", "dist0", "dist1", "fov0", "fov1", "near", "far")
    for name in fields:
        lines.append(f"fixed[{n}] gv_introRow_{name};")
    for name in ("ease", "variant"):
        lines.append(f"int[{n}] gv_introRow_{name};")
    lines.append(f"bool[{n}] gv_introRow_dof;")
    lines += ["", "void gf_IntroShotsLoad () {"]
    for i, s in enumerate(rows):
        lines.append(f"    // {s.name}")
        for name in fields:
            lines.append(f"    gv_introRow_{name}[{i}] = {_f(s._asdict()[name])};")
        lines.append(f"    gv_introRow_ease[{i}] = c_INTRO_EASE_{s.ease};")
        lines.append(f"    gv_introRow_variant[{i}] = {s.variant};")
        lines.append(f"    gv_introRow_dof[{i}] = {'true' if s.dof else 'false'};")
    lines += ["}", ""]
    return "\n".join(lines)


def src_path() -> Path:
    from project_root import project_root

    return project_root() / "src" / "SCOBA.SC2Map" / DATA_FILE


def check(map_dir: Path) -> list[str]:
    path = map_dir / DATA_FILE
    have = path.read_text(encoding="utf-8").replace("\r\n", "\n") if path.exists() else ""
    return [] if have == galaxy() else [f"{DATA_FILE} does not match scripts/hitvolumes/intro_shots.py"]


def map_root() -> Path:
    from project_root import project_root

    return project_root() / "src" / "SCOBA.SC2Map"


def main(argv: list[str]) -> int:
    path = src_path()
    if "--check" in argv:
        bad = check(map_root())
        for line in bad:
            print(line)
        return 1 if bad else 0
    path.write_text(galaxy(), encoding="utf-8")
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
