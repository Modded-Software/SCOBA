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

# (CModel id, unit actors that must die with it, soundless). A soundless death has
# no sound anywhere. A death with sound keeps its CModel sound events, with
# times stretched to match the model.
SLOW_DEATH_MODELS = (
    ("BattlecruiserLokiDeathSlow", ("MengskBC", "DukesRevenge"), True),
    ("GoliathDeathSlow", ("Goliath",), False),
)

# Stock GoliathDeath sound event times (s), per (anim, name).
GOLIATH_EVENT_TIMES = {
    ("Death,00", "GoliathDeathFXA"): 0.01,
    ("Death,01", "GoliathDeathFXA"): 0.01,
    ("Death,00", "GoliathDeathFXB"): 2.0,
    ("Death,02", "GoliathDeathFXB"): 0.87,
}


def stretch_of(model_value: str) -> int:
    for _, relative, stretch, _ in SLOW_DEATHS:
        if str(relative).replace("/", "\\") == model_value:
            return stretch
    fail(f"no slow death entry for {model_value}")
    return 0


def check_slow_death_models(map_dir: Path) -> None:
    for _, relative, stretch, _ in SLOW_DEATHS:
        path = map_dir / relative
        if not path.is_file():
            fail(f"missing slow death model: {relative}")
        model = m3.loadModel(str(path))
        names = [str(sequence.name) for sequence in model.sequences]
        if not names or any(not name.startswith("Death") for name in names):
            fail(f"{relative} must hold only Death sequences, has {names}")
        for sequence in model.sequences:
            duration = int(sequence.animEndInMS) - int(sequence.animStartInMS)
            if duration <= 0 or duration % stretch != 0:
                fail(f"{relative} {sequence.name} length {duration} ms is not a multiple of the stretch {stretch}")
        if not model.particles:
            fail(f"{relative} lost its particle emitters")


def check_soundless_model(map_dir: Path, value: str) -> None:
    for _, relative, _, _ in SLOW_DEATHS:
        if str(relative).replace("/", "\\") != value:
            continue
        extra = sorted(set(event_names(m3.loadModel(str(map_dir / relative)))) - {"Evt_SeqEnd"})
        if extra:
            fail(f"{relative} carries model events {extra}; sounds must stay out")


def check_event_times(model_id: str, node, stretch: int) -> None:
    found = {}
    for event in node.findall("Events"):
        key = (event.find("Anim").get("value"), event.find("Name").get("value"))
        found[key] = float(event.find("Time").get("value"))
    if set(found) != set(GOLIATH_EVENT_TIMES):
        fail(f"CModel {model_id} events {sorted(found)} differ from the stock {sorted(GOLIATH_EVENT_TIMES)}")
    for key, base in GOLIATH_EVENT_TIMES.items():
        if abs(found[key] - base * stretch) > 1e-4:
            fail(f"CModel {model_id} event {key} at {found[key]} s, want {base * stretch} s")


def check_slow_death_data(map_dir: Path) -> None:
    models = ET.parse(map_dir / GAMEDATA / "ModelData.xml").getroot()
    actors = ET.parse(map_dir / GAMEDATA / "ActorData.xml").getroot()
    values = {str(relative).replace("/", "\\") for _, relative, _, _ in SLOW_DEATHS}
    for model_id, actor_ids, soundless in SLOW_DEATH_MODELS:
        node = models.find(f"./CModel[@id='{model_id}']")
        if node is None:
            fail(f"missing CModel {model_id}")
        model = node.find("Model")
        if model is None or model.get("value") not in values:
            fail(f"CModel {model_id} must point at a generated slow death model")
        if node.get("parent") != "UnitDeath":
            fail(f"CModel {model_id} must have parent UnitDeath, not inherit stock events or a low model")
        # A second speed factor or a low model would undo the copy.
        for child in ("AnimSpeed", "LowQualityModel"):
            if node.find(child) is not None:
                fail(f"CModel {model_id} must not define {child}")
        if soundless:
            if node.find("Events") is not None:
                fail(f"CModel {model_id} must not define Events")
            check_soundless_model(map_dir, model.get("value"))
        else:
            check_event_times(model_id, node, stretch_of(model.get("value")))
        for actor_id in actor_ids:
            actor = actors.find(f"./CActorUnit[@id='{actor_id}']")
            if actor is None:
                fail(f"missing actor {actor_id}")
            normal = [death for death in actor.findall("DeathArray") if death.get("index") == "Normal"]
            if len(normal) != 1 or normal[0].get("ModelLink") != model_id:
                fail(f"{actor_id} Normal death must use {model_id}")
            if soundless and (normal[0].get("SoundLink") != "" or normal[0].get("VoiceLink")):
                fail(f"{actor_id} Normal death must have no sound and no voice")
            for on in actor.findall("On"):
                if on.get("Terms") == "UnitDeath" and "AnimSetTimeScale" in (on.get("Send") or ""):
                    fail(f"{actor_id} must not also scale death time on the unit actor")


def check_slow_deaths(map_dir: Path) -> None:
    check_slow_death_models(map_dir)
    check_slow_death_data(map_dir)
