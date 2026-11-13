# SPEC-DAMAGE-FLOATERS: Hero Damage Floaters

## 1. Overview

The map uses the native Galaxy text tag system.
One global `UnitDamaged` trigger handles all hero damage.
Every damage event creates one independent floater at the damaged unit's position.
Area-of-effect effects fire the event once per victim, so each victim gets its own floater.
Floaters are not attached to units.

## 2. Event

`gt_DamageFloater` is registered once:

```galaxy
TriggerAddEventUnitDamaged(gt_DamageFloater, null, c_unitDamageTypeAny, c_unitDamageEither, null);
```

Event reads:

- `EventUnit()` - damaged unit.
- `EventUnitDamageSourceUnit()` - damage source unit.
- `EventUnitDamageAmount()` - actual damage taken.

## 3. Hero Filter

Use `gf_HeroPlayerFromUnit(EventUnitDamageSourceUnit())`.
Continue only when the result is a valid hero player.
This limits floaters to the active hero for each player.
Do not use the source player alone; summons and unrelated player units must not create hero floaters.

Skip the targetless aim shot proxy before creating a floater.
The helper `gf_AimShotProxyIs(victim)` returns true for that proxy.
The proxy is removed after the native attack starts.

## 4. Creation

For each valid positive damage event:

1. `TextTagCreate(text, 24, UnitGetPosition(victim), 1.6, true, false, PlayerGroupSingle(player))`
2. `TextTagSetColor(tag, c_textTagColorText, Color(100.0, 25.0, 25.0))`
3. `TextTagSetVelocity(tag, 0.35, 90.0)`
4. `TextTagSetTime(tag, c_textTagTimeDuration, 1.6)`
5. `TextTagSetTime(tag, c_textTagTimeFadeOut, 1.1)`
6. `TextTagShow(tag, PlayerGroupSingle(player), true)`

Text is `IntToString(FixedToInt(Round(damage)))`.
Do not aggregate or delay events.
Do not call `TextTagAttachToUnit` or `TextTagAttachToUnitPoint`.

## 5. Ordering

The floater trigger reads event values only.
It never issues orders, changes combat state, changes animation state, or writes damage.
It MUST NOT call `Wait`.

## 6. Text Tag Frame

`systems/gui_environment.galaxy` MUST keep the native text tag frame visible:

```galaxy
UISetFrameVisible(PlayerGroupAll(), c_syncFrameTypeTextTag, true);
```

Hiding this frame disables all text tags, including damage floaters and level-up tags.
`scripts/validate-map.py` MUST reject a build that hides the text tag frame.

## 7. Module

New file: `systems/damage_floaters.galaxy`.
Functions:

- `bool gt_DamageFloater_Func(bool testConds, bool runActions)`
- `void gt_DamageFloater_Init()`

New trigger global: `trigger gt_DamageFloater`.
Wire `gt_DamageFloater_Init()` in `main.galaxy`.

## 8. Limits

The tag uses the native duration and fade timers.
No manual tag list is stored.
No destruction pass is needed.
If no damage arrives, the system does nothing.

## 9. Verification

1. Build with `scripts/playtest.sh build`.
2. Basic attack an enemy and confirm one number per hit.
3. Use an area attack on several enemies and confirm one number per enemy at each enemy's position.
4. Confirm the number matches observed life loss.
5. Confirm no floater appears for non-hero damage.
6. Confirm floaters rise slowly and expire without leaving tags behind.
7. Confirm combat behavior is unchanged.