# SCOBA Command Card Audit

Status: active  
Scope: all uncommitted changes in the working tree affecting the SCOBA map, its build pipeline, and supporting tools.  
Baseline: `HEAD` = `52e43bd feat: order mode HUD, medic companion, and fixed window sizing`.  
Method: `git status`, `git diff --ignore-space-at-eol`, direct source inspection, SC2 `ScriptError.txt` / `Alerts.txt` logs.

## Severity legend

- **S1**: breaks gameplay or corrupts repository state.
- **S2**: architectural defect that causes recurring regressions.
- **S3**: maintainability, tooling, or documentation issue.
- **S4**: cosmetic.

## Findings

### A01 - Line endings converted and mixed

Severity: **S1**  
Files:
- `src/SCOBA.SC2Map/MapScript.galaxy`
- `src/SCOBA.SC2Map/Base.SC2Data/GameData/UnitData.xml`
- `src/SCOBA.SC2Map/Base.SC2Data/GameData/BehaviorData.xml`
- `src/SCOBA.SC2Map/Base.SC2Data/GameData/AbilData.xml`
- `src/SCOBA.SC2Map/Base.SC2Data/GameData/ButtonData.xml`

Evidence:
- `HEAD` versions are CRLF.
- Working versions are LF or mixed CRLF/LF.

Impact:
- Real change set is hidden inside ~9,500 changed lines.
- Diffs are unreviewable.
- Editors and tooling can corrupt files further.

Status: open.

### A02 - Existing end-of-MapInit deselect loop deleted

Severity: **S1**  
File: `src/SCOBA.SC2Map/MapScript.galaxy`

Evidence:
- `HEAD` has:
  ```galaxy
  for (lv_localPlayer = 1; lv_localPlayer <= 6; lv_localPlayer += 1) {
      UnitClearSelection(lv_localPlayer);
  }
  ```
- Working tree replaced it with toggle init calls.

Impact:
- Initial selection behavior changed.
- Possible interference with new selection polling.

Status: open.

### A03 - `UnitClearSelection` removed from `gf_ShowTarget`

Severity: **S2**  
File: `src/SCOBA.SC2Map/scripts/combat.galaxy`

Evidence:
- Diff removes `UnitClearSelection(lp_player);` inside `gf_ShowTarget`.

Impact:
- Target hover/selection behavior changed.
- Stale selections can persist.

Status: open.

### A04 - `gt_DisableClickMove` disabled but left dead

Severity: **S3**  
File: `src/SCOBA.SC2Map/MapScript.galaxy`

Evidence:
- `gt_DisableClickMove_Init()` call removed.
- Trigger variable, function, and init function still present.

Impact:
- Dead code.
- Click-move behavior changed without documented replacement.

Status: open.

### A05 - 0.1s polling hero reselection

Severity: **S2**  
File: `src/SCOBA.SC2Map/MapScript.galaxy`

Evidence:
- New `gt_KeepHeroSelected` trigger.
- `TriggerAddEventTimePeriodic(..., 0.1, c_timeGame)`.
- Reselects heroes every 0.1s, skipping only order mode.

Impact:
- Fights manual selection.
- Fights target ring and order UI.
- Constant trigger churn.

Status: open.

### A06 - Custom `CAbilBehavior` toggles with hidden buffs as state flags

Severity: **S2**  
Files:
- `Base.SC2Data/GameData/AbilData.xml`
- `Base.SC2Data/GameData/BehaviorData.xml`

Evidence:
- `SCOBAAutoAttackToggle` and `SCOBARightClickToggle` are toggles.
- Behaviors `SCOBAAutoAttackBehavior` and `SCOBARightClickStandBehavior` carry no gameplay modification; they exist only as flags.

Impact:
- State is encoded in behavior presence, duplicated in Galaxy flags.
- Custom data must stay valid for basic UI to work.

Status: open.

### A07 - Two sources of truth for toggle state

Severity: **S2**  
Files:
- `scripts/combat.galaxy`
- `MapScript.galaxy`

Evidence:
- Tick uses `gv_sCOBAAutoAttack` and `gv_sCOBARmbStand`.
- `gt_TargetClick` uses `UnitHasBehavior(..., "SCOBARightClickStandBehavior")`.
- Behavior engine uses buff presence.

Impact:
- State can disagree.
- Bugs depend on which subsystem is queried.

Status: open.

### A08 - Toggle triggers registered with `c_unitAbilStageAll`

Severity: **S1**  
File: `scripts/combat.galaxy`

Evidence:
- All four toggle trigger registrations use `c_unitAbilStageAll`.

Impact:
- Handlers fire for multiple ability stages.
- Flags flap.
- Current auto-attack and chase breakage.

Status: open.

### A09 - Toggle triggers moved into `gt_MapInit_Func`

Severity: **S2**  
File: `MapScript.galaxy`

Evidence:
- Four toggle init calls added before MapInit `return`.
- Prototypes added to compile.

Impact:
- Fixes null `gv_tPSUNIT` binding but couples trigger creation to map init.
- Duplicate creation risk if MapInit reruns.

Status: open.

### A10 - MapInit executes a toggle ability as an order to seed state

Severity: **S2**  
File: `MapScript.galaxy`

Evidence:
- `UnitIssueOrder(..., Order(AbilityCommand("SCOBARightClickToggle", 0)), ...)` in hero setup.

Impact:
- Uses command execution as initialization.
- Depends on ability stage behavior and current binding timing.

Status: open.

### A11 - Auto OFF disables the `attack` ability

Severity: **S2**  
File: `scripts/combat.galaxy`

Evidence:
- Auto ON handler enables `attack`.
- Auto OFF handler disables `attack`.
- MapInit disables `attack` by default.

Impact:
- Auto-attack depends entirely on toggle command events firing correctly.
- Manual attack disabled while Auto is OFF.
- If On event misfires, hero cannot attack at all.

Status: open.

### A12 - Hero `DefaultAcquireLevel` changed to `Defensive`

Severity: **S2**  
File: `UnitData.xml`

Evidence:
- Kerrigan and Tosh changed from `None` to `Defensive`.

Impact:
- Engine now auto-acquires independently of the custom auto-attack toggle.
- Previously caused attacking while Auto was OFF.

Status: open.

### A13 - Duplicate toggle abilities on Kerrigan

Severity: **S2**  
File: `UnitData.xml`

Evidence:
- Kerrigan has `SCOBAAutoAttackStatus`, `SCOBAAutoAttackToggle`, `SCOBARightClickToggle` in two separate `AbilArray` groups.

Impact:
- Duplicate abilities.
- Undefined card/ability behavior.
- Possible duplicate command events.

Status: open.

### A14 - Two layout buttons per slot

Severity: **S3**  
File: `UnitData.xml`

Evidence:
- Index 51/52 share Row 0 Column 3.
- Index 53/54 share Row 0 Column 4.

Impact:
- Relies on engine On/Off rendering.
- Any invalid behavior state can hide or duplicate buttons.

Status: open.

### A15 - Button faces inverted relative to command semantics

Severity: **S3**  
File: `AbilData.xml`

Evidence:
- On command uses `AutoAttackOff` icon.
- Off command uses `AutoAttackOn` icon.
- On command uses `RightClickMove` icon.
- Off command uses `RightClickStand` icon.

Impact:
- Intentional state display, but confusing data.
- Depends on engine toggle rendering.

Status: open.

### A16 - Combat state polled every 0.5s

Severity: **S2**  
File: `scripts/combat.galaxy`

Evidence:
- `gt_AutoAttackTick` uses `TriggerAddEventTimePeriodic(..., 0.5, c_timeGame)`.

Impact:
- Delayed acquisition.
- Chase can overshoot between ticks.
- Stand/attack transitions lag.

Status: open.

### A17 - Cooldown polled every 0.1s

Severity: **S2**  
File: `scripts/combat.galaxy`

Evidence:
- `gt_CooldownTick` uses 0.1s period.
- Uses `UnitWeaponPeriodRemaining(hero, 0)` and `UnitAbilityAddCooldown`.

Impact:
- Fake ability cooldown used as UI.
- Weapon index and cooldown link unverified.
- Cooldown can desync or disappear.

Status: open.

### A18 - Stand issues hold only when `UnitOrderCount == 0`

Severity: **S2**  
File: `scripts/combat.galaxy`

Evidence:
- Stand branch issues `Order(AbilityCommand("move", 2))` only if no orders.
- User movement overrides hold.

Impact:
- Stand attack behavior depends on timing and order bookkeeping.

Status: open.

### A19 - Walk issues attack orders without protecting user orders

Severity: **S2**  
File: `scripts/combat.galaxy`

Evidence:
- Walk branch issues `OrderTargetingUnit(attack, target)`.
- `gv_sCOBAAutoTarget` is reused.

Impact:
- Can override user intent.
- Manual attack and auto target share state.

Status: open.

### A20 - Manual attack path duplicates tick logic

Severity: **S2**  
File: `scripts/combat.galaxy`

Evidence:
- `gt_TargetClick` directly issues attack and sets `gv_sCOBAAutoTarget`.

Impact:
- Two attack controllers.
- Hard to reason about priority.

Status: open.

### A21 - Shared auto-target state across modes

Severity: **S2**  
File: `scripts/combat.galaxy`

Evidence:
- `gv_sCOBAAutoTarget` used by manual click, stand, and walk logic.

Impact:
- Mode switching can carry stale target state.

Status: open.

### A22 - Hardcoded radii and hero range

Severity: **S3**  
File: `scripts/combat.galaxy`

Evidence:
- `c_SCOBA_CHASE_RADIUS = 10.0`
- `c_SCOBA_KEEP_RADIUS = 12.0`
- Hero loops `1..6`

Impact:
- Tuning requires code changes.
- Not data-driven.

Status: open.

### A23 - Zergling spawns hardcoded inside hero setup

Severity: **S3**  
File: `MapScript.galaxy`

Evidence:
- Spawns only for players `1..3`.
- Owner hardcoded as `lv_localPlayer + 3`.
- Positions hardcoded as polar offsets `8.0 / 45 / 225`.

Impact:
- Test spawns mixed into production init.
- Not configurable.
- Easily forgotten.

Status: open.

### A24 - Build anchor made fragile

Severity: **S3**  
File: `scripts/expand_map.py`

Evidence:
- Anchor changed to `text.rindex("    }\n", 0, text.index("void gt_MapInit_Init ()"))`.

Impact:
- Inserts code after an arbitrary last `    }`.
- Breaks if MapInit structure changes.

Status: open.

### A25 - Untracked 840KB binary

Severity: **S3**  
File: `tools/stormex`

Evidence:
- Untracked executable, 839,200 bytes.

Impact:
- Unclear provenance/build.
- Repository bloat.

Status: open.

### A26 - Untracked resource tools

Severity: **S3**  
Files:
- `scripts/sc2res`
- `scripts/sc2res.py`

Impact:
- Not committed.
- Environment-dependent Python path.
- Undocumented failure modes.

Status: open.

### A27 - Untracked log checker

Severity: **S3**  
Files:
- `scripts/sc2-check-logs`
- `scripts/sc2-check-logs.py`

Impact:
- Hardcoded user path.
- Only detects script compile/load errors.
- Not wired into persistent `scripts/launch-scoba.sh`.

Status: open.

### A28 - Dependency changes undocumented in code

Severity: **S3**  
Files:
- `pyproject.toml`
- `uv.lock`

Evidence:
- Added `pillow>=13.0.0`.

Impact:
- Lockfile churn.
- No documentation of why Pillow is required.

Status: open.

### A29 - Documentation drift

Severity: **S3**  
File: `AGENTS.md`

Evidence:
- Documents resource tools and output root.
- Does not document command-card subsystem, toggles, or known breakage.

Status: open.

### A30 - Two reload/launch paths

Severity: **S3**  
Files:
- `scripts/launch-scoba.sh`
- `/tmp/opencode/launch_sc2.sh`

Impact:
- Error checking exists only in the temporary helper.
- Behavior differs between manual launch and agent launch.

Status: open.

### A31 - Indentation and formatting regressions in XML

Severity: **S4**  
Files:
- `BehaviorData.xml` closing `</Catalog>` is indented.
- `ButtonData.xml` `SCOBAAutoAttackStatus` is not aligned.

Impact:
- No functional effect, but noise in a codebase already hard to diff.

Status: open.

### A32 - No automated gameplay verification

Severity: **S2**

Evidence:
- Verification depended on manual screenshots.
- Log checker only checks script errors.

Impact:
- Regressions reach gameplay.
- No repeatable acceptance test.

Status: open.

## Current runtime failures

- Auto-attack does not work after `c_unitAbilStageAll` change.
- Chase Walk does not clear Stand.
- Cooldown indicator is unreliable.
- Toggle state depends on ability-stage events with duplicated flags.

## Root cause

No single source of truth. The same feature is controlled by:

1. Behavior presence.
2. Two boolean arrays.
3. Ability command triggers.
4. A 0.5s combat poll.
5. A 0.1s cooldown poll.
6. Manual click logic.

## Verification gaps

- No assertion of behavior presence.
- No assertion of order state after toggle.
- No assertion that cooldown matches weapon cooldown.
- No automated check that default state matches button state.

## Evidence commands

```bash
git status --short
git diff --stat
git diff --ignore-space-at-eol --stat
git diff --ignore-space-at-eol -- src/SCOBA.SC2Map/MapScript.galaxy
git diff --ignore-space-at-eol -- src/SCOBA.SC2Map/scripts/combat.galaxy
git diff --ignore-space-at-eol -- src/SCOBA.SC2Map/Base.SC2Data/GameData
file src/SCOBA.SC2Map/MapScript.galaxy src/SCOBA.SC2Map/Base.SC2Data/GameData/UnitData.xml
```