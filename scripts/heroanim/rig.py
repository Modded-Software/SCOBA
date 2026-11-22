"""Hero rigs for the split-body bake (character_anim_assets).

One record per hero model names its bones and its options. Turn axes are not
configured: they are read from the model's rest pose, so a new hero needs no
axis tuning (operator 2026-11-21: a copied torso axis tilted a body sideways).
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from hitvolumes.shapes import axis, columns, inverse, norm

MODEL_SIDE = 0  # model X: left-right
MODEL_UP = 2  # model Z
FRAME_MS = 1000.0 / 30.0  # the stock clips are keyed at 30 frames per second


class HeroRig(BaseModel):
    """What the bake needs to know about one hero model."""

    # A rig is a fixed record: no field changes after it is made, and no unknown field is taken.
    model_config = ConfigDict(frozen=True, extra="forbid")

    entry: str  # stock model in the game archives
    target: Path  # generated model in the map
    model_id: str
    model_value: str
    upper_roots: tuple[str, ...]
    attack_roots: tuple[str, ...]
    lower_roots: tuple[str, ...]
    turn_bone: str  # the pelvis: walk direction clips turn the legs about it
    unit_speed: float
    pitch_bones: tuple[str, ...]  # the torso bones the aim pitch turns
    pitch_weights: tuple[float, ...]
    kick_bones: tuple[str, ...]
    kick_axis: str
    kick_sign: float
    kick_degrees: float
    head_bone: str
    # Bones outside the pelvis that belong to the legs (feet keyed on their
    # own bones). They turn with the pelvis in the walk direction clips.
    leg_roots: tuple[str, ...] = ()
    # The stock clip the aim pose is one frame of.
    aim_source: str = "Attack"
    # Aim pose breathing: the pose swings this many source frames to each
    # side of its frame, once per breath_ms. 0 frames: a still pose.
    breath_frames: int = 0
    breath_ms: int = 0

    @property
    def aim_pose_clip(self) -> str:
        """The upper-body copy of `aim_source` (character_anim_assets CLIP_JOBS)."""
        return self.aim_source + " Arm Alternate"


HEROES: dict[str, HeroRig] = {
    "tosh": HeroRig(
        entry=r"mods\liberty.sc2mod\base.sc2assets\assets\units\terran\tosh\tosh.m3",
        target=Path("Assets") / "Units" / "Terran" / "Tosh" / "ToshSCOBA.m3",
        model_id="ToshSCOBA",
        model_value="Assets\\Units\\Terran\\Tosh\\ToshSCOBA.m3",
        upper_roots=("BoneSpine01",),
        attack_roots=("BoneShoulderL", "BoneShoulderR", "BoneHead"),
        lower_roots=("BoneWaist", "Root", "Main"),
        turn_bone="BoneWaist",
        unit_speed=3.1015,
        pitch_bones=("BoneSpine01",),
        pitch_weights=(1.0,),
        kick_bones=("BoneShoulderR",),
        kick_axis="Y",
        kick_sign=-1.0,
        kick_degrees=12.0,
        # The parent of the Ref_Head attachment on this model.
        head_bone="BoneHead",
    ),
    "kerrigan": HeroRig(
        entry=r"mods\liberty.sc2mod\base.sc2assets\assets\units\zerg\kerrigan\kerrigan.m3",
        target=Path("Assets") / "Units" / "Zerg" / "Kerrigan" / "KerriganSCOBA.m3",
        model_id="KerriganSCOBA",
        model_value="Assets\\Units\\Zerg\\Kerrigan\\KerriganSCOBA.m3",
        upper_roots=("Bone07",),
        attack_roots=("Box04", "Box05", "Bone29"),
        lower_roots=("Box01", "Bone34", "Bone34(mirrored)", "Root", "Bone_Link_Object"),
        turn_bone="Box01",
        unit_speed=2.5,
        pitch_bones=("Bone07",),
        pitch_weights=(1.0,),
        kick_bones=("Box04",),
        kick_axis="Y",
        kick_sign=-1.0,
        kick_degrees=12.0,
        # This model has no Ref_Head attachment; Bone29 is taken from the
        # attack roots above. Unproven: operator check.
        head_bone="Bone29",
        # Her feet (Bone04, Bone05 and their mirrors) hang on these two bones
        # under the model root, not under the pelvis.
        leg_roots=("Dummy01", "Dummy02"),
        # Operator 2026-11-22: the aim pose breathes. Asked as +-8 frames; on
        # her Attack (talons) clip that moves a hand 78 % of her height, so
        # the operator chose the Psi Blast cast pose, +-4 frames, 4 s a breath
        # (hands 5 % of her height, chest 3 %).
        aim_source="Spell",
        breath_frames=4,
        breath_ms=4000,
    ),
}


def rest_axis(model, bone: str, row: int) -> tuple[str, float]:
    """The bone's local axis closest to model axis `row`, and the sign of
    that alignment, in the rest pose."""
    index = next(i for i, item in enumerate(model.bones) if item.name == bone)
    rest = inverse(columns(model.absoluteInverseBoneRestPositions[index].matrix))
    dots = [rest[row][c] / max(1e-9, norm(axis(rest, c))) for c in range(3)]
    best = max(range(3), key=lambda c: abs(dots[c]))
    return "XYZ"[best], (1.0 if dots[best] > 0.0 else -1.0)


def yaw_axis(model, bone: str) -> tuple[str, float]:
    """Local axis and sign of a turn about model up: a positive angle turns
    counter-clockwise seen from above, as a rising camera yaw does."""
    return rest_axis(model, bone, MODEL_UP)


def pitch_axis(model, bone: str) -> tuple[str, float]:
    """Local axis and sign of a nod: a positive angle turns the front up.
    The model faces -Y, so that is a turn about model -X."""
    name, side = rest_axis(model, bone, MODEL_SIDE)
    return name, -side


def shared_pitch_axis(model, bones: tuple[str, ...]) -> tuple[str, float]:
    """The nod axis of a chain of bones that pitch together."""
    found = {pitch_axis(model, bone) for bone in bones}
    if len(found) != 1:
        raise ValueError(f"pitch bones {bones} have different nod axes: {sorted(found)}")
    return found.pop()
