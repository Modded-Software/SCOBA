"""Hero rig checks for scripts/validate-map.py (R-TPS-18, 19; SPEC-TPS 5.2).

Run on the built hero models: the torso pitch nods (it does not roll), the
walk direction clips turn the legs as one body, and the aim pose breathes
where the rig says so, in step with the script's breath period.
"""

from __future__ import annotations

import math
import re
from pathlib import Path

import m3
from character_anim_assets import AIM_DIRECTIONS, AIM_PITCH_GROUP, AIM_PITCH_STEPS
from heroanim.rig import HEROES, HeroRig
from jumpanim.kin import bone_world, clip_pose, group_clip
from walkanim.strafe import check as check_strafe

BREATH_CONST_RE = re.compile(r"const fixed c_ANIM_BREATH_(\w+) = ([0-9.]+);")
BREATH_CONFIG_RE = re.compile(r"gv_animBreathPeriod\[c_ANIM_HERO_(\w+)\] = c_ANIM_BREATH_(\w+);")
# A nod moves the head up-down and front-back; a roll moves it sideways.
# The torso nods about its own left-right axis as the aim pose holds it,
# and the pose itself turns the torso (Tosh stands side-on: measured share
# 0.43; Kerrigan 0.08). A roll has a share near 1.
MAX_SIDE_SHARE = 0.5
MIN_NOD_TRAVEL = 0.05  # model units, lowest to highest pitch step
SAME = 1e-6


def pitch_clip(step: int) -> str:
    return f"{AIM_PITCH_GROUP} {step:02d}"


def check_nod(model, label: str, rig: HeroRig, fail) -> str:
    """From the lowest to the highest pitch step the head moves back and not
    sideways: the torso turns about the model's left-right axis."""
    low, high = (bone_world(model, clip_pose(model, pitch_clip(step), 0), (rig.head_bone,))[rig.head_bone][0] for step in (1, AIM_PITCH_STEPS))
    side, back = high[0] - low[0], high[1] - low[1]
    travel = math.dist(low, high)
    if travel < MIN_NOD_TRAVEL:
        fail(f"{label}: the head moves {travel:.4f} between the lowest and highest aim pitch (want {MIN_NOD_TRAVEL}): the torso does not pitch")
    if abs(side) > MAX_SIDE_SHARE * travel:
        fail(f"{label}: the aim pitch moves the head {side:+.4f} sideways of {travel:.4f}: the torso rolls, it does not nod")
    # The model faces -Y: looking up carries the head back, to +Y.
    if back <= 0.0:
        fail(f"{label}: the highest aim pitch moves the head {back:+.4f} along the back axis: the pitch is upside down")
    return f"{label}: aim pitch moves the head {travel:.3f}, sideways {abs(side):.4f} (limit {MAX_SIDE_SHARE * travel:.4f}), back {back:+.3f}"


def moving_tracks(stc, label: str, fail) -> int:
    """Tracks whose keys differ. Every track must end on its first key."""
    moving = 0
    for blocks, size in ((stc.sd3v, 3), (stc.sd4q, 4)):
        for block in blocks:
            keys = [(float(key.x), float(key.y), float(key.z)) + ((float(key.w),) if size == 4 else ()) for key in block.keys]
            if not keys:
                continue
            if max(abs(a - b) for a, b in zip(keys[0], keys[-1])) > SAME:
                fail(f"{label}: a track does not end on its first key: the loop would jump")
            moving += any(max(abs(a - b) for a, b in zip(key, keys[0])) > SAME for key in keys)
    return moving


def check_breath(model, label: str, rig: HeroRig, fail) -> str:
    """A breathing rig: every pitch step is one closed loop of one breath
    with moving tracks. A still rig: no pitch step moves."""
    least = None
    for step in range(1, AIM_PITCH_STEPS + 1):
        name = pitch_clip(step)
        stc, start, end, _ = group_clip(model, name)
        moving = moving_tracks(stc, f"{label} {name}", fail)
        if rig.breath_frames == 0:
            if moving:
                fail(f"{label} {name}: {moving} tracks move, but the rig has a still aim pose")
            continue
        if end - start != rig.breath_ms:
            fail(f"{label} {name}: {end - start} ms long, one breath is {rig.breath_ms} ms; the script could not keep the phase")
        if moving == 0:
            fail(f"{label} {name}: no track moves; the aim pose does not breathe")
        least = moving if least is None else min(least, moving)
    if rig.breath_frames == 0:
        return f"{label}: still aim pose, {AIM_PITCH_STEPS} pitch steps"
    return f"{label}: aim pose breathes, {AIM_PITCH_STEPS} pitch steps of {rig.breath_ms} ms, at least {least} tracks move"


def check_breath_script(galaxy: str, fail) -> str:
    """The script's breath periods are the rigs' (gf_AnimAimBreathSync)."""
    want = {key.upper(): rig.breath_ms / 1000.0 for key, rig in HEROES.items() if rig.breath_frames}
    found = {name: float(value) for name, value in BREATH_CONST_RE.findall(galaxy)}
    if found != want:
        fail(f"script breath periods {found} differ from the rigs' {want}")
    config = sorted(BREATH_CONFIG_RE.findall(galaxy))
    if config != sorted((name, name) for name in want):
        fail(f"gv_animBreathPeriod is set for {config}, the rigs breathe for {sorted(want)}")
    if "gf_AnimAimBreathSync(lp_player, lv_hero);" not in galaxy:
        fail("no pitch clip play calls gf_AnimAimBreathSync")
    return f"script breath periods match the rigs: {want}"


def check_heroes(map_dir: Path, galaxy: str, fail) -> None:
    for key, rig in HEROES.items():
        model = m3.loadModel(str(map_dir / rig.target))
        print(f"hero: {check_nod(model, key, rig, fail)}")
        clips = [("Attack Walk " + name, yaw, reverse) for name, yaw, reverse in AIM_DIRECTIONS]
        print(f"hero: {check_strafe(model, key, rig.turn_bone, rig.leg_roots, 'Walk Leg', clips, fail)}")
        print(f"hero: {check_breath(model, key, rig, fail)}")
    print(f"hero: {check_breath_script(galaxy, fail)}")
