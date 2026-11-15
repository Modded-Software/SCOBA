from pathlib import Path

from project_root import project_root

ROOT = project_root()

PROFILE_OUTPUTS = {
    "combat": ROOT / "out" / "SCOBA256_test.SC2Map",
    "aim": ROOT / "out" / "SCOBA256_aimtest.SC2Map",
    "controls": ROOT / "out" / "SCOBA256_controlstest.SC2Map",
    "motion": ROOT / "out" / "SCOBA256_motiontest.SC2Map",
    "pitch": ROOT / "out" / "SCOBA256_pitchtest.SC2Map",
    "aimfreeze": ROOT / "out" / "SCOBA256_aimfreezetest.SC2Map",
    "rungun": ROOT / "out" / "SCOBA256_runguntest.SC2Map",
    "pncprobe": ROOT / "out" / "SCOBA256_pncprobe.SC2Map",
    "tps": ROOT / "out" / "SCOBA256_tpstest.SC2Map",
    "treepath": ROOT / "out" / "SCOBA256_treepath.SC2Map",
    "fprot": ROOT / "out" / "SCOBA256_fprot.SC2Map",
    "flora": ROOT / "out" / "SCOBA256_flora.SC2Map",
}

PROFILE_BANKS = {
    "combat": ("SCOBATEST", "SCOBADBG"),
    "aim": ("SCOBAAIMTEST",),
    "controls": ("SCOBACONTROLSTEST",),
    "motion": ("SCOBAMOTIONTEST",),
    "pitch": ("SCOBAPITCHTEST",),
    "aimfreeze": ("SCOBAAIMFREETEST",),
    "rungun": ("SCOBARUNGUNTEST",),
    "pncprobe": ("SCOBAPNCPROBE",),
    "tps": ("SCOBATPSTEST",),
    "treepath": ("SCOBATREEPATH",),
    "fprot": ("SCOBAFPROT",),
    "flora": ("SCOBAFLORA",),
}


def profile_module(name):
    if name == "combat":
        from . import combat
        return combat
    if name == "aim":
        from . import aim
        return aim
    if name == "controls":
        from . import controls
        return controls
    if name == "pitch":
        from . import pitch
        return pitch
    if name == "motion":
        from . import motion
        return motion
    if name == "aimfreeze":
        from . import aimfreeze
        return aimfreeze
    if name == "rungun":
        from . import rungun
        return rungun
    if name == "pncprobe":
        from .pncprobe import spec as pncprobe
        return pncprobe
    if name == "tps":
        from . import tps
        return tps
    if name == "treepath":
        from . import treepath
        return treepath
    if name == "fprot":
        from . import fprot
        return fprot
    if name == "flora":
        from . import flora
        return flora
    raise SystemExit(f"unknown test profile: {name}")
