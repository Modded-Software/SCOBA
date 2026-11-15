"""TPS overlay checks for scripts/validate-map.py.

The crosshair and the shot texts are frames of the map's UI layout. They
must not accept the mouse: a frame that does blocks the engine's cursor
pick of every unit behind it (R-TPS-85).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from validate_assets import fail

UI = Path("Base.SC2Data") / "UI"
LAYOUT = UI / "Layout" / "Custom" / "ScobaTps.SC2Layout"
SYSTEMS = Path("scripts") / "app" / "systems"
PARENT = "GameUI/UIContainer/FullscreenUpperContainer"
TEXT_STYLE = "SCOBAFloaterText"
TEXT_TEMPLATE = "ScobaTps/ShotTextTemplate"
TEXT_COUNT = 4


def child_value(frame: ET.Element, tag: str) -> str | None:
    node = frame.find(tag)
    return None if node is None else node.get("val")


def check_no_mouse(frame: ET.Element, name: str) -> None:
    if child_value(frame, "AcceptsMouse") != "false":
        fail(f"TPS overlay frame {name} must not accept the mouse")


def check_layout(map_dir: Path) -> None:
    index = (map_dir / UI / "Layout" / "DescIndex.SC2Layout").read_text(encoding="utf-8")
    if "UI/Layout/Custom/ScobaTps.SC2Layout" not in index:
        fail("DescIndex.SC2Layout must include the TPS overlay layout")
    root = ET.parse(map_dir / LAYOUT).getroot()
    template = root.find("Frame[@name='ShotTextTemplate']")
    if template is None or template.get("type") != "Label":
        fail("TPS overlay layout lacks the shot text label template")
    check_no_mouse(template, "ShotTextTemplate")
    if child_value(template, "Style") != TEXT_STYLE:
        fail(f"shot text labels must use the {TEXT_STYLE} font style")
    parent = root.find(f"Frame[@name='{PARENT}']")
    if parent is None:
        fail(f"TPS overlay frames must be children of {PARENT}")
    crosshair = parent.find("Frame[@name='ScobaCrosshair']")
    if crosshair is None or crosshair.get("type") != "Image":
        fail("TPS overlay layout lacks the crosshair image")
    check_no_mouse(crosshair, "ScobaCrosshair")
    if "cursor-target-none.dds" not in (child_value(crosshair, "Texture") or ""):
        fail("the crosshair must use the crosshair texture")
    panel = parent.find("Frame[@name='ScobaShotText']")
    if panel is None:
        fail("TPS overlay layout lacks the shot text panel")
    check_no_mouse(panel, "ScobaShotText")
    labels = panel.findall("Frame")
    names = [label.get("name") for label in labels]
    if names != [f"Text{index}" for index in range(TEXT_COUNT)]:
        fail(f"the shot text panel must hold Text0 to Text{TEXT_COUNT - 1}, has {names}")
    for label in labels:
        if label.get("type") != "Label" or label.get("template") != TEXT_TEMPLATE:
            fail(f"shot text {label.get('name')} must be a label from {TEXT_TEMPLATE}")


def check_font(map_dir: Path) -> None:
    styles = ET.parse(map_dir / UI / "FontStyles.SC2Style").getroot()
    floater = [style for style in styles.iter("Style") if style.get("name") == TEXT_STYLE]
    if len(floater) != 1 or int(floater[0].get("height", "0")) < 28:
        fail(f"{TEXT_STYLE} font style missing or smaller than 28")


def check_script(map_dir: Path, combined: str) -> None:
    if "storm_ui_cursor_default_enemy" in combined or "storm_ui_cursor_default_friendly" in combined:
        fail("reticle must use the crosshair texture, not arrow cursors")
    if "gf_ReticleColor" not in combined:
        fail("reticle must be tinted per state")
    if "gf_UiFloaterShow" not in combined or "gf_AimMissFloater" in combined:
        fail("shot outcome text must be the UI-layer floater")
    if f"c_UI_FLOATER_POOL = {TEXT_COUNT};" not in combined:
        fail(f"the script text pool must match the {TEXT_COUNT} layout labels")
    for constant, frame in (("c_UI_FLOATER_FRAME", "ScobaShotText"), ("c_UI_RETICLE_FRAME", "ScobaCrosshair")):
        if f'{constant} = "UIContainer/FullscreenUpperContainer/{frame}";' not in combined:
            fail(f"{constant} must name the layout frame {frame}")
    # A trigger dialog takes the mouse over its whole rectangle.
    for name in ("aim.galaxy", "ui_floaters.galaxy"):
        text = (map_dir / SYSTEMS / name).read_text(encoding="utf-8", errors="replace")
        if "DialogCreate(" in text or "libNtve_gf_CreateDialogItem" in text:
            fail(f"{name} must hook up layout frames, not create a trigger dialog")
        if "DialogControlHookupStandard(" not in text:
            fail(f"{name} must hook up its layout frame")


def check_tps_overlay(map_dir: Path, combined: str) -> None:
    check_layout(map_dir)
    check_font(map_dir)
    check_script(map_dir, combined)
