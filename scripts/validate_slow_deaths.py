"""Slow death model checks for scripts/validate-map.py."""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR / "vendor" / "m3addon"))

import m3
from slow_death_assets import SLOW_DEATHS, event_names
from validate_assets import fail

GAMEDATA = Path("Base.SC2Data") / "GameData"

# (CModel id, unit actors that must die with it).
SLOW_DEATH_MODELS = (
    ("BattlecruiserLokiDeathSlow", ("MengskBC", "DukesRevenge")),
)


def check_slow_death_models(map_dir: Path) -> None:
    for _, relative, stretch, _ in SLOW_DEATHS:
        path = map_dir / relative
        if not path.is_file():
            fail(f"missing slow death model: {relative}")
        model = m3.loadModel(str(path))
        names = [sequence.name for sequence in model.sequences]
        if names != ["Death"]:
            fail(f"{relative} must hold one Death sequence, has {names}")
        duration = int(model.sequences[0].animEndInMS) - int(model.sequences[0].animStartInMS)
        if duration <= 0 or duration % stretch != 0:
            fail(f"{relative} Death length {duration} ms is not a multiple of the stretch {stretch}")
        if not model.particles:
            fail(f"{relative} lost its particle emitters")
        extra = sorted(set(event_names(model)) - {"Evt_SeqEnd"})
        if extra:
            fail(f"{relative} carries model events {extra}; sounds must stay out")


def check_slow_death_data(map_dir: Path) -> None:
    models = ET.parse(map_dir / GAMEDATA / "ModelData.xml").getroot()
    actors = ET.parse(map_dir / GAMEDATA / "ActorData.xml").getroot()
    values = {str(relative).replace("/", "\\") for _, relative, _, _ in SLOW_DEATHS}
    for model_id, actor_ids in SLOW_DEATH_MODELS:
        node = models.find(f"./CModel[@id='{model_id}']")
        if node is None:
            fail(f"missing CModel {model_id}")
        model = node.find("Model")
        if model is None or model.get("value") not in values:
            fail(f"CModel {model_id} must point at a generated slow death model")
        # Sound events, a second speed factor, or a low model would undo the copy.
        for child in ("Events", "AnimSpeed", "LowQualityModel"):
            if node.find(child) is not None:
                fail(f"CModel {model_id} must not define {child}")
        for actor_id in actor_ids:
            actor = actors.find(f"./CActorUnit[@id='{actor_id}']")
            if actor is None:
                fail(f"missing actor {actor_id}")
            normal = [death for death in actor.findall("DeathArray") if death.get("index") == "Normal"]
            if len(normal) != 1 or normal[0].get("ModelLink") != model_id:
                fail(f"{actor_id} Normal death must use {model_id}")
            if normal[0].get("SoundLink") != "" or normal[0].get("VoiceLink"):
                fail(f"{actor_id} Normal death must have no sound and no voice")
            for on in actor.findall("On"):
                if on.get("Terms") == "UnitDeath" and "AnimSetTimeScale" in (on.get("Send") or ""):
                    fail(f"{actor_id} must not also scale death time on the unit actor")


def check_slow_deaths(map_dir: Path) -> None:
    check_slow_death_models(map_dir)
    check_slow_death_data(map_dir)
