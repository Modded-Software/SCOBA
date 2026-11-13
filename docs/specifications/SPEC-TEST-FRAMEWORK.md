# SPEC-TEST-FRAMEWORK: Reusable Test Framework

**Date:** 2026-11-10
**Status:** Active implementation specification
**Requirements:** [REQ-TEST-FRAMEWORK](../requirements/REQ-TEST-FRAMEWORK.md)

## 1. Purpose

This document specifies a reusable test framework for instrumented StarCraft
II maps. It separates shared test machinery from profile-specific test cases.

It defines:

- the module layout;
- the map specification model;
- the instrumented map build flow;
- the Galaxy harness split;
- the bank schema;
- the runner lifecycle;
- the input and frame hooks;
- the in-game character frame probe;
- the check module;
- the combat, aim, pitch, controls, and motion profiles;
- animation layer and generated asset checks;
- the command line;
- the run artifact layout;
- the framework unit tests;
- the migration steps.

## 2. Design Overview

The framework has four layers.

1. **Shared Python testkit**
   - build maps;
   - launch games;
   - read banks;
   - scan logs;
   - drive input;
   - capture frames;
   - run checks;
   - write summaries.

2. **Shared Galaxy harness**
   - bank helpers;
   - player reset;
   - enemy cleanup;
   - unit spawn;
   - snapshots;
   - finish marker.

3. **Profile modules**
   - map specification;
   - Galaxy test cases;
   - input hook;
   - checks.

4. **Thin command entrypoints**
   - combat build and run;
   - aim build and run;
   - generic profile CLI.

Profiles do not copy launch, wait, bank, log, or check logic.

## 3. Module Layout

```text
scripts/
  testkit/
    __init__.py
    map_builder.py
    bank.py
    runner.py
    input_driver.py
    frames.py
    framelog.py
    watch_framelog.py
    checks.py
    logs.py
    summary.py
    galaxy/
      common.galaxy
      combat.galaxy
      aim.galaxy
    profiles/
      __init__.py
      registry.py
      combat.py
      aim.py
      controls.py
      motion.py
    tests/
      __init__.py
      test_animation_tokens.py
      test_character_anim.py
      test_bank.py
      test_checks.py
      test_profiles.py
      test_summary.py
  testmap.py
  build-test-map.py
  run-map-test.py
  build-aim-test-map.py
  run-aim-test.py
  build-controls-test-map.py
  run-controls-test.py
  build-motion-test-map.py
  run-motion-test.py
  dump_m3_attachments.py
  dump_m3_clip_metrics.py
  watch-framelog.py
```

`scripts/input_inject.py` remains the low-level input helper.

## 4. Map Specification

`testkit/map_builder.py` defines:

```py

class TestMapSpec:
    profile: str
    source: Path
    output: Path
    bank_names: tuple[str, ...]
    galaxy_files: tuple[Path, ...]
    galaxy_includes: tuple[str, ...]
    init_calls: tuple[str, ...]
    options: Mapping[str, bool] = field(default_factory=dict)
```

Field rules:

- `profile` is a short lowercase name.
- `source` is the normal built map.
- `output` is the profile test map.
- `bank_names` lists banks owned by the profile.
- `galaxy_files` are copied into the test map.
- `galaxy_includes` are added to the map script entry point.
- `init_calls` are added to `main()`.
- `options` holds map data switches.

Ownership rule:

```py
PROFILE_OUTPUTS = {
    "combat": ROOT / "out" / "SCOBA256_test.SC2Map",
    "aim": ROOT / "out" / "SCOBA256_aimtest.SC2Map",
}
```

The builder fails when `output` does not match the profile output.

## 5. Map Build Flow

`build_instrumented_map(spec)` performs these steps.

1. Validate the source directory.
2. Validate the profile output path.
3. Remove only the profile output directory.
4. Copy the source map to the profile output.
5. Apply profile map data options.
6. Patch `MapInfo`.
7. Patch `BankList.xml`.
8. Copy Galaxy harness files into the output map.
9. Add harness includes to `scripts/app/main.galaxy`.
10. Add profile init calls inside `main()`.
11. Print the output path.
12. Return the output path.

### 5.1 MapInfo patch

The builder preserves the current MapInfo patch logic.

- Locate the game options flags field.
- Clear bit `0x02`.
- Recompute the integrity hash.
- Write the file back.

### 5.2 BankList patch

For every profile bank name:

- skip when the bank is already listed;
- insert `<Bank Name="..." Player="1"/>` before `</BankList>`.

### 5.3 Harness include patch

Harness files are copied to:

```text
<test map>/scripts/test/<profile>/<name>.galaxy
```

Includes are inserted after the last existing `include` line in
`scripts/app/main.galaxy`.

Example:

```galaxy
include "scripts/test/combat/common"
include "scripts/test/combat/combat"
```

### 5.4 Init call patch

Init calls are inserted immediately before the closing brace of `main()`.

Example:

```galaxy
    gt_DbgTest_Init();
```

No core gameplay globals are patched.

## 6. Galaxy Harness

### 6.1 Common harness

`testkit/galaxy/common.galaxy` owns shared test state and helpers.

Required globals:

```galaxy
bank gv_testBank;
string gv_testBankName;
point gv_testAnchor;
fixed gv_testSpawnAt;
unit gv_testEnemy;
```

Required functions:

| Function | Purpose |
| --- | --- |
| `gf_TestBankOpen` | Load the profile bank for player 1 |
| `gf_TestBankSave` | Save the profile bank |
| `gf_TestSetMeta` | Write profile, anchor, and done state |
| `gf_TestCaptureAnchor` | Save the hero start point |
| `gf_TestClearEnemies` | Remove enemies near the anchor |
| `gf_TestSpawnEnemy` | Spawn and configure one enemy |
| `gf_TestResetPlayer` | Clear input and combat test state |
| `gf_TestSnapCommon` | Write common snapshot fields |
| `gf_TestFinish` | Write the finish marker and save |

Common snapshot fields:

- `AtMs`
- `HeroX`
- `HeroY`
- `Auto`
- `Stand`
- `Root`
- `MoveSuppressed`
- `AttackOrder`
- `TargetEnemy`
- `Forward`
- `CooldownMs`
- `CmdCooldown`
- `EnemyValid`
- `EnemyHp`
- `Distance`

The common harness does not decide pass or fail.

### 6.2 Combat harness

`testkit/galaxy/combat.galaxy` owns the current combat cases.

It preserves these case sections:

- `startup`
- `auto_off`
- `stand_in`
- `stand_out`
- `stand_outside`
- `stand_auto_off`
- `stand_wake_manual`
- `right_click`
- `right_drag`
- `right_point`
- `right_ground_walk`
- `right_ground_stand`
- `right_target_kept`
- `both_forward`
- `walk_ground`
- `stand_ground`
- `move_wake`
- `walk_chase`
- `walk_idle`
- `weapon`
- `camera_heading`
- `real_input`

It also writes these non-case sections:

- `meta`
- `engine`
- `grid`

### 6.3 Aim harness

`testkit/galaxy/aim.galaxy` owns aim cases.

Required globals:

```galaxy
int gv_aimVisualReady;
int gv_aimVisualActive;
```

Required sections:

| Section | Purpose |
| --- | --- |
| `meta` | Profile and finish state |
| `aim_enter` | Aim entered |
| `aim_idle` | Aim held at rest |
| `aim_enemy` | Enemy under the centered cursor |
| `aim_hold` | Aim pose after one second |
| `aim_walk` | Movement and baseline leg frames |
| `aim_turn` | Facing while aiming and moving |
| `aim_stop` | Movement stopped frame |
| `aim_settle` | Lower idle after movement stops |
| `aim_release` | Aim exited and camera restored |

Required keys per aim section:

- common snapshot keys;
- `AimActive`;
- `AimCursorTarget`;
- `CursorVisible`;
- `AimFov`;
- `AimDistance`;
- `AimVisualReady`;
- `UpperState`;
- `LowerState`;
- `UpperClip`;
- `LowerClip`;
- `UnitFacing`;
- `CameraYaw`.

Aim case flow:

1. Open the aim bank.
2. Capture the anchor.
3. Reset player to stand and set `gv_cameraCollisionOff[1]` so collision cannot write distance during pitch sampling.
4. Call `gf_AimBegin(1)`.
5. Wait until aim is active.
6. Save `aim_enter`.
7. Wait and save `aim_idle`.
8. Wait one second and save `aim_hold`.
9. Spawn an enemy at the aim point.
10. Save `aim_enemy`.
11. Set `aim_walk` visual ready state.
12. Save the bank.
13. Wait for the input hook while aim is active.
14. Save `aim_walk`.
15. Save `aim_turn` after a camera yaw change while moving.
16. Save `aim_stop` after forward release.
17. Save `aim_settle` after the idle settle.
18. Call `gf_AimEnd(1)`.
19. Wait and save `aim_release`.
20. Write the finish marker.

The input hook holds the forward key and captures three frames.
The input hook changes camera yaw before the `aim_turn` snapshot.
The input hook captures the last walk frame and the settled stop frame.
The stop frame must differ from the last walk frame.
The `aim_hold` upper state must still be an aim state after one second.
The aim group lower STC must keep the lower frame IDs advancing.

### 6.4 Pitch harness

`testkit/galaxy/pitch.galaxy` owns the dedicated pitch case.

Required sections:

| Section | Purpose |
| --- | --- |
| `meta` | Profile and finish state |
| `pitch` | Ready marker and camera pitch samples |

Required keys per pitch sample:

- `<tag>Camera`;
- `<tag>Rest`;
- `<tag>Time`.

Pitch case flow:

1. Open the pitch bank.
2. Capture the anchor.
3. Reset player to stand and set `gv_cameraCollisionOff[1]` so collision cannot write distance during pitch sampling.
4. Call `gf_AimBegin(1)`.
5. Save `entry`.
6. Set camera pitch to 80 and save `down`.
7. Set camera pitch to 30 and save `mid`.
8. Set camera pitch to -60 and save `up`.
9. Set camera pitch back to 30 and save `hold`.
10. Call `gf_AimEnd(1)`.
11. Set camera pitch to 70, call `gf_AimBegin(1)`, and save `entry70`.
12. Set camera pitch to 80 and save `down70`.
13. Set camera pitch to -60 and save `up70`.
14. Set camera pitch back to 30 and save `hold70`.
15. Call `gf_AimEnd(1)` and write the finish marker.

Camera pitch is recorded in degrees and normalized to signed range.
Selected keyframes must reach the target within tolerance.

### 6.5 Controls harness

`testkit/galaxy/controls.galaxy` owns control mode cases.

Required sections:

| Section | Purpose |
| --- | --- |
| `meta` | Profile and finish state |
| `controls_default` | RPG mode at start |
| `controls_action` | Action mode after toggle |
| `controls_mouselook` | Mouse look with no held button |
| `controls_turn` | Facing and no upper turn overlay during mouse look |
| `controls_move` | Action mode movement |
| `controls_cursor` | Centered action cursor |
| `controls_alt` | Alt pause and free UI cursor |
| `controls_alt_release` | Mouse look restored |
| `controls_aim` | Right hold aim with no right command |
| `controls_attack` | Left click attack |
| `controls_ground` | Ground left click |
| `controls_alt_click` | Alt UI click |
| `controls_rpg` | Return to RPG mode |
| `controls_zoom` | Zoom distance animates to the target |
| `controls_collision` | Flat-ground collision keeps the desired distance |
| `controls_collision_clamp` | Underground eye shortens camera distance |
| `controls_collision_restore` | Clear view restores the desired distance |
| `controls_rpg_hold` | RPG right hold does not aim |
| `controls_rpg_click_move` | RPG Walk real right-click movement |
| `controls_rpg_click_stop` | RPG Stand real right-click stop |
| `controls_rpg_select` | Real left click sets an enemy target and keeps the hero selected |
| `controls_rpg_target_idle` | Target persists through idle and Stop |
| `controls_rpg_stale` | Outside-radius click is rejected at a ground press point |
| `controls_aim_distance` | Action right hold keeps scroll distance |
| `controls_move_tick` | Aim movement loop order and displacement bounds |
| `controls_action_turn` | Action A/D/S turn toward movement |
| `controls_reset` | Animation state resets after mode change |
| `controls_rpg_stop_idle` | RPG lower idle after stop |

Required keys per controls section:

- common snapshot keys;
- `ActionMode`;
- `AltPaused`;
- `AimActive`;
- `CursorVisible`;
- `CursorCentered`;
- `CameraYaw`;
- `UnitFacing`;
- `TargetType`;
- `CombatState`;
- `Cooldown`;
- `CameraDistance`;
- `HeroX`;
- `HeroY`;
- `MoveTarget`;
- `MoveRetarget`;
- `MoveTick`;
- `UpperState`;
- `LowerState`.

Controls case flow:

1. Open the controls bank.
2. Capture the anchor.
3. Save `controls_default`.
4. Signal the RPG input phase.
5. Save `controls_rpg_hold` after the RPG right hold check.
6. Save `controls_rpg_click_move` after the RPG Walk ground click.
7. Save `controls_rpg_click_stop` after the RPG Stand ground click.
8. Save `controls_rpg_select` after the real left click.
9. Save `controls_rpg_target_idle` after idle and Stop.
10. Save `controls_rpg_stale` after the outside-radius ground press.
11. Save `controls_rpg_stop_idle` after movement stops.
12. Toggle to action mode and save `controls_action`.
13. Move the mouse with no button held and save `controls_mouselook`.
14. Hold forward and change camera yaw, then save `controls_move`.
15. Save `controls_move_tick` with two position samples.
16. Save `controls_cursor`.
17. Hold Alt and save `controls_alt`.
18. Release Alt and save `controls_alt_release`.
19. Hold right and save `controls_aim`.
20. Save `controls_aim_distance` and `controls_reset` while aim is held.
21. Spawn an enemy at the cursor and save `controls_attack`.
22. Click ground and save `controls_ground`.
23. Hold Alt and click the enemy, then save `controls_alt_click`.
24. Toggle to RPG mode and save `controls_rpg`.
25. Write the finish marker.

The input hook drives RPG right hold, real clean clicks, real ground clicks,
action mode mouse movement, forward movement, Alt, right hold, and click
positions.
The RPG input phase must finish before the action mode toggle.
Each RPG click uses the native per-player `UnitClick` unit.
Action-mode clicks use `gf_UnitTargetAtPoint` at the camera target.
The outside-radius case keeps an enemy hover while the press point moves to
a ground point.
The movement tick case samples hero position across two consecutive
`gt_AimMoveTick` intervals.

## 7. Bank Schema

### 7.1 Common meta keys

| Section | Key | Type |
| --- | --- | --- |
| `meta` | `profile` | string |
| `meta` | `done` | int |
| `meta` | `anchorX` | int |
| `meta` | `anchorY` | int |

### 7.2 Combat profile banks

Primary bank:

```text
SCOBATEST
```

Auxiliary input bank:

```text
SCOBADBG
```

### 7.3 Aim profile bank

Primary bank:

```text
SCOBAAIMTEST
```

The aim profile has no auxiliary bank.

### 7.3A Controls profile bank

Primary bank:

```text
SCOBACONTROLSTEST
```

The controls profile has no auxiliary bank.

### 7.4 Read rules

The bank reader supports:

- integer values;
- flag values;
- string values;
- text values.

Unknown key types are skipped with a warning.

## 8. Runner

`testkit/runner.py` defines:

```py

class TestRunSpec:
    profile: str
    map_name: str
    map_source: Path
    map_cache_name: str
    bank_names: tuple[str, ...]
    launch_timeout_s: float
    case_timeout_s: float
    run_root: Path
    on_bank_ready: Callable | None
```

Runner lifecycle:

1. Create the timestamped run directory.
2. Remove only the profile map cache.
3. Kill StarCraft II.
4. Delete only profile banks and the probe bank.
5. Launch the profile map.
6. Poll for the primary bank.
7. Read the bank.
8. Call `on_bank_ready` once when the ready key is set.
9. Continue until `meta.done == 1`.
10. Read the completed bank.
11. Dump the probe bank.
12. Collect new script errors.
13. Collect new error folders.
14. Collect new alerts.
15. Run profile checks.
16. Write `summary.json`.
17. Write `summary.txt`.
18. Stop StarCraft II.
19. Return zero on pass and one on failure.

Ready rule:

- The profile input hook runs after the bank contains its ready key.
- The hook runs once.
- The bank is re-read after the hook returns.

Timeout rule:

- The launch timeout is read from `SC2_LAUNCH_TIMEOUT`.
- The case timeout is read from `SC2_CASE_TIMEOUT`.
- The launch timeout starts when the game process starts.
- The case timeout starts when the profile bank first appears.
- A timeout fails the run.
- A new `ScriptError.txt` fails the run immediately.
- A new error folder fails the run immediately.
- A launcher exit before game start fails the run immediately.

## 9. Log Checks

`testkit/logs.py` owns:

- new `ScriptError.txt` detection;
- new `*Error` folder detection;
- new alert parsing;
- red diagnostic printing;
- failure counting.

A new script error fails the run.

A new error folder fails the run.

An alert with any of these words fails the run:

- `error`
- `damaged`
- `failed`
- `exception`
- `assert`
- `script`

## 10. Input Driver

`testkit/input_driver.py` wraps `scripts/input_inject.py`.

Required functions:

| Function | Purpose |
| --- | --- |
| `window_geometry` | Read StarCraft II window rectangle |
| `focus` | Focus the game window |
| `click` | Left click |
| `rclick` | Right click |
| `rclick_fast` | Right click with no hold gap |
| `ldrag` | Left drag |
| `rdrag` | Right drag |
| `rhold` | Right hold |
| `rrelease` | Right release |
| `key_down` | Press and hold a key |
| `key_up` | Release a key |
| `key` | Hold a key for a duration |

The driver does not decide test order.

## 11. Frames

`testkit/frames.py` defines a per-run frame collector.

```py
class FrameCollector:
    def capture(self, case: str) -> Path: ...
    def crop(self, path: Path, box: tuple[float, float, float, float]) -> Path: ...
    def difference(self, first: Path, second: Path, box) -> int: ...
```

Rules:

- Each capture uses the next sequence number.
- The file name contains the case name and sequence number.
- The collector fails when the output path exists.
- The collector keeps PNG files.
- The collector removes its temporary XWD file after conversion.
- Crops use normalized coordinates.

Aim baseline leg crop:

```py
AIM_LEG_CROP = (0.30, 0.45, 0.70, 0.90)
```

Aim torso crop:

```py
AIM_TORSO_CROP = (0.30, 0.10, 0.70, 0.55)
```

Aim leg frame check:

- capture frame 1 after aim is active;
- hold forward for the first interval;
- capture frame 2;
- hold forward for the second interval;
- capture frame 3;
- compare frame 1 with frame 2;
- compare frame 2 with frame 3;
- pass when either region changes above the profile threshold.



## 11A. Character frame probe

The frame probe is in-game instrumentation. It does not use screenshots.

Module:

```text
scripts/app/systems/anim_probe.galaxy
```

Trigger:

```galaxy
TriggerAddEventTimePeriodic(gt_AnimProbe, 0.01, c_timeGame);
```

The probe samples on the periodic game-time trigger while `gv_bPROBE` is true.

### 11A.1 Probe globals

```galaxy
bool gv_bPROBE;
int gv_probeTick;
int gv_probeSeq;
int gv_probeEventSeq;
int gv_probeRowCount;
bank gv_probeBank;
fixed gv_probeLastFlush;
string[8][2] gv_probeClipName;
int[8][2] gv_probeClipLen;
int[8][2] gv_probeClipFrameMs;
int[8][2] gv_probeClipFrames;
int[8][2] gv_probeClipQuery;
int[8][2] gv_probeClipStartMs;
bank gv_probeMetrics;
```

`gv_probeClipQuery` values:

| Value | Meaning |
| --- | --- |
| 0 | no clip |
| 2 | ok |
| 3 | fail |

### 11A.2 Probe bank

Bank name:

```text
SCOBAFRAMELOG
```

Sections:

| Section | Purpose |
| --- | --- |
| `meta` | Start and stop markers |
| `config` | Hero type, model, clip names, and attachment names |
| `frames` | One row per hero per sample |
| `events` | Aim group, direction, lower clip changes, and upper state events |

Frame keys use this form:

```text
p<player>_<zero-padded sample index>
```

Keys do not contain the timestamp. The reader orders rows by player and sample index.

`meta` keys:

| Key | Type |
| --- | --- |
| `probe` | int |
| `started` | int |
| `stopped` | int |
| `tick` | int |
| `rows` | int |

`config` keys:

| Key | Type |
| --- | --- |
| `hero` | string |
| `model` | string |
| `a0` to `a5` | string |
| `upper` | string |

Frame row text fields:

| Field | Meaning |
| --- | --- |
| `ms` | Game timestamp in milliseconds |
| `seq` | Sample index |
| `tick` | Tick index within the enabled session |
| `type` | Hero unit type |
| `up` | Upper state index |
| `lo` | Lower state index |
| `uc` | Upper clip index |
| `lc` | Lower clip index |
| `uclip` | Upper clip props |
| `lclip` | Lower clip props |
| `uq` | Upper metrics state: `none`, `ok`, or `fail` |
| `lq` | Lower metrics state: `none`, `ok`, or `fail` |
| `ulen` | Upper clip length in milliseconds |
| `urem` | Upper clip remaining milliseconds |
| `uplayed` | Upper played milliseconds |
| `uframe` | Upper exact model frame index |
| `uframes` | Upper model frame count |
| `ufms` | Upper model frame duration in milliseconds |
| `llen` | Lower diagnostic clip length in milliseconds |
| `lrem` | Lower diagnostic remaining milliseconds |
| `lplayed` | Lower diagnostic played milliseconds |
| `lframe` | Lower diagnostic model frame index |
| `lframes` | Lower model frame count |
| `lfms` | Lower model frame duration in milliseconds |
| `x`, `y`, `z` | Hero world position |
| `facing` | Hero facing |
| `speed` | Current movement speed |
| `orders` | Order count |
| `yaw` | Camera yaw |
| `pitch` | Camera pitch |
| `dist` | Camera distance |
| `aim` | Aim active flag |
| `action` | Action mode flag |
| `alt` | Alt pause flag |
| `hold` | Lower hold counter |
| `a0` to `a5` | Attachment world position `x,y,z` |

Event row text fields:

| Field | Meaning |
| --- | --- |
| `ms` | Game timestamp in milliseconds |
| `seq` | Event index |
| `kind` | `upper_start` or `upper_stop` |
| `clip` | Clip props |
| `flags` | Animation flags |
| `up` | Upper state |
| `lo` | Lower state |

### 11A.2A Clip metrics bank

Bank name:

```text
SCOBACLIPMETRICS
```

The runner and `scripts/launch-scoba.sh` write this bank before launch from the active model M3.

Sections use the model type, for example `Tosh` or `Kerrigan`.

Keys use the sequence name and a suffix:

| Key | Type |
| --- | --- |
| `<clip>.fc` | int frame count |
| `<clip>.fms` | int frame duration |
| `<clip>.dur` | int sequence duration |

The clip name uses the sequence spelling with spaces, for example `Stand Left`.

The probe reads `SCOBACLIPMETRICS` when enabled. It stores frame count and frame duration per aim clip.

Frame index:

```text
frame = floor(played_ms / frame_ms)
```

When a clip loops, `frame` wraps at `frame_count`.

When metrics are absent for a clip, the probe records `uframes=0`, `ufms=0`, and `uframe=-1`. It still samples.

### 11A.2B Clip metrics lookup

The sampling trigger does not call `AnimLengthQueryByName()` or `AnimLengthQueryWait()`.

Lookup rules:

1. An aim clip change stores the clip name and the clip start time.
2. The setter maps comma props to the sequence name, for example `Stand,Work` to `Stand Work`.
3. The setter reads `<clip>.fms`, `<clip>.fc`, and `<clip>.dur` from the model section.
4. A complete metrics entry sets query state to `ok`.
5. A missing metrics entry sets query state to `fail`.
6. The sampler never blocks and never calls a native query.
7. An unknown clip still produces rows with `uframe=-1`.

Model played time:

```text
played_ms = (now_ms - start_ms) mod length_ms
remaining_ms = length_ms - played_ms
frame = (played_ms / frame_ms) mod frame_count
```

### 11A.2C No live actor time

The probe does not query live actor time.
It has no actor reset, actor freeze, or completion event data.
Model frames are derived from M3 metrics and local timing.
They do not prove actor playback phase.

A live actor worker is out of scope until it can stay within the 512-query limit
and use `AnimLengthQueryWait` correctly.

### 11A.3 Attachment names

Attachment names come from the generated model.

Tool:

```bash
uv run python scripts/dump_m3_attachments.py
```

Tosh names:

```text
Ref_Weapon
Ref_Hardpoint 02
Ref_Hardpoint 01
Ref_Head
Ref_Center
Ref_Overhead
```

Kerrigan names:

```text
Ref_Weapon
Ref_Target
Ref_Center
Ref_Origin
Ref_Overhead
Ref_Target 01
```

The probe does not use names that are absent from the model.

### 11A.4 Buffering

The probe does not save the bank on every tick.

- Each row is written to the `frames` section as it is sampled.
- The buffer capacity is 64 rows.
- The buffer flushes when full.
- The buffer flushes at least every 0.25 seconds.
- A flush saves the bank once.
- Enabling and disabling the probe flush the buffer.

### 11A.4A Arbitrary clip tracking

The probe does not read clip names from a fixed hero table.

API:

```galaxy
void gf_ProbeSetUpperClip (int lp_player, string lp_clip);
void gf_ProbeClearUpperClip (int lp_player);
```

Rules:

1. The aim clip path calls the setter.
2. The setter stores the clip name, start time, and metrics lookup result.
3. The setter accepts any aim clip name.
4. The probe writes the active name to `lclip`.
5. A test harness can call the setter for any unit and any aim clip.
6. The probe uses the state table only to seed the first active clip after enable.
7. The clear path empties the clip name and frame fields.

### 11A.5 Live toggle

`F9` toggles `gv_bPROBE`.

Enabling the probe:

1. Clears the probe bank.
2. Writes `meta.probe = 1`.
3. Writes `meta.started`.
4. Writes the `config` section.
5. Loads `SCOBACLIPMETRICS` for the active model.
6. Resets the tick and sample counters.

Disabling the probe:

1. Flushes remaining rows.
2. Writes `meta.stopped`.
3. Writes `meta.tick` and `meta.rows`.

### 11A.6 Separate process reader

`scripts/watch-framelog.py` reads the latest `SCOBAFRAMELOG` bank.

It performs these steps:

1. Locate the bank in the StarCraft II Documents folder.
2. Read the bank XML.
3. Convert rows to records.
4. Order rows by player and sample index.
5. Print each row.
6. Flag anomalies.

Anomaly rules:

| Name | Rule |
| --- | --- |
| `slide` | Hero position changes while all attachment positions stay fixed |
| `spike` | Attachment distance from `Ref_Center` grows above the profile limit |
| `gap` | Consecutive sample index difference is above the profile limit |
| `clock` | Timestamp decreases between consecutive sample indexes |
| `metrics` | An aim clip changes to `fail` after a valid `ok` sample |
| `churn` | Aim group start count grows above the profile limit per second |

### 11A.7 Dump files

The runner writes:

```text
framelog.tsv
framelog.jsonl
frameprobe.txt
```

`framelog.tsv` uses a header row and tab separators.

The runner writes `SCOBACLIPMETRICS` before launch. It is an input to the probe and is not a run artifact.

`frameprobe.txt` contains:

- row count;
- session duration;
- sample rate;
- state counts;
- metrics state counts;
- frame advancement and wrap counts;
- anomaly counts;
- model clip durations and frame counts.

## 12. Checks

`testkit/checks.py` defines:

```py
class Checks:
    def eq(self, section, tag, key, want): ...
    def true(self, section, tag, key): ...
    def false(self, section, tag, key): ...
    def gt(self, section, tag, key, floor): ...
    def lt(self, section, tag, key, ceiling): ...
    def displacement(self, section, tag_a, tag_b, min_pixels): ...
    def damage(self, section, tag_before, tag_after): ...
    def frame_diff(self, name, changed, minimum): ...
```

Output format:

```text
<profile> <case> <key>: got=<value> want=<value> PASS
<profile> <case> <key>: got=<value> want=<value> FAIL
```

Rules:

- A missing value prints `got=None`.
- A missing value fails.
- A failed check increments the failure count.
- A parser error increments the failure count.
- A runner error increments the failure count.

## 13. Profiles

### 13.1 Combat profile

File: `testkit/profiles/combat.py`

Map spec:

```py
TestMapSpec(
    profile="combat",
    source=ROOT / "out" / "SCOBA256.SC2Map",
    output=ROOT / "out" / "SCOBA256_test.SC2Map",
    bank_names=("SCOBATEST", "SCOBADBG"),
    galaxy_files=(
        ROOT / "scripts" / "testkit" / "galaxy" / "common.galaxy",
        ROOT / "scripts" / "testkit" / "galaxy" / "combat.galaxy",
    ),
    galaxy_includes=(
        'scripts/test/combat/common',
        'scripts/test/combat/combat',
    ),
    init_calls=('gt_CombatTest_Init();',),
)
```

The combat profile moves the current real input hook into
`testkit/profiles/combat.py`.

Combat real input probe:

1. Focus the game window.
2. Click the center point.
3. Right click the center point.
4. Drag left to right.
5. Drag right to left.
6. Read `SCOBADBG` input keys.
7. Assert `leftDrag` and `rightDrag` are `yes`.
8. Assert `leftDx` and `rightDx` are at least 5.
9. Assert `leftCancel`, `rightCancel`, `leftDy`, and `rightDy` are `no` or `0`.
10. Assert `rightRan` is `yes`.

The harness clears drag keys and displacement before the probe.

Non-aim attack checks:

1. Attack while stationary and record native lower frame IDs across two samples.
2. Require the lower frame IDs to advance.
3. Attack while moving and require the native Walk lower clip.
4. Require no non-aim `SCOBALo` animation start.
5. Require no duplicate actor for `Tosh` or `QueenOfBlades`.
6. Require the upper attack clip to restart on a repeated `UnitStartedAttack2`.

### 13.2 Aim profile

File: `testkit/profiles/aim.py`

Map spec:

```py
TestMapSpec(
    profile="aim",
    source=ROOT / "out" / "SCOBA256.SC2Map",
    output=ROOT / "out" / "SCOBA256_aimtest.SC2Map",
    bank_names=("SCOBAAIMTEST",),
    galaxy_files=(
        ROOT / "scripts" / "testkit" / "galaxy" / "common.galaxy",
        ROOT / "scripts" / "testkit" / "galaxy" / "aim.galaxy",
    ),
    galaxy_includes=(
        'scripts/test/aim/common',
        'scripts/test/aim/aim',
    ),
    init_calls=('gt_AimTest_Init();',),
)
```

Aim input hook:

1. Focus the game window.
2. Wait for `aim_enter` and `aim_idle` data.
3. Press the forward key.
4. Capture walk frame 1.
5. Wait 250 ms.
6. Capture walk frame 2.
7. Wait 250 ms.
8. Capture walk frame 3.
9. Change camera yaw with a drag.
10. Wait for the `aim_turn` snapshot.
11. Release the forward key.
12. Wait 500 ms.
13. Capture stop frame 1.
14. Wait 250 ms.
15. Capture stop frame 2.
16. Wait for the finish marker.

Aim movement is issued only by `gt_AimMoveTick`.
Per-key handlers only set flags.
`gf_AnimFacingTick` is the only aim facing writer.
Facing samples are compared with camera yaw, not with movement orders.
Aim adds `SCOBAAimNoTurn` on entry and removes it on release.

Aim checks:

| Check | Rule |
| --- | --- |
| `aim_enter AimActive` | `1` |
| `aim_enter CursorVisible` | `1` |
| `aim_enter UpperState` | an aim state |
| `aim_enter LowerState` | idle |
| `aim_idle AimActive` | `1` |
| `aim_idle LowerState` | idle |
| `aim_hold UpperState` | an aim state |
| `aim_hold AimGroup` | the generated `Attack Stand` splitbody group |
| `aim_hold UpperClip` | frozen aim upper STC |
| `aim_hold LowerClip` | idle lower STC |
| aim upper pitch start count | one at entry, no repeats |
| aim lower frame IDs | advance during aim idle, walk, and backpedal |
| real W/A/S/D and diagonal keys | eight directions are selected |
| `aim_direction UnitFacing` | within tolerance of `CameraYaw` |
| `aim_back LowerClip` | reversed backpedal lower STC |
| `aim_back` displacement | opposite camera forward |
| `aim_strafe` displacement | lateral to camera forward |
| `aim_twist Twist` | at or below 65 degrees in either strafe direction |
| `aim_attack` | deferred; no aim attack overlay in this stage |
| `aim_hold AimActive` | `1` |
| `aim_walk AimActive` | `1` |
| `aim_walk LowerState` | a walk state |
| aim idle lower frame difference | at least profile threshold |

| `aim_walk` leg frame difference | at least profile threshold |
| `aim_walk LowerState` frames 1 to 3 | one walk state |
| `aim_settle LowerState` | idle |
| stop frame versus last walk frame | at least profile threshold |
| stop frame 1 versus stop frame 2 | below profile threshold |
| `aim_turn` facing delta | within profile tolerance |
| `aim_enemy AimCursorTarget` | `1` |
| `aim_enemy CursorVisible` | `1` |
| `aim_release AimActive` | `0` |
| `aim_release UpperState` | none |
| `aim_release LowerState` | idle |
| `aim_release` combat keys | match aim enter |
| `aim_release` camera keys | match pre-aim values |
| generated model files | exist |
| generated model data | points to generated files |
| model hash repeat | equal |

### 13.3 Pitch profile

File: `testkit/profiles/pitch.py`

Map spec:

```py
TestMapSpec(
    profile="pitch",
    source=ROOT / "out" / "SCOBA256.SC2Map",
    output=ROOT / "out" / "SCOBA256_pitchtest.SC2Map",
    bank_names=("SCOBAPITCHTEST",),
    galaxy_files=(
        ROOT / "scripts" / "testkit" / "galaxy" / "common.galaxy",
        ROOT / "scripts" / "testkit" / "galaxy" / "pitch.galaxy",
    ),
    galaxy_includes=(
        'scripts/test/pitch/common',
        'scripts/test/pitch/pitch',
    ),
    init_calls=('gt_PitchTest_Init();',),
)
```

The pitch profile is a dedicated ten-second playtest.
It does not run aim movement, targeting, combat, or turn cases.

Pitch case flow:

1. Open the pitch bank.
2. Capture the anchor.
3. Reset player to stand and set `gv_cameraCollisionOff[1]` so collision cannot write distance during pitch sampling.
4. Call `gf_AimBegin(1)`.
5. Save `entry`.
6. Set camera pitch to 80 and save `down`.
7. Set camera pitch to 30 and save `mid`.
8. Set camera pitch to -60 and save `up`.
9. Set camera pitch back to 30 and save `hold`.
10. Call `gf_AimEnd(1)`.
11. Set camera pitch to 70, call `gf_AimBegin(1)`, and save `entry70`.
12. Set camera pitch to 80 and save `down70`.
13. Set camera pitch to -60 and save `up70`.
14. Set camera pitch back to 30 and save `hold70`.
15. Call `gf_AimEnd(1)` and write the finish marker.

Pitch samples record normalized camera pitch, rest pitch, and `SCOBAUp` time.
Camera pitch is recorded in degrees and normalized to signed range.
Selected keyframes must be tightly spaced and reach the target within tolerance.

Pitch bank sections:

| Section | Purpose |
| --- | --- |
| `meta` | Profile and finish state |
| `pitch` | Ready marker and pitch samples |

Pitch checks:

| Check | Rule |
| --- | --- |
| `meta done` | `1` |
| `meta profile` | `pitch` |
| `down Camera` | near 80 degrees |
| `mid Camera` | near 30 degrees |
| `up Camera` | near -60 degrees |
| `down Time` | at most `400` ms and less than `mid Time` |
| `up Time` | at least `9590` ms and greater than `mid Time` |
| `entry70 Rest` | `-13` |
| `down70 Time` | at most `400` ms |
| `up70 Time` | at least `9590` ms |
| `hold Time` | near `mid Time` |
| selected keyframe | reaches target within tolerance |
| pitch samples | lower frame ID unchanged |
| pitch samples | model root rotation unchanged |

### 13.4 Controls profile

File: `testkit/profiles/controls.py`

Map spec:

```py
TestMapSpec(
    profile="controls",
    source=ROOT / "out" / "SCOBA256.SC2Map",
    output=ROOT / "out" / "SCOBA256_controlstest.SC2Map",
    bank_names=("SCOBACONTROLSTEST",),
    galaxy_files=(
        ROOT / "scripts" / "testkit" / "galaxy" / "common.galaxy",
        ROOT / "scripts" / "testkit" / "galaxy" / "controls.galaxy",
    ),
    galaxy_includes=(
        'scripts/test/controls/common',
        'scripts/test/controls/controls',
    ),
    init_calls=('gt_ControlsTest_Init();',),
)
```

Controls case flow:

1. Reset the hero to Stand with auto-attack off.
2. Save `controls_default`.
3. Signal the RPG input phase.
4. Save `controls_rpg_hold`.
5. Set Walk and save `controls_rpg_click_move`.
6. Set Stand and save `controls_rpg_click_stop`.
7. Save `controls_rpg_select` after the real left click.
8. Issue a Stop order and save `controls_rpg_target_idle`.
9. Save `controls_rpg_stale` after the outside-radius ground press.
10. Move the hero, then Stop and save `controls_rpg_stop_idle`.
11. Toggle to action mode and save `controls_action`.
12. Change camera yaw and save `controls_mouselook`.
13. Step the hero and save `controls_move`.
14. Sample hero position twice and save `controls_move_tick`.
15. Save `controls_cursor`.
16. Set Alt pause and save `controls_alt`.
17. Release Alt pause and save `controls_alt_release`.
18. Enter aim and save `controls_aim`.
19. Save `controls_aim_distance` and `controls_reset`.
20. Attack the enemy at the cursor and save `controls_attack`.
21. Save `controls_ground`.
22. Set Alt pause over the enemy and save `controls_alt_click`.
23. Toggle to RPG mode and save `controls_rpg`.
24. Write the finish marker.

The harness drives camera yaw and movement steps.
The input hook sends real RPG right hold, left click, right click, and drag input.
The input hook reads the result bank before the action phase starts.
The movement tick case uses two adjacent `gt_AimMoveTick` intervals at
`c_ANIM_MOVE_TICK`.
The reset case reads upper and lower state after the mode change.

Controls checks:

| Check | Rule |
| --- | --- |
| `controls_default ActionMode` | `0` |
| `controls_action ActionMode` | `1` |
| `controls_mouselook CameraYaw` | differs from default |
| `controls_mouselook UnitFacing` | matches camera yaw |
| `controls_turn UpperState` | `0` |
| `controls_move` displacement | greater than `1` |
| `controls_move UnitFacing` | matches camera yaw |
| `controls_cursor CursorVisible` | `1` |
| `controls_cursor CursorCentered` | `1` |
| `controls_default ControlRelative` | `0` |
| `controls_default RotateUnit` | `0` |
| `controls_default RotateCamera` | `0` |
| `controls_alt AltPaused` | `1` |
| `controls_alt CursorVisible` | `1` |
| `controls_alt_release AltPaused` | `0` |
| `controls_aim AimActive` | `1` |
| `controls_aim CombatState` | matches action mode |
| `controls_attack TargetType` | hostile |
| `controls_attack CombatState` | manual attack |
| `controls_ground TargetType` | unchanged |
| `controls_ground CombatState` | unchanged |
| `controls_alt_click TargetType` | unchanged |
| `controls_alt_click CombatState` | unchanged |
| `controls_rpg ActionMode` | `0` |
| `controls_rpg AimActive` | `0` |
| `controls_rpg` field of view | equals `controls_default` |
| `controls_rpg_hold AimActive` | `0` |
| `controls_rpg_hold` field of view | equals `controls_default` |
| `controls_rpg_click_move` displacement | greater than `1` |
| `controls_rpg_click_move LowerState` | walk |
| `controls_rpg_click_stop` displacement | `0` |
| `controls_rpg_click_stop LowerState` | idle |
| `controls_rpg_select TargetType` | hostile |
| `controls_rpg_target_idle TargetType` | hostile |
| `controls_rpg_stale TargetType` | unchanged |
| `controls_rpg_stale CombatState` | no attack |
| `controls_rpg_stop_idle LowerState` | idle |
| `controls_aim_distance CameraDistance` | equals `controls_action` |
| `controls_zoom Distance` | at least `controls_default` + `1` |
| `controls_collision Distance` | within `1` of `controls_default` on flat ground |
| `controls_collision_clamp Distance` | less than flat-ground distance |
| `controls_collision_restore Distance` | within `1` of flat-ground distance |
| `controls_move_tick MoveTarget` | equals `c_ANIM_MOVE_TARGET` |
| `controls_move_tick` tick interval | `c_ANIM_MOVE_TICK` |
| `controls_action_left` facing delta | turns left |
| `controls_action_right` facing delta | turns right |
| `controls_action_back` facing delta | turns around |
| action left/right/back lower state | walk |
| `controls_reset UpperState` | non-aim state |
| `controls_reset LowerState` | non-aim state |
| turn `upper_stop` event count | at most `1` after the turn settles |
| RPG and action icons | different files and images |
| combat cooldown | unchanged by mode toggle |

## 14. Command Line

Canonical command:

```bash
scripts/playtest.sh build
scripts/playtest.sh launch
scripts/playtest.sh combat
scripts/playtest.sh aim
scripts/playtest.sh motion
scripts/playtest.sh controls
```

Every profile command rebuilds `out/SCOBA256.SC2Map` from `src/` first.
It then builds the profile map and runs that profile.
It never copies from a pre-existing `out/SCOBA256.SC2Map` before the rebuild.

Generic low-level command:

```bash
uv run python scripts/testmap.py build combat
uv run python scripts/testmap.py run combat
uv run python scripts/testmap.py build aim
uv run python scripts/testmap.py run aim
uv run python scripts/testmap.py build controls
uv run python scripts/testmap.py run controls
```

`scripts/testmap.py` delegates to `scripts/playtest.sh` unless
`SC2_PLAYTEST_ACTIVE=1` is set.

Options:

| Option | Purpose |
| --- | --- |
| `--profile` | Profile name |
| `--out` | Map output override |
| `--run-root` | Artifact root override |
| `--launch-timeout` | Launch timeout in seconds |
| `--case-timeout` | Case timeout in seconds |
| `--visual` | Enable frame capture |

Thin entrypoints:

| Command | Action |
| --- | --- |
| `scripts/build-test-map.py` | Rebuild fresh, then build combat |
| `scripts/run-map-test.py` | Rebuild fresh, then run combat |
| `scripts/build-aim-test-map.py` | Rebuild fresh, then build aim |
| `scripts/run-aim-test.py` | Rebuild fresh, then run aim |
| `scripts/build-controls-test-map.py` | Rebuild fresh, then build controls |
| `scripts/run-controls-test.py` | Rebuild fresh, then run controls |
| `scripts/build-motion-test-map.py` | Rebuild fresh, then build motion |
| `scripts/run-motion-test.py` | Rebuild fresh, then run motion |

Wrappers delegate through `scripts/playtest.sh` unless
`SC2_PLAYTEST_ACTIVE=1`.
Unknown profile names fail with a clear message.

## 15. Run Artifacts

Run root:

```text
out/test-runs/<profile>/<YYYYmmdd-HHMMSS>/
```

Required files:

```text
summary.json
summary.txt
framelog.tsv
framelog.jsonl
frameprobe.txt
frames/
  <case>-0001.png
  <case>-0002.png
  <case>-0003.png
```

`summary.json` keys:

- `profile`
- `run_id`
- `map`
- `bank`
- `exit_code`
- `failures`
- `checks`
- `script_errors`
- `error_folders`
- `alerts`
- `artifacts`

`summary.txt` contains:

- profile name;
- run folder;
- map path;
- bank path;
- failure count;
- one line per check.

## 16. Unit Tests

Framework tests use `unittest`.

Command:

```bash
uv run python -m unittest discover -s scripts/testkit/tests -t scripts
```

Required test modules:

| Module | Coverage |
| --- | --- |
| `test_bank.py` | XML parsing and latest bank selection |
| `test_checks.py` | Pass, fail, missing values, displacement, damage |
| `test_profiles.py` | Profile map paths, bank names, and output isolation |
| `test_summary.py` | JSON and text summary files |
| `test_framelog.py` | Probe row parsing, TSV output, and anomaly flags |

Unit tests do not launch StarCraft II.

## 17. Migration Steps

1. Add `testkit` package.
2. Add shared bank, log, check, input, frame, and summary modules.
3. Split `test_harness.galaxy` into common and combat files.
4. Move combat builder configuration into `testkit/profiles/combat.py`.
5. Move combat runner configuration into `testkit/profiles/combat.py`.
6. Replace `scripts/build-test-map.py` with a thin entrypoint.
7. Replace `scripts/run-map-test.py` with a thin entrypoint.
8. Add aim builder and runner profile.
9. Add aim Galaxy harness.
10. Add aim input hook and frame checks.
11. Add animation layer and facing bank keys.
12. Add fixed pose frame checks.
13. Add generated model asset checks.
14. Add controls builder and runner profile.
15. Add controls Galaxy harness.
16. Add controls harness and checks.
17. Add framework unit tests.
18. Update `AGENTS.md`.

## 18. Verification

Combat verification:

```bash
scripts/playtest.sh combat
```

Aim verification:

```bash
scripts/playtest.sh aim
```

Controls verification:

```bash
scripts/playtest.sh controls
```

Frame probe verification:

```bash
uv run python scripts/dump_m3_attachments.py
uv run python scripts/dump_m3_clip_metrics.py
uv run python scripts/watch-framelog.py
```

Clip metrics verification:

1. Run the metrics tool on the Tosh and Kerrigan models.
2. Require a frame count and frame duration for `Stand`, `Stand Left`, and `Walk`.
3. Require a second model with different frame durations.
4. Require frame counts from real M3 animation blocks.
5. Require model clip durations to match the M3 sequences.

Probe verification:

1. Run a 20 s motion profile.
2. Require advancing lower frame IDs in the aim group after aim starts.
3. Require a wrap at `uframes`.
4. Require rows for a second model.
5. Require no data claims for live actor time.

Motion checks:

| Check | Rule |
| --- | --- |
| `motion_move` displacement | greater than `10` |
| walking displacement samples | no zero dips while forward is held |
| walking move orders | above zero while forward is held |
| aim lateral move displacement | greater than `10` |
| aim lateral move lower state | walk |
| aim lateral move lower frame IDs | advance |

Framework unit tests:

```bash
uv run python -m unittest discover -s scripts/testkit/tests -t scripts
```

Idempotency check:

1. Build the same profile twice.
2. Compare output map hashes.
3. Require equality.

Isolation check:

1. Record combat map hash.
2. Run aim build and aim test.
3. Run controls build and controls test.
4. Compare combat map hash.
5. Require equality.

## 19. Non-Goals

This framework does not:

- replace gameplay requirements;
- add gameplay behavior;
- change the normal game map;
- test the StarCraft II editor;
- run multiple profiles in one game process;
- share a bank between profiles;
- share a run artifact folder between runs;
- read the StarCraft II process memory.
