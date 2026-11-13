# REQ-HERO-SWITCH: Controlled Hero Switching

## Scope

Local player 1 can switch the controlled hero between Tosh and Kerrigan during play.
The inactive hero stays in the map, paused, hidden, and parked off-screen.
Switching exists for gameplay and for testing both hero animation sets.

## Requirements

| ID | Requirement |
| --- | --- |
| R-SWITCH-1 | `Alt+1` MUST make Tosh the controlled hero for player 1. |
| R-SWITCH-2 | `Alt+2` MUST make Kerrigan the controlled hero for player 1. |
| R-SWITCH-3 | A switch to the already active hero MUST be a no-op. |
| R-SWITCH-4 | Only one hero MAY be controlled by player 1 at a time. |
| R-SWITCH-5 | The active hero MUST be owned by player 1 and have `UnitDirectControl`. |
| R-SWITCH-6 | The inactive hero MUST lose player 1 control. |
| R-SWITCH-7 | The inactive hero MUST be hidden and unselectable. |
| R-SWITCH-8 | The inactive hero MUST be moved to a dedicated off-screen parking point. |
| R-SWITCH-9 | The inactive hero MUST receive a stop order and hold position off-screen. |
| R-SWITCH-10 | The active hero MUST appear at the old active hero position and face. |
| R-SWITCH-11 | Switching MUST exit aim mode before changing the hero. |
| R-SWITCH-12 | Switching MUST exit order mode before changing the hero. |
| R-SWITCH-13 | Switching MUST clear combat target, combat state, and animation state. |
| R-SWITCH-14 | The camera MUST follow the new active hero. |
| R-SWITCH-15 | Tosh camera distance MUST be 1.5 and Kerrigan camera distance MUST be 2.5. |
| R-SWITCH-16 | The new active hero MUST receive the same custom toggles as the map-start hero. |
| R-SWITCH-17 | The hero selection loop MUST keep the active hero selected. |
| R-SWITCH-18 | The selection loop MUST NOT reselect or reveal the parked hero. |
| R-SWITCH-19 | Both heroes MUST remain valid units after switching. |
| R-SWITCH-20 | Switching MUST NOT change the model, animation groups, or actor IDs. |

## Acceptance Criteria

| ID | Criterion |
| --- | --- |
| AC-SWITCH-1 | `Alt+1` controls Tosh and `Alt+2` controls Kerrigan. |
| AC-SWITCH-2 | Repeating the active hero key does nothing. |
| AC-SWITCH-3 | The parked hero is not visible, not selectable, and not clickable. |
| AC-SWITCH-4 | The parked hero stays at the parking point and does not move. |
| AC-SWITCH-5 | The new hero appears at the old hero position and facing. |
| AC-SWITCH-6 | The camera follows the new hero with the correct distance. |
| AC-SWITCH-7 | Switching while aiming exits aim cleanly. |
| AC-SWITCH-8 | Switching while in order mode exits order mode cleanly. |
| AC-SWITCH-9 | Attack, aim, and movement work on both heroes after switching. |
| AC-SWITCH-10 | Animation state resets on every switch. |
| AC-SWITCH-11 | No duplicate actor or duplicate model appears. |