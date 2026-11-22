"""Jump leg clips for the split-body heroes (REQ-JUMP R-JUMP-10 to 12, 16, 18).

The jump poses are built from the hero's own lower clips: the stand and the
eight walk directions. No donor model is used. Three operations shape a pose:

- crouch: the pelvis (`Root`) moves down and back, as the hips do when they
  flex; a foot on the ground stays where it is, a foot in the air moves with
  the pelvis. Down sets the knee bend, back sets how far the shin leans;
- tuck: the feet rise toward the pelvis;
- point: the foot turns at the ankle, toes down.

Crouch and tuck are solved per leg with two-bone inverse kinematics (thigh,
calf). On the ground the foot keeps its world rotation: the ankle bends as
the shin leans (dorsiflexion). A stand jump keeps the stand stance and a walk
jump keeps the stride of the walk.

How far the joints bend comes from motion capture (`REFERENCE`): CMU Graphics
Lab Motion Capture Database, mocap.cs.cmu.edu, subject 16 trials 01, 02
(jump), 03, 04 (high jump), 05 (forward jump); subject 75 trials 01-03 (run
jump), 12 (hops). Angles are changes from the standing pose, mean of the legs:

    trial            crouch knee ankle   flight knee hip ankle   landing knee ankle
    16_01 16_02 16_05   +64 +71 +53 / -17   +9 +12 +19 / +35       +40 +38 +44 / -15
    16_03 high jump     +71 / -17           +19 (max +23), hip +17, ankle +34   +52 / -16
    16_04 high jump     +70 / -21           +13, hip +8, ankle +29              +47 / -22
    75_12 hops          up to +85           +25 to +35, hip +6                  up to +64
    75_03 run jump      +30 (run-up)        +39, hip +4, ankle +39              +49

Operator 2026-11-17 (the jump was stiff): the targets are the strongest
trials: high jump crouch and landing, tucked air knee. The feet stay under
the hips in flight; the thigh goes forward by about half the knee bend.
The ankle is flat through the crouch, swings toes down at liftoff, and is
flat again about 70 ms around touchdown (toes first). At liftoff the knees
are about 70% extended.

Three phases per base:

- Start: crouch on the ground, extend through liftoff, point the feet;
- Air: knees slightly bent, feet pointed, held;
- End: feet flat, impact crouch, recover.

Stand base: the stand clip runs under all three phases.

Walk base (R-JUMP-18). The walk is a jog with two flight frames per cycle,
half a cycle apart (`FLIGHT_PHASE`; the back walks are the walk reversed,
`FLIGHT_PHASE_BACK`); in each, one foot is ahead. A walk jump exists once
per stride (the flight frame it uses):

- Start plays the walk from mid-stance to the flight frame (`PUSH_CYCLE`)
  during the crouch: the stance leg pushes off;
- Air holds the flight frame: the legs are split along the walk direction;
- End plays the walk on from the flight frame (`LAND_CYCLE`): the lead foot
  lands first and the walk continues.

The script picks the stride whose Start begins nearest the walk phase it
tracks, as the left or right foot variants of a locomotion system do.
Forward kinematics of the feet proves the poses at build time
(scripts/jumpanim/validate.py).
"""

from __future__ import annotations

import math
from typing import NamedTuple

from animation_tokens import validate_animation_name
from character_anim_m3 import append_stc, clone
from jumpanim.kin import (
    FEET,
    LEGS,
    PELVIS,
    SAMPLE_MS,
    TRACK_LOC,
    TRACK_ROT,
    add,
    base_ms,
    base_tracks,
    bone_world,
    clip_pose,
    conj,
    cross,
    dot,
    feet_distance,
    foot_positions,
    gait_flights,
    group_clip,
    leg_length,
    length,
    lerp_key,
    mul,
    quat_tuple,
    rotate,
    sample_key,
    sample_times,
    shortest_arc,
    smoothstep,
    sub,
    unit,
)
from jumpanim.ik import (
    AIR_ANKLE_DEG,
    AIR_KNEE_DEG,
    CROUCH_ANKLE_DEG,
    CROUCH_KNEE_DEG,
    GATHER_FEET,
    GATHER_KNEES,
    GATHER_REFERENCE,
    LAND_ANKLE_DEG,
    LAND_KNEE_DEG,
    MIN_REACH,
    PLANT_HIGH,
    PLANT_LOW,
    REFERENCE,
    Rig,
    SOLVE_STEPS,
    SWIVEL_MAX,
    angle_between,
    ankle_angle,
    ankle_change,
    axis_turn,
    bisect,
    body_forward,
    bone_named,
    crouch_for,
    crouch_shift,
    gather_foot,
    gather_knee,
    hip_change,
    joint_width,
    knee_change,
    knee_flexion,
    knee_position,
    local_rotation,
    make_rig,
    measure_rig,
    move_pelvis,
    point_foot,
    set_world_rotation,
    shape_pose,
    side_axis,
    solve_leg,
    tuck_for,
    turn_bone,
)

# Gait (mirrored in core/jump.galaxy, checked by jumpanim/validate.py).
STRIDES = 2
FLIGHT_PHASE = 0.05       # walk phase of stride 0's flight frame; stride k: + k / STRIDES
FLIGHT_PHASE_BACK = 0.95  # the back walks are the walk reversed
# Start and End play the walk at walk rate 1 (operator 2026-11-16: the feet
# slid): the script plays them at the walk clip rate, as the walk itself.
# PUSH_CYCLE = CROUCH_MS / cycle; LAND_CYCLE - AIR_CYCLE = End length / cycle.
PUSH_CYCLE = 0.225   # walk cycle part Start plays before the flight frame
LAND_CYCLE = 0.405   # walk cycle part End ends at, after the flight frame
# Walk cycle part the legs move on in the air, liftoff to touchdown: about
# 4% of the walk rate (operator 2026-11-16: not a freeze frame). The legs
# swing fast at the flight frame: 0.08 closed the stride below the build
# limit (jumpanim.validate.MIN_STRIDE_SPLIT).
AIR_CYCLE = 0.03

# Timing (ms), from core/jump.galaxy: c_JUMP_CROUCH, _RISE_TIME, _LAND_TIME.
CROUCH_MS = 150
# Flight, from core/jump.galaxy: c_JUMP_TIME_UP, c_JUMP_FALL_GAIN. The fall
# takes the rise time / sqrt(gain).
TIME_UP_MS = 300
FALL_GAIN = 1.6
APEX_MS = CROUCH_MS + TIME_UP_MS
TOUCHDOWN_MS = APEX_MS + TIME_UP_MS / math.sqrt(FALL_GAIN)


class JumpBase(NamedTuple):
    token: str   # name token(s) in the baked clip
    group: str   # the model group the base is sampled from
    walk: bool   # walk bases exist once per stride
    flight: float = 0.0  # walk phase of stride 0's flight frame


class JumpClip(NamedTuple):
    name: str  # phase prefix; the baked clip is "<name> <base> [<stride>] Leg"
    length_ms: int
    looping: bool


START = JumpClip("Jump Start", 267, False)
# Air covers the whole flight after Start (TOUCHDOWN_MS - 267 = 420 ms; up to
# 60 ms more when a walk jump plays Start faster) plus one game loop, so it
# never wraps in a jump: its pose can change over time.
AIR = JumpClip("Jump", 533, True)
END = JumpClip("Jump End", 250, False)
JUMP_PHASES = (START, AIR, END)
# Heroes with jump clips (keys of heroanim.rig.HEROES).
JUMP_HEROES = frozenset({"tosh"})

# Walk directions, as character_anim_assets.AIM_DIRECTIONS.
WALK_DIRECTIONS = ("Forward", "Forward Left", "Left", "Back Left", "Back", "Back Right", "Right", "Forward Right")
STAND_BASE = JumpBase("Stand", "Attack Stand", False)
JUMP_BASES = (STAND_BASE,) + tuple(
    JumpBase("Walk " + name, "Attack Walk " + name, True, FLIGHT_PHASE_BACK if name.startswith("Back") else FLIGHT_PHASE)
    for name in WALK_DIRECTIONS
)


def baked_name(phase: JumpClip, base: JumpBase, stride: int | None = None) -> str:
    suffix = "" if stride is None else f" {stride + 1:02d}"
    return f"{phase.name} {base.token}{suffix} Leg"


def clip_plan() -> list[tuple[JumpClip, JumpBase, int | None]]:
    plan = []
    for phase in JUMP_PHASES:
        for base in JUMP_BASES:
            strides = range(STRIDES) if base.walk else (None,)
            plan.extend((phase, base, stride) for stride in strides)
    return plan


JUMP_GROUPS = tuple(baked_name(phase, base, stride) for phase, base, stride in clip_plan())


CROUCH_PEAK_MS = 60    # deepest takeoff crouch
CROUCH_EXTEND_MS = 165  # legs straight, just after liftoff
LAND_PEAK_MS = 60      # deepest landing crouch
LAND_RECOVER_MS = 220  # standing again
FEET_DOWN_MS = 66      # touchdown to feet flat and down (toes first); liftoff to toes pointed


def punch(peak: float, done: float, ms: float) -> float:
    """0 -> 1 -> 0: fast down, slowing into the peak (the legs brake);
    slow out of the peak, fastest at the end (the legs push)."""
    if ms <= 0.0 or ms >= done:
        return 0.0
    if ms <= peak:
        return 1.0 - (1.0 - ms / peak) ** 2
    return 1.0 - ((ms - peak) / (done - peak)) ** 2


def crouch_weight(phase: JumpClip, ms: float) -> float:
    """Crouch depth (0..1) at ms into the phase clip.

    Operator 2026-11-16: explosive, not eased. Start: down by CROUCH_PEAK_MS,
    then the legs extend faster and faster through liftoff; at liftoff
    (CROUCH_MS) about 30% is left, as in the reference. End: the impact
    takes the legs down by LAND_PEAK_MS; standing again by LAND_RECOVER_MS."""
    if phase is START:
        return punch(CROUCH_PEAK_MS, CROUCH_EXTEND_MS, ms)
    if phase is END:
        return punch(LAND_PEAK_MS, LAND_RECOVER_MS, ms)
    return 0.0


def walk_rate(phase: JumpClip, cycle_ms: float) -> float:
    """Walk rate under the walk part of Start or End at clip time scale 1.

    1.0: the feet move as in the walk clip, so they keep the ground speed
    when the script plays the clip at the walk clip rate."""
    if phase is START:
        return PUSH_CYCLE * cycle_ms / CROUCH_MS
    if phase is END:
        return (LAND_CYCLE - AIR_CYCLE) * cycle_ms / END.length_ms
    raise ValueError("the air clip has no walk rate")


def tuck_weight(phase: JumpClip, ms: float) -> float:
    """Foot rise (0..1) at ms into the phase clip: only while airborne."""
    if phase is START:
        return smoothstep(CROUCH_MS, START.length_ms, ms)
    if phase is END:
        return 1.0 - smoothstep(0.0, FEET_DOWN_MS, ms)
    return 1.0


def point_weight(phase: JumpClip, ms: float) -> float:
    """Ankle swing toes down (0..1) at ms into the phase clip.

    Flat on the ground; down over FEET_DOWN_MS from liftoff; flat again FEET_DOWN_MS into
    the landing, while the feet are still raised by the tuck (toes first)."""
    if phase is START:
        return smoothstep(CROUCH_MS, CROUCH_MS + FEET_DOWN_MS, ms)
    if phase is END:
        return 1.0 - smoothstep(0.0, FEET_DOWN_MS, ms)
    return 1.0


def gather_weight(phase: JumpClip, ms: float) -> float:
    """Legs together (0..1) at ms into the phase clip of a stand jump.

    It follows the flight: 0 at liftoff, 1 at the apogee, 0 at touchdown.
    The feet leave and reach the ground in the stand stance."""
    if phase is END:
        return 0.0
    at = ms + (START.length_ms if phase is AIR else 0)
    return smoothstep(CROUCH_MS, APEX_MS, at) * (1.0 - smoothstep(APEX_MS, TOUCHDOWN_MS, at))


def flight_phase(base: JumpBase, stride: int) -> float:
    return (base.flight + stride / STRIDES) % 1.0


def air_drift(ms: float) -> float:
    """Walk cycle part the legs have moved on in the air, ms after the press:
    0 at liftoff, AIR_CYCLE at touchdown, at a steady slow rate."""
    return AIR_CYCLE * min(1.0, max(0.0, (ms - CROUCH_MS) / (TOUCHDOWN_MS - CROUCH_MS)))


def walk_phase(phase: JumpClip, base: JumpBase, stride: int, ms: float) -> float:
    """Walk cycle phase (0..1) under a walk jump clip at ms."""
    flight = flight_phase(base, stride)
    if phase is START and ms <= CROUCH_MS:
        return (flight - PUSH_CYCLE * (1.0 - ms / CROUCH_MS)) % 1.0
    if phase is END:
        # From where the air left the legs, on to the end of the landing.
        return (flight + AIR_CYCLE + (LAND_CYCLE - AIR_CYCLE) * min(ms, END.length_ms) / END.length_ms) % 1.0
    return (flight + air_drift(ms + (START.length_ms if phase is AIR else 0))) % 1.0


def base_time(phase: JumpClip, base: JumpBase, stride: int | None, ms: float, cycle: int) -> float:
    """Time (ms) in the base clip under a jump clip at ms."""
    if base.walk:
        return walk_phase(phase, base, stride, ms) * cycle
    # The stand runs on: Air continues where Start left it.
    return ms + (START.length_ms if phase is AIR else 0)


# --- Bake ---


def crouch_depth(phase: JumpClip, rig: Rig) -> tuple:
    return rig.land if phase is END else rig.crouch


def clip_forward(model, group: str) -> tuple[float, float, float]:
    """The way the knees bend over a whole clip, along the ground.

    The walk directions turn the legs at the waist: the crouch moves the
    pelvis back along the legs, not along the model."""
    _, start, end, _ = group_clip(model, group)
    total = (0.0, 0.0, 0.0)
    for ms in range(0, max(1, end - start), SAMPLE_MS):
        total = add(total, body_forward(model, clip_pose(model, group, ms)))
    return unit((total[0], total[1], 0.0))


def make_baked_clip(model, groups, phase: JumpClip, base: JumpBase, stride: int | None, rig: Rig) -> int:
    """One phase on one base (and stride). Returns the track count."""
    name = baked_name(phase, base, stride)
    validate_animation_name(name)
    group_source = groups[base.group]
    source = model.sequenceTransformationCollections[group_source.stcIndices[0]]
    sequences = {sequence.name: sequence for sequence in model.sequences}
    base_sequence = sequences[base.group]
    start, end = base_sequence.animStartInMS, base_sequence.animEndInMS
    looping = not (base_sequence.flags & 1)
    times = sample_times(phase.length_ms)
    bases = base_tracks(source)
    owned = {bone_named(model, PELVIS).location.header.animId}
    owned.update(bone_named(model, bone).rotation.header.animId for chain in LEGS for bone in chain)
    missing = owned - set(bases)
    if missing:
        raise ValueError(f"{base.group} has no track for {len(missing)} of the jump bones")

    forward = clip_forward(model, base.group)
    keys: dict[int, list] = {anim_id: [] for anim_id in bases}
    for ms in times:
        at = base_ms(start, end, base_time(phase, base, stride, ms, end - start), looping)
        pose = {
            anim_id: sample_key(list(block.frames), list(block.keys), at, kind == TRACK_ROT)
            for anim_id, (kind, block) in bases.items()
        }
        shift = crouch_shift(forward, crouch_depth(phase, rig), crouch_weight(phase, ms))
        # Only the stand jump gathers: a walk jump keeps its stride.
        gather = 0.0 if base.walk else gather_weight(phase, ms)
        shape_pose(model, pose, rig, shift, tuck_weight(phase, ms) * rig.tuck, point_weight(phase, ms), gather)
        for anim_id in bases:
            keys[anim_id].append(pose[anim_id])

    stc = clone(source)
    # All key blocks are rebuilt below. Events (footsteps) are dropped: the
    # thump is the landing sound.
    stc.sdev = []
    stc.sd2v = []
    stc.sd3v = []
    stc.sd4q = []
    stc.sdcc = []
    stc.sdr3 = []
    stc.sds6 = []
    stc.sdu6 = []
    stc.sdu3 = []
    stc.sdfg = []
    stc.sdmb = []
    stc.name = name
    stc.animIds = []
    stc.animRefs = []
    for anim_id, (kind, block) in bases.items():
        target = clone(block)
        target.frames = list(times)
        target.keys = keys[anim_id]
        target.fend = phase.length_ms
        blocks = stc.sd3v if kind == TRACK_LOC else stc.sd4q
        blocks.append(target)
        stc.animIds.append(anim_id)
        stc.animRefs.append((kind << 16) | (len(blocks) - 1))
    stc_index = append_stc(model, stc, 0)

    group = clone(group_source)
    group.name = name
    group.stcIndices = [stc_index]
    model.sequenceTransformationGroups.append(group)
    groups[name] = group

    sequence = clone(base_sequence)
    sequence.name = name
    sequence.animStartInMS = 0
    sequence.animEndInMS = phase.length_ms
    sequence.movementSpeed = 0.0
    sequence.frequency = 100
    sequence.flags = 0 if phase.looping else 1
    model.sequences.append(sequence)
    return len(stc.animIds)


def make_jump_groups(model, groups) -> str:
    """Adds the jump clips for every base and stride. Returns a build log line."""
    rig = make_rig(model, clip_pose(model, STAND_BASE.group, 0))
    counts = sorted({make_baked_clip(model, groups, phase, base, stride, rig) for phase, base, stride in clip_plan()})
    flights = " ".join(f"{value:.2f}" for value in gait_flights(model, JUMP_BASES[1].group))
    depths = "crouch down %.3f back %.3f, land down %.3f back %.3f, tuck %.3f" % (*rig.crouch, *rig.land, rig.tuck)
    return f"jump: {len(JUMP_GROUPS)} clips, tracks {counts}, leg {rig.leg:.3f}, hips {rig.hips:.3f}, {depths}, flights {flights}"

# Re-exported for the validator and the tests.
__all__ = [
    "AIR", "AIR_ANKLE_DEG", "AIR_CYCLE", "AIR_KNEE_DEG", "APEX_MS", "CROUCH_ANKLE_DEG",
    "CROUCH_EXTEND_MS", "CROUCH_KNEE_DEG", "CROUCH_MS", "CROUCH_PEAK_MS", "END", "FALL_GAIN", "FEET_DOWN_MS",
    "FEET", "FLIGHT_PHASE", "FLIGHT_PHASE_BACK", "GATHER_FEET", "GATHER_KNEES", "GATHER_REFERENCE",
    "JUMP_BASES", "JUMP_GROUPS", "JUMP_HEROES", "JUMP_PHASES", "JumpBase", "JumpClip",
    "LAND_ANKLE_DEG", "LAND_CYCLE", "LAND_KNEE_DEG", "LAND_PEAK_MS", "LAND_RECOVER_MS", "LEGS",
    "MIN_REACH", "PELVIS", "PLANT_HIGH", "PLANT_LOW", "PUSH_CYCLE", "REFERENCE", "Rig", "SAMPLE_MS",
    "SOLVE_STEPS", "STAND_BASE", "START", "STRIDES", "SWIVEL_MAX", "TIME_UP_MS", "TOUCHDOWN_MS",
    "TRACK_LOC", "TRACK_ROT", "WALK_DIRECTIONS", "add", "air_drift", "angle_between", "ankle_angle",
    "ankle_change", "axis_turn", "baked_name", "base_ms", "base_time", "base_tracks", "bisect",
    "body_forward", "bone_named", "bone_world", "clip_forward", "clip_plan", "clip_pose", "conj",
    "cross", "crouch_depth", "crouch_for", "crouch_shift", "crouch_weight", "dot", "feet_distance",
    "flight_phase", "foot_positions", "gait_flights", "gather_foot", "gather_knee", "gather_weight",
    "group_clip", "hip_change", "joint_width", "knee_change", "knee_flexion", "knee_position", "leg_length",
    "length", "lerp_key", "local_rotation", "make_baked_clip", "make_jump_groups", "make_rig",
    "measure_rig", "move_pelvis", "mul", "point_foot", "point_weight", "punch", "quat_tuple",
    "rotate", "sample_key", "sample_times", "set_world_rotation", "shape_pose", "shortest_arc",
    "side_axis", "smoothstep", "solve_leg", "sub", "tuck_for", "tuck_weight", "turn_bone", "unit",
    "walk_phase", "walk_rate",
]
