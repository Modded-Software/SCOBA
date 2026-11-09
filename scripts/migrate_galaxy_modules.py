#!/usr/bin/env python3
"""Split the generated Galaxy monoliths into the new module tree."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import NotRequired, TypedDict

from project_root import project_root

ROOT = project_root()
SRC = ROOT / "src" / "SCOBA.SC2Map"
OUT = SRC / "scripts" / "app"

MAPSCRIPT = SRC / "MapScript.galaxy"
COMBAT = SRC / "scripts" / "combat.galaxy"

FUNC_RE = re.compile(
    r"^([A-Za-z_][A-Za-z0-9_ ]*?)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^;]*)\)\s*\{\s*$"
)
PROTO_RE = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_ ]*\s+[A-Za-z_][A-Za-z0-9_]*\s*\([^;]*\)\s*;\s*$"
)
GLOBAL_RE = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(?:[ ]*\[[^\]]*\])*[ ]+"
    r"[A-Za-z_][A-Za-z0-9_]*(?:[ ]*\[[^\]]*\])*[ ]*;[ ]*$"
)

SKIP_FUNCS = {"InitLibs", "InitGlobals", "InitTriggers", "InitMap"}

MODULE = {
    "gf_InitializeLevelingInterface": "ui/stats_dialog",
    "gf_ShowStasLevelingInterface": "ui/stats_dialog",
    "gf_GetLifeandEnergyStatFormula": "ui/stats_dialog",
    "gf_GetToolTipLifeandEnergyFormula": "ui/stats_dialog",
    "gf_GetMovementStatFormula": "ui/stats_dialog",
    "gf_GetRegenStatFormula": "ui/stats_dialog",
    "gf_SBDialogShowStatsButton": "ui/stats_dialog",
    "gt_SBDialogStatsCallback_Func": "ui/stats_dialog",
    "gt_SBDialogStatsCallback_Init": "ui/stats_dialog",
    "gf_PlayerBarsCreate": "ui/player_bars",
    "gf_PlayerBarsUpdate": "ui/player_bars",
    "gt_PlayerBars_Func": "ui/player_bars",
    "gt_PlayerBars_Init": "ui/player_bars",
    "gf_SBDialogCreateStatsButton": "ui/hud_buttons",
    "gf_SBDialogCreateAbilitiesButton": "ui/hud_buttons",
    "gf_SBDialogCreateInventoryButton": "ui/hud_buttons",
    "gf_UnitSelectionDialogUpdateToolTip": "ui/unit_selection_dialog",
    "gf_UnitSelectionDialogShow": "ui/unit_selection_dialog",
    "gf_UnitSelectionDialogCreate": "ui/unit_selection_dialog",
    "gf_InitializeUnitButtons": "ui/unit_selection_dialog",
    "gf_AddUnitButton": "ui/unit_selection_dialog",
    "gt_UserSelectionDialogCallback_Func": "ui/unit_selection_dialog",
    "gt_UserSelectionDialogCallback_Init": "ui/unit_selection_dialog",
    "gf_Createalinefordialog": "ui/dialog_helpers",
    "gf_GetTalentTreeType": "ui/abilities_dialog",
    "gf_GetNextRow": "ui/abilities_dialog",
    "gf_CanLevelAbility": "ui/abilities_dialog",
    "gf_ShowAbilityLevelingInterface": "ui/abilities_dialog",
    "gf_SBDialogShowAbilitiesButton": "ui/abilities_dialog",
    "gf_AbilitiesSelectionDialogLockAbilities": "ui/abilities_dialog_update",
    "gf_AbilitiesSelectionDialogUnlockAbilities": "ui/abilities_dialog_update",
    "gf_AbilitiesSelectionDialogUpdateButtonsandIcons": "ui/abilities_dialog_update",
    "gf_AbilitiesSelectionDialogUnlockUltimates": "ui/abilities_dialog_update",
    "gf_AbilitiesSelectionDialogAddLinestoDialog": "ui/abilities_dialog",
    "gf_AbilitiesSelectionDialogAddButtonstoDialog": "ui/abilities_dialog",
    "gf_AbilitiesSelectionDialogAddKeyColumn": "ui/abilities_dialog",
    "gf_AbilitiesSelectionDialogUpdateKeyColumn": "ui/abilities_dialog_update",
    "gf_AbilitiesSelectionDialogHide": "ui/abilities_dialog_update",
    "gf_AbilitiesSelectionDialogShow": "ui/abilities_dialog_update",
    "gf_AbilitiesSelectionDialogCreate": "ui/abilities_dialog",
    "gf_InitializeAbilitiesButtons": "ui/abilities_dialog",
    "gf_AddAbilitiesButton": "ui/abilities_dialog",
    "gt_AbilitiesandStatsTriggerDevelopment_Func": "ui/abilities_dialog_update",
    "gt_AbilitiesandStatsTriggerDevelopment_Init": "ui/abilities_dialog_update",
    "gt_AbilitiesandStatsCreateTrigger_Func": "ui/abilities_dialog",
    "gt_AbilitiesandStatsCreateTrigger_Init": "ui/abilities_dialog",
    "gt_SBDialogAbilitiesCallback_Func": "ui/abilities_dialog_update",
    "gt_SBDialogAbilitiesCallback_Init": "ui/abilities_dialog_update",
    "gt_AbilitiesSelectionDialogCallback_Func": "ui/abilities_dialog_update",
    "gt_AbilitiesSelectionDialogCallback_Init": "ui/abilities_dialog_update",
    "gf_UnlockSupportTalentTree": "ui/ability_talent_trees",
    "gf_UnlockDefenseTalentTree": "ui/ability_talent_trees",
    "gf_UnlockOffenseTalentTree": "ui/ability_talent_trees",
    "gf_UnlockSpecialistTalentTree": "ui/ability_talent_trees",
    "gt_MapInit_Func": "app/init",
    "gt_MapInit_Init": "app/init",
    "gt_SetAlliances_Func": "app/alliances",
    "gt_SetAlliances_Init": "app/alliances",
    "gt_GUIEnvironmentSetup_Func": "systems/gui_environment",
    "gt_GUIEnvironmentSetup_Init": "systems/gui_environment",
    "gt_UnitSelection_Func": "systems/selection",
    "gt_UnitSelection_Init": "systems/selection",
    "gt_NewUnitSelection_Func": "systems/selection",
    "gt_NewUnitSelection_Init": "systems/selection",
    "gt_KeepHeroSelected_Func": "systems/selection",
    "gt_KeepHeroSelected_Init": "systems/selection",
    "gt_ShowStatusBar_Func": "systems/status_bar",
    "gt_ShowStatusBar_Init": "systems/status_bar",
    "gt_HideStatusBar_Func": "systems/status_bar",
    "gt_HideStatusBar_Init": "systems/status_bar",
    "gt_CameraFollowDistance_Func": "systems/camera",
    "gt_CameraFollowDistance_Init": "systems/camera",
    "gt_Jump_Func": "systems/camera",
    "gt_Jump_Init": "systems/camera",
    "gt_ZoomEnd_Func": "systems/camera",
    "gt_ZoomEnd_Init": "systems/camera",
    "gt_ZoomStart_Func": "systems/camera",
    "gt_ZoomStart_Init": "systems/camera",
    "gt_CursorStart_Func": "systems/camera",
    "gt_CursorStart_Init": "systems/camera",
    "gt_CursorEnd_Func": "systems/camera",
    "gt_CursorEnd_Init": "systems/camera",
    "gt_XCenterUnitOrders_Func": "systems/camera",
    "gt_XCenterUnitOrders_Init": "systems/camera",
    "gt_XTopUnitOrders_Func": "systems/camera",
    "gt_XTopUnitOrders_Init": "systems/camera",
    "gt_XBottomUnitOrders_Func": "systems/camera",
    "gt_XBottomUnitOrders_Init": "systems/camera",
    "gt_DisableClickMove_Func": "systems/movement",
    "gt_DisableClickMove_Init": "systems/movement",
    "gt_ForwardStart_Func": "systems/movement",
    "gt_ForwardStart_Init": "systems/movement",
    "gt_ForwardEnd_Func": "systems/movement",
    "gt_ForwardEnd_Init": "systems/movement",
    "gt_BackwardStart_Func": "systems/movement",
    "gt_BackwardStart_Init": "systems/movement",
    "gt_BackwardEnd_Func": "systems/movement",
    "gt_BackwardEnd_Init": "systems/movement",
    "gt_LeftStart_Func": "systems/movement",
    "gt_LeftStart_Init": "systems/movement",
    "gt_LeftEnd_Func": "systems/movement",
    "gt_LeftEnd_Init": "systems/movement",
    "gt_RightStart_Func": "systems/movement",
    "gt_RightStart_Init": "systems/movement",
    "gt_RightEnd_Func": "systems/movement",
    "gt_RightEnd_Init": "systems/movement",
    "gt_Target_Func": "systems/targeting",
    "gt_Target_Init": "systems/targeting",
    "gt_ClearTarget_Func": "systems/targeting",
    "gt_ClearTarget_Init": "systems/targeting",
    "gf_ShowTarget": "systems/targeting",
    "gt_TargetClick_Func": "systems/targeting",
    "gt_TargetClick_Init": "systems/targeting",
    "gt_TargetRing_Func": "systems/targeting",
    "gt_TargetRing_Init": "systems/targeting",
    "gt_ZerusSpawn_Func": "systems/spawns",
    "gt_ZerusSpawn_Init": "systems/spawns",
    "gt_TerranSpawn_Func": "systems/spawns",
    "gt_TerranSpawn_Init": "systems/spawns",
    "gt_JungleCatsLeft_Func": "systems/spawns",
    "gt_JungleCatsLeft_Init": "systems/spawns",
    "gt_JungleCatsRight_Func": "systems/spawns",
    "gt_JungleCatsRight_Init": "systems/spawns",
    "gt_JungleCatsLeftInit_Func": "systems/spawns",
    "gt_JungleCatsLeftInit_Init": "systems/spawns",
    "gt_JungleCatsRightInit_Func": "systems/spawns",
    "gt_JungleCatsRightInit_Init": "systems/spawns",
    "gt_SummonCompanion_Func": "systems/companion",
    "gt_SummonCompanion_Init": "systems/companion",
    "gt_EnableCloakingField_Func": "systems/companion",
    "gt_EnableCloakingField_Init": "systems/companion",
    "gt_DisableCloakingField_Func": "systems/companion",
    "gt_DisableCloakingField_Init": "systems/companion",
    "gt_RefreshEnergyBar_Func": "systems/energy_bar",
    "gt_RefreshEnergyBar_Init": "systems/energy_bar",
    "gf_IsHeroPlayer": "systems/xp",
    "gf_DamageKey": "systems/xp",
    "gf_ClearDamageRecord": "systems/xp",
    "gf_AwardExperience": "systems/xp",
    "gt_DamageTrack_Func": "systems/xp",
    "gt_DamageTrack_Init": "systems/xp",
    "gt_HealAward_Func": "systems/xp",
    "gt_HealAward_Init": "systems/xp",
    "gt_DeathAward_Func": "systems/xp",
    "gt_DeathAward_Init": "systems/xp",
    "gt_DamageCleanup_Func": "systems/xp",
    "gt_DamageCleanup_Init": "systems/xp",
    "gf_OrderCreate": "systems/orders",
    "gf_OrderEnter": "systems/orders",
    "gf_OrderExit": "systems/orders",
    "gf_OrderToggle": "systems/orders",
    "gf_OrderExecute": "systems/orders",
    "gf_HeroPlayerFromUnit": "systems/orders",
    "gf_MovementKeyHeld": "systems/combat_tick",
    "gf_HeroWeaponIndex": "systems/combat_cooldown",
    "gt_ToggleCommands_Init": "systems/combat_attack",
    "gt_AutoOnCmd_Func": "systems/combat_attack",
    "gt_AutoOffCmd_Func": "systems/combat_attack",
    "gt_StandCmd_Func": "systems/combat_attack",
    "gt_WalkCmd_Func": "systems/combat_attack",
    "gt_AttackEvent_Init": "systems/combat_attack",
    "gt_AttackCooldown_Func": "systems/combat_cooldown",
    "gt_CooldownSync_Func": "systems/combat_cooldown",
    "gt_CooldownSync_Init": "systems/combat_cooldown",
    "gt_AutoAttackTick_Func": "systems/combat_tick",
    "gt_CombatTick_Init": "systems/combat_tick",
    "gt_OrderKey_Func": "systems/input",
    "gt_OrderKey_Init": "systems/input",
    "gt_OrderCancel_Func": "systems/input",
    "gt_OrderCancel_Init": "systems/input",
    "gt_OrderButton_Func": "systems/input",
    "gt_OrderButton_Init": "systems/input",
    "gf_BossBarSetup": "ui/boss_bar",
    "gf_BossBarEnsure": "ui/boss_bar",
    "gf_BossBarUpdate": "ui/boss_bar",
    "gf_MedicSpawn": "systems/medic",
    "gt_MedicSpawn_Func": "systems/medic",
    "gt_MedicSpawn_Init": "systems/medic",
}

MODULES = sorted(set(MODULE.values()))

INIT_CALLS = [
    "gt_MapInit_Init",
    "gt_SetAlliances_Init",
    "gt_AbilitiesandStatsTriggerDevelopment_Init",
    "gt_AbilitiesandStatsCreateTrigger_Init",
    "gt_SBDialogStatsCallback_Init",
    "gt_UserSelectionDialogCallback_Init",
    "gt_SBDialogAbilitiesCallback_Init",
    "gt_AbilitiesSelectionDialogCallback_Init",
    "gt_GUIEnvironmentSetup_Init",
    "gt_UnitSelection_Init",
    "gt_NewUnitSelection_Init",
    "gt_KeepHeroSelected_Init",
    "gt_ShowStatusBar_Init",
    "gt_HideStatusBar_Init",
    "gf_OrderCreate",
    "gf_BossBarSetup",
    "gt_OrderKey_Init",
    "gt_OrderButton_Init",
    "gt_OrderCancel_Init",
    "gt_CombatTick_Init",
    "gt_CooldownSync_Init",
    "gt_MedicSpawn_Init",
    "gt_TargetRing_Init",
    "gt_TargetClick_Init",
    "gt_CameraFollowDistance_Init",
    "gt_RefreshEnergyBar_Init",
    "gt_PlayerBars_Init",
    "gt_Jump_Init",
    "gt_DisableClickMove_Init",
    "gt_ForwardStart_Init",
    "gt_ForwardEnd_Init",
    "gt_BackwardStart_Init",
    "gt_BackwardEnd_Init",
    "gt_LeftStart_Init",
    "gt_LeftEnd_Init",
    "gt_RightStart_Init",
    "gt_RightEnd_Init",
    "gt_ZoomEnd_Init",
    "gt_ZoomStart_Init",
    "gt_CursorStart_Init",
    "gt_CursorEnd_Init",
    "gt_Target_Init",
    "gt_ZerusSpawn_Init",
    "gt_TerranSpawn_Init",
    "gt_XCenterUnitOrders_Init",
    "gt_XTopUnitOrders_Init",
    "gt_XBottomUnitOrders_Init",
    "gt_JungleCatsLeft_Init",
    "gt_JungleCatsRight_Init",
    "gt_JungleCatsLeftInit_Init",
    "gt_JungleCatsRightInit_Init",
    "gt_SummonCompanion_Init",
    "gt_EnableCloakingField_Init",
    "gt_DisableCloakingField_Init",
    "gt_DamageTrack_Init",
    "gt_HealAward_Init",
    "gt_DeathAward_Init",
    "gt_DamageCleanup_Init",
]


def split_file(path: Path) -> dict[str, list[str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    result: dict[str, list[str]] = {
        "constants": [],
        "types": [],
        "globals": [],
        "prototypes": [],
        "functions": [],
    }
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            index += 1
            continue
        if stripped.startswith("include "):
            index += 1
            continue
        func = FUNC_RE.match(line)
        if func is not None:
            name = func.group(2)
            block = [line]
            index += 1
            while index < len(lines):
                block.append(lines[index])
                if lines[index].rstrip() == "}":
                    index += 1
                    break
                index += 1
            result["functions"].append((name, block))
            continue
        if stripped.startswith("struct "):
            block = [line]
            index += 1
            while index < len(lines):
                block.append(lines[index])
                if lines[index].rstrip() == "};":
                    index += 1
                    break
                index += 1
            result["types"].append(block)
            continue
        if PROTO_RE.match(line):
            result["prototypes"].append(line)
            index += 1
            continue
        if stripped.startswith("const "):
            if "c_SCOBA_BUILD_STAMP" in line:
                index += 1
                continue
            result["constants"].append(line)
            index += 1
            continue
        if GLOBAL_RE.match(line):
            result["globals"].append(line)
            index += 1
            continue
        index += 1
    return result


class Part(TypedDict):
    constants: list[str]
    types: list[str]
    globals: list[str]
    prototypes: list[str]
    modules: dict[str, dict[str, list[str]]]
    init_globals: NotRequired[list[str]]
    init_libs: NotRequired[list[str]]


def collect() -> Part:
    missing = [str(path) for path in (MAPSCRIPT, COMBAT) if not path.is_file()]
    if missing:
        raise SystemExit("source monoliths already removed: " + ", ".join(missing))
    data = {"constants": [], "types": [], "globals": [], "prototypes": [], "modules": {}}
    for path in (MAPSCRIPT, COMBAT):
        part = split_file(path)
        for key in ("constants", "globals", "prototypes"):
            data[key].extend(part[key])
        data["types"].extend(part["types"])
        for name, block in part["functions"]:
            if name == "InitGlobals":
                data["init_globals"] = block
                continue
            if name == "InitLibs":
                data["init_libs"] = block
                continue
            if name in SKIP_FUNCS:
                continue
            target = MODULE.get(name)
            if target is None:
                raise SystemExit(f"unmapped function: {name}")
            bucket = data["modules"].setdefault(target, {})
            if name in bucket:
                raise SystemExit(f"duplicate function: {name}")
            bucket[name] = block
    return data


def write_module(name: str, functions: dict[str, list[str]]) -> None:
    path = OUT / f"{name}.galaxy"
    path.parent.mkdir(parents=True, exist_ok=True)
    parts = [f"// Module: {name}"]
    for block in functions.values():
        parts.append("")
        parts.extend(block)
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def write_core(data: Part) -> None:
    core = OUT / "core"
    core.mkdir(parents=True, exist_ok=True)
    types_text = ["// Module: core/types"]
    for block in data["types"]:
        types_text.append("")
        types_text.extend(block)
    (core / "types.galaxy").write_text("\n".join(types_text) + "\n", encoding="utf-8")

    constants_text = ["// Module: core/constants", ""]
    constants_text.extend(data["constants"])
    (core / "constants.galaxy").write_text("\n".join(constants_text) + "\n", encoding="utf-8")

    globals_text = ["// Module: core/globals", ""]
    globals_text.extend(data["globals"])
    (core / "globals.galaxy").write_text("\n".join(globals_text) + "\n", encoding="utf-8")

    header_text = ["// Module: header", ""]
    seen: set[str] = set()
    for line in data["prototypes"]:
        name = line.split("(")[0].split()[-1]
        if name in seen:
            continue
        seen.add(name)
        header_text.append(line)
    for functions in data["modules"].values():
        for block in functions.values():
            line = block[0].rsplit("{", 1)[0].rstrip() + ";"
            name = line.split("(")[0].split()[-1]
            if name in seen:
                continue
            seen.add(name)
            header_text.append(line)
    (OUT / "header.galaxy").write_text("\n".join(header_text) + "\n", encoding="utf-8")


def write_main() -> None:
    lines = ["// Module: main", ""]
    lines.append('include "scripts/app/core/types"')
    lines.append('include "scripts/app/core/constants"')
    lines.append('include "scripts/app/core/globals"')
    lines.append('include "scripts/app/core/build_stamp"')
    lines.append('include "scripts/app/header"')
    lines.append('include "scripts/app/core/config"')
    seen = {"app/init"}
    lines.append('include "scripts/app/app/init"')
    for module in MODULES:
        if module in seen:
            continue
        seen.add(module)
        lines.append(f'include "scripts/app/{module}"')
    lines.append("")
    lines.append("void main () {")
    lines.append("    InitGlobals();")
    for call in INIT_CALLS:
        lines.append(f"    {call}();")
    lines.append("}")
    (OUT / "main.galaxy").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_init(data: Part) -> None:
    app = OUT / "app"
    app.mkdir(parents=True, exist_ok=True)
    funcs = data["modules"].get("app/init", {})
    parts = ["// Module: app/init", ""]
    parts.extend(data["init_libs"])
    for name, block in funcs.items():
        parts.append("")
        parts.extend(block)
    (app / "init.galaxy").write_text("\n".join(parts) + "\n", encoding="utf-8")

    config = OUT / "core" / "config.galaxy"
    config.write_text(
        "// Module: core/config\n\n" + "\n".join(data["init_globals"]) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    data = collect()
    for module in MODULES:
        write_module(module, data["modules"][module])
    write_core(data)
    write_init(data)
    write_main()
    print(f"wrote {len(MODULES)} modules")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())