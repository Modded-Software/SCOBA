# SPEC-AIR-CREEP: air creeps

Implements REQ-AIR-CREEP.

## Data (`src/SCOBA.SC2Map/Base.SC2Data/GameData/`)

- **Units** (`UnitData.xml`):
  - `SCOBAMutalisk` has parent `Mutalisk`.
  - `SCOBAWraith` has parent `MengskWraith`. The stock `Wraith` lives in
    liberty.sc2campaign, which VoidStory does not load.
  - Both have `Height` 72 and the attribute `User1`.
  - Speed and acceleration:
    - Mutalisk: 12 and 10.5, 3x stock (stock 4 and 3.5, void.sc2mod; 2x,
      then 1.5x by the operator 2026-11-17).
    - Wraith: 22.5 and 15.75, 6x stock (stock 3.75 and 2.625,
      swarm.sc2campaign; 2x, then 3x by the operator 2026-11-17).
  - `Sight` covers the weapon range (Mutalisk 60, Wraith 60). The weapon
    filter needs `Visible`.
  - Each has one SCOBA weapon.
- **Weapons** (`WeaponData.xml`):
  - `SCOBAAirGlaive` has parent `GlaiveWurm` and effect `GlaiveWurm`.
    `Range` is 60 and `MinScanRange` is 100 (stock 3 and 5; 20x: 5x, then
    4x by the operator 2026-11-17).
  - `SCOBAWraithA` has parent `MengskWraithA` and effect
    `MengskWraithAPersistent`. `Range` is 60 and `MinScanRange` is 60
    (stock 5 and 5). It was 20x (100), then cut to the glaive range by the
    operator 2026-11-17.
  - Wraith missiles fly at 48, 2x the map's `MissileDefault` speed (24)
    (operator 2026-11-17).
    - The mover is `SCOBAWraithMissile` (`MoverData.xml`, parent
      `MissileDefault`).
    - `SCOBAWraithA` keeps the stock launch effects, so its missiles are the
      stock ammo units `MengskWraithAirWeaponLeft` and `-Right`.
      `UnitData.xml` sets their `Mover` to `SCOBAWraithMissile`.
    - No stock MengskWraith is on the map, so no other unit is affected.
  - Stock values with no entry of their own come from the Core `CWeapon`
    default: `Range` 5, `MinScanRange` 5.
  - Both use the target filter `Air,User1,Visible;Missile,Stasis,Dead,Hidden,Invulnerable`.
  - Air and User1 are required, so the two types hit only each other.
- **Glaive bounces** (`EffectData.xml`): `GlaiveWurmE1` and `GlaiveWurmE2`
  search only `Air,User1`. These are stock effects. On this map only
  `SCOBAMutalisk` uses the glaive. The bounce radius (3) is unchanged.
- **Actors** (`ActorData.xml`):
  - `SCOBAMutalisk` has parent `GenericUnitStandard` and model `Mutalisk`.
  - `SCOBAWraith` has parent `GenericUnitBase` and model `MengskWraith`. It
    omits `SOpBankerWraith`, which lives in liberty.sc2campaign.
  - Both have `Scale` 5.
  - An actor whose parent is a concrete actor is not created
    (`validate_pod_actor`), so the parents are templates.
- **Inherited weapons**: a data child keeps its parent's weapons. An indexed
  replace or remove in the child did not take effect (aircreep/20261117-164144,
  -164529). `gf_AirCreepCreate` removes `GlaiveWurm`, `MengskWraithA` and
  `MengskWraithG` with `UnitWeaponRemove`.
  - The removal shows one game tick later. Until then the unit stays hidden,
    because a stock glaive fired in that tick (aircreep/20261117-164924).
  - Pausing the unit does not work: a paused unit keeps its weapons
    (aircreep/20261117-165253).

## Script (`src/SCOBA.SC2Map/scripts/app/systems/air_creep.galaxy`)

- **Home** (`gf_AirCreepHome`): the first `SCOBAOvermind` for Zerg, the first
  `PsiDecimator` for Terran.
- **Owner** (`gf_AirCreepPlayer`): player 4 (Kerrigan) for Zerg, player 1
  (Tosh) for Terran.
- **Wave** (`gf_AirCreepWave`): two formations at home.
  - Formation 1 is centred on home. Formation 2 is centred 18 (3 x spacing)
    to the side, toward the map centre.
  - Formation 1 attack-moves to X Top (region 9). Its queued order is a
    patrol (`move`, command 1) to X Bottom (region 7).
  - Formation 2 does the same with the regions swapped.
- **Formation** (`gf_AirCreepFormation`):
  - Size (`gf_AirCreepFormationSize`): Terran 3. Zerg `RandomInt(4, 6)`, so
    the mean is 5.
  - Slots (`gf_AirCreepSlot`): an octagon of 8 slots, each 6
    (`c_AIR_CREEP_SPACING`) from the centre. The fill order is 90°, 270°,
    180°, 0°, 135°, 315°, 225°, 45°, so any size stays balanced. Opposite
    slots are 12 apart.
  - A wave has at most 12 units (2 x 6). `c_AIR_CREEP_MAX_PER_WAVE` (16,
    two full octagons) is an upper bound used by the test harness wait.
  - At spawn, the slots sit around the spawn centre.
  - Each X gets one formation centre (`gf_AirCreepCentreIn`): uniform over
    a disc of radius 9.5 around the X centre. 9.5 + 6 < 16, so every slot
    target lies inside the X region.
  - Each unit attack-moves to its slot around the first centre, then
    patrols to its slot around the second. All units of a type have the
    same speed, so the formation holds.
  - A unit is skipped while the player has 32 live air creeps.
- **Balance** (`gf_AirCreepBalance`, R-AIR-16):
  - At the start of each wave, before any unit is made, it counts the live
    air creeps: the spawning side's (`gf_AirCreepAlive`) and the enemy's.
    Other air units do not count.
  - It returns a per-formation step (`c_AIR_CREEP_BALANCE_STEP` = 1):
    - fewer than the enemy: +1;
    - more than the enemy: −1;
    - equal: 0.
  - `gf_AirCreepBalanced` adds the step to each formation's base size and
    clamps the result to 1..8. With the current sizes the clamp never
    applies.
  - Two formations, so a wave changes by +2 or −2.
  - Wave sizes:

    | Side | Behind | Equal | Ahead |
    |---|---|---|---|
    | Wraith | 8 | 6 | 4 |
    | Mutalisk | 10-14 | 8-12 | 6-10 |

  - The 32 cap still applies per unit.
  - The test reads the last wave's step, counts and sizes from
    `gv_airCreepLastBalance`, `gv_airCreepBalanceOwn`/`Enemy` and
    `gv_airCreepLastSize1`/`2`.
- **Schedule**:
  - At map init (`gt_AirCreepStart`), the next side is set to Zerg and
    `gv_airCreepTimer` starts. No wave spawns. The timer is periodic, 10 s,
    real time.
  - Each expiry (`gt_AirCreepTick`) flips the next side, then spawns a wave
    for the side whose slot it is.
  - So Mutalisks come first, at 10, 30, 50 s. Wraiths come one slot later,
    at 20, 40, 60 s.
  - Units of one wave are made one after the other, about one game tick
    apart (the weapon removal wait).
- **Lanes**: `gf_GateFromX` (`lanegates.galaxy`) ignores air creeps, so the
  X region triggers do not send them down a lane.
- **Intro**: not touched. The air creep triggers are not in the intro trigger
  list, so they run during the intro.

## Known side effects

- Zerg spore crawlers shoot air units in range. In aircreep/20261117-170156
  a SporeCrawler hit the harness Banshee; the run records such shots as
  `otherHits`. Whether spore crawlers hit patrolling Wraiths is not tested.
- Sight 60 also widens what Kerrigan and Tosh see near the air creeps.
- Tosh owns the Wraiths. Whether the player can select them is an operator
  check.

## Tests

- **In game**: profile `aircreep`, harness
  `scripts/testkit/galaxy/aircreep.galaxy` (helpers, timer, wave) and
  `aircreep_cases.galaxy` (route, fight, ground, cap, balance, trigger).

  | Group | What it checks |
  |---|---|
  | `timer` | The live schedule over the first 42 s: no wave at map start, wave times from the wave counters (Zerg 10 and 30 s, Terran 20 and 40 s), period and phase, and units made between waves. |
  | `wave` | Formation sizes over 600 draws per side. One wave per side: home, owner, orders, formation size per X, slot targets together and distinct, height 72, one weapon. |
  | `route` | Arrival, patrol, and the turn back. |
  | `fight` | A Mutalisk and a Wraith damage each other. |
  | `ground` | No damage event from an air creep on a ground unit, an Overlord, a Banshee or a MengskBC. |
  | `cap` | The 32 limit. |
  | `balance` | Per side: behind (2 vs 10), ahead (10 vs 2) and equal (5 vs 5), with the two presets out of range of each other. Checks the counts read, the step, both formation sizes, units made, and that the other side got none. The `timer` group also checks each live wave's step against the counts it saw. |

- **Host**: `testkit.tests.test_air_creep` checks the data (height, scale 5,
  speed 3x Mutalisk and 6x Wraith, glaive range 20x, Wraith range 60, sight, Wraith missile speed 2x), the filters, the
  constants, the map start (timer armed, Zerg first, no wave) and the
  profile registry.
