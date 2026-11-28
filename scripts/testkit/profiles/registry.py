from pathlib import Path

import workpaths

# Profile -> the test map it builds, below SC2_OUT (SPEC-PATHS).
PROFILE_MAPS = {
        "combat": "SCOBA256_test.SC2Map",
        "aim": "SCOBA256_aimtest.SC2Map",
        "controls": "SCOBA256_controlstest.SC2Map",
        "motion": "SCOBA256_motiontest.SC2Map",
        "pitch": "SCOBA256_pitchtest.SC2Map",
        "aimfreeze": "SCOBA256_aimfreezetest.SC2Map",
        "rungun": "SCOBA256_runguntest.SC2Map",
        "pncprobe": "SCOBA256_pncprobe.SC2Map",
        "tps": "SCOBA256_tpstest.SC2Map",
        "treepath": "SCOBA256_treepath.SC2Map",
        "fprot": "SCOBA256_fprot.SC2Map",
        "flora": "SCOBA256_flora.SC2Map",
        "crushtest": "SCOBA256_crushtest.SC2Map",
        "fxgallery": "SCOBA256_fxgallery.SC2Map",
        "waterprobe": "SCOBA256_waterprobe.SC2Map",
        "dissolveview": "SCOBA256_dissolveview.SC2Map",
        "dropview": "SCOBA256_dropview.SC2Map",
        "jump": "SCOBA256_jumptest.SC2Map",
        "slowwalk": "SCOBA256_slowwalk.SC2Map",
        "herodrop": "SCOBA256_herodroptest.SC2Map",
        "intro": "SCOBA256_introtest.SC2Map",
        "podbirth": "SCOBA256_podbirth.SC2Map",
        "aimdof": "SCOBA256_aimdof.SC2Map",
        "skyduel": "SCOBA256_skyduel.SC2Map",
        "aircreep": "SCOBA256_aircreep.SC2Map",
        "ui": "SCOBA256_uitest.SC2Map",
        "baseai": "SCOBA256_baseai.SC2Map",
        "roster": "SCOBA256_roster.SC2Map",
        "ground": "SCOBA256_ground.SC2Map",
        "waterfeat": "SCOBA256_waterfeat.SC2Map",
        "hdbake": "SCOBA256_hdbake.SC2Map",
        "loadwait": "SCOBA256_loadwait.SC2Map",
        "cinematic": "SCOBA256_cinematic.SC2Map",
}


def profile_output(name: str) -> Path:
    """The test map of profile `name`."""
    return workpaths.path("SC2_OUT") / PROFILE_MAPS[name]


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
    "dropview": ("SCOBADROPVIEW",),
    "jump": ("SCOBAJUMPTEST",),
    "slowwalk": ("SCOBASLOWWALK",),
    "herodrop": ("SCOBAHERODROP",),
    "intro": ("SCOBAINTRO",),
    "podbirth": ("SCOBAPODBIRTH",),
    "aimdof": ("SCOBAAIMDOF",),
    "skyduel": ("SCOBASKYDUEL",),
    "aircreep": ("SCOBAAIRCREEP",),
    "ui": ("SCOBAUITEST",),
    "baseai": ("SCOBABASEAI",),
    "roster": ("SCOBAROSTER",),
    "ground": ("SCOBAGROUND",),
    "waterfeat": ("SCOBAWATERFEAT",),
    "hdbake": ("SCOBAHDBAKE",),
    "loadwait": ("SCOBALOADWAIT",),
    "cinematic": ("SCOBACINETEST",),
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
    if name == "slowwalk":
        from . import slowwalk
        return slowwalk
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
    if name == "ui":
        from . import ui
        return ui
    if name == "baseai":
        from . import baseai
        return baseai
    if name == "roster":
        from . import roster
        return roster
    if name == "ground":
        from . import ground
        return ground
    if name == "waterfeat":
        from . import waterfeat
        return waterfeat
    if name == "hdbake":
        from . import hdbake
        return hdbake
    if name == "loadwait":
        from . import loadwait
        return loadwait
    if name == "cinematic":
        from . import cinematic
        return cinematic
    raise SystemExit(f"unknown test profile: {name}")
