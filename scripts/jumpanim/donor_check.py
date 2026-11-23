"""Build checks of the source-clip jump (jumpanim.donor, REQ-JUMP R-JUMP-23).

Reads the built hero model and the map script: clip set and lengths, lower
bones only, the body rise removed, the cut at the ground, the End seam, and
the walk cycle constant of the script."""

from __future__ import annotations

import math
import re
from pathlib import Path

import m3
from animation_tokens import normalized_animation_name
from heroanim.rig import HEROES
from jumpanim.bake import END, JUMP_BASES, JUMP_PHASES, STAND_BASE, baked_name, base_time, clip_plan
from jumpanim.donor import DONOR_HEROES, body_height, cut_ms, lowest_foot
from jumpanim.kin import bone_world, clip_pose, group_clip
from walkanim.strafe import subtree

# Body height in a jump clip vs the range of the stand and walk it is built
# on (model units; the source clip itself rises 0.85).
BODY_TOLERANCE = 0.01
# Lowest foot at the cut vs its first frame height.
CUT_TOLERANCE = 0.005
# Feet at the end of End vs the base clip it hands back to.
SEAM_TOLERANCE = 0.01
CYCLE_RE = re.compile(r"const fixed c_JUMP_GAIT_CYCLE_(\w+) = ([0-9.]+);")


def body_range(model, donor, group: str) -> tuple[float, float]:
    _, start, end, _ = group_clip(model, group)
    heights = [body_height(model, donor, clip_pose(model, group, ms)) for ms in range(0, end - start + 1, 33)]
    return min(heights), max(heights)


def check_hero(map_dir: Path, galaxy: str, key: str, fail) -> list[str]:
    rig, donor = HEROES[key], DONOR_HEROES[key]
    model = m3.loadModel(str(map_dir / rig.target))
    label = rig.target.name
    groups = {normalized_animation_name(group.name): group for group in model.sequenceTransformationGroups}
    sequences = {sequence.name: sequence for sequence in model.sequences}
    for phase in JUMP_PHASES:
        if normalized_animation_name(phase.name + " Leg") in groups:
            fail(f"{label} has the unmixed jump clip {phase.name} Leg")
    forbidden = set(subtree(model, rig.upper_roots))
    owner = {}
    for bone in model.bones:
        for track in (bone.location, bone.rotation, bone.scale):
            owner[track.header.animId] = bone.name
    low, high = math.inf, -math.inf
    for base in JUMP_BASES:
        a, b = body_range(model, donor, base.group)
        low, high = min(low, a), max(high, b)
    worst = 0.0
    for phase, base, stride in clip_plan():
        name = baked_name(phase, base, stride)
        group = groups.get(normalized_animation_name(name))
        if group is None:
            fail(f"{label} missing jump group {name!r}")
        sequence = sequences[group.name]
        if sequence.animEndInMS - sequence.animStartInMS != phase.length_ms:
            fail(f"{label} {name} is {sequence.animEndInMS - sequence.animStartInMS} ms, want {phase.length_ms}")
        if bool(sequence.flags & 1) == phase.looping:
            fail(f"{label} {name} looping flag differs from the phase")
        stc = model.sequenceTransformationCollections[group.stcIndices[0]]
        bad = sorted({owner.get(anim_id, "?") for anim_id in stc.animIds} & forbidden)
        if bad:
            fail(f"{label} {name} animates upper-body bones: {bad}")
        for ms in range(0, phase.length_ms + 1, 33):
            height = body_height(model, donor, clip_pose(model, name, ms))
            gap = max(0.0, low - height, height - high)
            worst = max(worst, gap)
            if gap > BODY_TOLERANCE:
                fail(f"{label} {name} at {ms} ms: body at {height:.3f}, outside the base range {low:.3f}..{high:.3f}")
    # Negative: the source clip itself leaves that range (the check can fail).
    _, src_high = body_range(model, donor, donor.source)
    if src_high - high <= BODY_TOLERANCE:
        fail(f"{label} {donor.source} does not rise above the base range: the body check proves nothing")
    cut = cut_ms(model, donor)
    ground = lowest_foot(model, donor.source, 0, donor.feet)
    at_cut = lowest_foot(model, donor.source, cut, donor.feet)
    if abs(at_cut - ground) > CUT_TOLERANCE:
        fail(f"{label} {donor.source} cut at {cut} ms: lowest foot {at_cut:.4f}, ground {ground:.4f}")
    seam = 0.0
    for base in JUMP_BASES:
        for stride in (range(2) if base.walk else (None,)):
            name = baked_name(END, base, stride)
            _, start, end, _ = group_clip(model, base.group)
            want = bone_world(model, clip_pose(model, base.group, base_time(END, base, stride, END.length_ms, end - start)), donor.feet)
            got = bone_world(model, clip_pose(model, name, END.length_ms), donor.feet)
            gap = max(math.dist(want[foot][0], got[foot][0]) for foot in donor.feet)
            seam = max(seam, gap)
            if gap > SEAM_TOLERANCE:
                fail(f"{label} {name}: feet end {gap:.4f} from {base.group}")
    cycles = {name.lower(): float(value) for name, value in CYCLE_RE.findall(galaxy)}
    _, start, end, _ = group_clip(model, JUMP_BASES[1].group)
    if abs(cycles.get(key, -1.0) - (end - start) / 1000.0) > 0.0015:
        fail(f"c_JUMP_GAIT_CYCLE_{key.upper()} {cycles.get(key)} differs from the walk cycle {end - start} ms")
    return [
        f"{label}: {len(clip_plan())} clips from {donor.source} 0-{cut} ms (lowest foot {at_cut:.4f}, ground {ground:.4f})",
        f"{label}: body off the base range max {worst:.4f}/{BODY_TOLERANCE}; source rises to {src_high:.3f} (base {low:.3f}..{high:.3f})",
        f"{label}: End seams max {seam:.4f}/{SEAM_TOLERANCE}, walk cycle {end - start} ms, stand base {STAND_BASE.group}",
    ]


def check_donors(map_dir: Path, galaxy: str, fail) -> list[str]:
    out = []
    for key in DONOR_HEROES:
        out.extend(check_hero(map_dir, galaxy, key, fail))
    return out
