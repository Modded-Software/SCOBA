# REQ-AIM-SHOOTING: Aim-Mode Shooting

**Date:** 2026-11-13
**Status:** Active binding requirement

## 1. Scope

This contract binds left-click shooting while aim mode is active in action mode:

- crosshair target selection;
- in-range attack and out-of-range feedback;
- crosshair range coloring;
- native attack from a hidden aim shooter for every shot;
- targetless attack and `Miss` feedback at the crosshair;
- exact crosshair targeting with no hero movement interruption;
- aim attack animation on mouse press;
- combat-state isolation.

Mouse and aim behavior lives in
[REQ-MOUSE-CONTROLS](REQ-MOUSE-CONTROLS.md).
Combat state lives in [REQ-COMBAT-CONTROLS](REQ-COMBAT-CONTROLS.md).
Animation lives in [REQ-CHARACTER-ANIMATION](REQ-CHARACTER-ANIMATION.md).
Floaters live in [REQ-DAMAGE-FLOATERS](REQ-DAMAGE-FLOATERS.md).
Implementation lives in
[SPEC-AIM-SHOOTING](../specifications/SPEC-AIM-SHOOTING.md).

## 2. Definitions

- **Aim shot**: a left press while aim mode is active.
- **Crosshair point**: the world point on the aim ray from the hero shoulder
  along `CameraGetYaw` and `CameraGetPitch`, clamped to the current weapon range.
- **In range**: `UnitInRangeAndAbleToAttackTarget(hero, target)` is true.
- **Target resolution order**: crosshair geometry, then `UnitClick`, then
  press-time Unit Highlight.
- **Aim shooter**: a hidden friendly unit pinned to the hero position.
  It carries the hero weapon and receives the native aim attack order.
- **Shot proxy**: an invisible, unselectable, non-status, non-scoring unit used
  for one native attack on a targetless shot.

## 3. Requirements

### 3.1 Aim press and target

| ID | Requirement |
| --- | --- |
| R-AIMSHOT-1 | An aim shot MUST run on left mouse press. |
| R-AIMSHOT-2 | Left mouse release MUST NOT fire a second aim shot. |
| R-AIMSHOT-3 | An aim shot MUST resolve its target at the crosshair first, then use `UnitClick` and press-time Unit Highlight. |
| R-AIMSHOT-4 | An aim shot MUST accept only alive hostile units. |
| R-AIMSHOT-5 | A resolved hostile target MUST update the Unit Target and boss bar. |
| R-AIMSHOT-6 | Clicks while Alt is held MUST NOT fire. |
| R-AIMSHOT-7 | A target outside the unit radius MUST NOT be selected by crosshair geometry. |
| R-AIMSHOT-8 | Aim shots MUST be registered per hero player. `EventPlayer` MUST NOT infer another player. |
| R-AIMSHOT-8a | An aim shot MUST start the attack animation immediately on press. |
| R-AIMSHOT-8b | An aim shot MUST be ignored while the previous aim attack animation is active. |
| R-AIMSHOT-8c | An aim shot MUST be ignored while the hero weapon or hidden shooter weapon is not ready. |
| R-AIMSHOT-8d | Fast repeated clicks MUST NOT restart the attack animation or reset the attack cooldown early. |

### 3.2 Range and reticle

| ID | Requirement |
| --- | --- |
| R-AIMSHOT-9 | Every aim shot MUST issue one native attack order from the hidden aim shooter and start the native weapon event. |
| R-AIMSHOT-9a | An in-range hostile target MUST receive the shooter attack order directly, with the hero as the logical owner. |
| R-AIMSHOT-9b | The hero MUST NOT receive an attack order from an aim shot. |
| R-AIMSHOT-9c | The aim shooter MUST be pinned to the hero position and camera yaw on every aim tick. |
| R-AIMSHOT-9d | The aim shooter MUST be hidden, unselectable, untargetable, non-colliding, and non-scoring. |
| R-AIMSHOT-9e | Native shooter cooldown MUST be mirrored to the hero weapon cooldown. |
| R-AIMSHOT-9f | Moving aim shots MUST NOT stop, pause, or restart hero locomotion. |
| R-AIMSHOT-10 | An out-of-range hostile target MUST NOT receive an attack order. |
| R-AIMSHOT-11 | An out-of-range hostile target MUST show one gray `Out of range` floater at the target. |
| R-AIMSHOT-12 | The aim reticle MUST stay hostile-colored for an in-range hostile unit. |
| R-AIMSHOT-13 | The aim reticle MUST gray out for a hostile unit that is not in range. |
| R-AIMSHOT-14 | The reticle MUST restore full color when the unit is in range or no longer hostile. |
| R-AIMSHOT-15 | Range MUST use the hero's current enabled weapon and target filters. |

### 3.3 Targetless attack

| ID | Requirement |
| --- | --- |
| R-AIMSHOT-16 | An aim shot with no valid hostile target MUST play the aim attack animation. |
| R-AIMSHOT-17 | A targetless aim shot MUST spawn one hidden attackable shot proxy at the crosshair point and issue one native shooter attack against it. |
| R-AIMSHOT-17a | An air targetless shot MUST use an attackable air proxy at the crosshair height. |
| R-AIMSHOT-18 | The shot proxy MUST be invisible, unselectable, untargetable by other units, non-scoring, and non-colliding. |
| R-AIMSHOT-18a | The shot proxy MUST accept the shooter attack and MUST NOT be immune to damage. |
| R-AIMSHOT-19 | The shot proxy MUST be removed after the native attack starts, with a short safety timeout. |
| R-AIMSHOT-20 | A targetless aim shot MUST show one gray `Miss` floater at the crosshair point. |
| R-AIMSHOT-21 | The `Miss` position MUST include a random horizontal component. |
| R-AIMSHOT-22 | The `Miss` floater MUST be visible only to the shooting player. |
| R-AIMSHOT-22a | The map MUST keep the native text tag UI frame visible. |
| R-AIMSHOT-22b | The shot proxy MUST NOT create a damage floater, XP award, or kill credit. |
| R-AIMSHOT-22c | Native weapon cooldown, muzzle flash, launch effect, and sound MUST run for every shot. |
| R-AIMSHOT-22d | The shot proxy MUST NOT become the Unit Target, boss bar target, reticle target, click candidate, or hover candidate. |

### 3.4 Hidden aim shooter

| ID | Requirement |
| --- | --- |
| R-AIMSHOT-38 | The aim shooter MUST carry the same weapon as the active hero. |
| R-AIMSHOT-39 | The aim shooter MUST originate at the hero position and use its own weapon hardpoint for native effects. |
| R-AIMSHOT-40 | The aim shooter MUST use the exact crosshair target resolved by the hero. |
| R-AIMSHOT-41 | The aim shooter MUST be created on aim entry and parked on aim exit. |
| R-AIMSHOT-42 | The aim shooter MUST be teleported to the hero muzzle on every aim tick and before every shot. |
| R-AIMSHOT-43 | The aim shooter MUST NOT auto-acquire targets outside an aim shot. |
| R-AIMSHOT-44 | Shooter damage and kill credit MUST map to the active hero player. |
| R-AIMSHOT-45 | The hero weapon cooldown MUST mirror the shooter cooldown after each shot. |

### 3.5 Animation

| ID | Requirement |
| --- | --- |
| R-AIMSHOT-23 | An aim shot MUST play a root-excluded upper attack clip on `SCOBAAimAtk`. |
| R-AIMSHOT-24 | The attack clip MUST blend into and out of the aim pose. |
| R-AIMSHOT-25 | The lower aim animation MUST keep playing during the attack. |
| R-AIMSHOT-26 | Aim pitch updates MUST keep running during the attack. |
| R-AIMSHOT-27 | The aim yaw and pitch MUST survive the attack without snapping forward. |
| R-AIMSHOT-28 | Aim exit, hero switch, and animation reset MUST clear `SCOBAAimAtk`. |
| R-AIMSHOT-29 | Attack clip selection MUST use the started weapon and the root-excluded aim attack clips. |
| R-AIMSHOT-30 | Aim attack clips MUST omit the pitch root bone tracks. |
| R-AIMSHOT-31 | Aim attack MUST NOT pause, clear, or replace `SCOBAUp`. |
| R-AIMSHOT-32 | Aim attack MUST play at 2x animation speed. |

### 3.6 Combat isolation

| ID | Requirement |
| --- | --- |
| R-AIMSHOT-33 | An aim shot MUST NOT change the combat FSM state, auto-attack flag, stand flag, root flag, manual-order flag, or control mode. |
| R-AIMSHOT-34 | Combat auto-attack stepping MUST NOT issue orders while aim mode is active. |
| R-AIMSHOT-35 | Aim exit MUST resume normal combat stepping. |
| R-AIMSHOT-36 | Aim shooting MUST NOT write camera pitch, camera yaw, or camera distance. |
| R-AIMSHOT-37 | Aim shooting MUST NOT change native unit selection. |

## 4. Acceptance Criteria

| ID | Criterion |
| --- | --- |
| AC-AIMSHOT-1 | Press left on an in-range enemy: the hero fires immediately and the enemy takes damage. |
| AC-AIMSHOT-2 | Press left on an out-of-range enemy: no shot fires, the enemy is targeted, and `Out of range` appears. |
| AC-AIMSHOT-3 | Hovering an out-of-range enemy grays the crosshair; moving in range restores color. |
| AC-AIMSHOT-4 | Press left on ground or air: the native attack runs, the attack animation plays, and `Miss` appears at the crosshair. |
| AC-AIMSHOT-5 | The one-tick shot proxy is invisible and leaves no persistent unit. |
| AC-AIMSHOT-6 | The `Miss` position varies between shots and tracks the crosshair. |
| AC-AIMSHOT-7 | Release does not fire a second shot. |
| AC-AIMSHOT-8 | The attack animation starts on press, not release. |
| AC-AIMSHOT-9 | The upper attack blends over the aim pose while the lower body keeps moving. |
| AC-AIMSHOT-10 | The aim yaw and pitch stay on target throughout the attack and after it ends. |
| AC-AIMSHOT-11 | The attack animation plays at 2x speed. |
| AC-AIMSHOT-12 | Aim shots do not change the combat toggles or FSM state. |
| AC-AIMSHOT-13 | Aim shots do not change native selection or camera values. |
| AC-AIMSHOT-14 | Text tags remain visible for all players. |
| AC-AIMSHOT-15 | Native cooldown, muzzle flash, launch effect, and sound run on enemy, ground, and air shots. |
| AC-AIMSHOT-16 | Crosshair targeting is stable across camera yaw and pitch. |
| AC-AIMSHOT-17 | Fast repeated clicks during cooldown produce no extra shot, no animation restart, and no cooldown reset. |
| AC-AIMSHOT-18 | Moving aim shots do not stop, pause, or restart hero locomotion. |
| AC-AIMSHOT-19 | Moving aim shots hit the exact crosshair target, not a nearest-neighbor target. |
| AC-AIMSHOT-20 | The hero never receives an aim attack order. |
| AC-AIMSHOT-21 | Shooter damage and kill credit go to the active hero player. |
| AC-AIMSHOT-22 | The hero weapon cooldown mirrors the hidden shooter cooldown. |