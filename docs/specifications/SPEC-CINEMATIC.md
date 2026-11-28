# SPEC-CINEMATIC: Cinematic Mode on F9

Requirements: [REQ-CINEMATIC](../requirements/REQ-CINEMATIC.md).

## 1. Facts

| ID | Fact | Source |
| --- | --- | --- |
| F1 | The scene module (`systems/scene`) is the only writer of the UI mode, the minimap and the map dialogs (SPEC-HERO-DROP 3b). Cinematic mode lives there. | `systems/scene.galaxy` header |
| F2 | The UI is 1200 units high. A 16:10 screen is 1920 wide; 16:9 of that width is 1080 high: 60 per bar. | operator 2026-11-27: size for 16:10 |
| F3 | Galaxy has no getter for the screen size. | `natives.galaxy` |
| F4 | Shift is the slow walk key (REQ-SLOW-WALK): Shift+F9 while walking also slows the hero for that moment. | `systems/input.galaxy` |

## 2. Design

- State in `core/scene.galaxy`: `gv_cineOn`, `gv_cineBox`, the two bar
  controls `gv_cineBarCtl`, the pending hide time `gv_cineHideAt`,
  counters for tests.
- Keys (`gt_Scene_Init`): `gt_CineKey` on F9 with Shift excluded,
  `gt_CineBoxKey` on F9 with Shift required. Both call `gf_CineKeyPress`.
  Not gated by the scene's input hold: the key works in the intro too.
- `gf_CineSet(p, true)` -> `gf_CineUiHide`: fullscreen UI mode, minimap off,
  the scene dialog list hidden and kept (`gf_SceneDialogsEnforce`), world
  texts off (`c_syncFrameTypeTextTag`), the TPS text panel hidden. The
  crosshair tick (`gt_AimCursorTick`) shows the crosshair only with
  `gv_cineOn` false. `gt_SceneTick` hides re-shown dialogs every loop while
  the mode is on.
- `gf_CineSet(p, false)`: bars off, `gf_CineUiShow` restores the kept
  dialogs, console UI mode, minimap, texts.
- In a scene (intro, drop): `gf_SceneEnter` keeps the dialogs cinematic mode
  recorded. `gf_SceneLeave` with the mode on leaves the UI hidden. Toggling
  the mode inside a scene changes only the texts; the scene restores the
  rest when it ends.
- Letterbox: two layout frames, `ScobaCineTop` and `ScobaCineBottom`
  (`UI/Layout/Custom/ScobaCine.SC2Layout`, children of `GameUI`), full
  width, 60 high, black, no mouse. Script hooks them up
  (`DialogControlHookupStandard`). On: shown, event "In": the anchor
  slides from 60 off screen to 0 in 0.4 s (R-CINE-10). Off: event "Out",
  the reverse; the bars stay shown until `gt_SceneTick` hides them at
  `gv_cineHideAt` (`c_CINE_HIDE_AFTER` 0.7 game s: 0.4 UI s at "Faster"
  is 0.56 game s). "In" during a slide out clears the pending hide.
  The slide runs in the layout, not in script: smooth at any frame rate.
- The animation probe lost its F9 trigger (`gt_AnimProbeToggle` removed,
  scene trigger list 43). Tests call `gf_ProbeEnable` / `gf_ProbeDisable`.

## 3. Test

`scripts/playtest.sh cinematic` (`galaxy/cinematic.galaxy`,
`profiles/cinematic.py`). TPS on, then: Shift+F9 with the mode off (refused,
no bars: negative), F9 (dialogs 0, minimap, world texts, crosshair, TPS
texts off; no input hold; a move order walks the hero 1+ unit), Shift+F9:
in (bars 2, both 60 high, one "In"), out (bars still 2 while sliding, one
"Out", then 0 after 1 s), in again. Negative: in during a slide out, the
bars stay (no late hide). F9 off: a slide out, then bars 0 and the same
dialog count, minimap, texts and crosshair as before. The UI mode and the
slide position have no getter: the console's absence and the motion are
operator checks.

## 4. State

| ID | State | Evidence |
| --- | --- | --- |
| R-CINE-1..10 | [built] | Not run in game. |
| Bar look, slide motion, 16:9 picture, nothing left on screen | [operator] | |
