# SPEC-UI-PANELS: stats and abilities panels

Implements REQ-UI-PANELS.

## 1. Cause of the closing panels

`gf_AwardExperience` (`systems/xp.galaxy`) runs on every kill and every heal
of an ally. It ends with `gf_ShowStasLevelingInterface` and
`gf_ShowAbilityLevelingInterface`. Both used to hide the panel if it was
open, and the stats one hid it for all players. During fights XP comes in
every 0.5 to 2 s, so the panels closed.

## 2. Behaviour

- `gf_ShowStasLevelingInterface(p)`: if the stats panel is open for `p`,
  `gf_UnitSelectionDialogRefresh(p)` (tooltips, points label). Then show the
  HUD stats button with the point count. Visibility is not changed (R-UI-1,
  R-UI-2).
- `gf_ShowAbilityLevelingInterface(p)`: same, with
  `gf_AbilitiesSelectionDialogRefresh(p)` (buttons, icons, points label).
- `gf_StatsPanelToggle(p)`, `gf_AbilitiesPanelToggle(p)`: the HUD buttons.
  Open or close for `p` only (R-UI-4).
- `gf_AbilitiesSelectionDialogHide(p)`: close button. Hides the panel and
  the key column for `p` only (R-UI-4).
- `gf_UnitSelectionSpend(p, button)`: one stat click. Returns false and
  spends nothing at 0 points. Never hides the panel (R-UI-3).
- The dialog click triggers only map the clicked control to these functions,
  so the test calls the same code a click runs.
- The abilities button loops run over 0 .. n - 1. Index n has no control.

## 3. Test (profile `ui`)

Scenarios, each starting with both panels closed and 0 points:
`xp_stats`, `lvl_stats`, `abil` (R-UI-1), `closed` (R-UI-2, negative),
`other` (R-UI-4, negative: player 2 levels), `spend` (R-UI-3), `toggle`
(R-UI-4), `kill` (R-UI-1 integration: the hero kills a zergling; XP comes
from the engine damage and death events).
