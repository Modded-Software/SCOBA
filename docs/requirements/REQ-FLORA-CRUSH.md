# REQ-FLORA-CRUSH: crushable flora

Operator requirements, 2026-11-16.

1. Goliaths and Queens remove every generated flora doodad they walk into.
2. Other units (e.g. Marines) remove nothing.
3. Each removed plant plays a destruction effect at its spot:
   - `PhysicsImpactRockMassive` at impact;
   - `PhysicsImpactDustMassive` and `JumpLandDust` after a random 0.1-0.3 s delay each.
4. Effect size follows the plant's size, then 1.5x to 2.0x at random per clip.
5. Each clip's origin jitters randomly in x and y.
6. Effects play at 25 % animation speed and linger until done.
7. Lava hazards (`ZerusLavaGroundCrack`, `ZerusLavaGroundSpire`) keep a distance
   from water.

## Verification

- 1, 2: `scripts/playtest.sh crushtest` (in-game).
- 3-6: operator check (looks and timing).
- 7: build check in `flora.build.check_flora`; lane walk in `scripts/playtest.sh flora`.
