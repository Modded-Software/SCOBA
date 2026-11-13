# REQ-DAMAGE-FLOATERS: Hero Damage Floaters

## Scope

Show a floating damage number on every unit damaged by the controlled hero.
Cover single-target and area-of-effect damage.

## Requirements

| ID | Requirement |
| --- | --- |
| R-FLOAT-1 | A hero damage event MUST create one floating text tag on the damaged unit. |
| R-FLOAT-2 | The floater MUST show the actual damage dealt by that event. |
| R-FLOAT-3 | Area-of-effect damage MUST create one floater per damaged unit. |
| R-FLOAT-4 | Single-target damage MUST create one floater on the target. |
| R-FLOAT-5 | Only damage caused by a hero controlled through `gv_tPSUNIT` MAY create a floater. |
| R-FLOAT-6 | The floater MUST be visible only to the hero player. |
| R-FLOAT-7 | The floater MUST start at the damaged unit's position and remain independent. |
| R-FLOAT-8 | The floater MUST rise and expire automatically. |
| R-FLOAT-9 | Zero and negative damage MUST NOT create a floater. |
| R-FLOAT-10 | Invalid source or victim units MUST NOT create a floater. |
| R-FLOAT-11 | Damage floaters MUST NOT change combat state, orders, or animation. |
| R-FLOAT-12 | Damage floaters MUST NOT modify the damage amount. |
| R-FLOAT-13 | The map MUST keep the native text tag UI frame visible. |
| R-FLOAT-14 | A targetless aim shot proxy MUST NOT create a damage floater. |

## Acceptance Criteria

| ID | Criterion |
| --- | --- |
| AC-FLOAT-1 | A hero weapon hit shows one red number on the target. |
| AC-FLOAT-2 | A hero area attack shows one number on each damaged enemy. |
| AC-FLOAT-3 | The number equals the damage taken for that event. |
| AC-FLOAT-4 | No floater appears for damage not caused by the active hero. |
| AC-FLOAT-5 | The floater rises and disappears without leaving text tags behind. |
| AC-FLOAT-6 | Combat, aim, movement, and animation behave exactly as before. |
| AC-FLOAT-7 | `c_syncFrameTypeTextTag` is visible for all players. |
| AC-FLOAT-8 | Multiple damaged units show floaters at their own positions. |