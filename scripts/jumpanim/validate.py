"""Jump clip checks for scripts/validate-map.py (REQ-JUMP R-JUMP-10, 11, 16, 18)."""

from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import m3
from animation_tokens import normalized_animation_name
from jumpanim.bake import (
    AIR,
    APEX_MS,
    CROUCH_MS,
    END,
    FEET_DOWN_MS,
    FEET,
    FLIGHT_PHASE,
    FLIGHT_PHASE_BACK,
    GATHER_REFERENCE,
    JUMP_BASES,
    JUMP_GROUPS,
    JUMP_PHASES,
    LAND_CYCLE,
    LEGS,
    PUSH_CYCLE,
    REFERENCE,
    STAND_BASE,
    START,
    STRIDES,
    TOUCHDOWN_MS,
    ankle_change,
    hip_change,
    baked_name,
    base_time,
    bone_world,
    clip_plan,
    clip_pose,
    feet_distance,
    flight_phase,
    foot_positions,
    gait_flights,
    group_clip,
    joint_width,
    knee_change,
    measure_rig,
    walk_rate,
)
from character_anim_assets import AIM_DIRECTIONS
from validate_assets import fail
from walkanim.slow import check_slow
from jumpanim.donor_check import check_donors

# Feet match between a jump clip and the clip it continues (model units).
SEAM_TOLERANCE = 0.01
# Feet horizontal position vs the base pose (stand feet are 0.37 apart).
STANCE_TOLERANCE = 0.02
# Flight frame phase vs the pelvis height maximum of the walk (cycle parts).
FLIGHT_TOLERANCE = 0.03
# Walk jump in the air: feet at least this far apart along the ground (the
# forward flight frame has 0.64; the stand 0.39), and across the forward
# walk no wider than this part of the stand width (operator report
# 2026-11-16: legs spread left to right).
MIN_STRIDE_SPLIT = 0.45
MAX_STRIDE_WIDTH = 0.75
# Walk jump in the air: a foot moves at least and at most this far between
# the start of the air clip and touchdown (operator 2026-11-16: the walk
# plays on very slowly, not a freeze frame). Model units; a stride is 0.6.
# Walk under Start and End at clip time scale 1, as a part of the walk rate.
WALK_RATE_TOLERANCE = 0.1
MIN_AIR_DRIFT = 0.01
MAX_AIR_DRIFT = 0.12
BONE_LENGTH_TOLERANCE = 1e-3
# Joint angles vs the motion capture reference (jumpanim.bake.REFERENCE):
# the range of the three trials, widened by this margin, degrees.
REFERENCE_MARGIN = 5.0
GAIT_CONST_RE = re.compile(r"const (?:fixed|int) (c_JUMP_GAIT_\w+) = ([0-9.]+);")
GAIT_CONSTS = {
    "c_JUMP_GAIT_STRIDES": STRIDES,
    "c_JUMP_GAIT_FLIGHT": FLIGHT_PHASE,
    "c_JUMP_GAIT_FLIGHT_BACK": FLIGHT_PHASE_BACK,
    "c_JUMP_GAIT_PUSH": PUSH_CYCLE,
    "c_JUMP_GAIT_LAND": LAND_CYCLE,
}

TOSH_MODEL = Path("Assets") / "Units" / "Terran" / "Tosh" / "ToshSCOBA.m3"
UPPER_ROOT = "BoneSpine01"
JUMP_PROFILES = ("c_ANIM_HERO_TOSH", "c_ANIM_HERO_KERRIGAN")
JUMP_CONFIG_RE = re.compile(r'gf_JumpConfigClip\((c_ANIM_HERO_\w+),\s*c_JUMP_\w+,\s*"([^"]+)"\)')
JUMP_DIR_RE = re.compile(r'gv_jumpDirName\[c_ANIM_DIR_\w+\] = "([^"]+)";')


def subtree(model, root: str) -> set[str]:
    names = [bone.name for bone in model.bones]
    inside = set()
    for index, bone in enumerate(model.bones):
        cursor = index
        while cursor >= 0:
            if names[cursor] == root:
                inside.add(bone.name)
                break
            cursor = model.bones[cursor].parent
    return inside


THUMP_RE = re.compile(r'const string c_JUMP_THUMP_(MODEL|SOUND) = "([^"]+)";')
THUMP_CATALOGS = {"MODEL": ("ModelData.xml", "CModel"), "SOUND": ("SoundData.xml", "CSound")}


def check_thump(map_dir: Path, galaxy: str) -> None:
    """R-JUMP-8: the touchdown thump ids exist in the built data."""
    found = dict(THUMP_RE.findall(galaxy))
    for kind, (catalog, tag) in THUMP_CATALOGS.items():
        ident = found.get(kind)
        if ident is None:
            fail(f"c_JUMP_THUMP_{kind} missing from the map script")
        text = (map_dir / "Base.SC2Data" / "GameData" / catalog).read_text(encoding="utf-8")
        if f'<{tag} id="{ident}"' not in text:
            fail(f"jump thump {tag} {ident!r} missing from {catalog}")


def check_camera(map_dir: Path) -> str:
    """R-JUMP-20: the engine adds no smoothing to the follow target or to
    the height offset, so the camera arm is rigid."""
    path = map_dir / "Base.SC2Data" / "GameData" / "CameraData.xml"
    camera = ET.parse(path).getroot().find("CCamera[@id='Dflt']")
    if camera is None:
        fail("CameraData.xml has no Dflt camera")
    fields = {
        "follow target": camera.find("TargetSmooth"),
        "height offset": camera.find("ParamSmooth[@index='HeightOffset']"),
    }
    for label, field in fields.items():
        if field is None:
            fail(f"camera {label} smoothing is not set: the stock value lags the hero")
        for key in ("SmoothTimeMin", "SmoothTimeMax"):
            if float(field.get(key, "-1")) != 0.0:
                fail(f"camera {label} {key} must be 0, found {field.get(key)}")
    return "camera smoothing: follow target 0, height offset 0"


def clip_times(model, name: str) -> range:
    _, start, end, _ = group_clip(model, name)
    return range(0, end - start + 1, 33)


def ground_gap(a: dict, b: dict) -> float:
    """Largest horizontal foot position difference between two foot sets."""
    return max(math.hypot(a[name][0] - b[name][0], a[name][1] - b[name][1]) for name in FEET)


def ground_split(feet: dict) -> tuple[float, float]:
    """(distance, width across model X) between the feet along the ground."""
    dx, dy = feet[FEET[0]][0] - feet[FEET[1]][0], feet[FEET[0]][1] - feet[FEET[1]][1]
    return math.hypot(dx, dy), abs(dx)


def circular_gap(a: float, b: float) -> float:
    gap = abs(a - b) % 1.0
    return min(gap, 1.0 - gap)


def bone_lengths(model, pose: dict) -> list[float]:
    out = []
    for thigh, calf, foot in LEGS:
        world = bone_world(model, pose, (thigh, calf, foot))
        out.append(math.dist(world[thigh][0], world[calf][0]))
        out.append(math.dist(world[calf][0], world[foot][0]))
    return out


def check_constants(model, galaxy: str) -> int:
    consts = {name: float(value) for name, value in GAIT_CONST_RE.findall(galaxy)}
    _, start, end, _ = group_clip(model, JUMP_BASES[1].group)
    cycle = end - start
    if abs(consts.get("c_JUMP_GAIT_CYCLE", -1.0) - cycle / 1000.0) > 0.0015:
        fail(f"c_JUMP_GAIT_CYCLE {consts.get('c_JUMP_GAIT_CYCLE')} differs from the walk cycle {cycle} ms")
    for name, value in GAIT_CONSTS.items():
        if name not in consts or abs(consts[name] - value) > 1e-6:
            fail(f"{name} {consts.get(name)} differs from the bake value {value}")
    return cycle


def check_flights(model) -> str:
    """The strides are the flight frames of every walk direction."""
    worst = 0.0
    for base in JUMP_BASES:
        if not base.walk:
            continue
        found = gait_flights(model, base.group)
        for stride in range(STRIDES):
            want = flight_phase(base, stride)
            gap = min(circular_gap(want, phase) for phase in found)
            worst = max(worst, gap)
            if gap > FLIGHT_TOLERANCE:
                fail(f"{TOSH_MODEL} {base.group}: stride {stride + 1} at phase {want:.2f}, flight frames at {found}")
    return f"flight frames off by max {worst:.3f}/{FLIGHT_TOLERANCE}"


def check_reference(model) -> list[str]:
    """Stand jump joint angles match the motion capture reference.

    Knee and ankle changes from the standing pose at the deepest takeoff
    crouch, in the air, and at the deepest landing crouch."""
    rig = measure_rig(model, clip_pose(model, STAND_BASE.group, 0))
    start, air, end = (baked_name(phase, STAND_BASE) for phase in JUMP_PHASES)

    def deepest(name: str, first_ms: int, last_ms: int) -> dict:
        poses = [clip_pose(model, name, ms) for ms in clip_times(model, name) if first_ms <= ms <= last_ms]
        return max(poses, key=lambda pose: knee_change(model, pose, rig))

    crouch = deepest(start, 0, CROUCH_MS)
    # The landing crouch with the feet down: before FEET_DOWN_MS the air tuck
    # still bends the knees and the toes still point.
    landing = deepest(end, FEET_DOWN_MS, END.length_ms)
    flight = clip_pose(model, air, 0)
    # The stand under the air clip at its start: the hip change is the jump's only.
    under = clip_pose(model, STAND_BASE.group, base_time(AIR, STAND_BASE, None, 0, 0))
    got = {
        "crouch knee": knee_change(model, crouch, rig),
        "crouch ankle": ankle_change(model, crouch, rig),
        "air knee": knee_change(model, flight, rig),
        "air ankle": ankle_change(model, flight, rig),
        "air hip": hip_change(model, flight, under, rig),
        "landing knee": knee_change(model, landing, rig),
        "landing ankle": ankle_change(model, landing, rig),
    }
    log = []
    for name, value in got.items():
        low, high = REFERENCE[name]
        log.append(f"{name} {value:+.1f} (reference {low:+.1f}..{high:+.1f})")
        if not low - REFERENCE_MARGIN <= value <= high + REFERENCE_MARGIN:
            fail(f"{TOSH_MODEL} stand jump {name} {value:+.1f} deg, reference {low:+.1f}..{high:+.1f} (margin {REFERENCE_MARGIN})")
    # Negative: on the ground the foot is flat; the toes never point down.
    for name, last_ms in ((start, CROUCH_MS - 33), (end, END.length_ms)):
        for ms in clip_times(model, name):
            if (name == start and ms > last_ms) or (name == end and ms < 99):
                continue
            pose = clip_pose(model, name, ms)
            for leg in LEGS:
                rotation = bone_world(model, pose, (leg[2],))[leg[2]][1]
                base = bone_world(model, clip_pose(model, STAND_BASE.group, base_time(START if name == start else END, STAND_BASE, None, ms, 0)), (leg[2],))[leg[2]][1]
                turned = 2.0 * math.degrees(math.acos(min(1.0, abs(sum(a * b for a, b in zip(rotation, base))))))
                if turned > 1.0:
                    fail(f"{TOSH_MODEL} {name} at {ms} ms: {leg[2]} turned {turned:.1f} deg on the ground (not flat)")
    return ["reference: " + ", ".join(log)]


def check_stand(model) -> list[str]:
    """Stand jump: stand stance on the ground, legs together at the apogee.

    R-JUMP-16: on the ground (takeoff crouch, landing) the feet are on the
    stand stance. R-JUMP-21: in the air the feet only move sideways, never
    outward; at the apogee feet and knees are as close as the reference."""
    rig = measure_rig(model, clip_pose(model, STAND_BASE.group, 0))
    stand_feet = joint_width(model, clip_pose(model, STAND_BASE.group, 0), rig.forward, 2)
    stand_knees = joint_width(model, clip_pose(model, STAND_BASE.group, 0), rig.forward, 1)
    worst = 0.0
    planted = 0.0
    along = 0.0
    for phase in JUMP_PHASES:
        name = baked_name(phase, STAND_BASE)
        for ms in clip_times(model, name):
            pose = clip_pose(model, name, ms)
            feet = foot_positions(model, pose)
            base_pose = clip_pose(model, STAND_BASE.group, base_time(phase, STAND_BASE, None, ms, 0))
            base = foot_positions(model, base_pose)
            grounded = phase is END or (phase is START and ms <= CROUCH_MS)
            if grounded:
                gap = ground_gap(feet, base)
                worst = max(worst, gap)
                if gap > STANCE_TOLERANCE:
                    fail(f"{TOSH_MODEL} {name} at {ms} ms: feet {gap:.3f} off the stand stance on the ground")
            else:
                # In the air: no move along forward, and never wider than the stand.
                for foot in FEET:
                    move = (feet[foot][0] - base[foot][0], feet[foot][1] - base[foot][1], 0.0)
                    off = abs(move[0] * rig.forward[0] + move[1] * rig.forward[1])
                    along = max(along, off)
                    if off > STANCE_TOLERANCE:
                        fail(f"{TOSH_MODEL} {name} at {ms} ms: {foot} {off:.3f} off the stand stance along forward")
                wide = joint_width(model, pose, rig.forward, 2) - joint_width(model, base_pose, rig.forward, 2)
                if wide > STANCE_TOLERANCE:
                    fail(f"{TOSH_MODEL} {name} at {ms} ms: feet {wide:.3f} wider than the stand in the air")
            if phase is START and ms <= CROUCH_MS - 33:
                # On the ground: the feet do not move at all.
                lift = max(abs(feet[n][2] - base[n][2]) for n in FEET)
                planted = max(planted, lift)
                if lift > STANCE_TOLERANCE:
                    fail(f"{TOSH_MODEL} {name} at {ms} ms: feet {lift:.3f} off the ground in the crouch")
    # The apogee, in the air clip.
    air_name = baked_name(AIR, STAND_BASE)
    apogee = clip_pose(model, air_name, APEX_MS - START.length_ms)
    got = {
        "feet": joint_width(model, apogee, rig.forward, 2) / rig.hips,
        "knees": joint_width(model, apogee, rig.forward, 1) / rig.hips,
    }
    for what, value in got.items():
        low, high = GATHER_REFERENCE[what]
        if not low <= value <= high:
            fail(f"{TOSH_MODEL} {air_name} at the apogee: {what} {value:.2f} hip widths apart, reference {low}..{high}")
    if got["knees"] * rig.hips >= stand_knees - STANCE_TOLERANCE:
        fail(f"{TOSH_MODEL} {air_name} at the apogee: knees {got['knees'] * rig.hips:.3f} apart, stand {stand_knees:.3f} (not closer)")
    # No step between the clips: Start -> Air, and Air at touchdown -> End.
    seams = {
        "Start last frame vs Air": feet_distance(model, clip_pose(model, baked_name(START, STAND_BASE), START.length_ms), clip_pose(model, air_name, 0)),
        "Air at touchdown vs End": feet_distance(
            model, clip_pose(model, air_name, TOUCHDOWN_MS - START.length_ms), clip_pose(model, baked_name(END, STAND_BASE), 0)
        ),
    }
    for what, seam in seams.items():
        if seam > SEAM_TOLERANCE:
            fail(f"{TOSH_MODEL} stand jump {what}: feet {seam:.3f} apart")
    if AIR.length_ms < TOUCHDOWN_MS - START.length_ms:
        fail(f"the air clip ({AIR.length_ms} ms) is shorter than the flight after Start: it would wrap")
    return [
        f"stand jump feet off the stance on the ground max {worst:.4f}/{STANCE_TOLERANCE}, in the crouch {planted:.4f}, along forward in the air {along:.4f}",
        "stand jump apogee: feet %.3f -> %.3f (%.2f hip widths), knees %.3f -> %.3f (%.2f hip widths), seams max %.4f/%s"
        % (stand_feet, got["feet"] * rig.hips, got["feet"], stand_knees, got["knees"] * rig.hips, got["knees"], max(seams.values()), SEAM_TOLERANCE),
    ]


def check_walk(model, cycle: int) -> list[str]:
    """Walk jump: the air pose is the stride of the walk; the seams match;
    on the ground the feet move at the walk's own rate (R-JUMP-22)."""
    rates = {phase.name: walk_rate(phase, cycle) for phase in (START, END)}
    for name, rate in rates.items():
        if abs(rate - 1.0) > WALK_RATE_TOLERANCE:
            fail(f"{name} plays the walk at {rate:.2f} of the walk rate: the feet slide on the ground (want 1 +- {WALK_RATE_TOLERANCE})")
    stand_width = ground_split(foot_positions(model, clip_pose(model, STAND_BASE.group, 0)))[1]
    worst_pose = 0.0
    worst_seam = 0.0
    split_min = 9.0
    width_max = 0.0
    drift_min, drift_max = 9.0, 0.0
    for base in JUMP_BASES:
        if not base.walk:
            continue
        for stride in range(STRIDES):
            air_name = baked_name(AIR, base, stride)
            air = clip_pose(model, air_name, 0)
            landing = TOUCHDOWN_MS - START.length_ms  # touchdown, in the air clip
            # Through the flight the legs are the walk, moving on slowly.
            for ms in [t for t in clip_times(model, air_name) if t < landing] + [landing]:
                pose = clip_pose(model, air_name, ms)
                walk = clip_pose(model, base.group, base_time(AIR, base, stride, ms, cycle))
                gap = ground_gap(foot_positions(model, pose), foot_positions(model, walk))
                worst_pose = max(worst_pose, gap)
                if gap > STANCE_TOLERANCE:
                    fail(f"{TOSH_MODEL} {air_name} at {ms:.0f} ms: feet {gap:.3f} off the walk stride along the ground")
                split, width = ground_split(foot_positions(model, pose))
                split_min = min(split_min, split)
                if split < MIN_STRIDE_SPLIT:
                    fail(f"{TOSH_MODEL} {air_name} at {ms:.0f} ms: feet {split:.3f} apart, want a stride of {MIN_STRIDE_SPLIT} (legs together)")
                if base.token in ("Walk Forward", "Walk Back"):
                    width_max = max(width_max, width)
                    if width > MAX_STRIDE_WIDTH * stand_width:
                        fail(f"{TOSH_MODEL} {air_name} at {ms:.0f} ms: feet {width:.3f} apart across the walk, stand {stand_width:.3f} (legs spread sideways)")
            # Not a freeze frame: the legs move in the air, but only a little.
            drift = feet_distance(model, air, clip_pose(model, air_name, landing))
            drift_min, drift_max = min(drift_min, drift), max(drift_max, drift)
            if not MIN_AIR_DRIFT <= drift <= MAX_AIR_DRIFT:
                fail(f"{TOSH_MODEL} {air_name}: feet move {drift:.3f} in the air, want {MIN_AIR_DRIFT}..{MAX_AIR_DRIFT}")
            start_name, end_name = baked_name(START, base, stride), baked_name(END, base, stride)
            seams = {
                f"{start_name} first frame vs the walk": feet_distance(
                    model, clip_pose(model, start_name, 0), clip_pose(model, base.group, base_time(START, base, stride, 0, cycle))
                ),
                f"{start_name} last frame vs the air pose": feet_distance(model, clip_pose(model, start_name, START.length_ms), air),
                f"{end_name} first frame vs the air pose at touchdown": feet_distance(
                    model, clip_pose(model, end_name, 0), clip_pose(model, air_name, landing)
                ),
                f"{end_name} last frame vs the walk": feet_distance(
                    model, clip_pose(model, end_name, END.length_ms), clip_pose(model, base.group, base_time(END, base, stride, END.length_ms, cycle))
                ),
            }
            for what, seam in seams.items():
                worst_seam = max(worst_seam, seam)
                if seam > SEAM_TOLERANCE:
                    fail(f"{TOSH_MODEL} {what}: feet {seam:.3f} apart")
    return [
        f"walk jump air feet off the stride max {worst_pose:.4f}/{STANCE_TOLERANCE}",
        f"walk jump stride split min {split_min:.3f}/{MIN_STRIDE_SPLIT}, forward width max {width_max:.3f}/{MAX_STRIDE_WIDTH * stand_width:.3f}",
        f"walk jump feet move in the air {drift_min:.3f}..{drift_max:.3f} (want {MIN_AIR_DRIFT}..{MAX_AIR_DRIFT})",
        f"walk jump seams max {worst_seam:.4f}/{SEAM_TOLERANCE}",
        "walk jump ground walk rate: " + ", ".join(f"{name} {rate:.3f}" for name, rate in rates.items()) + f" (want 1 +- {WALK_RATE_TOLERANCE})",
    ]


def check_bones(model) -> str:
    """The leg bones keep their length in every jump clip (the IK is sound)."""
    want = bone_lengths(model, clip_pose(model, STAND_BASE.group, 0))
    worst = 0.0
    for phase, base, stride in clip_plan():
        name = baked_name(phase, base, stride)
        for ms in clip_times(model, name):
            gap = max(abs(a - b) for a, b in zip(bone_lengths(model, clip_pose(model, name, ms)), want))
            worst = max(worst, gap)
            if gap > BONE_LENGTH_TOLERANCE:
                fail(f"{TOSH_MODEL} {name} at {ms} ms: a leg bone changes length by {gap:.4f}")
    return f"leg bone length change max {worst:.5f}/{BONE_LENGTH_TOLERANCE}"


def check_gait(model, galaxy: str) -> list[str]:
    """R-JUMP-16, 18: stance, stride, seams, and the script constants."""
    cycle = check_constants(model, galaxy)
    return [check_flights(model)] + check_stand(model) + check_reference(model) + check_walk(model, cycle) + [check_bones(model)]


def check_jump(map_dir: Path, galaxy: str) -> None:
    check_thump(map_dir, galaxy)
    print(f"jump: {check_camera(map_dir)}")
    configured = JUMP_CONFIG_RE.findall(galaxy)
    if not configured:
        fail("no gf_JumpConfigClip calls in the map script")
    by_profile: dict[str, list[str]] = {}
    for profile, prefix in configured:
        by_profile.setdefault(profile, []).append(prefix.replace(",", " "))
    # Tosh: the IK bake; Kerrigan: her own source clip (jumpanim.donor).
    if sorted(by_profile) != sorted(JUMP_PROFILES):
        fail(f"jump clips configured for {sorted(by_profile)}, want {sorted(JUMP_PROFILES)}")
    for profile, prefixes in by_profile.items():
        if sorted(prefixes) != sorted(phase.name for phase in JUMP_PHASES):
            fail(f"script jump prefixes of {profile} {sorted(prefixes)} differ from the baked phases")
    walks = sorted(name.replace(",", " ") for name in JUMP_DIR_RE.findall(galaxy))
    if walks != sorted(base.token for base in JUMP_BASES if base.walk):
        fail(f"script walk bases {walks} differ from the baked bases")
    model = m3.loadModel(str(map_dir / TOSH_MODEL))
    groups = {normalized_animation_name(group.name): group for group in model.sequenceTransformationGroups}
    # R-JUMP-16: no jump clip without a base is in the model, so none can play.
    for _, prefix in configured:
        bare = prefix.replace(",", " ") + " Leg"
        if normalized_animation_name(bare) in groups:
            fail(f"{TOSH_MODEL} still has the unmixed jump clip {bare!r}")
    forbidden = subtree(model, UPPER_ROOT)
    owner = {}
    for bone in model.bones:
        for track in (bone.location, bone.rotation, bone.scale):
            owner[track.header.animId] = bone.name
    for name in JUMP_GROUPS:
        group = groups.get(normalized_animation_name(name))
        if group is None:
            fail(f"{TOSH_MODEL} missing jump group {name!r}")
        stc = model.sequenceTransformationCollections[group.stcIndices[0]]
        if not stc.animIds:
            fail(f"{TOSH_MODEL} {name} has no tracks")
        bad = sorted({owner.get(anim_id, "?") for anim_id in stc.animIds} & forbidden)
        if bad:
            fail(f"{TOSH_MODEL} {name} animates non-leg bones: {bad}")
    for line in check_gait(model, galaxy):
        print(f"jump: {line}")
    # REQ-SLOW-WALK: the slow walk clips live in the same model.
    for line in check_slow(model, galaxy, AIM_DIRECTIONS, forbidden, fail):
        print(f"slow: {line}")
    for line in check_donors(map_dir, galaxy, fail):
        print(f"jump: {line}")
