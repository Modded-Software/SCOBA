# REQ-AIR-CREEP: Mutalisks vs Wraiths (proof of concept)

Operator requirements, 2026-11-17. R-AIR-2, 3, 6, 7, 8, 13 and 14 were
revised the same day.

| ID | Requirement |
|---|---|
| R-AIR-1 | Two new unit types: one based on the Mutalisk, one based on the Wraith. |
| R-AIR-2 | Both fly at height 72. |
| R-AIR-3 | Both are 5x the scale of the stock unit. |
| R-AIR-4 | Mutalisks spawn at the Overmind (south-west corner). Wraiths spawn at the Psi Destroyer (north-east corner). |
| R-AIR-5 | Mutalisks belong to Kerrigan (player 4). Wraiths belong to Tosh (player 1). |
| R-AIR-6 | Every 20 s each side spawns one wave. The Terran waves come 10 s after the Zerg waves. The timer runs in real time, like the reinforcement timer. |
| R-AIR-7 | No wave at 0 s. One early wave of each side: Mutalisks 5 s after map start, Wraiths at 10 s (operator 2026-11-20; before: no early wave). The first timed wave is Mutalisks and comes 1 s into the first S7 of the intro, the shot that looks up at the Overmind (S7 starts at 50 s, so at 51 s), so their Birth shows in that shot (operator 2026-11-20; 45 s in S6 was tried: at height 72 they are out of that frame; before that 12 s and 10 s). The Wraiths come one slot later (61 s). Then the 20 s period of R-AIR-6. |
| R-AIR-8 | A wave is two formations: one goes to X Top, one goes to X Bottom. A Terran formation has 3 units (operator 2026-11-17: 4 was tried and was unbalanced). A Zerg formation has 4 to 6 units, chosen at random, 5 on average (operator 2026-11-17: down from 3 to 7, Mutalisks overpowered). On arrival each unit patrols between X Top and X Bottom. |
| R-AIR-9 | No ground attack. |
| R-AIR-10 | They fight only each other, and only when they meet. |
| R-AIR-11 | At most 32 live air creeps per player. |
| R-AIR-12 | The intro is not changed. |
| R-AIR-13 | Faster than the stock units: Mutalisk 3x, Wraith 6x speed and acceleration (operator 2026-11-17: Mutalisk 1.5x the earlier 2x, Wraith 3x the earlier 2x). |
| R-AIR-14 | Mutalisk air weapon range 20x the stock range (operator 2026-11-17: 4x the earlier 5x). Wraith air weapon range equal to the Mutalisk range, 60 (operator 2026-11-17: reduced from 20x, 100). |
| R-AIR-15 | Wraith projectiles fly 2x as fast as before (operator 2026-11-17). |
| R-AIR-16 | Air balance (operator 2026-11-17). Before each wave, count the live air creeps of both sides. Only Mutalisks and Wraiths count. A side with fewer than the enemy spawns 2 more units in that wave. A side with more spawns 2 fewer. Equal counts change nothing. |
| R-AIR-17 | Every Mutalisk of an air creep wave MUST play its birth animation when it appears, every wave (operator 2026-11-20). |

## Verification

- R-AIR-2, 4 to 11, 16: in-game profile `aircreep`, run with
  `scripts/playtest.sh aircreep`.
- R-AIR-1, 3, 13, 14, 15: host test `testkit.tests.test_air_creep`, which reads
  the data. The engine cannot read an actor's scale, so how big the units
  look is an operator check.
- Whether the formations look right in flight: operator check.
- Animation, attack effects and sound: operator check.
