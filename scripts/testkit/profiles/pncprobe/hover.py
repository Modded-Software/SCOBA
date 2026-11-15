"""pncprobe reports for the hover-based groups: hover, recenter, rotate, recentre, scale."""

from __future__ import annotations

HOVER_STAGES = ("pnc", "free", "freehid", "look2hid")
HOVER_SNAPS = ("clear", "pre", "post")
HOVER_FIELDS = ("UnitHighlighted", "HeroHighlighted", "On", "Off", "Moves", "MouseX", "MouseY", "Cam", "TpsMode")
HOVER_PULSES = 5
CURSOR_IDS = ("Arrow", "Arrow_Terr", "Arrow_Prot", "Arrow_Zerg")


def _hover_snap(raw: dict, tag: str) -> str:
    return " ".join(f"{field}={raw.get(tag + field)}" for field in HOVER_FIELDS)


def print_hover(data: dict) -> None:
    """Raw engine hover state per mouse mode.

    Each stage starts with the pointer parked on the left of the window and
    the unit on the camera centre line. `clear`: unit hidden. `pre`: unit
    shown, no pointer move since the mode change. Then the pointer sweeps to
    the right and back; every highlight event names its unit. `post`: after.
    The pulses switch relative mode off and on in mouse look and count the
    game loops until the highlight follows (-1: never).
    """
    raw = data.get("hover", {})
    print(f"hover: dist10={raw.get('Dist10')} parkReady={raw.get('parkReady')} done={raw.get('hoverDone')}")
    for stage in HOVER_STAGES:
        for snap in HOVER_SNAPS:
            print(f"hover {stage} {snap}: {_hover_snap(raw, stage + snap)}")
        print(f"hover {stage} swept={raw.get(stage + 'Swept')}")
        for key in sorted(name for name in raw if name.startswith(stage + "ev")):
            print(f"hover {stage} event {key[len(stage) + 2:]}: {raw[key]}")
    print(f"hover look mid: {_hover_snap(raw, 'lookmid')}")
    print(f"hover pulse pre: {_hover_snap(raw, 'pulsepre')}")
    for index in range(HOVER_PULSES):
        print(
            f"hover pulse {index}: onTicks={raw.get('pulse' + str(index) + 'OnTicks')}"
            f" offTicks={raw.get('pulse' + str(index) + 'OffTicks')}"
        )
    print(f"hover pulse post: {_hover_snap(raw, 'pulsepost')}")
    for ident in CURSOR_IDS:
        print(
            f"hover cursor {ident}: exists={raw.get('cursor' + ident + 'Exists')}"
            f" texture={raw.get('cursor' + ident + 'Texture')}"
        )


RECENTER_CASES = (
    ("a", "unit hidden and shown"),
    ("b", "nothing changes"),
    ("c", "camera set to its own values"),
    ("d", "camera turned away and back"),
    ("e", "unit moved aside and back"),
    ("g", "after the nudge: relative on for two loops, off, unit hidden and shown"),
)


def print_recenter(data: dict) -> None:
    """Raw engine pick state right after mouse look ends.

    The pointer rests on the left of the window; the target is on the camera
    centre line. `base pre` is the negative case: cursor free and hidden, on
    the left, target not highlighted. Each case leaves mouse look (relative
    mode off, cursor hidden), applies one change, and counts the game loops
    until the target is highlighted (-1: never in 2 s).
    """
    raw = data.get("hover", {})
    print(f"recenter: dist10={raw.get('Dist10')} parkReady={raw.get('parkReady')} done={raw.get('hoverDone')}")
    print(f"recenter ground: heroAt={raw.get('heroAt')} hero={raw.get('groundHero')} unit={raw.get('groundUnit')}")
    for snap in HOVER_SNAPS:
        print(f"recenter base {snap}: {_hover_snap(raw, 'base' + snap)}")
    for key in sorted(name for name in raw if name.startswith("baseev")):
        print(f"recenter base event {key[6:]}: {raw[key]}")
    for tag, label in RECENTER_CASES:
        print(f"recenter {tag} ({label}): ticks={raw.get(tag + 'Ticks')}")
        print(f"recenter {tag} in mouse look: {_hover_snap(raw, tag + 'look')}")
        print(f"recenter {tag} result: {_hover_snap(raw, tag)}")
    print(f"recenter d camera turned: {_hover_snap(raw, 'dturn')}")
    print(f"recenter e unit aside: {_hover_snap(raw, 'emove')}")
    print(f"recenter f before the nudge: {_hover_snap(raw, 'fbefore')}")
    print(f"recenter f after the nudge: {_hover_snap(raw, 'f')}")


ROTATE_STAGES = ("relhid", "rot", "rothid", "free")


def print_rotate(data: dict) -> None:
    """Raw camera, cursor and pick state per mouse mode; see rotateprobe.galaxy."""
    raw = data.get("hover", {})
    print(f"rotate: dist10={raw.get('Dist10')} parkReady={raw.get('parkReady')} done={raw.get('hoverDone')}")
    for stage in ROTATE_STAGES:
        for snap in HOVER_SNAPS:
            print(f"rotate {stage} {snap}: {_hover_snap(raw, stage + snap)}")
        print(f"rotate {stage} swept={raw.get(stage + 'Swept')}")
        for key in sorted(name for name in raw if name.startswith(stage + "ev1")):
            print(f"rotate {stage} event {key[len(stage) + 2:]}: {raw[key]}")


RECENTRE_CASES = ("none", "lock", "letterbox", "console", "cinematic", "world", "cursor", "lockfree")


def print_recentre(data: dict) -> None:
    """Raw cursor position after each candidate call; see recentreprobe.galaxy."""
    raw = data.get("hover", {})
    print(f"recentre: dist10={raw.get('Dist10')} parkReady={raw.get('parkReady')} done={raw.get('hoverDone')}")
    for tag in RECENTRE_CASES:
        print(f"recentre {tag}: ticks={raw.get(tag + 'Ticks')}")
        print(f"  after: {_hover_snap(raw, tag)}")
        print(f"  nudged: {_hover_snap(raw, tag + 'nudged')}")


SCALE_UNITS = ("medic", "marine", "ultra", "hive")


def print_scale(data: dict) -> None:
    """Raw engine highlight events per unit; see scaleprobe.galaxy."""
    raw = data.get("hover", {})
    print(f"scale: parkReady={raw.get('parkReady')} done={raw.get('hoverDone')}")
    for tag in SCALE_UNITS:
        print(f"scale {tag}: dist100={raw.get(tag + 'Dist100')} z100={raw.get(tag + 'Z100')} fov100={raw.get(tag + 'Fov100')} swept={raw.get(tag + 'Swept')}")
        for snap in HOVER_SNAPS:
            print(f"  {snap}: {_hover_snap(raw, tag + snap)}")
        for key in sorted(name for name in raw if name.startswith(tag + "ev1")):
            print(f"  event {key[len(tag) + 2:]}: {raw[key]}")
