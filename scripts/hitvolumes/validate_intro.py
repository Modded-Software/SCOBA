"""Map checks split out of validate-map.py: gameplay actors, the intro
(SPEC-INTRO 3.12) and the pod Birth path (SPEC-HERO-DROP 3)."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from . import intro_shots, intro_trees, pod_birth


def animation_actor_problems(map_dir: Path, actors) -> list[str]:
    problems: list[str] = []
    actor_root = ET.parse(map_dir / "Base.SC2Data" / "GameData" / "ActorData.xml").getroot()
    for actor_id, unit_name, model_name in actors:
        node = actor_root.find(f".//CActorUnit[@id='{actor_id}']")
        if node is None:
            problems.append(f"missing gameplay actor {actor_id}")
            continue
        if node.get("parent") != "GenericUnitBase":
            problems.append(f"{actor_id} parent must be GenericUnitBase")
        if node.get("unitName") != unit_name:
            problems.append(f"{actor_id} unitName must be {unit_name}")
        model = node.find("Model")
        if model is None or model.get("value") != model_name:
            problems.append(f"{actor_id} model must be {model_name}")
        events = [(on.get("Terms"), on.get("Send")) for on in node.findall("On")]
        for terms, _ in events:
            if terms is None:
                continue
            if terms.startswith("Abil.attack.") or terms.startswith("WeaponStart.") or terms.startswith("WeaponStop."):
                problems.append(f"{actor_id} must not define native attack event {terms!r}")
    return problems


def intro_problems(map_dir: Path) -> list[str]:
    problems: list[str] = []
    problems.extend(intro_shots.check(map_dir))
    # R-INTRO-17: no map tree in the canopy of the two S2 trees.
    problems.extend(intro_trees.problems(map_dir))
    # SPEC-HERO-DROP 3: the pod's Birth path, generated from the model.
    problems.extend(pod_birth.check(map_dir))
    text = (map_dir / "scripts" / "app" / "core" / "intro.galaxy").read_text(encoding="utf-8")
    if "const bool c_INTRO_ENABLED = true;" not in text:
        problems.append("core/intro.galaxy: c_INTRO_ENABLED must be true in the map")
    main_text = (map_dir / "scripts" / "app" / "main.galaxy").read_text(encoding="utf-8")
    for needed in ('include "scripts/app/core/intro"', 'include "scripts/app/data/intro_shots"', 'include "scripts/app/systems/intro"', "gt_Intro_Init();"):
        if needed not in main_text:
            problems.append(f"main.galaxy missing {needed}")
    init_text = (map_dir / "scripts" / "app" / "app" / "init.galaxy").read_text(encoding="utf-8")
    if "gf_IntroStart();" not in init_text:
        problems.append("gt_MapInit must start the intro (gf_IntroStart)")
    return problems
