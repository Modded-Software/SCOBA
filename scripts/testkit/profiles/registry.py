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
    "crushtest": ROOT / "out" / "SCOBA256_crushtest.SC2Map",
    "fxgallery": ROOT / "out" / "SCOBA256_fxgallery.SC2Map",
    "waterprobe": ROOT / "out" / "SCOBA256_waterprobe.SC2Map",
    "dissolveview": ROOT / "out" / "SCOBA256_dissolveview.SC2Map",
    "jump": ROOT / "out" / "SCOBA256_jumptest.SC2Map",
    "herodrop": ROOT / "out" / "SCOBA256_herodroptest.SC2Map",
    "intro": ROOT / "out" / "SCOBA256_introtest.SC2Map",
    "podbirth": ROOT / "out" / "SCOBA256_podbirth.SC2Map",
    "aimdof": ROOT / "out" / "SCOBA256_aimdof.SC2Map",
    "skyduel": ROOT / "out" / "SCOBA256_skyduel.SC2Map",
    "aircreep": ROOT / "out" / "SCOBA256_aircreep.SC2Map",
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
    "crushtest": ("SCOBACRUSH",),
    "fxgallery": (),
    "waterprobe": ("SCOBAWATERPROBE",),
    "dissolveview": ("SCOBADISSOLVE",),
    "jump": ("SCOBAJUMPTEST",),
    "herodrop": ("SCOBAHERODROP",),
    "intro": ("SCOBAINTRO",),
    "podbirth": ("SCOBAPODBIRTH",),
    "aimdof": ("SCOBAAIMDOF",),
    "skyduel": ("SCOBASKYDUEL",),
    "aircreep": ("SCOBAAIRCREEP",),
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
    if name == "crushtest":
        from . import crushtest
        return crushtest
    if name == "waterprobe":
        from . import waterprobe
        return waterprobe
    if name == "jump":
        from . import jump
        return jump
    if name == "herodrop":
        from . import herodrop
        return herodrop
    if name == "intro":
        from . import intro
        return intro
    if name == "podbirth":
        from . import podbirth
        return podbirth
    if name == "aimdof":
        from . import aimdof
        return aimdof
    if name == "skyduel":
        from . import skyduel
        return skyduel
    if name == "aircreep":
        from . import aircreep
        return aircreep
    raise SystemExit(f"unknown test profile: {name}")
