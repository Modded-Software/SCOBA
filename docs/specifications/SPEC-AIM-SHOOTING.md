# SPEC-AIM-SHOOTING: Aim-Mode Shooting

**Date:** 2026-11-13
**Status:** Active implementation specification
**Requirements:** [REQ-AIM-SHOOTING](../requirements/REQ-AIM-SHOOTING.md)

## 1. Overview

Aim mode is entered by a right hold in action mode.
A left mouse press while aim is active is an aim shot.
Release never fires a second shot.

Every shot resolves from the crosshair, not the mouse.
An in-range enemy gets one native attack order.
An out-of-range enemy gets a gray `Out of range` floater and no order.
A targetless shot spawns one hidden shot proxy at the crosshair, or at its
ground projection for an air shot, attacks it natively, shows a random `Miss`
at the crosshair, and removes the proxy.

Aim shots do not use the combat controller.
They preserve the combat FSM, auto-attack, stand, root, manual-order, and
control state.

## 2. Module Layout

New module: `systems/aim_shooting.galaxy`.

It owns:

- left-press shot handling;
- crosshair world-point computation;
- crosshair target resolution;
- range checks;
- native shot execution;
- hidden targetless shot proxy;
- targetless `Miss` feedback.

Changed modules:

- `systems/targeting.galaxy`: action-mode left press calls aim shooting.
- `systems/aim.galaxy`: reticle uses the crosshair point.
- `systems/damage_floaters.galaxy`: skip the shot proxy.
- `systems/xp.galaxy`: skip the shot proxy.
- `systems/combat_fsm.galaxy`: skip combat stepping while aim is active.
- `systems/animation_fsm.galaxy`: aim attack state, duplicate suppression.
- `systems/animation_bracket.galaxy`: root-excluded attack instance.
- `systems/animation_aim.galaxy`: pitch stays live during aim attack.
- `core/globals.galaxy`: new state globals.
- `core/constants.galaxy`: new constants.
- `header.galaxy`: new prototypes.
- `main.galaxy`: init the new module.

## 3. Constants

Add to `core/constants.galaxy`:

| Constant | Value | Purpose |
| --- | --- | --- |
| `c_SCOBA_MISS_RADIUS` | `0.75` | Random horizontal Miss offset |
| `c_SCOBA_MISS_HEIGHT` | `1.5` | Miss height above crosshair point |
| `c_SCOBA_AIM_ATTACK_SUPPRESS` | `0.25` | Ignore duplicate native attack event |
| `c_SCOBA_WEAPON_READY_EPSILON` | `0.05` | Weapon cooldown ready threshold |
| `c_SCOBA_SHOT_PROXY_TIMEOUT` | `0.25` | Proxy removal timeout |
| `c_SCOBA_SHOT_PROXY_MIN_RANGE` | `1.0` | Minimum proxy distance |
| `c_SCOBA_SHOT_PROXY_RANGE_MARGIN` | `1.0` | Keep proxy inside weapon range |
| `c_SCOBA_SHOT_PROXY_PLAYER` | `8` | Unused hostile Zerg owner |
| `c_SCOBA_OUT_OF_RANGE_TEXT` | `"Out of range"` | Range floater text |
| `c_SCOBA_MISS_TEXT` | `"Miss"` | Targetless floater text |

Add to `core/animation.galaxy`:

| Constant | Value | Purpose |
| --- | --- | --- |
| `c_ANIM_AIM_ATTACK_BLEND` | `0.1` | Attack blend into and out of aim |
| `c_ANIM_ATTACK_TIME_SCALE` | `2.0` | Attack playback speed |
| `c_ANIM_ATTACK_START_TIME` | `0.35` | Firing/recoil frame to skip windup |
| `c_ANIM_ATTACK_DURATION` | `0.5` | Attack safety cap at 2x speed |
| `c_ANIM_BRACKET_ATTACK` | `"SCOBAAimAtk"` | Shared root-excluded attack instance |

## 4. Globals

Add to `core/globals.galaxy`:

| Global | Type | Purpose |
| --- | --- | --- |
| `gv_aimShots` | `int[8]` | Aim shots issued |
| `gv_aimOutOfRange` | `int[8]` | Out-of-range feedback count |
| `gv_aimShotProxy` | `unit[8]` | Active shot proxy |
| `gv_aimShotProxyUntil` | `fixed[8]` | Shot proxy expiry time |
| `gv_animAimAttackUntil` | `fixed[8]` | Aim attack end time |
| `gv_animAimAttackSuppressUntil` | `fixed[8]` | Ignore duplicate native start |
| `gv_animTargetPitchStep` | `int[8]` | Non-aim target pitch key |
| `gv_animTargetPitchTime` | `fixed[8]` | Non-aim target pitch time |

## 5. Crosshair Point

`point gf_AimCrosshairPoint(int player)`:

1. Return `CameraGetTarget(player)` when the hero is invalid.
2. `origin = gf_AimProxyPoint(player)`.
3. `yaw = CameraGetYaw(player)`.
4. `pitch = CameraGetPitch(player)`; normalize above 180 degrees by subtracting 360.
5. `dirX = Cos(yaw) * Cos(pitch)`.
6. `dirY = Sin(yaw) * Cos(pitch)`.
7. `dirZ = -Sin(pitch)` because SC2 camera pitch is positive down.
8. `maxRange = gf_AimWeaponRange(player)`.
9. When `dirZ < 0`, intersect the ray with the plane at
   `PointGetHeight(CameraGetTarget(player))`.
10. Clamp the ray distance to `0.5..maxRange`.
11. Return `origin + dir * distance`.
12. When no ground intersection exists, use `origin + dir * maxRange`.

The crosshair point is the only target point for aim shots.
Do not use `EventMouseClickedPosXWorld` or `EventMouseClickedPosYWorld` for aim.

`fixed gf_AimWeaponRange(int player)`:

1. Return `UnitWeaponRange(hero, i)` for the first enabled weapon.
2. Return `0` when no weapon is enabled.

`bool gf_WeaponReady(int player)`:

1. Read every enabled weapon.
2. Return true when `UnitWeaponPeriodRemaining(hero, i)` is at or below
   `c_SCOBA_WEAPON_READY_EPSILON`.
3. Return false when no enabled weapon is ready.

The readiness check is the native weapon cooldown.
Do not use the custom `SCOBAAutoAttackStatus` cooldown for the press gate.

## 6. Press And Release

`gt_TargetClick_Func` action-mode left press:

1. Set `gv_aCTIONPRESSED[player] = true`.
2. Store press world point, yaw, and pitch for drag detection only.
3. Clear `gv_unitClickCandidate[player]`.
4. Set `gv_unitPressHighlight[player] = gv_unitHighlight[player]`.
5. When aim is active, call `gf_AimShotPress(player)`.

`gt_TargetRelease_Func` action-mode left release:

1. Clear `gv_aCTIONPRESSED`.
2. Clear `gv_unitClickCandidate` and `gv_unitPressHighlight`.
3. When aim is active, return without firing.
4. When aim is not active, keep the existing action-mode attack behavior.

## 7. Target Resolution

`unit gf_AimTargetAtCrosshair(int player)`:

1. `point = gf_AimCrosshairPoint(player)`.
2. `unit = gf_UnitTargetAtPoint(player, point, true)`.
3. If invalid, `unit = gv_unitClickCandidate[player]`.
4. If invalid, `unit = gv_unitPressHighlight[player]`.
5. Validate every candidate with `gf_UnitTargetValid(player, unit, true)`.
6. Return null when all fail.

Crosshair geometry is the primary aim target source.
UnitClick and Unit Highlight are secondary sources only.

## 8. Shot Execution

`gf_AimShotPress(int player)`:

1. Return when the player is not a hero player.
2. Return when aim is not active.
3. Return when the hero is invalid or dead.
4. Return when `gf_AnimAimAttackActive(player)` is true.
5. Return when `gf_WeaponReady(player)` is false.
7. `point = gf_AimCrosshairPoint(player)`.
8. `target = gf_AimTargetAtCrosshair(player)`.
9. Start the aim attack animation on press.
10. Set `gv_animAimAttackSuppressUntil[player] = now + c_SCOBA_AIM_ATTACK_SUPPRESS`.
11. When `target` is valid:
   1. Call `gf_UnitTargetSet(player, target)`.
   2. When in range, call `gf_AimShotFire(player, target)`.
   3. When out of range, increment `gv_aimOutOfRange` and show `Out of range` at the target.
   4. Return.
12. Clear the previous proxy, then spawn a new proxy at `point`.
13. Clamp the proxy inside weapon range and its Z to the camera-target ground plane.
14. Call `gf_AimShotFire(player, proxy)`.
15. Show `Miss` at `point`.
16. Set the proxy expiry to `now + c_SCOBA_SHOT_PROXY_TIMEOUT`.

`gf_AimShotFire(int player, unit target)`:

1. Return when the target is invalid, dead, or not hostile.
2. Return when `gf_WeaponReady(player)` is false.
3. Return when not in range.
4. Issue one native attack order with `OrderTargetingUnit`.
5. Return when the hero has no attack order after issuance.
6. Increment `gv_aimShots`.
7. Do not call `gf_CombatManualAttack`.
8. Do not write FSM, root, auto, stand, selection, facing, camera, or control state.

`gf_AimWeaponName(player)` returns the first enabled weapon name.
It returns `"Attack"` when no weapon is enabled.
The press animation uses this name.

A native `UnitStartedAttack2` event inside the suppress window is ignored so
the press animation is not restarted.
Outside the window, the native event starts the aim attack normally.
The native event is the cooldown, muzzle flash, launch effect, and sound source.
Clicks before `UnitWeaponPeriodRemaining` reaches zero are ignored before the
animation starts, so they cannot reset the native cooldown or jitter the attack.

## 9. Targetless Shot Proxy

`gf_AimShotProxyCreate(int player, point where)`:

1. Return the existing proxy when it is still valid.
2. Clamp the horizontal spawn distance inside weapon range.
3. Create one `InvisibleTargetDummy` at the clamped point for `c_SCOBA_SHOT_PROXY_PLAYER`.
4. Set state selectable false.
5. Set state status bar false.
6. Set life to a high value.
7. Store `gv_aimShotProxy[player]`.
8. Return the proxy.

`gt_AimShotCleanup_Func` removes expired proxies every 0.05 s.
It reads `gv_aimShotProxyUntil[player]`.
It clears `gv_aimShotProxy[player]` and removes the unit.

The proxy is not a persistent dummy.
It exists only long enough for `UnitStartedAttack2` to fire.
It has no model, no status bar, no selection, no score, no food, and no collision.
It must not create a damage floater, XP award, or kill credit.
`gf_UnitTargetAtPoint`, `gf_UnitTargetValid`, `gf_UnitTargetSet`, and
`gf_IsClickEnemy` MUST reject the proxy, so it never drives the reticle, Unit
Target, boss bar, click candidate, or hover candidate.

## 10. Targetless Miss

`gf_AimMissFloater(int player, point crosshair)`:

1. Add `RandomFixed(-c_SCOBA_MISS_RADIUS, c_SCOBA_MISS_RADIUS)` to X.
2. Add `RandomFixed(-c_SCOBA_MISS_RADIUS, c_SCOBA_MISS_RADIUS)` to Y.
3. Set Z to `PointGetHeight(crosshair) + c_SCOBA_MISS_HEIGHT`.
4. Call `gf_FloaterCreate` with `"Miss"` and `Color(70,70,70)`.

The Miss point comes from `gf_AimCrosshairPoint`, not `CameraGetTarget`.

## 11. Reticle Range Color

`gf_ReticleKindAt(player, point)` gains kind `3`:

- `0` neutral;
- `1` hostile in range;
- `2` friendly;
- `3` hostile out of range.

`gf_ReticleKind(player)` uses `gf_AimCrosshairPoint(player)`.

Flow:

1. Resolve the unit with `gf_UnitTargetAtPoint(player, point, false)`.
2. Return `0` when no unit.
3. When hostile:
   1. When the hero is valid and not in range, return `3`.
   2. Return `1`.
4. Return `2` when owned by the player.
5. Return `0`.

Every reticle layer uses `cursor-target-none.dds`.
Neutral is white, hostile is red, friendly is blue.
`gf_ReticleCreate` sets the enemy desaturation color to gray.
`gt_AimCursorTick_Func` shows the enemy control for kind `1` or `3` and sets
desaturated when kind is `3`.
Full red returns when kind is no longer `3`.
Do not use the native arrow cursor textures.

## 12. Floater Helper

`damage_floaters.galaxy` exposes:

```galaxy
void gf_FloaterCreate(int lp_player, point lp_point, text lp_text, color lp_color);
```

Flow:

1. `TextTagCreate(text, 24, point, 1.6, true, false, PlayerGroupSingle(player))`.
2. `TextTagSetColor(tag, c_textTagColorText, color)`.
3. `TextTagSetVelocity(tag, 0.35, 90.0)`.
4. `TextTagSetTime(tag, c_textTagTimeDuration, 1.6)`.
5. `TextTagSetTime(tag, c_textTagTimeFadeOut, 1.1)`.
6. `TextTagShow(tag, PlayerGroupSingle(player), true)`.

Damage uses red.
`Miss` and `Out of range` use `Color(70,70,70)`.
Do not attach tags to units.
Skip the shot proxy in the damage floater trigger.

## 13. Aim Attack Animation

`gf_AnimAttackStart(player, weapon, target)` changes its aim branch:

```galaxy
if (gv_aIMACTIVE[player]) {
    if (now < gv_animAimAttackSuppressUntil[player]) {
        return;
    }
    gf_AnimAimAttackStart(player, weapon);
    return;
}
```

`gf_AnimAimAttackStart`:

1. Resolve the aim attack state from the weapon.
2. Resolve the clip from `gv_animUpperClip[profile][state]`.
3. Send `MakeMsgAnimPlay("SCOBAAimAtk", clip, c_animFlagFullMatch | c_animFlagNonLooping, c_ANIM_AIM_ATTACK_BLEND, c_ANIM_AIM_ATTACK_BLEND, c_ANIM_ATTACK_TIME_SCALE, c_animTimeVariantAsTimeScale)`.
4. Send `AnimSetTime SCOBAAimAtk c_ANIM_ATTACK_START_TIME 0` to skip the windup.
5. Set `gv_animAimAttackUntil[player] = now + c_ANIM_ATTACK_DURATION`.
6. Keep `gv_animAimUpperOn[player] = true`.
7. Do not touch `SCOBAUp` or `SCOBALo`.

The aim attack clips are root-excluded:

- Tosh removes `BoneSpine01` tracks.
- Kerrigan removes `Bone07` tracks.
- Priority is 12.

`gf_AnimTick` aim branch always calls `gf_AnimUpperSet` and
`gf_AnimAimPitchTick`.
Aim pitch stays live during the attack.
The lower `SCOBALo` animation never stops.

`gf_AnimAimAttackClear` sends `AnimClear SCOBAAimAtk` and resets the attack time.
`gf_AnimReset` calls it.
`gf_AimEnd` clears through `gf_AnimReset`.

## 14. Combat Interaction

`gf_CombatStep` returns early while aim is active.
Aim owns its own movement loop and shot orders.
Combat stepping resumes after aim ends.
No combat flag is written by the aim shot path.
The native `UnitStartedAttack2` event still updates cooldown and weapon effects.

## 15. Reset And Cleanup

`gf_AimEnd` calls `gf_AnimReset`, which clears `SCOBAAimAtk`, the suppress
window, target pitch state, and any active shot proxy.
`gf_HeroSwitchTo` calls `gf_AimEnd`.
Control mode changes route through `gf_AimEnd`.

## 16. Initialization

Add `gt_AimShootingInit_Init()` to `main.galaxy`.
`gt_AimShootingInit_Func` clears:

- `gv_animAimAttackUntil[player] = -1.0`;
- `gv_animAimAttackSuppressUntil[player] = -1.0`;
- `gv_aimShots[player] = 0`;
- `gv_aimOutOfRange[player] = 0`;
- `gv_aimShotProxy[player] = null`.

## 17. Validation

`scripts/validate-map.py` MUST check:

1. `systems/aim_shooting.galaxy` exists.
2. `gf_AimShotPress`, `gf_AimCrosshairPoint`, `gf_AimShotProxyCreate`, and `gf_FloaterCreate` are referenced.
3. The text tag frame stays visible.
4. Aim attack clips exist and omit the pitch root.
5. Aim attack clip priority is 12.

## 18. Test Matrix

| ID | Setup | Action | Expected |
| --- | --- | --- | --- |
| AIMSHOT-1 | Active hero, action mode, aim | press left in-range enemy | one attack on press, damage number, no FSM change |
| AIMSHOT-2 | Active hero, action mode, aim | press left out-of-range enemy | no attack, boss bar target, `Out of range` |
| AIMSHOT-3 | Active hero, action mode, aim | hover out-of-range enemy | enemy reticle desaturated |
| AIMSHOT-4 | Active hero, action mode, aim | hover in-range enemy | enemy reticle full color |
| AIMSHOT-5 | Active hero, action mode, aim | press left ground | native attack, muzzle flash, random `Miss`, no persistent proxy |
| AIMSHOT-6 | Active hero, action mode, aim | release left after press | no second shot |
| AIMSHOT-7 | Active hero, action mode, aim | repeated ground presses | one attack per press, random Miss positions |
| AIMSHOT-8 | Active hero, action mode, aim | aim attack | upper attack blends, lower continues, yaw and pitch stay |
| AIMSHOT-9 | Active hero, action mode, aim | attack with auto on | FSM and toggles unchanged |
| AIMSHOT-10 | Active hero, action mode, aim | Alt + left press | no shot |
| AIMSHOT-11 | Active hero, action mode, aim | switch hero | attack state and proxy cleared |
| AIMSHOT-12 | Active hero, action mode, aim | attack speed | animation runs at 2x |
| AIMSHOT-13 | Active hero, action mode, aim | crosshair over enemy at different camera yaw and pitch | target and reticle stay consistent |
| AIMSHOT-14 | Active hero, action mode, aim | press left air | native attack, muzzle flash, `Miss` at crosshair |
| AIMSHOT-15 | Active hero, action mode, aim | fast clicks during weapon cooldown | no extra shot, no animation restart, no cooldown reset |

## 19. Verification

1. Run `scripts/playtest.sh build`.
2. Run `uv run python -m unittest discover -s scripts/testkit/tests -t scripts`.
3. Run `scripts/playtest.sh launch-check`.
4. Confirm aim attack clips omit the pitch root and use priority 12.
5. Manually test the matrix in game.
6. Confirm no script errors in the game logs.