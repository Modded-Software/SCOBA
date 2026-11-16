"""Control icon and build stamp checks for scripts/validate-map.py."""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from control_mode_icons import ICONS


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def check_control_icons(map_dir: Path) -> None:
    """The mode buttons use the two stock icons; no generated icon remains."""
    if len(set(ICONS.values())) != len(ICONS):
        fail("control mode icons must differ")
    for stale in ("SCOBAModePNC.dds", "SCOBAModeTPS.dds"):
        if (map_dir / "Assets" / "Textures" / stale).exists():
            fail(f"generated control icon still in map: {stale}")
    tree = ET.parse(map_dir / "Base.SC2Data" / "GameData" / "ButtonData.xml")
    buttons = {element.get("id"): element for element in tree.getroot().iter("CButton")}
    for button_id, icon_path in ICONS.items():
        button = buttons.get(button_id)
        if button is None:
            fail(f"missing button: {button_id}")
        icon = button.find("Icon")
        if icon is None or icon.get("value") != icon_path:
            fail(f"{button_id} has wrong control icon")
    script = map_dir / "scripts" / "app" / "ui" / "hud_buttons.galaxy"
    text = script.read_text(encoding="utf-8", errors="replace")
    for icon_path in ICONS.values():
        if icon_path.replace("\\", "\\\\") not in text:
            fail(f"hud_buttons.galaxy does not use {icon_path}")


def check_skybox_flip(map_dir: Path) -> None:
    """Each flipped sky: the generated m3 and its CModel are in the map."""
    from skybox_flip import FLIPS

    models = ET.parse(map_dir / "Base.SC2Data" / "GameData" / "ModelData.xml").getroot()
    for _entry, target in FLIPS:
        if not (map_dir / target).is_file():
            fail(f"missing flipped sky model: {target}")
        model_id = target.stem
        model = models.find(f"CModel[@id='{model_id}']")
        if model is None:
            fail(f"missing CModel: {model_id}")
        value = model.find("Model")
        if value is None or value.get("value") != str(target).replace("/", "\\"):
            fail(f"CModel {model_id} does not point at {target}")


def check_footfall_fx(map_dir: Path) -> None:
    """Every footfall unit (scripts/footfall/fx.py): attach points on the foot
    bones, a footstep event per foot, and every actor, model, sound and
    filter the unit actor refers to."""
    from footfall.fx import FOOTFALL_UNITS, event_name, m3

    data = map_dir / "Base.SC2Data" / "GameData"
    models = ET.parse(data / "ModelData.xml").getroot()
    actors = ET.parse(data / "ActorData.xml").getroot()
    sounds = ET.parse(data / "SoundData.xml").getroot()
    methods_path = data / "AttachMethodData.xml"
    methods = ET.parse(methods_path).getroot() if methods_path.exists() else ET.Element("Catalog")
    for spec in FOOTFALL_UNITS:
        u = spec.unit
        path = map_dir / spec.target
        if not path.is_file():
            fail(f"missing {u} foot model: {spec.target}")
        model = m3.loadModel(str(path))
        bones = [b.name for b in model.bones]
        points = {a.name: a.boneIndex for a in model.attachmentPoints}
        for foot in spec.feet:
            index = points.get(foot.point)
            if index is None or bones[index] != foot.point:
                fail(f"{u} attach point {foot.point} has no bone of its name")
            if model.bones[index].parent != bones.index(foot.bone):
                fail(f"{u} bone {foot.point} is not under {foot.bone}")
            if not foot.filter_id(u).startswith("AMFilter") and methods.find(f"CAttachMethodFilter[@id='{foot.filter_id(u)}']") is None:
                fail(f"missing attach filter {foot.filter_id(u)}")
        if len(model.attachmentPointAddons) != len(model.attachmentPoints):
            fail(f"{u} attach point addon count mismatch")
        if len(model.absoluteInverseBoneRestPositions) != len(model.bones):
            fail(f"{u} rest pose count mismatch")
        cmodel = models.find(f"CModel[@id='{u}']")
        names = {e.find("Name").get("value") for e in cmodel.findall("Events")} if cmodel is not None else set()
        for i in range(len(spec.feet)):
            if event_name(i) not in names:
                fail(f"CModel {u} has no {event_name(i)} event")
        for kind in ("Dust", "Splash", "Ripple"):
            if models.find(f"CModel[@id='{u}Foot{kind}']") is None:
                fail(f"missing CModel {u}Foot{kind}")
        if sounds.find(f"CSound[@id='{u}Footstep']") is None:
            fail(f"missing CSound {u}Footstep")
        unit_actor = actors.find(f"CActorUnit[@id='{u}']")
        if unit_actor is None:
            fail(f"missing CActorUnit {u}")
        defined = {e.get("id") for e in actors}
        for on in unit_actor.findall("On"):
            send = on.get("Send", "")
            if send.startswith("Create ") and send.split(" ", 1)[1] not in defined:
                fail(f"{u} creates undefined actor {send.split(' ', 1)[1]}")


def check_stamp(map_dir: Path) -> None:
    stamp_path = map_dir / "BuildStamp.txt"
    if not stamp_path.is_file():
        fail("missing BuildStamp.txt")
    stamp = stamp_path.read_text(encoding="utf-8").strip()
    if not stamp:
        fail("empty BuildStamp.txt")
    stamp_file = (map_dir / "scripts" / "app" / "core" / "build_stamp.galaxy").read_text(encoding="utf-8", errors="replace")
    if f'const string c_SCOBA_BUILD_STAMP = "{stamp}";' not in stamp_file:
        fail("build_stamp.galaxy build stamp does not match BuildStamp.txt")
