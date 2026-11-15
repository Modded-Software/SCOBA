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

Out of scope for this phase: textures of doodads, units, effects, and the UI.
The design must leave room for them (R-HD-40).

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

## 4. Operator Checks

Only a person can judge these. The tooling does not claim them.

| ID | Check |
| --- | --- |
| O-HD-1 | The ground in the game looks sharper than before and keeps its look. |
| O-HD-2 | No seams, grain, or invented patterns show on the ground. |
| O-HD-3 | Lighting on the ground looks as before: no flat or inverted bumps, no new shine. |
| O-HD-4 | The game runs as smoothly as before. |
