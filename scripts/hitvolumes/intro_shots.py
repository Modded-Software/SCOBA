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
EASES = {"E": 0, "L": 1, "S": 2, "A": 3, "O": 4, "Z": 5}
ARC_RAMP = 0.1  # A: smoothstep share at each end
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
    # Focal distance; 0 = the shot's arm (dist0). Near falloffs scale with it.
    focus: float = 0.0


def dolly_k() -> float:
    return DOLLY_DIST * math.tan(math.radians(DOLLY_FOV / 2))


def dolly_dist(fov: float) -> float:
    return dolly_k() / math.tan(math.radians(fov / 2))


BC = (103.8, 153.2)
X = (125.3, 118.8)
HYBRID = (194.4, 193.1)
# S4 eye exactly at (193.5, 164.5), height 10.2 (operator 2026-11-18),
# looking at the Hybrid (ground + 3). Yaw, pitch and arm from the built
# terrain: Hybrid ground 8.76, so target height 11.76.
S4_EYE = (193.5, 164.5)
S4_EYE_Z = 10.2
S4_TZ = 3.0
S4_GROUND = 8.76
_S4_FLAT = math.hypot(HYBRID[0] - S4_EYE[0], HYBRID[1] - S4_EYE[1])
S4_YAW = round(math.degrees(math.atan2(HYBRID[1] - S4_EYE[1], HYBRID[0] - S4_EYE[0])), 2)
S4_PITCH = round(math.degrees(math.atan2(S4_EYE_Z - (S4_GROUND + S4_TZ), _S4_FLAT)), 2)
S4_DIST = round(math.hypot(_S4_FLAT, S4_EYE_Z - (S4_GROUND + S4_TZ)), 2)
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
# S8 ends 1 s earlier at the same 2.5 cells/s (operator 2026-11-18: 8, 7.5, then 7 s): 2.5 cells short of 170.
JUNGLE_END = (120.0, 167.5)
BRAMBLE = (194.85, 162.8)  # S4 eye: survey spot 3 cells back along the yaw (operator 2026-11-17)
# S1: the eye sits at the Brakk mob boss (Objects) and looks at the
# battlecruiser (operator 2026-11-17). Target = eye + arm along the yaw.
BRAKK = (14.9558, 113.3615)
BRAKK_YAW = round(math.degrees(math.atan2(BC[1] - BRAKK[1], BC[0] - BRAKK[0])), 2)
S1_D0, S1_D1 = 8.0, 14.0
S1_Z = 14.0  # target height: the eye looks up from below it and must clear the ridge
# S1 focus far out (operator 2026-11-18, option 2): the Zerus trees ahead are
# 26..58 from the eye, the BC about 97. Focus 60, near 2.0: full near blur
# closer than 37.5, fading out by 56; the BC beyond stays sharp.
S1_FOCUS = 60.0
# S1 eye to the left of the Brakk facing. Left = Brakk yaw + 90. 0.5
# (operator 2026-11-18), 1.0 (operator 2026-11-20: 0.5 more, keep
# targeting the BC): the yaw turns from the new eye onto the BC.
S1_LEFT = 1.0
S1_EYE = (
    BRAKK[0] + S1_LEFT * math.cos(math.radians(BRAKK_YAW + 90)),
    BRAKK[1] + S1_LEFT * math.sin(math.radians(BRAKK_YAW + 90)),
)
S1_YAW = round(math.degrees(math.atan2(BC[1] - S1_EYE[1], BC[0] - S1_EYE[0])), 2)


def _ahead(d: float, pitch: float) -> tuple[float, float]:
    h = d * math.cos(math.radians(pitch))
    return (round(S1_EYE[0] + h * math.cos(math.radians(S1_YAW)), 2), round(S1_EYE[1] + h * math.sin(math.radians(S1_YAW)), 2))


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
    Shot("S1 Pride", 12, "E", *S1_T0, *S1_T1, S1_Z, S1_Z, S1_YAW, S1_YAW, S1_P0, S1_P1, S1_D0, S1_D1, 50, 40, False, VAR_NONE, 2.0, 0.0, S1_FOCUS),  # more near DOF (operator 2026-11-18)
    Shot("S2 Line", 12, "L", 119.6, 113.1, 131.0, 124.5, round(WATER + 1.2 - S2_GROUND[0], 2), round(WATER + 1.2 - S2_GROUND[1], 2), 135, 135, 6, 6, 16, 16, 50, 50, True, VAR_TARGET),
    # S3 and S6: 1.5x the arm, FOV narrowed to keep the framing (operator
    # 2026-11-18: farther, tighter lens). S3 was 150 / 22, S6 66 / 55.
    Shot("S3 Map", 10, "E", *X, *X, 0, 0, 45, 75, 80, 80, 225, 225, 14.8, 14.8, False, VAR_NONE, 1.3),
    Shot("S4 Brambles", 6, "E", *HYBRID, *HYBRID, S4_TZ, S4_TZ, S4_YAW, S4_YAW, S4_PITCH, S4_PITCH, S4_DIST, S4_DIST, 70, 45, False, VAR_NONE),
    Shot("S5 Shackled", 4, "E", *HYBRID, *HYBRID, 4, 4, 90.8, 90.8, 8, 8, 18, 12, 48, 44, False, VAR_NONE, 0.3, 0.15),
    # S6 orbit at half the rate (operator 2026-11-18): 20 degrees in 6 s, was 40.
    Shot("S6 Overmind", 6, "A", *HIVE, *HIVE, 3, 3, 215, 235, 18, 18, 99, 99, 38.3, 38.3, False, VAR_YAW, 1.5, 0.3),  # near DOF: 4.0 was too much (operator 2026-11-18)
    # S7 4 s longer (operator 2026-11-18: +2 s, then +2 s): the pitch up over 7 s, was 3.
    Shot("S7 Worm", 7, "O", *NYDUS, *NYDUS, 6, 12, 225, 225, -20, -35, 9, 9, 80, 80, False, VAR_NONE, 6.0),  # near DOF up (operator 2026-11-18: 2.0, 4.0, then 6.0)
    Shot("S8 Jungle", 7, "L", *JUNGLE_START, *JUNGLE_END, 2, 2, 90, 90, 12, 12, 6, 6, 60, 60, False, VAR_NONE, 2.0, 1.5),
    Shot("S9 Decimator", 8, "Z", *PSI, *PSI, 4, 4, 45, 45, 10, 10, DOLLY_DIST, round(dolly_dist(24), 1), 70, 24, False, VAR_NONE, 2.0),
)
# The crash zoom after SPACE is the hero drop's (core/hero_drop.galaxy,
# SPEC-HERO-DROP 3a), not a row here.
LOOP_LENGTH = sum(s.length for s in SHOTS)


def smooth(u: float) -> float:
    return u * u * (3 - 2 * u)


def ease(code: str, u: float) -> float:
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
    e = ease(shot.ease, u)
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


# S6 foreground pods (operator 2026-11-20): three empty Zerg drop pods in
# the near view of the first Overmind orbit. Ahead of the eye at the middle
# yaw of the orbit, along the view line, and to its left (+) or right (-).
# Closer (operator 2026-11-20; was 64, 70, 76): the eye is 33.6 above
# the ground, so ground nearer than about 54 is under the frame.
# Closer again and apart (operator 2026-11-20; was 54, 58, 62 and -3, 3,
# 0): the nearest lands at the lower edge of the frame.
S6_POD_AHEAD = (46.0, 52.0, 60.0)
S6_POD_SIDE = (-6.0, 6.0, 0.0)


def s6_row() -> int:
    return next(i for i, s in enumerate(SHOTS) if s.name.startswith("S6"))


def s7_row() -> int:
    return next(i for i, s in enumerate(SHOTS) if s.name.startswith("S7"))


def s7_eye() -> tuple[float, float]:
    s7 = SHOTS[s7_row()]
    ex, ey, _ = eye(s7.x0, s7.y0, s7.z0, s7.yaw0, s7.pitch0, s7.dist0)
    return (round(ex, 2), round(ey, 2))


def s6_pods() -> tuple[tuple[float, float], ...]:
    s6 = SHOTS[s6_row()]
    yaw = (s6.yaw0 + s6.yaw1) / 2.0
    ex, ey, _ = eye(s6.x0, s6.y0, s6.z0, yaw, s6.pitch0, s6.dist0)
    a, left = math.radians(yaw), math.radians(yaw + 90.0)
    return tuple(
        (round(ex + d * math.cos(a) + side * math.cos(left), 2), round(ey + d * math.sin(a) + side * math.sin(left), 2))
        for d, side in zip(S6_POD_AHEAD, S6_POD_SIDE)
    )


# A permanent Zerus tree just behind the S2 start eye (operator 2026-11-20):
# its leaves come into close view. The first-pass start (left to right,
# the southwest, Zerg side of the river); TREE_BACK cells behind the eye
# on the view line. Variation 4. Scale 75 % as an editor doodad: the map's
# ZerusTree actor scale (ActorData: random 4..6, mid 5, z x1.4) times 0.75.
TREE_BACK = 1.0  # operator 2026-11-21: 1 cell (was 2.0, 3.0; 1.0 before was too close at 300 %)
TREE_VARIATION = 4
TREE_DOODAD_SCALE = 0.75  # operator 2026-11-20: 75 % (was 100 %, 200 %, 275 %, 300 %)
TREE_ACTOR_SCALE = 5.0
TREE_ACTOR_Z = 1.4
# A second tree (operator 2026-11-20): TREE2_ALONG cells further down the
# camera's first-pass path, as far behind the eye as the first, 75 % of
# the first, turned.
TREE2_ALONG = 8.0  # operator 2026-11-21: 8 cells (2.0 was too close to the first)
TREE2_DOODAD_SCALE = 0.75 * 0.75  # 75 % of the first tree's 75 % (operator 2026-11-20: both, relative)
TREE2_FACING = 135.0  # the first tree keeps the actor's own facing, 0


def s2_tree() -> tuple[float, float]:
    s2 = next(s for s in SHOTS if s.name.startswith("S2"))
    ex, ey, _ = eye(s2.x0, s2.y0, s2.z0, s2.yaw0, s2.pitch0, s2.dist0)
    back = math.radians(s2.yaw0 + 180.0)
    return (round(ex + TREE_BACK * math.cos(back), 2), round(ey + TREE_BACK * math.sin(back), 2))


def s2_tree2() -> tuple[float, float]:
    s2 = next(s for s in SHOTS if s.name.startswith("S2"))
    tx, ty = s2_tree()
    n = math.hypot(s2.x1 - s2.x0, s2.y1 - s2.y0)
    return (round(tx + TREE2_ALONG * (s2.x1 - s2.x0) / n, 2), round(ty + TREE2_ALONG * (s2.y1 - s2.y0) / n, 2))


def galaxy() -> str:
    rows = list(SHOTS)
    n = len(rows)
    lines = [
        "// Generated by scripts/hitvolumes/intro_shots.py. Do not edit.",
        f"// Rows 0..{len(SHOTS) - 1}: shots S1..S{len(SHOTS)}.",
        f"const int c_INTRO_SHOTS = {len(SHOTS)};",
        f"const fixed c_INTRO_LOOP_LENGTH = {_f(LOOP_LENGTH)};",
        f"const fixed c_INTRO_DOLLY_K = {_f(dolly_k())};",
        f"const fixed c_INTRO_ARC_RAMP = {_f(ARC_RAMP)};",
    ]
    for code, value in EASES.items():
        lines.append(f"const int c_INTRO_EASE_{code} = {value};")
    lines += [
        f"const int c_INTRO_VAR_NONE = {VAR_NONE};",
        f"const int c_INTRO_VAR_TARGET = {VAR_TARGET};",
        f"const int c_INTRO_VAR_YAW = {VAR_YAW};",
    ]
    tx, ty = s2_tree()
    xy = TREE_DOODAD_SCALE * TREE_ACTOR_SCALE
    t2x, t2y = s2_tree2()
    xy2 = TREE2_DOODAD_SCALE * TREE_ACTOR_SCALE
    lines += [
        "// The S2 Zerus tree (s2_tree).",
        f"const fixed c_INTRO_TREE_X = {_f(tx)};",
        f"const fixed c_INTRO_TREE_Y = {_f(ty)};",
        f"const int c_INTRO_TREE_VARIATION = {TREE_VARIATION};",
        f"const fixed c_INTRO_TREE_SCALE_XY = {_f(xy)};",
        f"const fixed c_INTRO_TREE_SCALE_Z = {_f(xy * TREE_ACTOR_Z)};",
        "// The second S2 tree (s2_tree2).",
        f"const fixed c_INTRO_TREE2_X = {_f(t2x)};",
        f"const fixed c_INTRO_TREE2_Y = {_f(t2y)};",
        f"const fixed c_INTRO_TREE2_SCALE_XY = {_f(xy2)};",
        f"const fixed c_INTRO_TREE2_SCALE_Z = {_f(xy2 * TREE_ACTOR_Z)};",
        f"const fixed c_INTRO_TREE2_FACING = {_f(TREE2_FACING)};",
        "// The S6 foreground pods (s6_pods).",
        f"const int c_INTRO_S6_ROW = {s6_row()};",
        "// S7 looks up at the Overmind: the first Mutalisk wave (systems/air_creep).",
        f"const fixed c_INTRO_S7_START = {_f(sum(s.length for s in SHOTS[:s7_row()]))};",
        "// The S7 eye on the ground plane: one pod lands on it at the cut into S7 (systems/scenery).",
        f"const fixed c_INTRO_S7_EYE_X = {_f(s7_eye()[0])};",
        f"const fixed c_INTRO_S7_EYE_Y = {_f(s7_eye()[1])};",
        f"const int c_INTRO_S6_PODS = {len(s6_pods())};",
        f"fixed[{len(s6_pods())}] gv_introS6PodX;",
        f"fixed[{len(s6_pods())}] gv_introS6PodY;",
    ]
    fields = ("length", "x0", "y0", "x1", "y1", "z0", "z1", "yaw0", "yaw1", "pitch0", "pitch1", "dist0", "dist1", "fov0", "fov1", "near", "far")
    for name in fields + ("focus",):
        lines.append(f"fixed[{n}] gv_introRow_{name};")
    for name in ("ease", "variant"):
        lines.append(f"int[{n}] gv_introRow_{name};")
    lines.append(f"bool[{n}] gv_introRow_dof;")
    lines += ["", "void gf_IntroShotsLoad () {"]
    for i, s in enumerate(rows):
        lines.append(f"    // {s.name}")
        for name in fields:
            lines.append(f"    gv_introRow_{name}[{i}] = {_f(s._asdict()[name])};")
        lines.append(f"    gv_introRow_focus[{i}] = {_f(s.focus or s.dist0)};")
        lines.append(f"    gv_introRow_ease[{i}] = c_INTRO_EASE_{s.ease};")
        lines.append(f"    gv_introRow_variant[{i}] = {s.variant};")
        lines.append(f"    gv_introRow_dof[{i}] = {'true' if s.dof else 'false'};")
    for i, (px, py) in enumerate(s6_pods()):
        lines.append(f"    gv_introS6PodX[{i}] = {_f(px)};")
        lines.append(f"    gv_introS6PodY[{i}] = {_f(py)};")
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
