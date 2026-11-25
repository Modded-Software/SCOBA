# REQ-TPS: WASD / TPS Mode

**Date:** 2026-11-14
**Status:** Requirements stated by the operator on 2026-11-14. Awaiting
operator review of this text. Built. The specification lists the state of
each requirement and the test run that backs it.

## 1. Scope

This contract binds the control mode named `WASD / TPS` (short: TPS). The code
calls it TPS too.

In scope:

- movement and body orientation in TPS;
- the mouse cursor and the crosshair;
- the free-cursor state;
- the aiming state;
- the aim shot and its outcomes;
- the shot floaters;
- highlight, targeting, and selection in TPS.

Out of scope: `WASD / Point & Click`. Its contract is
[REQ-POINT-AND-CLICK](REQ-POINT-AND-CLICK.md). This phase MUST NOT change its
behavior.

Implementation lives in [SPEC-TPS](../specifications/SPEC-TPS.md).

## 2. Definitions

- **Hero**: the character unit the player controls.
- **Mouse look**: mouse movement turns the camera. No button is held.
- **Crosshair**: the UI image fixed at the screen center.
- **Under the crosshair**: what the camera center ray meets first.
- **Aiming**: the state held by the right mouse button.
- **Free-cursor state**: the TPS state toggled by a middle mouse click. The cursor is shown and mouse look is off. It holds with the button released.
- **Aim shot**: one hero attack started by a left click while aiming.
- **Proxy**: a hidden unit that receives an aim shot which has no enemy to hit.
- **Proxy shot**: an aim shot fired at the proxy.
- **In range**: the hero can hit the target from where it stands.
- **UI target**: the unit shown in the boss bar. It is script state.
- **UI layer**: screen-space UI. It does not depend on a world position being
  on screen.
- **Floater**: short text that appears, drifts, and fades.

## 3. Requirements

### 3.1 Design rule

| ID | Requirement |
| --- | --- |
| R-TPS-1 | The aim shot MUST run the hero weapon's own effect in the engine: damage, muzzle effect, launch effect, sound, and the button clock. The weapon cooldown MUST use the time stated in the weapon data. Script MUST NOT copy any weapon value. Changed 2026-11-14 with O-TPS-4: the text was "a real hero attack"; an attack order stops a walking hero. |
| R-TPS-2 | TPS MUST reuse the Point & Click code for the strafe walk, the UI target, the toggles, the floaters, and the weapon effect handler. It MUST NOT keep a second copy. Changed 2026-11-14 with O-TPS-4: the aim shot no longer uses the Point & Click attack order (R-TPS-1, R-TPS-61). |
| R-TPS-3 | TPS MUST NOT add abilities to the hero. |

### 3.2 Movement and body

| ID | Requirement |
| --- | --- |
| R-TPS-10 | Backpedal MUST always be on. S MUST walk the hero backward. A and D MUST strafe. The hero MUST NOT turn to face its travel direction. |
| R-TPS-11 | The hero torso MUST always follow the camera yaw, standing and moving. |
| R-TPS-12 | While not aiming, the torso MUST NOT follow the camera pitch. |
| R-TPS-13 | While not aiming, the head MUST tilt up or down toward the camera pitch, to the R-TPS-16 look point (operator 2026-11-21; was "slightly"). |
| R-TPS-14 | While aiming, the whole torso MUST follow the camera pitch. The head MUST NOT tilt or lead separately. The torso MUST nod up and down, on every hero; it MUST NOT lean sideways (operator 2026-11-22: Kerrigan's torso turned on the wrong axis). |
| R-TPS-15 | The TPS walk MUST turn and animate as the Point & Click right-hold walk does (R-PNC-68). |
| R-TPS-16 | In TPS, while not aiming, the head MUST look at a point 8 units past the camera target along the view (operator 2026-11-21, "test with 8 first"): it MUST turn sideways and up or down toward it as far as the head range allows (25 degrees sideways, 30 up or down; operator 2026-11-21, was 15) and hold there while the camera is still. It MUST move smoothly and MUST NOT twitch. The torso animation MUST NOT change for this. Operator 2026-11-21 (was 2026-11-16: lead a fast camera turn and settle back; reported as twitching and not looking at the target). |
| R-TPS-18 | Added 2026-11-22 by the operator. Each hero's walk direction clips (strafe, backpedal, diagonals) MUST turn that hero's whole legs: thighs, shins and feet together. Feet MUST NOT stay on the forward walk path while the pelvis turns. The bake MUST be generic: one rig record per hero, no per-hero code. |
| R-TPS-19 | Added 2026-11-22 by the operator. Kerrigan's aim pose MUST breathe: a slow, small, looping motion in place of a still pose. Operator choice: her Psi Blast cast pose, 4 source frames to each side, 4 s per breath. The breath MUST NOT restart when the camera pitch changes. Tosh's aim pose stays still. |
| R-TPS-17 | In TPS with Attack `auto`, while not aiming, Tosh MUST hold the shooting pose between shots as R-PNC-80 to 82 define it, standing and walking. Aiming MUST own the upper body instead. With Attack `single` no pose is held: no shot fires outside the aim. Switching to `single` MUST end the pose at once. The pose MUST NOT follow the camera pitch (R-TPS-12). Operator 2026-11-16. |

### 3.3 Cursor and crosshair

| ID | Requirement |
| --- | --- |
| R-TPS-20 | The mouse cursor MUST be hidden in TPS. |
| R-TPS-21 | Mouse look MUST be on in TPS. |
| R-TPS-22 | The crosshair MUST be shown at the screen center. |
| R-TPS-23 | The crosshair MUST be gray over an enemy that is out of range. |
| R-TPS-24 | The crosshair MUST be green over an enemy that is in range. |
| R-TPS-25 | The crosshair MUST be yellow over a friendly unit. |
| R-TPS-26 | The crosshair MUST have its normal color over anything else. |
| R-TPS-27 | The four crosshair colors MUST contrast clearly with each other and with the terrain. |

### 3.4 Free-cursor state

| ID | Requirement |
| --- | --- |
| R-TPS-30 | In the free-cursor state, mouse look MUST be off. The camera MUST NOT turn. |
| R-TPS-31 | In the free-cursor state, the regular mouse cursor MUST be shown and free for UI interaction. |
| R-TPS-32 | In the free-cursor state, the crosshair MUST be hidden. |
| R-TPS-33 | A middle click MUST enter the free-cursor state. A second middle click MUST leave it and restore mouse look, the hidden cursor, and the crosshair. The state MUST change on the release of the button, never on the press. |
| R-TPS-34 | The Alt key MUST NOT have this function any more. |
| R-TPS-35 | The free-cursor state MUST NOT enter aiming and MUST NOT fire an aim shot. |
| R-TPS-36 | The free-cursor state MUST NOT depend on a held mouse button. The script MUST NOT lock the engine camera input. A switch to Point & Click MUST end the free-cursor state. |
| R-TPS-37 | A middle press and drag MUST NOT scroll the camera, in any state. The engine drag scroll MUST be turned off in the camera data. |

### 3.5 Aiming

| ID | Requirement |
| --- | --- |
| R-TPS-40 | A right hold MUST enter aiming. Releasing it MUST leave aiming. |
| R-TPS-41 | Aiming MUST put the camera on an arm to one side of the hero. |
| R-TPS-42 | The side MUST be one named constant. Its value is `right`. |
| R-TPS-43 | Aiming MUST lower the field of view. Leaving aiming MUST restore it. |
| R-TPS-44 | Leaving aiming MUST restore the camera position and distance. |

### 3.6 Aim shot

| ID | Requirement |
| --- | --- |
| R-TPS-50 | While aiming, a left click MUST fire exactly one hero shot. |
| R-TPS-51 | While not aiming, a left click MUST NOT issue an attack. |
| R-TPS-52 | In-range enemy under the crosshair: the shot MUST hit that enemy and apply its damage. The damage MUST float. |
| R-TPS-53 | Out-of-range enemy under the crosshair: the shot MUST still fire. It MUST be a proxy shot. The enemy MUST take no damage. No text MUST float (R-TPS-79). |
| R-TPS-54 | Ground or sky under the crosshair: the shot MUST fire as a proxy shot. No text MUST float (R-TPS-79). |
| R-TPS-55 | Friendly unit under the crosshair: a real shot MUST fire at that unit. The unit MUST take no damage. No text MUST float (R-TPS-79). |
| R-TPS-56 | Every aim shot MUST show the muzzle effect, play the weapon sound, and play the attack animation, whatever its outcome. |
| R-TPS-57 | Every aim shot MUST start the hero attack cooldown and the cooldown clock on the `Weapon Attack` button (R-PNC-46). |
| R-TPS-58 | A left click while the weapon is on cooldown MUST NOT fire and MUST NOT float any text. |
| R-TPS-59 | The proxy MUST NOT be visible, selectable, targetable by the player, or attackable by any unit other than the hero's aim shot. It MUST NOT block movement. |
| R-TPS-60 | An aim shot MUST NOT move the hero. |
| R-TPS-61 | An aim shot MUST NOT stop or slow a walking hero. |
| R-TPS-62 | A proxy shot whose proxy is above the ground MUST show no hit effect: no impact model and no impact sound. A proxy shot that lands on the ground keeps its hit effect. |
| R-TPS-63 | Added 2026-11-22 by the operator; changed 2026-11-23. Kerrigan's ranged attack MUST be Psi Blast, in both modes and at every distance. The engine MUST use her Razor Talons on its own only with Attack `auto`. |
| R-TPS-66 | Added 2026-11-23 by the operator. In TPS without aim, the left mouse button down MUST swing Kerrigan's Razor Talons at once, with or without a target, and pick the UI target as the click did on release before. It MUST NOT swing while aiming or in Point & Click. The swing MUST hit every enemy in a 90 degree arc in front of her, within 1 of her edge, and no other unit. It MUST play `Attack 01` on her upper body and back talons, in 0.75 s (2x the first 1.5 s fit). Its cooldown MUST be 1 s. F MUST NOT start Order mode; Order is Ctrl + E. |
| R-TPS-64 | Added 2026-11-22 by the operator. A Psi Blast that reaches its target unit MUST deal its damage to that unit, at every distance within range. |
| R-TPS-65 | Added 2026-11-22 by the operator. Kerrigan MUST NOT have the Poison Nova ability. |

### 3.7 Shot floaters

| ID | Requirement |
| --- | --- |
| R-TPS-79 | Changed 2026-11-17 by the operator: the `Miss`, `Out of range`, and `Friendly Fire Disabled` floaters MUST NOT appear, in TPS and in Point & Click (R-PNC-24). R-TPS-70 to 76 and the shot-text part of R-TPS-78 are suspended while the texts are off. Damage numbers stay. |
| R-TPS-70 | `Miss` and `Out of range` MUST appear only when a proxy shot was executed. A mouse press alone MUST NOT create them. |
| R-TPS-71 | `Friendly Fire Disabled` MUST appear only when the shot at the friendly unit was executed. |
| R-TPS-72 | One executed shot MUST create exactly one floater. |
| R-TPS-73 | `Miss` MUST be drawn on the UI layer near the crosshair. It MUST NOT cover the crosshair. It MUST be visible when aiming at the sky. |
| R-TPS-74 | `Miss` MUST NOT be emitted from the proxy and MUST NOT be locked to the ground. |
| R-TPS-75 | `Out of range` and `Friendly Fire Disabled` SHOULD be drawn the same way as `Miss`. |
| R-TPS-76 | `Miss` and `Out of range` MUST be gray. `Friendly Fire Disabled` MUST be yellow. |
| R-TPS-77 | A damage number MUST be larger than before (font size 24). Its size MUST grow with the damage value and MUST reach its largest size at damage 1000. Applies in TPS and Point & Click. |
| R-TPS-84 | The crosshair MUST pick a unit along its whole visible body, not only near its base, also with the sky behind it. It MUST NOT pick a unit when aimed clear above it. |
| R-TPS-85 | No TPS overlay element (crosshair, shot texts) may take mouse input. Hover and click on a unit behind the overlay MUST work in Point & Click and in the free-cursor state, also after shot texts were shown. |
| R-TPS-78 | Every floater MUST start at a random x and y offset: the UI shot texts, the damage numbers, and the Point & Click `Out of range` text. The offset MUST NOT move a UI shot text onto the crosshair. |

### 3.8 Highlight, targeting, selection

| ID | Requirement |
| --- | --- |
| R-TPS-80 | While not aiming, highlight, UI targeting, and selection MUST work as in Point & Click, with the crosshair in place of the cursor. |
| R-TPS-81 | In the free-cursor state, highlight, UI targeting, and selection MUST work as in Point & Click, with the regular cursor. |
| R-TPS-82 | While aiming, a left click MUST NOT change the UI target. A unit that is already the UI target stays the UI target. |
| R-TPS-83 | Switching between TPS and Point & Click MUST leave no input, aim, cursor, or crosshair state from the previous mode active. |

### 3.9 Camera by unit height

| ID | Requirement |
| --- | --- |
| R-TPS-90 | Added 2026-11-19 by the operator. The TPS and Point & Click camera target height above the ground and the default camera arm MUST follow the bound unit's height. Tosh MUST keep 0.9 and 1.5. Every other unit MUST scale both by its height divided by Tosh's. The heights MUST come from the model bounds by a build script, at the scale the unit has in game. A bound unit type MUST have a measured height; the build check MUST fail when one has none. A height asked of no unit or of a type without a measured height MUST stop with a script error, never take another unit's values (operator 2026-11-25: no fallbacks). The Viking keeps its own arm. A morph (Viking landing and lift) MUST switch to the new form's height. Exception 2026-11-20 (operator): after a hero drop touchdown the arm is 1.0 for every unit (REQ-HERO-DROP R-DROP-6); the target height still follows this rule. Changed 2026-11-21 (operator): Tosh is 10 % smaller (actor scale 0.675, was 0.75), and every camera MUST stay as before: Tosh's height for this rule is his height at the old scale. |

## 4. Open Points

The operator has not decided these. The specification names the assumption it
uses for each.

| ID | Point |
| --- | --- |
| O-TPS-1 | Closed. The operator decided: the free-cursor state also turns off backpedal and the torso follow (R-TPS-10, 11). |
| O-TPS-2 | Closed. The operator decided on 2026-11-16: the head also turns sideways, as the lead of R-TPS-16. The R-TPS-13 tilt stays pitch only. |
| O-TPS-3 | Whether the damage floater of R-TPS-52 moves to the UI layer is not decided. The text assumes it stays at the enemy. |
| O-TPS-4 | Closed. The operator decided on 2026-11-14: a shot must not stop or slow the walk (R-TPS-61). R-TPS-1 changed with it. |

## 5. Acceptance Criteria

| ID | Criterion |
| --- | --- |
| AC-TPS-1 | In TPS, not aiming, hold S: the hero walks backward and keeps facing the camera view. Hold A: it strafes left. |
| AC-TPS-2 | In TPS, turn the camera while standing and while walking: the hero facing stays on the camera yaw. |
| AC-TPS-3 | In TPS, not aiming, look up and down: the torso does not pitch. The head tilts slightly. |
| AC-TPS-4 | Aiming, look up and down slowly: the torso pitches. The head does not tilt separately. |
| AC-TPS-4a | In TPS, not aiming, flick the camera sideways or up and down: the head turns ahead of the torso, then settles back. |
| AC-TPS-5 | Enter TPS: the cursor is hidden, the crosshair shows, mouse look is on. |
| AC-TPS-6 | Point the crosshair at an out-of-range enemy, an in-range enemy, a friendly unit, and the ground: it is gray, green, yellow, and normal. |
| AC-TPS-7 | Click the middle button and release it: the camera stops turning, the cursor shows, the crosshair hides. Click it again: all three return. |
| AC-TPS-8 | Press Alt in TPS: nothing changes. |
| AC-TPS-9 | Hold the right button: the camera moves to the side arm and the field of view drops. Release: both return. |
| AC-TPS-10 | Aiming, left click an in-range enemy: one shot, the enemy loses the weapon damage, the damage floats. |
| AC-TPS-11 | Aiming, left click an out-of-range enemy: one shot fires, the enemy loses no life, no text floats. |
| AC-TPS-12 | Aiming, left click the ground and the sky: one shot fires each time, no text floats. |
| AC-TPS-13 | Aiming, left click a friendly unit: one shot fires at it, it loses no life, no text floats. |
| AC-TPS-14 | Aiming, left click three times inside one weapon period: one shot and no shot floater. |
| AC-TPS-15 | Each of AC-TPS-10 to 13: the cooldown clock on `Weapon Attack` starts with the shot. The hero does not move. |
| AC-TPS-16 | Not aiming, left click: no shot and no shot floater. |
| AC-TPS-17 | Aiming, left click an enemy that is not the UI target: the UI target does not change. |
| AC-TPS-18 | Not aiming, left click a unit under the crosshair: it becomes the UI target, as in Point & Click. |
| AC-TPS-19 | Free-cursor state, left click a unit with the cursor: it becomes the UI target, as in Point & Click. |
| AC-TPS-20 | Both heroes hold no more abilities than before this phase. |
| AC-TPS-21 | Switch to Point & Click while aiming and in the free-cursor state: the cursor shows, the crosshair hides, the camera and field of view are restored, and no aim state is left. |
| AC-TPS-22 | Aiming, hold W, left click: one shot fires and the hero keeps its walking speed. |
| AC-TPS-23 | Aiming, left click the sky and an enemy out of range: the shot launches, and no hit effect shows or sounds. Left click the ground in range: the hit effect shows. |
| AC-TPS-24 | Free-cursor state, no button held, move the mouse: the cursor moves; the camera does not scroll and does not turn. |
| AC-TPS-25 | Switch Tosh, Kerrigan, SCV (Alt+1, 2, 3): each one is framed the same way, the camera looking at the same part of the body from the same relative distance. Alt+4, land the Viking: the camera rises to the landed body, it does not sink to the ground. |
