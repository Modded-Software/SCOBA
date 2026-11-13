# ATTACK-ANIMATION-AUDIT: Frozen Lower Body Root Cause

**Date:** 2026-11-13
**Status:** Root cause confirmed. Approved design implemented.
**Requirements:** [REQ-CHARACTER-ANIMATION](requirements/REQ-CHARACTER-ANIMATION.md)
**Specification:** [SPEC-CHARACTER-ANIMATION](specifications/SPEC-CHARACTER-ANIMATION.md)

## 1. Symptom

While attacking, the hero upper body plays the attack.
The lower body freezes at one walk or turn frame.
This happens while stationary, while moving, and while chasing.

## 2. Root Cause

The gameplay units still used the native `Tosh` and `QueenOfBlades` actors.

Those actors start native attack animation:

- Tosh applies `AnimGroupApply Work` on `Abil.attack.ReadyStart`.
- Tosh starts `AnimBracketStart Attack Attack` on `WeaponStart.*.AttackStart`.
- QueenOfBlades applies `AnimGroupApply Ready` on `Abil.attack.ReadyStart`.
- QueenOfBlades starts `AnimBracketStart Attack Spell` or `AnimBracketStart Attack Attack`.

A native attack group or bracket owns the whole model for its duration.
It suspends the lower locomotion layer.
The lower body stops advancing at the frame it was on when the attack started.

The generated model replaced the native `Attack` group with an upper-only group.
The native attack bracket therefore moved only the upper body.
The lower body had no driver during the bracket and stayed frozen.
This is exactly the observed screenshot.

## 3. Why The Previous Fix Failed

The previous fix removed actor events by index:

```xml
<On index="3" removed="1"/>
```

This did not stop the native attack events in game.

Reasons and evidence:

- The campaign dependency data contains no `On removed="1"` example.
  Its only `removed="1"` use is on `TexSets`.
- Indexes are fragile against inherited parent actor events.
- Wrong indexes can remove unrelated parent events.
- A run on 2026-11-13 logged `Unable to create unit actor` for `Kerrigan`.
  That is consistent with removing the wrong inherited event.
- The built map only contained removals, never a verified post-start stop.
- Native attack animation still appeared in game.

Removal by index is rejected for this feature.

## 4. Why The Custom Lower Layer Did Not Save It

The map sent lower locomotion on `SCOBALo` with `AnimPlay`.
That layer was valid once the clip tokens were fixed to comma form.
It still lost to the native attack group and bracket.

- A bracket or applied animation group takes priority over parallel `AnimPlay` layers.
- The native bracket was never removed.
- The custom lower layer cannot outrank it.

## 5. Rejected Designs

| Design | Why rejected |
| --- | --- |
| Remove native events with `<On index="N" removed="1"/>` | Unverified and fragile. Did not work in game. |
| Replace native `Attack`/`Spell`/`Stand Work` groups with upper-only groups | Broken native animation path. Freezes lower when native events run. |
| Stop the native attack bracket at runtime without ordering control | The inherited start can run after the map stop. The map must stop again from a short actor timer. |
| Reuse the native `unitName` with a new `CActorUnit` | SC2 creates both actors and renders the model twice. Never add a duplicate `unitName`. |
| Keep native actor and play custom lower on `SCOBALo` | Bracket priority wins. Lower still freezes. |
| Use `AnimBracketStart SCOBAUp ...` for an `AnimPlay` instance | `SCOBAUp` is an animation instance name, not a bracket. |
| Drive non-aim lower from movement intent plus a hold timer | Redundant with native locomotion and adds a second lower owner. |

## 6. Approved Design

Use clean gameplay unit types and actors. Do not fight native actor events.

Tosh:

- unit type `ToshSCOBA`, parent `Tosh`;
- actor ID `ToshSCOBAUnit`;
- unit name `ToshSCOBA`;
- model `ToshSCOBA`;
- no native attack, work, or ready animation events.

Kerrigan:

- unit type `KerriganSCOBA`, parent `Kerrigan`;
- actor ID `KerriganSCOBAUnit`;
- unit name `KerriganSCOBA`;
- model `KerriganSCOBA`;
- no native attack, work, or ready animation events.

Map init replaces the placed native heroes with these unit types.
Native `Tosh` and `QueenOfBlades` unit types and actors stay untouched.

Model rules:

- keep native Stand, Walk, Stand Left, Stand Right, Stand Work, Attack, and Spell groups;
- add upper-only `Attack Arm Alternate` and `Spell Arm Alternate` clips;
- do not empty tracks, shorten sequences, or rename native tokens;

Runtime rules:

- non-aim lower body is native Stand, Walk, and turn;
- the map writes no lower animation outside aim;
- non-aim attack is one upper `AnimPlay` instance on `SCOBAUp`;
- clear the upper attack on animation completion or weapon stop;
- a fixed timer is only a safety cap;
- `SCOBAUp` and `SCOBALo` are animation instance names, not bracket names.
- no actor stop timers, periodic native stop messages, empty tracks, or renamed native tokens.

## 7. Verification

Build and runtime checks:

1. `ToshSCOBA` and `KerriganSCOBA` unit types exist and parent the native heroes.
2. `ToshSCOBAUnit` and `KerriganSCOBAUnit` use clean unit names and define no native attack events.
3. Map init replaces the placed native heroes with the clean types.
4. Generated models keep native groups and add new upper-only clips.
5. Every configured clip name exists in the generated M3.
6. Attack while stationary keeps lower frame IDs advancing.
7. Attack while moving keeps the native Walk clip advancing.
8. Actor logs contain no duplicate actor for Tosh or Kerrigan.
9. Actor logs contain no invalid `SCOBAUp` or `SCOBALo` message.
10. The map sends no non-aim lower animation.

## 8. Related Runtime Errors

These are not caused by the attack design but pollute logs:

- `FlagArray[Unclickable]` and `FlagArray[Unhighlightable]` writes are denied.
- `Kerrigan` created a substitute sphere on 2026-11-13.

Fix these separately so real animation errors are visible.