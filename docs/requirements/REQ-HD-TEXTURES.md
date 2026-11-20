# REQ-HD-TEXTURES: Upscaled Terrain Textures

**Date:** 2026-11-15
**Status:** Derived from the operator's task statements of 2026-11-15. Awaiting
operator review of this text. Built. The specification lists the state of
each requirement and what backs it.

## 1. Scope

This contract binds the tooling that replaces the game's built-in terrain
textures in the built map with 4x upscaled ones.

In scope:

- finding the terrain textures the map paints with;
- reading them from the installed game;
- upscaling them with the `upscale-on-arc` tool;
- putting the results into the built map in place of the built-in files;
- variants of the results, made by different models, and a build flag that
  picks one;
- checks that the results are sound and that the map still loads.

Out of scope: textures of effects and the UI, and of units other than the
two of section 3.6.

Section 3.6 adds model textures as a proof of concept (operator, 2026-11-19).
It is not finished: the specification, section 12, gives its state.

Implementation lives in
[SPEC-HD-TEXTURES](../specifications/SPEC-HD-TEXTURES.md).

## 2. Definitions

- **Terrain texture**: a ground texture the map lists in `t3Terrain.xml`. Each
  has a colour file and a normal map file.
- **Original**: the file as the installed game ships it.
- **Upscaled file**: the original enlarged four times per side.
- **Variant**: one set of upscaled files, named after how it is made.
  **Upscale 4x** uses models that stay close to the original.
  **Generative 4x** uses a generative model that invents detail.
- **Cache**: the folder that holds the upscaled files between map builds.
- **Built map**: `out/SCOBA256.SC2Map`.

## 3. Requirements

### 3.1 Tooling

| ID | Requirement |
| --- | --- |
| R-HD-1 | The tooling MUST be persistent and live under `scripts/`. A map build MUST apply the upscaled files on its own. `out/` MUST NOT be edited by hand. |
| R-HD-2 | The map source `src/SCOBA.SC2Map` MUST NOT hold upscaled files or their catalog entries. |
| R-HD-3 | The tooling MUST find every terrain texture the map paints with from the map's own files and the game's data. The list MUST NOT be typed in by hand. |
| R-HD-4 | The tooling MUST read the originals from the installed game. |
| R-HD-5 | Upscaling MUST use the `upscale-on-arc` tool, at four times per side. |
| R-HD-6 | A second run MUST redo only what changed. Upscaling takes minutes per texture. |

### 3.2 Result

| ID | Requirement |
| --- | --- |
| R-HD-10 | An upscaled file MUST keep the layout of its original: the same compression format, a full mip chain, the same channel meaning, and the bytes the game stores after the last mip. |
| R-HD-11 | An upscaled file MUST show the same picture as its original. Brightness, colour, and surface tilt seen from far away MUST match the original. |
| R-HD-12 | An upscaled file MUST tile as well as its original does. |
| R-HD-13 | The tooling MUST measure R-HD-10 to R-HD-12 and fail when a limit is missed. |
| R-HD-14 | The tooling MUST write comparison images so a person can judge the result. |
| R-HD-15 | One web page MUST show every cached texture of every source. It MUST sort them into categories and let a person filter by category, by plane, and by text. |

### 3.3 Map

| ID | Requirement |
| --- | --- |
| R-HD-20 | The built map MUST use the upscaled file for every terrain texture it paints with, colour and normal map. A map with only some of them MUST fail validation. |
| R-HD-21 | The built map MUST load with no script error, no load failure, and no texture warning in the game logs. |
| R-HD-22 | A build that names no variant and finds no cache MUST succeed, keep the built-in textures, and say so. |
| R-HD-23 | The build flag of R-HD-32 MUST also turn the step off for a build. |
| R-HD-24 | A cache that does not fit the map MUST fail the build with a message that names the fix. |

### 3.4 Variants

| ID | Requirement |
| --- | --- |
| R-HD-30 | The tooling MUST offer two variants, **Upscale 4x** and **Generative 4x**. They differ in the models that upscale the textures. |
| R-HD-31 | The variants MUST exist side by side. Building one MUST NOT change the files of the other. |
| R-HD-32 | One build flag MUST pick the variant the map build applies. Without the flag the build MUST apply Upscale 4x. |
| R-HD-33 | A build MUST fail when the flag names a variant that has no cache, and when its value names no variant. |
| R-HD-34 | R-HD-10 to R-HD-14, R-HD-20, and R-HD-21 hold for each variant. |
| R-HD-35 | The input of Generative 4x colour MUST be the Upscale 4x colour result shrunk to 2048 per side, not the original. |

### 3.5 Growth

| ID | Requirement |
| --- | --- |
| R-HD-40 | Adding another kind of texture, such as doodads, MUST NOT need a change to the extract, upscale, encode, or inject stages. |

### 3.6 Model textures (proof of concept)

| ID | Requirement |
| --- | --- |
| R-HD-50 | The tooling MUST find the textures of the models of every doodad the built map places, and of the units Command Center, psi destroyer, shackled ultralisk, Viking in both forms, Overlord, the Mengsk battlecruiser the map places with its death model, sensor tower, Hellion, Goliath, and the units of R-HD-60, from the map and the game's data. A model file the map itself ships MUST be read from the map. |
| R-HD-51 | A model texture MUST be upscaled four times per side and then shrunk so no side is above 2048. Only Upscale 4x is made. |
| R-HD-52 | A model texture MUST keep its compression format. |
| R-HD-53 | A texture the tooling cannot upscale soundly MUST be left as it is and listed with the reason. |
| R-HD-54 | The built map MUST hold a copy of each such model that names the upscaled textures, and the catalog MUST name the copy. |
| R-HD-56 | A flip book whose cells are known MUST be upscaled so that no cell takes pixels from another cell. A flip book whose cells are not known, or differ between its users, MUST be left as it is. |
| R-HD-55 | R-HD-13, R-HD-21, and R-HD-24 hold for model textures. |

### 3.7 Classic skins

Operator 2026-11-20: "replace all terran and zerg units that have remastered
versions with the remastered ones, upscale additionally where not 2048
already".

| ID | Requirement |
| --- | --- |
| R-HD-60 | The Marine, SCV, Battlecruiser, Hydralisk, Ultralisk, Drone, Hatchery, Lair, and Hive MUST show the models of their classic ("Remastered") collection skin, for every player, whether or not the player owns the skin. Their death, placement, and portrait models MUST be those of the skin, as the skin lists them. |
| R-HD-61 | The swap MUST keep the map's own changes to those model entries (scale, animation speed). |
| R-HD-62 | The Command Center, with its Orbital Command and Planetary Fortress forms, MUST show the classic model too. Its leg footprint (REQ-SCALED-FOOTPRINTS R-FP-10) MUST be measured on the classic model (operator 2026-11-20: "the legs are a tiny bit off need to recalculate footprint"). |
| R-HD-65 | The SCV MUST be drawn at 200% of its stock size (operator 2026-11-20; 150% first). |
| R-HD-63 | The textures of the classic models MUST be upscaled as R-HD-51 says. A texture of 2048 or more on a side is left. |
| R-HD-64 | The 2048 textures of the classic Command Center (colour and normal) MUST be upscaled all the same and kept at 4096 per side. The colour MUST be made by the generative model. Operator 2026-11-20: "texture needs upsampling regardless, it is very low quality"; then "instead of upscale, try the generative model on the classic cc tex and inject the 4096 output non-downsampled". A trial: the operator judges it (O-HD-6). |

### 3.8 Back faces

Operator 2026-11-20, on the psi destroyer: "find all culled / missing faces
... insides of pipes, under surfaces, etc. paint them solid dark gray".
Then, the same day: "texture from front of face mirrored on back instead of
solid color". The second replaces the gray.

| ID | Requirement |
| --- | --- |
| R-HD-70 | Where the eye meets the back of a solid surface of the psi destroyer model, it MUST see the texture of the front of that surface, mirrored, not through the model. This holds for every solid, one-sided surface: the inside of pipes, the underside of plates, the inside of the hull. |
| R-HD-71 | The front of every surface, and the glass and energy parts of the model, MUST look as before. |
| R-HD-72 | The tooling MUST report how many pieces of the model are open and how many open edges they have. |

## 4. Operator Checks

Only a person can judge these. The tooling does not claim them.

| ID | Check |
| --- | --- |
| O-HD-1 | The ground in the game looks sharper than before and keeps its look. |
| O-HD-2 | No seams, grain, or invented patterns show on the ground. |
| O-HD-3 | Lighting on the ground looks as before: no flat or inverted bumps, no new shine. |
| O-HD-4 | The game runs as smoothly as before. |
| O-HD-6 | The classic units look and animate right in the game: stand, walk, attack, death, portrait; the Hive at its scale of the map. |
| O-HD-7 | The psi destroyer shows no see-through holes from any side or from below. What was a hole shows the texture of the surface, with no flicker, and its lighting fits the model. |
| O-HD-5 | Doodads, the Command Center, the psi destroyer, the shackled ultralisk, the Viking in both forms, the overlords, the Mengsk battlecruiser and the explosions of its death, the sensor tower, the Hellion, and the Goliath look sharper and keep their look: edges of leaves, team colour, glow, and shine. |
