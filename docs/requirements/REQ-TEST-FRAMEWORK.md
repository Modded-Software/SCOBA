# REQ-TEST-FRAMEWORK: Reusable Test Framework

**Date:** 2026-11-10
**Status:** Active binding requirement

## 1. Scope

This contract binds the automated StarCraft II test framework:

- instrumented map builds;
- Galaxy test harnesses;
- map launches and bank collection;
- game log checks;
- mouse and keyboard probes;
- screenshot collection;
- animation, facing, and frame checks;
- generated model asset checks;
- assertion reporting;
- separate test profiles;
- isolated run artifacts.

Gameplay behavior lives in the control and animation requirements.
Implementation lives in
[SPEC-TEST-FRAMEWORK](../specifications/SPEC-TEST-FRAMEWORK.md).

## 2. Definitions

- **Test profile**: a named suite with its own map, bank, harness, and checks.
- **Instrumented map**: a built map copy with test hooks.
- **Test bank**: profile data read by the runner.
- **Run artifact**: one timestamped output folder.
- **Frame probe**: in-game sampling of animation and camera state.
- **Model frame**: frame index derived from M3 clip metrics and local timing.
- **Model frame data**: clip duration, frame count, and frame duration.
- **Attachment point**: a named model point attached to a bone.

## 3. Requirements

### 3.1 Profile isolation

| ID | Requirement |
| --- | --- |
| R-TF-1 | Each test profile MUST have a separate map, bank, harness, and run folder. |
| R-TF-2 | A profile MUST NOT change another profile's map, bank, or artifacts. |
| R-TF-3 | The builder MUST reject a map path owned by another profile. |
| R-TF-4 | The runner MUST touch only the active profile's map, bank, and cache. |

### 3.2 Shared components

| ID | Requirement |
| --- | --- |
| R-TF-5 | The framework MUST provide shared map building, launching, bank reading, log scanning, assertions, input, screenshots, and Galaxy helpers. |
| R-TF-6 | Profiles MUST use the shared components. |
| R-TF-7 | Launch, wait, bank, and log logic MUST stay out of profile code. |

### 3.3 Map builder

| ID | Requirement |
| --- | --- |
| R-TF-8 | The builder MUST accept a profile map specification. |
| R-TF-9 | The builder MUST clear the map wait-for-key option and recompute the map hash. |
| R-TF-10 | The builder MUST declare the profile bank and install harness files, includes, and init calls. |
| R-TF-11 | The builder MUST leave the source map unchanged. |
| R-TF-12 | The builder MUST produce the same output for the same input. |
| R-TF-13 | The builder MUST fail on a missing source map or map script entry point. |
| R-TF-14 | The builder MUST NOT add gameplay state for tests. |

### 3.4 Galaxy harness

| ID | Requirement |
| --- | --- |
| R-TF-15 | The common harness MUST provide bank, spawn, reset, snapshot, and finish helpers. |
| R-TF-16 | Each profile harness MUST own its cases, globals, and bank keys. |
| R-TF-17 | The finish marker MUST be written after all case data and saved last. |
| R-TF-18 | The harness MUST save the profile bank after each case group. |

### 3.5 Runner

| ID | Requirement |
| --- | --- |
| R-TF-19 | The runner MUST launch the active profile map and wait for its bank and finish marker. |
| R-TF-20 | The runner MUST enforce launch and case timeouts. |
| R-TF-21 | The runner MUST fail on new script errors, error folders, or fatal alerts. |
| R-TF-22 | The runner MUST write JSON and text summaries and return a nonzero exit code on failure. |
| R-TF-23 | The runner MUST run the profile input hook and then collect results. |
| R-TF-24 | The runner MUST stop StarCraft II after the run. |

### 3.6 Input and frames

| ID | Requirement |
| --- | --- |
| R-TF-25 | The input driver MUST support focus, click, right click, drag, hold, release, and key hold. |
| R-TF-26 | The input driver MUST read the game window geometry. |
| R-TF-27 | Every run and every screenshot MUST use a unique path. |
| R-TF-28 | Screenshot capture MUST reject an existing path and keep the image artifact. |
| R-TF-29 | Frame checks MUST compare declared regions and report changed pixel counts. |
| R-TF-30 | Frame checks MUST fail below the profile threshold. |

### 3.7 Checks

| ID | Requirement |
| --- | --- |
| R-TF-31 | Checks MUST support equality, booleans, ranges, displacement, damage, and frame difference. |
| R-TF-32 | Checks MUST print a stable pass or fail line. |
| R-TF-33 | A missing value MUST fail the check. |
| R-TF-34 | Parser and runner errors MUST surface as failures. |

### 3.8 Profiles

| ID | Requirement |
| --- | --- |
| R-TF-35 | The combat profile MUST cover the existing combat and real-input cases. |
| R-TF-36 | The combat profile MUST preserve existing case sections, keys, and pass or fail meaning. |
| R-TF-37 | The aim profile MUST cover aim entry, rest, movement, enemy crosshair, fixed pose, facing, and release. |
| R-TF-38 | The aim profile MUST cover splitbody aim hold, eight lower directions, backpedal, and generated model checks. |
| R-TF-39 | The controls profile MUST cover RPG mode, control toggle, action mouse look, aim, attack, clicks, Alt, facing, and movement. |
| R-TF-40 | The controls profile MUST cover target persistence, stale hover, aim distance, movement bounds, and animation reset. |
| R-TF-41 | The controls profile MUST cover RPG Stand and Walk ground clicks. |
| R-TF-42 | The aim profile MUST prove the upper aim pose does not loop and lower frame IDs advance in all eight directions. |
| R-TF-43 | The motion profile MUST prove aim movement has no stop and go bursts. |
| R-TF-44 | The motion profile MUST prove aim movement uses eight directional lower clips. |
| R-TF-45 | The controls profile MUST prove non-aim action A/D/S turn the hero toward movement. |
| R-TF-46 | The aim profile MUST prove backward movement uses a reversed backpedal clip and moves opposite camera forward. |
| R-TF-47 | The aim profile MUST prove torso-to-lower twist stays at or below 65 degrees in either strafe direction. |
| R-TF-48 | The aim profile MUST drive real W/A/S/D and diagonal key combinations and prove unit facing stays on camera yaw. |
| R-TF-66 | The aim profile MUST prove S backpedals and A/D strafe without turning the unit. |
| R-TF-67 | Aim attack animation is DEFERRED and MUST NOT be part of this test stage. |
| R-TF-68 | The aim profile MUST prove `SCOBAAimNoTurn` is present during aim and removed after release. |
| R-TF-69 | The aim profile MUST prove aim movement issues no per-key orders and writes no facing. |
| R-TF-70 | The aim profile MUST prove facing and movement remain smooth while camera yaw rotates. |
| R-TF-71 | The pitch profile MUST prove camera pitch changes `SCOBAUp` time and the spine pose using the `SCOBAUp` animation reference. |
| R-TF-72 | The pitch profile MUST prove pitch reaches the 60 degree up and 80 degree down camera limits. |
| R-TF-73 | The pitch profile MUST prove pitch changes no lower-body frame and no model root rotation. |
| R-TF-74 | The pitch profile MUST normalize wrapped camera pitch above 180 degrees before checking pitch time. |
| R-TF-75 | The pitch profile MUST prove pitch keyframes are tightly spaced and camera pitch selects the nearest keyframe immediately. |
| R-TF-76 | The pitch profile MUST use one lower-back spine pivot for the whole upper body and MUST NOT rotate the lower body or model root. |
| R-TF-77 | The pitch profile MUST record pitch ticks, pitch sends, remaining clip time, and model remaining time. |
| R-TF-78 | The pitch profile MUST prove camera pitch sends are paced by camera moves and reasserts. |
| R-TF-79 | Tests MUST cover camera collision distance clamping and restoration. |
| R-TF-80 | Tests MUST cover derived control/cursor state after real RPG clicks, action mode, Alt, and aim transitions. |
| R-TF-81 | Tests MUST use engine `UnitHighlight` and engine mouse-click world coordinates as the RPG hover and click inputs. |

### 3.9 Command line

| ID | Requirement |
| --- | --- |
| R-TF-42 | Each profile MUST have a build command and a run command. |
| R-TF-43 | A generic command MUST support build and run by profile. |
| R-TF-44 | The generic command MUST accept profile, output path, and timeout. |
| R-TF-45 | Unknown profiles MUST fail. |
| R-TF-71 | Every profile build and run MUST rebuild `out/SCOBA256.SC2Map` from `src/` first. |
| R-TF-72 | Profile builds MUST NOT copy from a stale `out/SCOBA256.SC2Map`. |
| R-TF-73 | `scripts/playtest.sh <profile>` MUST be the canonical profile test command. |
| R-TF-74 | Profile wrappers MUST delegate to `scripts/playtest.sh` unless `SC2_PLAYTEST_ACTIVE=1`. |

### 3.10 Framework tests

| ID | Requirement |
| --- | --- |
| R-TF-46 | Framework unit tests MUST run without StarCraft II. |
| R-TF-47 | Unit tests MUST cover bank parsing, checks, profile isolation, screenshot paths, and summaries. |

### 3.11 Character frame probe

| ID | Requirement |
| --- | --- |
| R-TF-48 | The framework MUST provide an in-game character frame probe. |
| R-TF-49 | The probe MUST sample on a game-time periodic trigger. |
| R-TF-50 | Each sample MUST record time, index, player, unit type, state, clip, camera, aim, action, and movement data. |
| R-TF-51 | Each sample MUST record model frame data derived from M3 clip metrics. |
| R-TF-52 | The probe MUST track the configured aim group and lower clip on any unit model. |
| R-TF-53 | The probe MUST distinguish model-derived frames from live actor time. |
| R-TF-54 | The probe MUST record aim group, direction, lower clip changes, and upper state events. |
| R-TF-55 | The probe MUST record attachment points from the generated model. |
| R-TF-56 | The probe MUST write its bank at a bounded interval with start and stop markers. |
| R-TF-57 | A debug hotkey MUST toggle the probe. |
| R-TF-58 | The reader MUST print rows and write `framelog.tsv`, `framelog.jsonl`, and `frameprobe.txt`. |
| R-TF-59 | The reader MUST flag gaps, clip changes, and frame wrap errors. |
| R-TF-60 | The runner MUST reset probe banks before a run and dump them after a run. |
| R-TF-61 | The launcher MUST prepare model clip metrics for the active map. |
| R-TF-62 | The framework MUST provide model attachment and clip metrics dump tools. |
| R-TF-63 | Unit tests MUST cover probe parsing, ordering, and frame wrap. |
| R-TF-64 | A probe run MUST record rows for a model other than the hero. |
| R-TF-65 | A probe run MUST verify model clip durations and frame counts. |

### 3.12 Documentation

| ID | Requirement |
| --- | --- |
| R-TF-67 | This file MUST hold test framework requirements. |
| R-TF-68 | The test framework specification MUST hold implementation detail. |
| R-TF-69 | `AGENTS.md` MUST list the test framework, animation, and control documents. |
| R-TF-70 | `AGENTS.md` MUST list the test commands. |

## 4. Acceptance criteria

| ID | Check |
| --- | --- |
| AC-TF-1 | Each profile builds only its own map. |
| AC-TF-2 | Profiles use separate banks and artifact folders. |
| AC-TF-3 | Running one profile does not change another profile's map, bank, or artifacts. |
| AC-TF-4 | Rebuilding the same profile gives the same map hash. |
| AC-TF-5 | No screenshot path is overwritten. |
| AC-TF-6 | Script compile errors, runtime errors, missing finish markers, and fatal alerts fail the run. |
| AC-TF-7 | Each run writes a JSON summary and a text summary. |
| AC-TF-8 | Framework unit tests pass without StarCraft II. |
| AC-TF-9 | Combat cases report pass or fail with existing meaning. |
| AC-TF-10 | Aim animation, facing, and release cases report pass or fail. |
| AC-TF-11 | Generated model and model data checks report pass or fail. |
| AC-TF-12 | Controls mode, cursor, aim, attack, click, Alt, facing, and movement cases report pass or fail. |
| AC-TF-13 | Target persistence, stale hover, aim distance, movement bounds, and animation reset cases report pass or fail. |
| AC-TF-14 | RPG Stand and Walk ground click cases report pass or fail. |
| AC-TF-15 | Frame probe rows report model frame values for any model. |
| AC-TF-16 | Idle, turn, and walk runs report one baseline loop without model frame gaps. |
| AC-TF-17 | Probe rows advance without gaps and report model clip timing. |
| AC-TF-18 | Attachment and clip metrics dump tools report model data. |
| AC-TF-19 | A profile run after a source change uses the freshly built map. |
| AC-TF-20 | A direct wrapper call rebuilds fresh through `scripts/playtest.sh`. |
