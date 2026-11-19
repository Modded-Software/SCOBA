# REQ-UI-PANELS: stats and abilities panels

Scope: the stats panel and the abilities panel (with its key column), opened
from the HUD buttons. Source: operator, 2026-11-18 ("panels close in 0.5-2
seconds by themselves").

- R-UI-1 An open panel stays open while the hero gains XP or levels up. It
  closes only when its player closes it (HUD button or close button).
- R-UI-2 XP and level-ups never open a closed panel. They update the point
  counts on the HUD buttons and show the buttons.
- R-UI-3 Spending the last stat point keeps the stats panel open. With 0
  points a stat click spends nothing.
- R-UI-4 Opening or closing a panel affects only the player who did it.
  Another player's XP or level-up does not change it.
- R-UI-5 The minimap only displays. Clicking it does not move the camera
  (operator 2026-11-18). Implemented in `UI/Layout/Custom/ScobaMinimap.SC2Layout`
  (`Minimap` frame `AcceptsMouse` false). Operator check.

Verification: profile `ui` (`scripts/playtest.sh ui`). Panel visibility is
read from the engine with `DialogIsVisible`. How the panels look is an
operator check.
