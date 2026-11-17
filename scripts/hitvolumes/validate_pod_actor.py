"""Drop pod art checks for scripts/validate-map.py.

The stock TerranDropPod actor and model live in liberty.sc2campaign, which
the map's dependency (VoidStory) does not load. A map actor of that id with
no parent and no model draws the engine's stand-in sphere. The pod art
is the DropPodFalling model of liberty.sc2mod. It lives in a default="1"
template: an actor whose parent is a concrete actor is not created
(podbirth/20261117-105245: "Unable to create unit actor").
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

ACTORS = Path("Base.SC2Data") / "GameData" / "ActorData.xml"
POD_ART = "SCOBADropPodArt"
POD_PARENT = "GenericUnitStandardNoAutoSoundLinks"
POD_MODEL = "DropPodFalling"
# The hero pod's own model: the same art with a point on the Birth root.
CHILD_MODELS: dict[str, str] = {}
# Unit actors that must draw the pod art through POD_ART.
POD_CHILDREN = ("TerranDropPod", "SCOBAHeroPod")


def pod_actor_problems(root: ET.Element) -> list[str]:
    actors = {a.get("id"): a for a in root.iter("CActorUnit")}
    problems: list[str] = []
    art = actors.get(POD_ART)
    if art is None:
        return [f"ActorData: missing CActorUnit {POD_ART}"]
    if art.get("default") != "1":
        problems.append(f"ActorData: {POD_ART} must be default=\"1\"")
    if art.get("parent") != POD_PARENT:
        problems.append(f"ActorData: {POD_ART} parent must be {POD_PARENT}, is {art.get('parent')}")
    model = art.find("Model")
    if model is None or model.get("value") != POD_MODEL:
        problems.append(f"ActorData: {POD_ART} Model must be {POD_MODEL}, is {None if model is None else model.get('value')}")
    for child in POD_CHILDREN:
        actor = actors.get(child)
        if actor is None:
            problems.append(f"ActorData: missing CActorUnit {child}")
            continue
        if actor.get("parent") != POD_ART:
            problems.append(f"ActorData: {child} parent must be {POD_ART}, is {actor.get('parent')}")
        if actor.get("unitName") != child:
            problems.append(f"ActorData: {child} unitName must be {child}, is {actor.get('unitName')}")
        own = actor.find("Model")
        want = CHILD_MODELS.get(child)
        if want is not None and (own is None or own.get("value") != want):
            problems.append(f"ActorData: {child} Model must be {want}, is {None if own is None else own.get('value')}")
        if want is None and own is not None and own.get("value") != POD_MODEL:
            problems.append(f"ActorData: {child} Model must be {POD_MODEL} or inherited, is {own.get('value')}")
    return problems


def check_pod_actor(map_dir: Path) -> list[str]:
    return pod_actor_problems(ET.parse(map_dir / ACTORS).getroot())
