"""pncprobe reports for the click, warp and hit groups."""

from __future__ import annotations

from .hover import _hover_snap

CLICK_CASES = (
    ("pnc", "point and click, cursor on the unit (positive control)"),
    ("free", "TPS free cursor at the centre, unit centred (positive control)"),
    ("look", "mouse look, unit on the crosshair"),
    ("target", "mouse look, attack targeting order, unit on the crosshair"),
    ("lookaway", "mouse look, camera turned 60 off the unit (negative)"),
    ("targetaway", "mouse look, attack targeting order, camera still 60 off (negative)"),
)
CLICK_PROBE_PRESSES = len(CLICK_CASES)


def print_click(data: dict) -> None:
    """Raw engine click state per case; see clickprobe.galaxy."""
    raw = data.get("hover", {})
    print(f"click: dist10={raw.get('Dist10')} parkReady={raw.get('parkReady')} done={raw.get('hoverDone')}")
    print(f"click ground: heroAt={raw.get('heroAt')} hero={raw.get('groundHero')} unit={raw.get('groundUnit')}")
    for tag in ("centrefree", "centrelook", "centreafter"):
        print(f"click {tag}: {_hover_snap(raw, tag)}")
    print(f"click centre ticks after mouse look: {raw.get('centreTicks')}")
    for tag, label in CLICK_CASES:
        print(f"click {tag} ({label}):")
        print(f"  downs={raw.get(tag + 'Downs')} pos={raw.get(tag + 'Pos')}")
        print(f"  unitClicks={raw.get(tag + 'UnitClicks')} unit={raw.get(tag + 'UnitClick')!r} selects={raw.get(tag + 'Selects')} select={raw.get(tag + 'Select')!r}")
        print(f"  heroOrder={raw.get(tag + 'Order')} uiTarget={raw.get(tag + 'UiTarget')}")
        print(f"  before: {_hover_snap(raw, tag + 'before')}")
        print(f"  after: {_hover_snap(raw, tag)}")


def print_warp(data: dict) -> None:
    """Raw pick state after mouse look, without and with mouse motion."""
    raw = data.get("hover", {})
    print(f"warp: dist10={raw.get('Dist10')} parkReady={raw.get('parkReady')} done={raw.get('hoverDone')}")
    print(f"warp still ticks={raw.get('stillTicks')} moved ticks={raw.get('movedTicks')}")
    for tag in ("wleft", "still", "movedlook", "moved"):
        print(f"warp {tag}: {_hover_snap(raw, tag)}")


def print_hit(data: dict) -> None:
    """Raw grid hits of the head actor; see hitprobe.galaxy."""
    raw = data.get("hit", {})
    print(f"hit: headValid={raw.get('headValid')} channel={raw.get('channel')} done={raw.get('hitDone')}")
    for c in range(1, 5):
        print(f"hit channel {c}: {raw.get(f'channel{c}')}")
    for key in ("eqMainTwice", "eqHostMain", "eqHeadSelf", "eqHeadMain", "nullUnset", "nullHead"):
        print(f"hit {key}={raw.get(key)}")
    for tag, count in (("stand", 6), ("bare", 1), ("attack", 6), ("scale", 6)):
        for i in range(count):
            key = f"{tag}{i}"
            print(f"hit {key}: hits={raw.get(key + 'Hits')} static={raw.get(key + 'Static')} cells={raw.get(key + 'Cells')!r}")
