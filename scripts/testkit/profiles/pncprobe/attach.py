"""pncprobe `attach` group report: raw live-unit geometry and camera values."""

from __future__ import annotations

ATTACH_UNITS = ("u0", "u1", "u2", "u3", "hero")
ATTACH_FIELDS = (
    "Pos", "Ground", "UnitHeight", "PropHeight", "RadiusCurrent", "RadiusNormal", "Facing",
    "Ref_Origin", "Ref_Center", "Ref_Overhead", "Ref_Head", "Ref_Target",
    "Origin", "Center", "Overhead", "Head", "Target",
)
ATTACH_CAMERA = ("CamTarget", "CamYaw", "CamPitch", "CamDist", "HeroPos", "HeroHeight")


def print_attach(data: dict) -> None:
    """Raw live-unit geometry at 100% and 200% scale, and the camera values."""
    raw = data.get("attach", {})
    print(f"attach: done={raw.get('attachDone')}")
    for unit in ATTACH_UNITS:
        print(f"attach {unit}: type={raw.get(unit + 'Type')}")
        for field in ATTACH_FIELDS:
            print(f"attach {unit} {field}: s100={raw.get(unit + 's100' + field)} s200={raw.get(unit + 's200' + field)}")
    for mode in ("pnc", "tps"):
        values = " ".join(f"{field}={raw.get(mode + field)}" for field in ATTACH_CAMERA)
        print(f"attach camera {mode}: {values}")
