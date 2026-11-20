"""Slow death model checks for scripts/validate-map.py."""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR / "vendor" / "m3addon"))

import m3
from slow_death_assets import FAST_CLIPS, SLOW_DEATHS, SLOW_SIMULATIONS, event_names
from validate_assets import fail

GAMEDATA = Path("Base.SC2Data") / "GameData"
# The HD texture step copies a model and points the CModel at the copy
# (scripts/hdtex/models.py, HD_MODEL_DIR). The copy keeps the file name.
HD_MODEL_DIR = "Assets\\Models\\scoba_hd\\"

# (CModel id, unit actors that must die with it, soundless). A soundless death has
# no sound anywhere. A death with sound keeps its CModel sound events, with
# times stretched to match the model.
SLOW_DEATH_MODELS = (
    ("BattlecruiserLokiDeathSlow", ("MengskBC", "DukesRevenge"), True),
    ("LeviathanDeathSlow", ("Leviathan",), True),
    ("GoliathDeathSlow", ("Goliath",), False),
)

# Stock GoliathDeath sound event times (s), per (anim, name).
GOLIATH_EVENT_TIMES = {
    ("Death,00", "GoliathDeathFXA"): 0.01,
    ("Death,01", "GoliathDeathFXA"): 0.01,
    ("Death,00", "GoliathDeathFXB"): 2.0,
    ("Death,02", "GoliathDeathFXB"): 0.87,
}


def generated_value(model_value: str | None) -> str | None:
    """The generated slow death model a CModel value stands for: itself, or the one its HD copy was made from."""
    values = [str(relative).replace("/", "\\") for _, relative, _, _ in SLOW_DEATHS]
    if model_value in values:
        return model_value
    if model_value and model_value.startswith(HD_MODEL_DIR):
        name = model_value[len(HD_MODEL_DIR) :]
        matches = [value for value in values if value.rsplit("\\", 1)[-1] == name]
        if len(matches) == 1:
            return matches[0]
    return None


def stretch_of(model_value: str) -> int:
    model_value = generated_value(model_value) or model_value
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
        # Evt_SeqEnd ends the clip; Evt_Simulate pre-runs particles. Neither is a sound.
        extra = sorted(set(event_names(m3.loadModel(str(map_dir / relative)))) - {"Evt_SeqEnd", "Evt_Simulate"})
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
    for model_id, actor_ids, soundless in SLOW_DEATH_MODELS:
        node = models.find(f"./CModel[@id='{model_id}']")
        if node is None:
            fail(f"missing CModel {model_id}")
        model = node.find("Model")
        if model is None or generated_value(model.get("value")) is None:
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


# (CModel id, generated model it must use).
SLOW_SIMULATION_MODELS = (("LeviathanTentacle", "Assets\\Effects\\Zerg\\LeviathanTentacle\\LeviathanTentacleSlow.m3"),)
# (CModel id, generated model with fast clips it must use).
FAST_CLIP_MODELS = (("Leviathan", "Assets\\Units\\Zerg\\Leviathan\\LeviathanSCOBA.m3"),)


def check_fast_clips(map_dir: Path) -> None:
    for _, relative, names, _ in FAST_CLIPS:
        if not (map_dir / relative).is_file():
            fail(f"missing fast clip model: {relative}")
        present = {str(s.name) for s in m3.loadModel(str(map_dir / relative)).sequences}
        if not set(names) <= present:
            fail(f"{relative} lost sequences {sorted(set(names) - present)}")
    models = ET.parse(map_dir / GAMEDATA / "ModelData.xml").getroot()
    for model_id, value in FAST_CLIP_MODELS:
        node = models.find(f"./CModel[@id='{model_id}']")
        if node is None or node.find("Model") is None or node.find("Model").get("value") != value:
            fail(f"CModel {model_id} must use {value}")


def check_slow_simulations(map_dir: Path) -> None:
    values = {str(relative).replace("/", "\\") for _, relative, _ in SLOW_SIMULATIONS}
    for _, relative, _ in SLOW_SIMULATIONS:
        path = map_dir / relative
        if not path.is_file():
            fail(f"missing slow simulation model: {relative}")
        model = m3.loadModel(str(path))
        if not model.particles and not model.ribbons:
            fail(f"{relative} has no particles or ribbons to slow")
    models = ET.parse(map_dir / GAMEDATA / "ModelData.xml").getroot()
    for model_id, value in SLOW_SIMULATION_MODELS:
        node = models.find(f"./CModel[@id='{model_id}']")
        if node is None or node.find("Model") is None or node.find("Model").get("value") != value or value not in values:
            fail(f"CModel {model_id} must use {value}")


def check_slow_deaths(map_dir: Path) -> None:
    check_slow_death_models(map_dir)
    check_slow_death_data(map_dir)
    check_slow_simulations(map_dir)
    check_fast_clips(map_dir)
