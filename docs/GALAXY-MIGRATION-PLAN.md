# Galaxy Migration Plan

## Purpose

Replace the GUI trigger graph and the generated MapScript monolith with handwritten Galaxy modules. No file is exempt from the 512-line code limit. No length overrides. No class-based skip.

## Constraints

- Every `.galaxy` file stays under 512 lines.
- No file length overrides and no exemptions.
- The build pipeline is the source of truth for `MapScript.galaxy`.
- Old files stay in place until the new build is verified.
- All changes are additive first, then swapped, then old files are deleted.
- Rebuilds are deterministic.
- In-game behavior must match the recorded baseline.

## Current state

`MapScript.galaxy` is 3352 lines and mixes several concerns:

- constants, structs, global variables: lines 1-260
- global function declarations: lines 261-361
- UI construction and talent trees: lines 362-1508
- map init and generated trigger handlers: lines 1509-3277
- generated trigger registration: lines 3283-3352

`scripts/combat.galaxy` is 972 lines and mixes several concerns:

- XP and damage tracking: lines 30-296
- order mode: lines 298-407
- auto-attack and movement commands: lines 409-535
- cooldown and combat tick: lines 537-694
- boss bar UI: lines 695-762
- targeting: lines 763-940
- medic spawn: lines 941-972

`Triggers` is 38489 lines with 47 root trigger items.

## Target layout

```text
src/SCOBA.SC2Map/scripts/app/
  main.galaxy
  header.galaxy

  core/
    types.galaxy
    constants.galaxy
    globals.galaxy
    config.galaxy
    engine_unit.galaxy
    engine_dialog.galaxy
    engine_bank.galaxy

  app/
    init.galaxy
    alliances.galaxy

  ui/
    hud_buttons.galaxy
    player_bars.galaxy
    boss_bar.galaxy
    unit_selection_dialog.galaxy
    stats_dialog.galaxy
    ability_talent_trees.galaxy
    abilities_dialog.galaxy
    dialog_helpers.galaxy

  systems/
    selection.galaxy
    status_bar.galaxy
    camera.galaxy
    movement.galaxy
    input.galaxy
    orders.galaxy
    targeting.galaxy
    combat_attack.galaxy
    combat_cooldown.galaxy
    combat_tick.galaxy
    xp.galaxy
    spawns.galaxy
    companion.galaxy
    medic.galaxy
    energy_bar.galaxy
    gui_environment.galaxy
```

Dependency direction:

```text
core -> systems -> ui -> app -> main
```

## Design patterns

- Modular monolith with one responsibility per file.
- Layered design: core, systems, ui, app.
- Composition root in `main.galaxy`.
- Facade modules around unit, dialog, and bank calls.
- Data tables for abilities, talent trees, spawn waves, and dialog layout.
- Strategy functions through typed function references.
- Observer registration: each system registers its own triggers.
- Module-owned state through `static` variables and public accessors.
- Builder functions for dialogs, buttons, and labels.
- Forward declarations in `header.galaxy` to break include cycles.

## Symbol mapping

### core

- `gs_UnitButtonRecord`, `gs_AbilitiesButtonRecord`: `core/types.galaxy`
- `gv_c*`, `gv_singleButtonConstant*`, `gv_abilities*Constant*`: `core/constants.galaxy`
- `gv_tPSUNIT`, `gv_tARGET`, `gv_xP`, `gv_lEVEL`, `gv_sTATLEVEL`, `gv_sPAWN*`, dialog handles: `core/globals.galaxy`
- `InitGlobals`: `core/config.galaxy`
- `InitLibs`: `app/init.galaxy`

### ui

- `gf_PlayerBarsCreate`, `gf_PlayerBarsUpdate`, `gt_PlayerBars_Func`, `gt_PlayerBars_Init`: `ui/player_bars.galaxy`
- `gf_BossBarSetup`, `gf_BossBarEnsure`, `gf_BossBarUpdate`: `ui/boss_bar.galaxy`
- `gf_SBDialogCreateStatsButton`, `gf_SBDialogCreateAbilitiesButton`, `gf_SBDialogCreateInventoryButton`: `ui/hud_buttons.galaxy`
- `gf_UnitSelectionDialog*`, `gf_InitializeUnitButtons`, `gf_AddUnitButton`: `ui/unit_selection_dialog.galaxy`
- `gf_InitializeLevelingInterface`, `gf_ShowStasLevelingInterface`, `gf_Get*Formula`, `gf_SBDialogShowStatsButton`: `ui/stats_dialog.galaxy`
- `gf_UnlockSupportTalentTree`, `gf_UnlockDefenseTalentTree`, `gf_UnlockOffenseTalentTree`, `gf_UnlockSpecialistTalentTree`: `ui/ability_talent_trees.galaxy`
- `gf_AbilitiesSelectionDialog*`, `gf_InitializeAbilitiesButtons`, `gf_AddAbilitiesButton`, `gf_GetTalentTreeType`, `gf_GetNextRow`, `gf_CanLevelAbility`, `gf_ShowAbilityLevelingInterface`, `gf_SBDialogShowAbilitiesButton`: `ui/abilities_dialog.galaxy`
- `gf_Createalinefordialog`: `ui/dialog_helpers.galaxy`

### systems

- `gt_UnitSelection*`, `gt_NewUnitSelection*`, `gt_KeepHeroSelected*`: `systems/selection.galaxy`
- `gt_ShowStatusBar*`, `gt_HideStatusBar*`: `systems/status_bar.galaxy`
- `gt_CameraFollowDistance*`, `gt_Jump*`, `gt_Zoom*`, `gt_Cursor*`, `gt_X*UnitOrders*`: `systems/camera.galaxy`
- `gt_Forward*`, `gt_Backward*`, `gt_Left*`, `gt_Right*`, `gt_DisableClickMove*`: `systems/movement.galaxy`
- `gt_OrderKey*`, `gt_OrderButton*`, `gt_OrderCancel*`: `systems/input.galaxy`
- `gf_OrderCreate`, `gf_OrderEnter`, `gf_OrderExit`, `gf_OrderToggle`, `gf_OrderExecute`, `gf_HeroPlayerFromUnit`: `systems/orders.galaxy`
- `gt_Target*`, `gt_ClearTarget*`, `gf_ShowTarget`, `gt_TargetRing*`, `gt_TargetClick*`: `systems/targeting.galaxy`
- `gt_ToggleCommands_Init`, `gt_AutoOnCmd*`, `gt_AutoOffCmd*`, `gt_StandCmd*`, `gt_WalkCmd*`, `gt_AttackEvent*`: `systems/combat_attack.galaxy`
- `gf_HeroWeaponIndex`, `gt_AttackCooldown*`, `gt_CooldownSync*`: `systems/combat_cooldown.galaxy`
- `gf_MovementKeyHeld`, `gt_AutoAttackTick*`, `gt_CombatTick*`: `systems/combat_tick.galaxy`
- XP and damage functions: `systems/xp.galaxy`
- `gt_ZerusSpawn*`, `gt_TerranSpawn*`, `gt_JungleCats*`: `systems/spawns.galaxy`
- `gt_SummonCompanion*`, `gt_EnableCloakingField*`, `gt_DisableCloakingField*`: `systems/companion.galaxy`
- `gv_sCOBAMedic`, `gt_MedicSpawn*`: `systems/medic.galaxy`
- `gt_GUIEnvironmentSetup*`: `systems/gui_environment.galaxy`
- `gt_RefreshEnergyBar*`: `systems/energy_bar.galaxy`
- `gt_MapInit*`: `app/init.galaxy`
- `gt_SetAlliances*`: `app/alliances.galaxy`

## Work packages

### WP0: inventory

- Produce the symbol mapping above.
- Record baseline logs and bank probes.
- Record the trigger init order from `InitTriggers`.

### WP1: create new files

- Create every module file under `scripts/app/`.
- Port function bodies from the monoliths.
- Keep each file under 512 lines.
- Add prototypes to `header.galaxy`.
- Replace the four duplicated talent tree functions with one data table and one apply function.
- Keep old files untouched.

### WP2: bootstrap generator

- Add `scripts/bootstrap_galaxy.py`.
- It writes a minimal `MapScript.galaxy` for the built map.
- It includes `scripts/app/main`.
- It calls `InitLibs`, then `main`.
- It does not edit the source tree.

Bootstrap content:

```c
include "TriggerLibs/NativeLib"
include "TriggerLibs/SwarmCampaignLib"
include "scripts/app/main"

void InitLibs () {
    libNtve_InitLib();
    libSwaC_InitLib();
}

void InitGlobals () { }
void InitTriggers () { main(); }
void InitMap () {
    InitLibs();
    InitGlobals();
    InitTriggers();
}
```

### WP3: additive wiring

- Call the generator from `scripts/expand_map.py`.
- Leave old `MapScript.galaxy`, `scripts/main.galaxy`, `scripts/combat.galaxy`, and `Triggers` in place.
- Build and confirm the output uses the new bootstrap.

### WP4: additive verification

- Build twice and compare hashes.
- Run `scripts/run-map-test.py`.
- Run `scripts/sc2-check-logs`.
- Compare behavior against the baseline.
- Confirm old files are not referenced by the new build.

### WP5: swap

- Point the bootstrap at the new entry point.
- Keep old files on disk.
- Rebuild and verify again.
- Only then remove old files.

### WP6: remove triggers and old code

- Add `scripts/strip_gui_triggers.py`.
- Prune all trigger items and orphan graph elements.
- Leave one empty category.
- Replace the source `MapScript.galaxy` with the bootstrap.
- Delete `scripts/main.galaxy` and `scripts/combat.galaxy`.
- Rebuild and verify.

### WP7: enforcement

- Add `.galaxy` to `WORKSPACE-CI/config/file_length_limits.yaml`.
- Update default lists in `lib/checks_files.sh` and `lib/check_module_size.sh`.
- Make `lib/checks_compliance.sh` read configured extensions.
- Add `ci/check_galaxy.py`.
- Add `config/galaxy.yaml` and schema.
- Register `check-galaxy` for the `galaxy` language.
- Add `galaxy` to the scaffold language list.
- Regenerate the profile template and hook docs.
- Run all checks.

## Verification gates

1. New modules compile in the built map.
2. Old build path still works.
3. New bootstrap build works.
4. Bank probes and logs match the baseline.
5. `Triggers` is empty.
6. Source `MapScript.galaxy` is the small bootstrap.
7. No `.galaxy` file exceeds 512 lines.
8. No overrides or exemptions exist.
9. Two builds produce identical hashes.

## Rollback

- Revert the generator call in `scripts/expand_map.py`.
- Revert the bootstrap include path.
- Restore the old build from `original/SCOBA.SC2Map` or git.
- The old monoliths are recoverable from git history.

## Acceptance

- One entry point: `main()`.
- One module per responsibility.
- No GUI trigger graph.
- No generated monolith.
- No file length overrides.
- Deterministic rebuild.
- Map test passes.
## Status

- Source monoliths are replaced by the bootstrap and `scripts/app/`.
- The GUI trigger graph is one empty category.
- `scripts/app/` holds 35 Galaxy files; the largest is under 512 lines.
- `scripts/build.sh` is idempotent.
- `scripts/launch-and-check.sh` reports a runtime stamp and no recent script errors.
- The map test compiles, writes its bank, and passes its behavior checks. It logs one movement probe for review.

## Remaining operator steps

- Add `".galaxy"` to `config/file_length_limits.yaml` in both repositories.
- Deploy the updated `WORKSPACE-CI` code to `/opt/workspace-ci`.
- Add `check-galaxy` to `config/required_hooks.yaml` and regenerate the pre-commit file.
