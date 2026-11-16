# SPEC-BLOOD-FX

## Runtime (`scripts/app/systems/blood.galaxy`)

- Trigger `gt_BloodDamaged` on any unit damaged event.
- Filters: victim valid, damage > 0, type has `c_unitAttributeBiological`,
  source is not the victim, victim not on `c_BLOOD_COOLDOWN` (0.15 s).
- Spurt: `c_BLOOD_SPURT` at the unit, life `c_BLOOD_SPURT_LIFE` (3 s).
- Splats: `c_BLOOD_SPLAT`, 1 to `c_BLOOD_SPLATS_MAX` (3), 0.2 to
  `c_BLOOD_SPLAT_REACH` (0.8) from the unit, life `c_BLOOD_SPLAT_LIFE` (8 s).
- Scale: linear from `c_BLOOD_SCALE_LO` (0.6) at 0 damage to
  `c_BLOOD_SCALE_HI` (1.6) at `c_BLOOD_DAMAGE_FULL` (100) and up.
- Models are created for all players and kept in a 256-slot ring.
  `gt_BloodSweep` destroys expired models every 0.5 s.
- Counters: `gv_bloodSpurts`, `gv_bloodSplats`, `gv_bloodSkipCooldown`.

## Status

Implemented, not verified. No in-game test exists (operator request).
Look of the models: operator check.
