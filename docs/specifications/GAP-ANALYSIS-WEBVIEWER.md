# Gap analysis: web viewer renderer vs. the SC2 engine

What the unit viewer (`webviewer/`, patched `mdx-m3-viewer`) does not draw
or draws differently from the game, counted over the unit models, and
ranked.

## Survey

- Command: `bash webviewer/scripts/gap-survey.sh` (tool
  `webviewer/tools/gap-survey.mjs`). Ids below are the tool's.
- Run 2026-11-21: 1530 unit model files (`catalog/unit-files.json`, one
  file per model, shared files counted once); 1529 surveyed, 1 unparsable.
- **Models** = model files using the feature. **Uses** = materials, layers
  or entries using it.
- Scope: unit models only. Skyboxes and doodads without a unit are not
  counted. Doodads have their own sample: see "Doodads".
- A feature counts as used when the file sets it (layer with an image or a
  constant colour; field not at its default; or animated through a
  sequence). Whether the game shows it on screen is not measured.

## Already supported

Standard materials (diffuse, decal, specular, emissive 1 and 2, alpha masks
1 and 2, normal map; blend modes 0 to 5; two-sided; unshaded; team colour),
composite materials (sections drawn in order), displacement materials
(drawn over a copy of the frame; animated strength), UV sets 0 to 3 with
region scale and offset, uncompressed and DXT DDS, mouse-over highlight and
outline. Models past 65536 vertices draw with 32-bit indices
(`wide-index.spec`; survey `wideIndices`: 10 models, e.g.
SpaceStationValerian with 200005); 16-bit indices wrapped and broke them.

Layer UV transform (former A1 and A2, G1; `uv-anim.spec`): offset, angle
and tiling, static or animated, on every bound layer including the normal
map. Rule from WhiteoutFlakes `M3ComposeUvTransform`, which cites the SC2
client: `uv' = 0.5 + S(tiling) * R(angle.z) * (uv - 0.5 - offset)`, angle in
radians. An undriven tiling of 0 reads as 1. Angle x and y are not used
(survey `uvAngleXY`: 33 layers set them). Survey run 2026-11-21: 1663
layers animated, 1690 static. Of the animated layers, 168 belong to
materials no mesh batch draws (particles, ribbons); they wait for E1 and E2
(`bash webviewer/scripts/uv-anim-survey.sh`, `mesh=no`).

Batch draw order (former M3, G2; `draw-order.spec`): opaque batches first
in file order, then blended batches by material priority ascending (higher
on top), ties in file order. Rule from WhiteoutFlakes `TransparentOrder`,
after the client's `CTransparentObject::HasHigherPriority`. Survey run
2026-11-21 (`bash webviewer/scripts/priority-survey.sh`): the order differs
from file order in 526 models; priority is set on 2163 blended and 257
opaque materials (opaque order does not change the picture). Not applied:
the engine's next key, camera distance between blended draws of different
units.

Constant colour layers (former A5; `constant-color.spec`): a layer with
flag 0x400 and no texture draws its colour, not a sample. The colour is
stored b, g, r, a; the value is the rest colour times the rest
`rgbMultiply` (the parser's `brightMult`), an all-zero colour and a
multiply <= 0 reading as unset. No channel select or team colour on such a
layer. Rule from WhiteoutFlakes `M3LayerValue` (mode 2) and `LayerTint`.
Drawn on the diffuse, decal, specular, emissive 1 and 2 and alpha mask
layers. Survey run 2026-11-21 (`constantColour`): diffuse 603, emissive
496, specular 218, alpha mask 128, emissive2 16, alpha mask 2 3, decal 1.
With a texture the flag has no effect. Not applied: an animated colour
(A6) plays its rest value.

Alpha test, cut-out (former M2; `cutout.spec`, patch 0028): a standard
material with `alphaTestThreshold` t > 0 draws only where the product of
its alpha-mask layers is at least min(t / 255, 1); the rest is discarded,
in the pick draw too, so a cut-away pixel takes no mouse hit. The diffuse
alpha does not count. Rule from WhiteoutFlakes `m3_surface_table.cpp` and
`m3_standard.slang` (alpha < threshold is discarded, equal survives).
Each textured mask is first multiplied and offset: value x (brightMult x
colour alpha) + midtoneOffset, before its clamp (patch 0041). Without it
the test cut most of the Giant Yeti and Ursadon bodies (mask multiply 10,
add 1; operator report 2026-11-23). Other layer types do not take
multiply and add yet.
Operator report 2026-11-22: the vine and leaf cards of Zerus Large Tree
drew as dark rectangles (vines 150, leaves 200). Measured: 309 of 1072
samples of the tree are cut away, none added.

Particle emitters, step 1 (part of E1; `particles.spec`, patches 0029 to
0034). Parser `particleemitter.ts` reads PAR_ versions 10 to 24 at the
m3addon offsets; checked against m3addon `m3.py` on one file per version
(8 files, 1119 fields, 0 differences). The renderer runs each emitter on
the CPU: births by rate (remainder carried, spread over the frame), life
from lifespan 1 or a random value up to lifespan 2, start position in the
emission area (point, plane, sphere, box, cylinder, disc; hollow middle),
start velocity (cone, radial, axis, random), the closed-form motion with
drag and vertical acceleration, size, rotation, colour and alpha over the
life (smoothing modes 0 to 4), world or emitter space, flipbook cells by
the two phases. Drawn in the material's blend mode with its layers
(patch 0035): colour is the diffuse plus the emissive layers, alpha the
product of the alpha masks, not the diffuse alpha (WhiteoutFlakes
`m3_standard.slang`); before, masked and emissive-only materials drew as
solid squares. Quads by particle type: billboard (0), tail and trail (1,
10) stretched along the current velocity by max(tail, speed x tail), or
the tail alone with `fixLengthTailParts`; pinned (9) from the birth point
to the particle; terrain (5) flat; emitter-oriented (7) on the emitter
axes. Measured: Battlecruiser tail quads lie along the travel (50 of 50,
cosine above 0.95) and are at least tail x width long; billboards stay
square; the Zerus Tree alpha masks (alpha channel) are bound per draw.
Rules from WhiteoutFlakes
`sc2_kernels_spawn.cpp`, `sc2_kernels_build.cpp`, `sc2_element_math.h`.
Survey 2026-11-22 over the unit models: 782 models, 5009 emitters, all
read; 4884 run (standard material), 105 with a displacement material
run and draw after the frame like displacement meshes (patch 0036: the
frame copy shifted along the normal map, times the strength layer and the
particle alpha; Xel'Naga Shrine 41 of 41 drawn, none with displacement
off), 20 with a composite material are reported as not drawn. Measured: Probe at rest
25 births per second, 9 alive (rate x mean life 9.75); Zerus Tree 31 to 36
of 35 expected; world-space spores stay put when the tree moves.
Colour tracks (SDCC) keep their keys in `\0COL` index entries, which the
parser did not read; particle colours sample them now, per channel
(Nova Defensive Drone threw before the fix). Layer colours still play
their rest value (A6). The skybox charskyparallax_prtmdl_group01 now
shows from inside by its particles alone (`skyboxes.spec`).

Done 2026-11-23 (`particles.spec`, patches 0038 to 0040): tails with
`clampTailParts` (0x40000) are cut to the distance travelled
(Searchlight); PARC copies emit from their own bones at their own rates
into the emitter's particles (Helios: 4 jet fires, end exhaust and fire);
`partEmit` bursts: each animated key the playhead steps over adds its
value once, for emitters and copies (Stalker Attack). Rules from
WhiteoutFlakes; the in-game look is an operator check.

Done 2026-11-23 (`particle-materials.spec`, patch 0042): particles take
the material cut-out like meshes (Helios debris: 11 of 25 quad points
drawn with the test, 25 of 25 without; nothing drawn only with it on).
Per-layer UV sources: a layer with uvSource 6 reads the flipbook cell,
every other layer the whole quad (WhiteoutFlakes `m3_surface_table`).
Blimp steam: centre 15, the four quad corners 0 (before, about a third of
the centre). Patch 0043 parses the two floats after `lengthWidthRatio`
(m3addon `unknownFloat7`, `unknown5AddedV21`), not used yet. Light shafts
(Shadow Battlecruiser, type 9, `lightcone4`): measured steady, 21 to 25
alive at rate 10 in Stand, Stand A, Walk and GLstand 01, with no re-fire
on a loop. The quad, the motion and the UV match WhiteoutFlakes, except
the far-end width scale (`instanceDistance`, a trapezoid). Which m3 field
holds that scale is not confirmed. Operator 2026-11-23: the shafts look
right in game.

Done 2026-11-23 (`particle-ground.spec`, patch 0044): the ground plane.
A flat invisible plane at world z = 0 stands in for terrain. Particles
with `collideTerrain` (PAR_ flags 0x2) that cross it downwards restart at
the contact (push-out 0.05) with the WhiteoutFlakes response: normal speed
x -bounce, tangent x friction while moving, rest below 3 x dt
(`sc2_kernels_move.cpp` CollideElement). `bounce` and `friction` are read
32 and 28 bytes before `particleType`. Helios acid drips: before, they fell
to z -478 with 48-unit tails until their 10 s life ended (they did die:
40 alive at most); now all rest at z 0.05, every drip over 2 s old has
touched down, emitters without the flag never do. Not done:
`spawnOnBounce` children and the bounce count that kills (fields not
located), collide-objects (0x4).

Done 2026-11-23 (`ground-lights.spec`, patches 0045 to 0047): spot lights
(LITE type 2) light the ground plane: colour x intensity x albedo 0.5 x
N.L x the squared near-far window (WhiteoutFlakes `m3_deferred_light`) x
the cone, full inside the hot spot, none past the falloff, along bone -z.
Shadow Battlecruiser: six lit patches, each lit only inside its predicted
cone and range and at least 60 % of it; nothing under the hull's centre or
12 units away; a Marine (no lights) draws the same. Viewer choices, not
confirmed: the albedo, and the angles read as half angles from the axis.
The patch shapes are an operator check. Lights do not light meshes yet (E3).

Done 2026-11-23 (`fresnel.spec`, patch 0048): the layer fresnel term
(F1), psmateriallayer.fx CalcFresnelTerm as WhiteoutFlakes has it: 1 -
|N.V| to the exponent, inverted for mode 2, then saturate(f x
fresnelMaxOffset + fresnelMin), on mesh layers (not particles). Diablo,
Lord of Terror (SpaceDiablo): its emissive plasma layer (x1.3, emissive
x3.3, mode 1) drew over the whole body; mean brightness 220 to 119,
near-white pixels 23.6 % to 0.9 %. Not done: the fresnel mask,
translation and rotation.

Not done (implemented nowhere, no test): particle types 2, 3, 4, 6 and 8 (29 emitters;
drawn as billboards), the terrain type's `instanceAngle` (not parsed),
emitter-oriented axes at birth for world space (the current axes are
used), the pinned type's far-end width (`instanceDistance`), spline and mesh areas (68; spawn at the centre), soft
edges M1, sorting, noise, forces, collision with objects and its children, trailing children, lit
particles, the random flipbook start, the mid-key collapse of random
colour and rotation, relative rotation. PAR_ version 14 (6 emitters, one
file) is skipped and reported: implemented, not verified, because that
file fails earlier on MODL version 24 (P1).

## Gaps by count

### Material types not drawn (`T*`)

| Id | Material type | Models | Uses |
|---|---|---:|---:|
| T11 | lens flare | 28 | 51 |
| T5 | volume (fog, beams) | 26 | 51 |
| T4 | terrain | 16 | 20 |
| T10 | reflection | 10 | 13 |
| T7 | creep | 4 | 4 |
| T9 | splat terrain bake | 3 | 3 |
| T6, T8, T12 | unknown 6, volume noise, buffer | 0 | 0 |

### Model parts not rendered (`E*`, skipped by the parser)

| Id | Part | Models | Entries |
|---|---|---:|---:|
| E1 | particle emitters (PAR_, PARC): step 1, bursts and PARC drawn, see "Already supported"; types 2, 3, 4, 6, 8 left | 783 | 5312 |
| E3 | lights (LITE) | 566 | 1957 |
| E2 | ribbons (RIB_, SRIB) | 203 | 1114 |
| E6 | physics (rigid bodies, joints, cloth) | 149 | 862 |
| E4 | projections: decals, shadow blobs (PROJ) | 87 | 91 |
| E5 | forces and warps (FOR_, WRP_) | 71 | 129 |
| E7 | turret parts, IK (PATU, IKJT) | 66 | 435 |
| E8 | billboards (BBSC): done (patch 0037); types 0 to 6 as WhiteoutFlakes `m3_billboard.cpp`, per frame in world space; Archon and Sentry keep their pose to the camera (`billboards.spec`); at rest (sequence -1) the skin uses no bones, so not shown | 45 | 60 |
| E9 | non-visual: MSEC, ATVL, SSGS, SHBX, TRGD, DMSE | 1510 | 13337 |

### Standard material: layers never read (`L*`)

| Id | Layer | Models | Uses |
|---|---|---:|---:|
| L2 | environment (evio, evio mask) | 484 | 2632 |
| L5 | ambient occlusion | 244 | 947 |
| L1 | gloss | 116 | 267 |
| L4 | light map (bound, not read) | 73 | 328 |
| L3 | height | 34 | 41 |

### Standard material: settings ignored (`M*`)

| Id | Setting | Models | Uses |
|---|---|---:|---:|
| M1 | depth blend falloff (soft edges) | 779 | 2771 |
| M8 | decal lighting, double lambert, clamp output | 142 | 241 |
| M6 | depth prepass | 131 | 164 |
| M7 | transparency depth effects | 80 | 236 |
| M5 | vertex colour / vertex alpha flags | 71 | 197 |
| M9 | excluded from mouse-over highlight | 20 | 31 |
| M10 | background object | 15 | 21 |
| M4 | blend modes 6 and 7 (meaning unknown) | 9 | 14 |
| M11 | environment multipliers | 0 | 0 |

Values seen: `layerBlendType` 2 in 8658 of 8710 materials (others 0, 1,
3); `specType` 0 in 8677 (1 in 33); `emisMode` 2 in 8638 (others 0, 1, 3,
4). The renderer ignores these fields.

### Layer features ignored (`U*`, `A*`, `F*`)

| Id | Feature | Models | Uses |
|---|---|---:|---:|
| A7 | bright multiply / midtone offset not default (meaning unconfirmed) | 1149 | 6713 |
| A8 | noise amplitude set (meaning unconfirmed) | 737 | 13472 |
| F1 | fresnel | 506 | 1557 |
| A3 | flipbook | 464 | 2162 |
| U2 | UV source: reflective cubic environment | 408 | 1198 |
| U6 | UV source: particle flipbook | 395 | 1772 |
| U-normal | normal map on a UV set other than 0 (now read through `getUV` with its own set; implemented, not verified) | 148 | 223 |
| U3 | UV source: reflective spherical environment | 70 | 114 |
| U5 | UV source: planar world z | 64 | 129 |
| A5 | constant colour on an environment mask layer (waits for L2) | 46 | 76 |
| A6 | animated layer colour | 40 | 104 |
| U7 | UV source: cubic environment | 33 | 53 |
| A4 | video texture | 26 | 49 |
| A9 | render target channel | 22 | 37 |
| U15 | UV source: screen space | 15 | 29 |
| U4, U8, U13, U14 | planar local z (11), spherical env (7), planar world x (1) and y (7); sum, a model may count twice | 26 | 30 |

The layer `brightness` field also takes many values (0.5 most often). Its
meaning is unconfirmed; it is listed by the survey, not counted.

### Other (`V*`, `C*`, parser)

| Id | Gap | Models | Uses |
|---|---|---:|---:|
| V1 | vertex colours in the vertex data, not drawn | 153 | 153 |
| C1 | composite section alpha factor (not 1, or animated) | 105 | 556 |
| P1 | model header MODL version 24 not parsed (SMX1KerriganUpgradeSet) | 1 | 1 |

### Displacement: drawn, not exact

Drawn (`displacement.spec`), with two guesses that need the operator:
the shift is the strength in pixels at a 1080 pixel high view, and the
direction is the normal map's tangent-space x and y, not turned to the
screen. Displacement is drawn after everything else.

## Doodads

Doodads (`CActorDoodad`) are in the viewer since 2026-11-22: catalog
`webviewer/tools/build_doodads.py`, tests `doodads-api.spec`,
`doodads-ui.spec`. The counts above do not include them.

- Catalog: 2588 doodads built; 2552 served; 36 have no model file in the
  storage.
- Sample: `DOODAD_SURVEY_STRIDE=7 bash webviewer/scripts/test.sh
  doodads-survey` (`doodads-survey.spec`), run 2026-11-22: every 7th
  doodad, 365 of 2552. All 365 loaded; none was rejected.
- A sample, not a count: multiply by 7 for a rough total.

| Gap | Doodads of 365 | Share |
|---|---:|---:|
| No batch the renderer draws: nothing shows | 46 | 13% |
| Some parts not drawn (material type) | 30 | 8% |

The two rows overlap in 3 doodads: they have vertices, but every part is
a terrain material.

Nothing shows: 43 of the 46 have no vertices at all. By their names these
are particle-only effects (fire, fog, sparks, rain), decals and splats,
lights, and roads. They wait for E1 (particles), E4 (projections), E3
(lights) and T4 (terrain). The kind of each was read from the name, not
measured.

Parts not drawn, by material type: terrain T4 in 17 doodads, lens flare
T11 in 8, creep T7 in 5 (one of the T4 doodads also has a splat bake T9
part). Terrain is far more common here than on units: 17 of 365 sampled
doodads against 16 of 1530 unit models.

Doodad data not applied (no test, not counted):

- child models attached on creation (`Create` sends), `ModelSwap`;
- texture selection sends;
- footprints (the footprint id is listed, nothing is drawn);
- `TexSets`: used as a list filter only;
- the list has no thumbnails or icons.

## Priorities

Rank by models affected, then by how visible the gap is, then by cost. A
feature used only by particle materials waits for particles.

### P1: most models, clearly visible

1. **Particles (E1, 783).** Engines exhaust, weapon glows, ambient
   sparks. With them come the particle material features: soft edges M1
   (779), flipbook A3 and U6 (464, 395), vertex alpha M5. Largest job.
   Step 1 done 2026-11-22 (`particles.spec`), with material layers and
   the tail, pinned, terrain and emitter-oriented quads; bursts, PARC
   copies and tail clamping 2026-11-23; next: the other quad types,
   soft edges.
2. ~~**UV transform and animation (A2 659, A1 534).**~~ Done 2026-11-21
   (`uv-anim.spec`, see "Already supported").
3. ~~**Draw order and cutout (M3 698, M2 534).**~~ Draw order done
   2026-11-21 (`draw-order.spec`), cutout 2026-11-22 (`cutout.spec`); see
   "Already supported".
4. **Environment reflection and fresnel (L2 484, U2 408, U3 70, U7 33,
   F1 506).** Metal and glass shine, rim glows. Needs an environment map
   (the fresnel term is done 2026-11-23, `fresnel.spec`). Medium.
5. ~~**Constant colour layers (A5, 493).**~~ Done 2026-11-21
   (`constant-color.spec`). Left: 46 models with a constant environment
   mask, with L2.
6. **Lights (E3, 566).** Local point lights on models (engine glows that
   light the hull). Medium.

### P2: hundreds of models, or cheap

7. **Confirm A7 and A8 (1149, 737).** Read the fields against the game
   before implementing; the counts may only mean "not at default".
8. **Ambient occlusion (L5, 244).** Small.
9. **Ribbons (E2, 203).** Trails. Medium, shares work with particles.
10. **Vertex colours (V1 153, M5 71).** Small.
11. **Normal map UV set (U-normal, 148).** Implemented with G1; needs a
    test.
12. **Material flags M8 (142), M6 (131), M7 (80).** Small each.
13. **Gloss (L1 116), light map (L4 73), height (L3 34).** Small each.
14. **Composite alpha factors (C1, 105).** Small.
15. **Projections (E4, 87).** Shadow blobs and decals on the ground.
    Medium.
16. **Highlight exclusion (M9, 20).** Tiny; belongs with the mouse-over
    outline.

### P3: few models, or needs more than the model

17. Planar, screen-space and spherical UV sources (U5 64, U15 15, rest
    26).
18. Lens flare (T11 28), volume (T5 26), reflection (T10 10), terrain
    (T4 16), creep (T7 4), splat bake (T9 3). Unit counts; terrain is
    far more common on doodads (see "Doodads").
19. Animated layer colour (A6 40), video textures (A4 26; not fetched
    since patch 0036, the layer stays off and is listed as not drawn,
    BlimpAds), render target
    channels (A9 22), blend modes 6 and 7 (M4 9), background object
    (M10 15).
20. Forces and warps (E5 71) after particles; turrets and IK (E7 66) need
    game data to aim; ~~billboards (E8 45)~~ done 2026-11-22 (patch 0037,
    `billboards.spec`).
21. Physics (E6 149): simulation, little to see in a still viewer.
22. MODL version 24 (P1, 1 model).
23. Not visual, not planned: E9.

## Updating

Rerun the survey after each gap is closed and update the counts here in the
same change. Each closed gap gets a Playwright test in `webviewer/tests/`
(AGENTS.md: verified only by a test that decides pass or fail).
