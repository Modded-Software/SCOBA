# SPEC-VIEWER-GHOST: StarCraft: Ghost in the Asset Viewer

**Date:** 2026-11-24
**Status:** Built. The NOD, NAD, NSA, NMS, NOT and DDS surveys (section
9), on the parsers of our nodsdk-scghost fork; NODExport (section 7); the
`ghost` game on the server (sections 5, 8) and in the page; the `nod`
format (section 7). Section 9 names the test runs. Section 10 lists what
only the operator can judge.
Every file layout below carries its source. Only the rows marked [checked]
or [survey] were measured on the real files. A row marked [docs] or [scripts] is a
claim by someone else and may be wrong: section 4.3 lists those found
wrong so far.
**Requirements:** [REQ-VIEWER](../requirements/REQ-VIEWER.md)
**Core:** [SPEC-VIEWER](SPEC-VIEWER.md)

## 1. Identity

| Field | Value |
| --- | --- |
| Game id | `ghost` |
| Label | StarCraft: Ghost |
| Tab text | SC:G (operator 2026-11-25) |
| Formats | `nod` (models, with NAD clips, NSA materials and DDS textures) |
| Datasets | one: `build`, the extracted game build |

## 2. Labels and sources

State:

- **[today]**: in the code. Sections 3 to 8 are [today], with the tests of
  section 9, except where a row says [plan] and except section 11.
- **[plan]**: not in the code: section 11, and the open points of section
  12 that say "not designed" or "not planned".

Source of a fact:

- **[checked]**: measured on the game build of this machine on 2026-11-23,
  with shell tools (file lists, byte dumps, counts). The survey tools of
  section 9 must repeat every such fact.
- **[survey]**: asserted over every file of its kind by
  `webviewer/scripts/ghost-survey.sh` (section 9), on 2026-11-24.
- **[sdk]**: the parsers of the OpenNOD SDK, `nodsdk-scghost`, in our fork
  `Modded-Software/nodsdk-scghost` (upstream `aknavj/nodsdk-scghost`).
- **[docs]**: the format notes in `webviewer/ref/nodsdk-docs` at commit
  `f2110b37`. Not confirmed here.
- **[scripts]**: the helper scripts of the `GhostPC` project on this machine
  (`nod_uvmap.py`, `convert_nova_dt.py`). Outside this repository. Not
  confirmed here.
- **[code]**: the engine reconstruction in `webviewer/ref/scghost-rev` at
  commit `4f1fd243`. Not confirmed here. It is rebuilt from a binary, not
  the game's source: section 4.3 lists a place where it does not fit the
  files. It holds no code that evaluates a clip.

Rules for the sources:

- `nodsdk-docs` and `scghost-rev` state no license. They are read. No code
  is copied from them.
- `nodsdk-scghost` is GPL v3. The Ghost readers are its parsers. Our
  changes are commits in our fork, not patches. The viewer uses them only
  through programs built in the fork (`NODSurvey` today), run as separate
  processes. No SDK code is copied into this repository.
- `nodsdk-radiant` (BSD, LGPL, GPL by file) is read for the level formats
  only.
- `webviewer/scripts/ref-docs-setup.sh` clones all four at pinned commits,
  outside git. `scripts/setup/deps.sh nodsdk` builds the fork's parser
  library and `NODSurvey` into `webviewer/build/nodsdk` (`build/` is a link
  into `WEBVIEWER_WORK`, SPEC-PATHS). GLM, which the
  parsers need, comes from `sudo make init`.
- No game data is in the repository (R-VIEW-9). Tests that need bytes of a
  game file read them from the build at run time.

## 3. Data on the machine

| What | Where | Setting |
| --- | --- | --- |
| The extracted game build | a folder outside git | `GHOST_PATH` |

`GHOST_PATH` is set in `webviewer/local.env`. It has no built-in value.
Unset, or without `3D/Models`, the game is not available (R-VIEW-8) and the
reason names the setting.

Folders the viewer reads [checked]:

| Folder | Files |
| --- | --- |
| `3D/Models` | 1401 `.nod`, 419 `.noc`, 40 `.nmb` |
| `3D/Anims` | 1551 `.nad`, 40 `.nnb`, 3 `.nak` |
| `3D/Motions` | 163 `.nms` |
| `3D/Materials` | 1116 `.dds`, 1 `.tga` |
| `Materials` | 52 `.nsa`, 40 `.xpr`, `shaderlist.txt`, and 11 texture folders with 892 `.dds`, 6 `.tga`, 2 `.nas` |
| `Misc/Templates` | `Global.not`, the only `.not` in the build |
| `Levels` | 8 `.nil`, 8 `.nsd`, 7 `.npd`, 2 `.nlfx` |
| the build's top folder | `MaterialDirs.txt` |

Read in this change: `.nod`, `.nad`, `.nms`, `.nsa`, `.nas`, `.dds`,
`Global.not`, `shaderlist.txt`, `MaterialDirs.txt`. The rest is deferred
(section 11).

A file named by another file is found without regard to case. The motion
set names `zergling_Death.nad`; the folder holds `zergling_death.nad`
[checked]. The index maps lower-case names to the names on disk. Two
files whose names differ only by case are reported.

The dataset signature is a hash over the path, size and change time of the
files read. A reload indexes the build again.

## 4. Formats

All numbers are little-endian [docs]. Names are matched without case
[docs]; [checked] for file names (section 3).

### 4.1 NOD, the model

| Part | Layout | Source |
| --- | --- | --- |
| Version | uint32 at 0. It is 10 in all 1401 files. | [checked] |
| Counts | uint8 at 4, 5, 6, 7: materials, bones, vertex sets, mesh groups | [docs]; fits the 4 files below |
| Bounds | two float3 at 0x0C: box minimum, box maximum | [docs]; plausible in the 4 files |
| Vertex sets | at 0x24, per set: uint32 type, uint32 count. Room for 4. | [scripts]; fits the 4 files |
| Index count | uint32 at 0x44 | [scripts]; fits the 4 files |
| Header size | 92 bytes. The first material name starts at 92. | [checked] on 4 files |
| Material names | 32 bytes each, zero-padded. A name of 32 letters has no zero at its end: 26 of the 1340 names are that long. The name is the 32 bytes up to the first zero. | [docs]; fits the 4 files; lengths [survey] |
| Bones | 64 bytes each: float3 position, 3x3 turn (rows), float3 offset, then 4 bytes; parent at +62, 0xFF for none | [docs], [scripts]; the parent byte [checked] on the 32 bones of `zergling.nod`: each names an earlier bone, the first has 0xFF |
| Bone links | the bytes at +60 and +61 look like the next bone under the same parent and the first bone under this one, 0xFF for none. Not read. | [checked] on `zergling.nod`; the meaning is a reading, not a source |
| Vertices | per set, `count` x stride. Type 0: 32 bytes (position, normal, uv). Type 1: 36 (plus a uint32 palette index). Type 2: 48 (plus 3 float weights and 4 uint8 palette indices; the fourth weight is 1 minus the sum). | [docs]; strides fit the 4 files |
| Vertices with tangents | Types 3, 4, 5: the bytes of type 0, 1, 2 for all vertices, then 36 bytes per vertex (tangent, binormal, normal). Strides 68, 72, 84. | [docs]; strides fit `lurker.nod` |
| Indices | uint16, `indexCount` of them | [docs]; fits the 4 files |
| Mesh groups | 56 bytes each. uint32 material index at 0. 13 uint16 at 4: for each of 4 detail levels a strip count, a list count and a vertex count; then, at 0x1C, the group's vertex count. Bone palette at 0x21. Bone count at 0x35. Vertex set at 0x36. | size [docs]; fields [scripts]; [checked] on 5 groups, see below |
| Bone palette | 20 uint8 at 0x21: the model's bone numbers this group uses. Only the first "bone count" entries are valid; the rest hold stale bytes. | [checked] on 5 groups |
| Group bytes not read | 0x1E, 0x1F (0 in the 5 groups), 0x20 (0 in `crate.nod`, 5 in `zergling.nod`), 0x37 (0) | [checked]; meaning not known |
| Group order | indices and vertices follow group by group; each detail level's strips, then its lists | [scripts] |
| Strips | a repeated index ends a sub-strip; winding alternates; a triangle with two equal indices is dropped | [docs] |
| Markers | uint32 count, then 52 bytes each: uint8 bone, uint8 type, uint16 id, 12 floats (three rows, then a position) | [docs], [code]; size fits the 4 files |
| Blend data | uint32 count, then 24 bytes each | [docs]; the count is 0 in the 4 files |
| Colours | optional: uint32 count, then one uint32 per vertex | [docs]; absent in the 4 files |

The four files [checked]: `crate.nod` (6,044 bytes), `zergling.nod`
(71,088), `nova.nod` (292,904), `lurker.nod` (264,168). With the layout
above, the bytes left after the mesh groups are exactly `8 + 52 x n` for a
whole `n` (0, 4, 39 and 9). That agrees with the sizes of every part.

The order of the parts (material names, bones, vertex sets, indices, mesh
groups, markers, blend data) is also the order [code] reads them in.

The fields inside a mesh group [checked] on the one group of `crate.nod`
and the four of `zergling.nod`:

| Group | Vertex set (0x36) | Set's vertex type | Bone count (0x35) | Valid palette bytes |
| --- | --- | --- | --- | --- |
| `crate` 0 | 0 | 0 | 1 | 1: bone 0 |
| `zergling` 0 | 0 | 0 | 1 | 1: bone 16 |
| `zergling` 1 | 1 | 1 | 20 | 20, all below 32 |
| `zergling` 2 | 1 | 1 | 19 | 19, then one stale byte |
| `zergling` 3 | 2 | 2 | 7 | 7, then stale bytes |

A group with one bone uses the rigid vertex type; the others use the
skinned types. The model has 32 bones. This fits. It is five groups of two
files, not a survey (O-GHOST-1).

The survey over all 1401 files [survey], with the parser of [sdk] (it has
the group fields at 0x21, 0x35 and 0x36, as above) and two additions of our
fork: it reads the blend data and the colours after the markers, and says
how many bytes the layout explains.

| Fact | Over all files |
| --- | --- |
| Read | 1401 of 1401, each to its last byte |
| Vertex sets | 1650: type 0 1379, type 1 154, type 2 102, type 3 11, type 4 3, type 5 1 |
| Mesh groups | 7747. 9 are empty: no index, no vertex. |
| Bones per group | 0 to 20. 0 only in the 9 empty groups. |
| Rigid and skinned | every group with geometry and at most one bone is on a rigid set (type 0 or 3); every other one on a skinned set |
| Palettes | every valid entry is a bone of the model |
| Bone parents | each an earlier bone, or 0xFF |
| Indices | per model, the strip and list counts of all groups and detail levels add up to the index count |
| Vertices | per vertex set, the group vertex counts (0x1C) add up to the set's count |
| Index range | every detail level 0 index is below its group's vertex count |
| Blend data | count 0 in every file |
| Colours | in 4 files |
| Group byte 0x1E | 0, or 2 in 21 groups |
| Group bytes 0x1F, 0x37 | always 0 |
| Group byte 0x20 | 0 to 255, 0 in 2198 groups. Not a count the survey matches. |

### 4.2 NAD, the animation clip

| Part | Layout | Source |
| --- | --- | --- |
| Version | uint32 at 0. It is 4 in all 1551 files. | [checked] |
| Header | 16 bytes: version, track count, flags, float length in frames | [docs]; fits `zergling_stand.nad` (40 tracks, 59 frames) |
| Frame rate | 30 per second | [docs] |
| Track header | 12 bytes: uint32 key count, uint32 bone number, uint32 kind | [checked] on 4 clips; see 4.3 and below |
| Key | 52 bytes: float frame, then float3 value, b, c, d | [docs]; fits the 4 clips |
| Value at time t | `value + t*b + t^2*c + t^3*d`, per axis | [docs] |
| Track kinds | 0: turn, as three angles in degrees. 1: position, added to the rest position. | [docs] |
| Last key | its `c` and `d` hold not-a-number in the one file. It ends the curve; it is not evaluated. | [checked] on one file |
| After the tracks | uint32 tag count, 8 bytes per tag; then a uint32 shape track count | [docs]; [checked] on 4 clips |
| Shape tracks | not read. A clip with a shape track count above 0 is played without them and named. | the count is 0 in the 4 clips |

The 4 clips [checked]: `zergling_stand`, `zergling_walk`, `zergling_run`,
`zergling_idle`. Read with this layout, each ends on its last byte. The
second field is never above 31; the model has 32 bones. The third is 0 or
1. `walk` and `run` hold 4 tags each.

The survey over all 1551 clips [survey], with the parser of [sdk] (12-byte
track header, as above) and our fork's count of the bytes read:

| Fact | Over all clips |
| --- | --- |
| Read | 1551 of 1551, each to its last byte; version 4; flags 0 |
| Tracks | 36472: 33382 turn, 3090 position. No other kind. |
| Keys | 669847, in frame order, inside the clip length |
| Bone numbers | 0 to 127. Whether each fits its model is a check of the motion set, not of the clip. |
| Last key | holds not-a-number in all 36472 tracks |
| Other keys | 6 hold not-a-number |
| Tags | 2168 |
| Shape tracks | none |
| Key joins | the curve of a key, at its end, against the next key's value (error below 0.001, relative): `t` in frames: 587182 of 588762 turn joins, 44396 of 44607 position joins. `t` from 0 to 1: 314874 and 23315. `t` in seconds: 95032 and 14985. So `t` is in frames. |

The joins that miss in frames (1580 turn, 211 position) are not explained.
An angle that wraps by 360 degrees between keys would be one reason; the
survey does not test it.

Bone pose, per bone, parents first [docs]:

1. local = turn(angles) x move(rest position + track position);
2. global = parent's global x local; a bone without a parent takes local;
3. matrix = global x move(-offset).

Bone pose as built (`src/formats/nod/clips.ts`) [checked]:

1. rest place = parent's `offset` - bone's `offset`; a bone without a
   parent: - its `offset`;
2. local = move(rest place + track position) x turn(Z x Y x X, degrees);
3. global = parent's global x local;
4. matrix = global x move(`offset`).

The bone's `position` and `orientation` are not read. With them, the rest
pose of 18 models breaks (O-GHOST-14). With the built reading the rest
pose of `zergling`, `lurker_alt` and `Zangakar` stands at the file
positions to below 1e-4 (worst 3e-8); with the [docs] sign of `offset`
each bone moves by twice its rest place (section 9, `ghost-page`).

A motion set may hold a clip for another model's bones. `zergling.nms` lists
`deathblown`, `nova_death_byZergling.nad`: Nova's side of a paired death.
Its track 11 names bone 32; the zergling has 32 bones. The viewer leaves
such a clip out and names it (section 7).

What decides the open parts of this:

| Part | Source | Decided by |
| --- | --- | --- |
| The meaning of `offset` | [docs] | Decided [checked]: the rest-pose test of section 9. The [docs] sign is wrong (4.3). |
| The range of `t` inside a key | [docs] | Decided [survey]: frames since the key (4.2, key joins). The page probe agrees on the zergling's clips: 18347 of 18352 joins hold in frames, 8315 in 0..1. |
| The order of the three angles | [docs]. [code] has one builder of a turn from three angles, `mathMatrix_Build34`: the X angle first, then Y, then Z, on row vectors. [code] does not show that a clip uses it. | no test of this document. A pose with no clip has all angles 0, so the rest-pose test cannot see the order. It is an operator check (section 10, O-GHOST-9). |

### 4.3 Where the sources are wrong

| Claim | Found |
| --- | --- |
| [docs] NAD track header: 8 bytes (uint32 bone, uint16 kind, uint16 key count) | 12 bytes: key count, bone number, kind, each a uint32 (4.2). The 8-byte form does not fit. |
| [docs] collision meshes are in `3D/Collision` | The build has no such folder. The 419 `.noc` files are in `3D/Models`. |
| [docs] NSA keys `diffuseMap`, `shaderType`, `blendMode` | The 52 files use `texture` (3570 times), `shader` (4231), `blend` (39). `diffuseMap` and `shaderType` do not occur. |
| [docs] file counts ("about 80 models") | 1401 `.nod`. |
| [docs] a material is found in the NSA files | Only 908 of the 1340 material names are in an NSA file [survey]. [code] goes on to a `.nas` file, then to the texture of the same name (4.4). |
| [code] mesh group: bone count at 0x2A, palette at 0x2D, vertex set at 0x42 | A palette at 0x2D and a vertex set at 0x42 lie past the end of a 56-byte group. The files have them at 0x21 and 0x36, and the bone count at 0x35 (4.1). |
| [docs] bone matrix = global x move(-offset) | With that sign each bone moves by twice its rest place. The files fit move(+offset), with the rest place from the offsets (4.2). |

### 4.4 NSA, the materials

Text. A name, then `{`, `key value` lines, `}` [docs]. A line that starts
with `;` or `/`, after blanks, is a comment [code]. The files hold 689 such
lines [survey]. The [sdk] reader read them as names and properties; our
fork skips them.

What the 52 files hold [survey], comments skipped: 4492 material blocks
with 1439 different names. 792 names are defined more than once. 4905 `{`
and 4905 `}`: every block closes. (A count by text search, comments
included, found one block not closed: a commented brace.) A block that
does not close is reported with file and line.

Nested blocks: only the 83 `dynamic` materials hold them (passes and
stages). Their lines stay flat properties of the material. 4 of them have
more than 32 properties, the reader's limit; 8 lines are dropped and
counted. `dynamic` is not drawn (table below), so no drawn material loses
a property.

Which definition of a name counts:

- `Materials/shaderlist.txt` lists 13 archives, in this order [checked]:
  `common`, `effects`, `metal`, `radiant`, `shaders`, `organic`, `lights`,
  `glass`, `wood`, `stone`, `skies`, `3dmaterials`, `constraints`. The
  build has no `organic.nsa` and no `wood.nsa`.
- The engine reads the archives in the order of that list. A name already
  known is skipped: the first definition counts [code].
- 41 `.nsa` files are not in the list: `global`, `menu`, `shell` and 38
  named after level parts. The viewer reads them after the listed ones, in
  name order, with the same first-counts rule. That order is this
  document's choice, not a source (O-GHOST-8).

How a NOD material name becomes a material, in this order [code]:

1. the name is defined in an archive: that definition;
2. a file `<name>.nas` exists: its content, one material in the same text
   form;
3. a texture file of the same name exists: a default material, drawn
   solid and lit, with that texture;
4. else the material `dflt`.

What this means for the 1340 different material names of the 1401 models
(4922 material slots) [survey], by `NODMaterialLibrary` of our fork:

| Names | Slots | Found as |
| --- | --- | --- |
| 908 | 3015 | step 1 |
| 0 | 0 | step 2. The build has 2 `.nas` files; no model names them. |
| 353 | 1744 | step 3. Not in any archive; a texture of that name exists. `zergling` and `chestCrate2` (`crate.nod`) are two of them. |
| 79 | 163 | none of steps 1 to 3: `collide`, `clothattach`, `fakeclip`, `deflector`, `*_physclip`, `hitregion_user*`, `dflt` itself, and names cut at 32 letters |

A group of the last row is not drawn, and named. These names read as
physics and hit shapes; the viewer does not put `dflt` on them. Whether
the game draws them is not known.

Keys the viewer reads [checked that they occur]: `shader`, `texture`,
`texture2`, `glow`, `intensity`, `envmap`, `detail`, `detailscale`,
`blend`, `alphatest`, `alphaop`, `colorop`, `cull`, `zwrite`.

Keys it does not read, by design: the `constraint_*`, `sight*`, `qer_*` and
`sound` keys. They are physics, game logic and editor data.

A `texture` value is a texture name without folder and extension. It is
found by name in `3D/Materials` and the folders under `Materials`, with
`.dds` added [docs]. Text after the first blank in the value is dropped
[docs].

Textures on disk [survey]:

- The archives name 870 different textures. 824 exist as a file. 46 do
  not; one of them is `$lightmap`, which is not a file name.
- 8 texture names exist in more than one folder. `MaterialDirs.txt` lists
  12 folders, `Materials\Colors` first. The viewer takes `3D/Materials`
  first, then the folders in the order of that list. That the game uses
  the list as its search order is not confirmed (O-GHOST-8).
- The list names `Materials\Radiant`. The build has no such folder.
- Materials named `hitRegion_*` and `attach_*` use `texture dflt`.

`shader` values and how they are drawn. The grouping is [docs]; whether it
looks right is an operator check. The files use 64 different values
[survey] in 4231 `shader` lines [checked]. The four most used: `glossenvmap` (875), `normal` (704), `glow`
(598), `masked` (286).

| `shader` | Drawn as |
| --- | --- |
| absent, `default`, `normal`, `detail`, `glossenvmap`, `glossenvmapdetail`, `envmap`, `metalgloss`, `metalenvmap`, `bump`, `bumpenv` | solid, lit, `texture` only |
| `masked`, `etchedmasked` | solid with an alpha cut |
| `glow`, `add`, `fullbright`, `halo` | added to the picture, not lit |
| `alpha`, `alphablend`, `glass`, `etchedglass` | blended |
| `ghostsuit`, `cloak` | solid, lit, `texture` only. The game's own effect is not drawn. |
| `sky`, `invis`, `video` | not drawn, as in the game [docs] |
| a value that starts with `constraint_` (9 values, 645 uses) | not drawn, not named: physics joints, not surfaces |
| any other value | not drawn, and named (R-VIEW-81) |

The rows above the last two hold 25 values with 3218 uses. The last row
is not small: 30 values with 368 uses fall in it [checked], led by
`dynamic` (83), `project` (61), `pageflip` (40), `bumpwater` (23) and
`membrane` (20).

The engine registers 44 shader kinds by name [code]. `normal`,
`alphablend`, `video` and `halo` are in the table above and not among the
44. What the game does with them is not known; the table follows [docs].

A group whose texture file is missing is not drawn, and named.

### 4.5 NMS, the motion sets

Text. `;` starts a comment. A line is a motion name, a `.nad` file name,
then flags, split by blanks or tabs [checked].

Flags seen [checked]: `noloop`, `endpause`, `variable`, `lowpriority`,
`noframereset`, `nofadeout`, `mix`, `fidget`, `nofadein`, `endtag`, `add`,
`resetmotion`, `movespeed`, and one misspelt `lowpriotity`. The viewer
keeps them as data. It acts on none of them (O-GHOST-4).

The survey over all 163 files [survey], with the parser of [sdk] and our
fork's counts of the lines it did not keep:

| Fact | Over all files |
| --- | --- |
| Read | 163 of 163. 100 have a model of the same name. |
| Entries | 2027. None without a clip file; none with more than 8 flags. |
| Flags | the 14 spellings above |
| Clip match | 1073 exact; 676 only without case; 216 only with `.nad` appended to a name without an extension; 62 entries name 20 clips that are not in `3D/Anims` |
| Case twins | no two clips of `3D/Anims` differ only by case |

The viewer finds a clip without case, and appends `.nad` to a name that
has no extension. That the game does so is not confirmed; without the
second rule 216 entries would have no clip.

### 4.6 NOT, the templates

| Part | Layout | Source |
| --- | --- | --- |
| Header | 12 bytes: `NOT\x10`, version 1, template count 1224 | [checked] on `Global.not` |
| Table | starts at 12. 36 bytes each: 32-byte name, uint32 data offset. The first data offset is 44076 = 12 + 1224 x 36. | [docs], [scripts]; [checked] |
| Names and values | the 32 bytes up to the first zero. Bytes after the zero are stale and are not part of the name. | [checked] |
| Template | uint32 count, then 36 bytes each: uint32 id, 32-byte value; then a length and editor bytes | [docs], [scripts] |
| Ids | 0 based-on, 4 model, 15 script, 20 kind, 143 model scale | [docs] |
| Id 13 | the motion set. The uint32 before every value that ends in `.nms` is 13 (217 times). | [checked] |
| Ids 166, 172 | they hold `.nod` names too (55 and 41 times; id 4: 644 times). Their meaning is not known. The viewer reads the model from id 4 only (O-GHOST-10). | [checked] |
| Expansion | in file order. Id 0 inserts the named template at that place. Another id replaces the same id, or is appended. A missing name, a loop, or more than 128 entries refuses the template. | [docs] |

`Global.not` names 577 different `.nod` files, 549 of which exist, and 163
different `.nms` files, 155 of which exist [checked, by text search]. The
id that carries the motion set is not in the notes; the files give it
(id 13, above).

The survey [survey], with `NOTDatabase` of [sdk], each template expanded
through its `basedon` chain:

| Fact | Over all templates |
| --- | --- |
| Read | 1224, every property at full width; no name defined twice |
| Expansion | 1223 expand. `scourge_track` has an empty `basedon` and is refused. |
| Ids past the table | 90 properties use ids 177 to 184. The engine table of [sdk] has 177 entries (ids 0 to 176). What they are is not known. |
| Model (id 4) | 858 templates, 509 names: 757 exact, 49 only without case, 12 only with `.nod` appended, 40 missing |
| Motion set (id 13) | 426 templates, all with a model; 167 names: 361 exact, 9 only without case, 34 only with `.nms` appended, 22 missing |

The text search counts names anywhere in the file; the survey counts the
value each template has after expansion. The two do not count the same
thing.

### 4.7 DDS, the textures

The 1116 files of `3D/Materials` [checked]: 745 DXT1, 307 DXT5, 54 DXT3,
6 DXT2, 4 without a compression code.

- The renderer library's reader takes DXT1, DXT3 and DXT5.
- The 4 files without a code are 32 bits a pixel with a mask for red,
  green, blue and alpha [checked]: `GE_crate_03_bmp`, `sky_Robota_02_Down`,
  `UI_icon_toon`, `ZergTestModel1Bump`. The library's reader has a path
  for such files (`loadUncompressed` in `parsers/dds/image.ts`, a change of
  this repository). Read from its code, it accepts these headers. No test
  has loaded one of the 4.
- The 6 DXT2 files are refused by the library's reader ("Unsupported
  FourCC"). A texture that is refused is named; its group is not drawn
  (O-GHOST-5).
- The 892 `.dds` files in the folders under `Materials` [checked]: 285
  DXT1, 275 DXT3, 253 DXT5, 4 DXT2, 75 without a compression code. The 75
  have the same pixel flags as the 4 above; their bit counts and masks
  were not read. `dds-survey` reads them.
- Over both places: 10 DXT2 files are refused; 79 files have no code.

The survey over every `.dds` of the build [survey], with the parser of
[sdk]. That parser checks only the header; the survey sizes the payload
from the format, the mip levels, the cube faces and the depth.

| Fact | Over all 2275 files (the two places above and `UI`) |
| --- | --- |
| Read | 2275 of 2275 |
| Formats | DXT1 1257, DXT2 10, DXT3 329, DXT5 590, 32-bit ARGB 89 (all with masks `FF0000`, `FF00`, `FF`, `FF000000`). No other. |
| Shape | every side a power of two; 39 cube maps, all with 6 faces; 2 volumes |
| Size | none shorter than its levels; 1735 exact; 540 with bytes over: 263 by 8, 212 by 16, the rest by other amounts |

What the bytes over hold is not known (O-GHOST-12). A reader takes the
declared levels and leaves the rest.

### 4.8 Axes

The game is left-handed with Z up: X right, Y forward [docs]. The viewer
is right-handed with Z up. The export keeps the file's axes, so bones and
clips need no conversion. The format module mirrors Y after skinning and
turns each triangle round. The axes test of section 9 confirms it: as
drawn, 76 of 76 (`crate`), 1372 of 1382 (`zergling`), 5959 of 5961
(`nova`) and 3656 of 3657 (`lurker`) triangles face their vertex normals;
unmirrored, at most 10.

## 5. Categories

### 5.1 `actors`

- One record per template of `Global.not` that expands without refusal and
  whose model file exists.
- A template that is refused is left out, counted and reported with the
  reason.
- Filter: `motion` (buttons): all, with a motion set, without.
- Search: by template name and model name.
- Record data: `template`, `model`, `scale`, `kind`, `script`, `motionSet`,
  `motions` (name, clip, flags).
- "Add all": yes.

### 5.2 `models`

- Every `.nod` of `3D/Models`, by name.
- Filter: `skin` (buttons): all, with bones to animate, without. Read from
  the vertex set types in the file header.
- Record data: the header counts, `motionSet`, `motions`.
- The motion set of a bare model is the `.nms` with the same name, when
  there is one. 100 models have one [checked].
- "Add all": no. 1401 models at once is not a use.

### 5.3 Not in this change

No backdrops: `/api/ghost/backdrops` answers an empty page. No icons.

## 6. From record to instance

| Rule | Detail |
| --- | --- |
| File | `3D/Models/<model>` |
| Scale | an actor: its model scale, the same on every axis; 1 when it has none. A model: 1. |
| Size between games | one game unit is one viewer unit. The header box of `nova.nod` reaches 1.84 up [checked]. Whether that stands right next to the other game is an operator check. |
| Height, angle, tint | 0, 0, none |
| Variants | one |
| Animations | the motions of the record's motion set, by motion name, handed over as the placement's `clips`. The clip file is found without regard to case (section 3). A motion whose clip is missing is left out and reported. Two actors may share one model file and differ in motion set, so the animations belong to the instance, not to the model (core specification, 6.1). |
| Rest animation | `stand`; else the first motion; else none |
| Play rate | 1 |
| Backdrop | never |

Item options: none.

## 7. Format module `nod`

`src/formats/nod/`. Our own code, on the renderer library's model and
instance base classes. It is not a change to the library.

The bytes are read by the parsers of [sdk], not by viewer code. `NODExport`
of our fork exports what the module draws; the server runs it as a child
process. The refusals below are made there.

| Command | Output |
| --- | --- |
| `NODExport nod <in> <out.json> <out.bin>` | `out.bin`: every vertex, 52 bytes (float3 position, float3 normal, float2 uv, uint8[4] bone numbers of the model, float[4] weights), then uint32 triangle indices. Detail level 0; strips turned into triangles, degenerate ones dropped. `out.json`: bounds, material names, bones (parent, position, 3x3 orientation, offset), and per group its material, vertex type, vertex and index range and palette. |
| `NODExport nad <in> <out.json>` | length in frames, 30 frames a second; tracks (bone, kind, keys of 13 numbers: frame, value, b, c, d); tags. Not-a-number as `null`. |
| `NODExport materials <build> <names.txt> <out.json>` | per material name: lookup step of 4.4, source file, properties in file order, texture file of each texture property (relative to the build; `null` when missing). |
| `NODExport catalog <build> <out.json>` | every template, expanded (4.6): name, model, motion set, script, type (id 20), model scale; every motion set with its entries (name, clip, flags); every model with its counts of materials, bones and groups and its vertex types. Names as the files give them; the server matches them to files (section 3). Templates, sets and models that are refused are listed with the reason. |

On a refusal the JSON holds `{"format", "error"}`, the exit code is 1,
and no binary is written.

- The library's base classes give: the place in the scene, culling by a
  sphere, show and hide, the texture loader, and the calls `renderOpaque`
  and `renderTranslucent` once a frame. The module writes the rest:
  parser, buffers, shaders, bone matrices, the pick draw.
- A NOD file has no magic number, only the version 10 at its start. The
  library picks a reader by looking at the bytes. So core hands a `.nod`
  file to this module by its extension (core specification, 6.3), not by
  its bytes.
- Clips are fetched and parsed by this module. They do not pass through
  the library's loader.

Scope G1, static:

- every mesh group, detail level 0 only;
- strips and lists; the materials of 4.4; DDS textures;
- bounds from the header box;
- the pick draw and the solid-only draw of the instance interface;
- every vertex type. Types 3 to 5 are read as 0 to 2; the tangents are
  skipped.

Scope G2, animated:

- bones, the palette of each group, weights;
- NAD clips through the motion set; one clip at a time;
- skinning in the vertex shader.

Refusals (R-VIEW-82), each with the file and the value:

- a version that is not 10 (NOD) or 4 (NAD);
- a vertex type above 5; a count that runs past the end of the file;
- bytes left over that the layout does not explain;
- a bone parent that is not earlier in the list, or a valid palette entry
  outside the bones;
- a group whose bone count is above 20, or whose vertex set is not one of
  the file's;
- a clip track whose bone number is outside the model's bones, or whose
  kind is not 0 or 1.

Capabilities (SPEC-VIEWER 6.2, 16.13): `edges`, the drawn groups'
triangle edges as lines, by `NodInstance.renderEdges`; and
`textureOverride` (R-VIEW-152). A slot is one drawn group with a texture
file; its `source` is that file, relative to the build. A set swaps the
group's texture on that instance alone: the model keeps its own, so two
instances of one model show two skins. `applied` counts the groups that
hold another texture. No team colour, no tint.

A clip that fails is left out; the others play. `attachClips` returns
the clips left out, each with its reason (HTTP status, or the check that
refused it). Core names them in the status and the console (core
specification, 6.4). A model the exporter refused (`{error}` in the
container) fails to load with that message.

The shaders are `public/shaders/nod.vert` and `nod.frag`, served as the
other page shaders. The handler fetches them once; every model waits for
them (the library's blockers). Without them a model fails to load and the
file is named. The model is drawn with Y mirrored after skinning and each
triangle turned round (4.8). Per material (4.4): the shader table gives a kind
`solid`, `cutout`, `add` or `blend`. `sky`, `invis`, `video` and
`constraint_*` are not drawn and not named. An unknown shader, a material
no step finds, a material missing from the export and a missing texture
are not drawn and named in the model's `undrawn` list. `cull cull_off`
draws both sides; else back faces are culled.

Probes for tests (`window.scobaeditor.probe('nod', name, ...)`):

| Probe | Gives |
| --- | --- |
| `layout` | vertex and index counts, stride, bones, material names, group table |
| `groups` | per group: material, kind drawn (null: not drawn), shader, triangles, texture and whether it loaded, why it is not drawn (`undrawn` "material: why", and `why` alone), whether the last frame drew it |
| `bones` | the clip, the playhead, bone matrices and globals now |
| `positions` | skinned positions now (Y mirrored), every n-th vertex; the file's positions of the same vertices |
| `axes` | per triangle: whether its corners face its vertex normals, as drawn and unmirrored |
| `holdAt` | plays clip n, holds the playhead at a time |
| `joins` | key joins of every clip, with `t` in frames and in 0..1 |
| `poseFinite` | whether every bone matrix is finite |
| `boneSpread` | the mean distance of skinned vertices from their main bone, the palette as read and shifted |
| `triangles` | the drawn corners of one group |

Known gaps, not drawn as the game does: environment maps, detail and glow
layers, bump maps, vertex colours, blend shapes, detail levels 1 to 3, key
tags, motion flags, markers.

## 8. As a game module

`src/games/ghost/`:

| Part | Holds |
| --- | --- |
| `server/build.ts` | the settings (`GHOST_PATH`, `NODSDK_EXPORT`), the index of the build, its signature, file lookup without regard to case |
| `server/exporter.ts` | NODExport runs, the cache `<cache>/ghost/<signature>/` |
| `server/container.ts` | the model container |
| `server/catalog.ts` | the two categories from `NODExport catalog`, filters and search |
| `server/index.ts` | `startGhost`: the game for the protocol; `GHOST_GAME`, the id, label and tab text that `server/main.ts` also lists when the game cannot start |
| `page/` | `place`, `describe`, the rest animation, the gallery parts, the texture window (`textures.ts`) |
| `shared/` | the actor and model record types |

`asset` kinds: `texture`, a `.dds` path relative to the build; `material`
by material name, answered as JSON (a control character in the name gives
400); `animation` by clip name, answered as the clip's JSON.

The texture service (operator 2026-11-25, R-VIEW-152): core's service over
the pipeline (`server/core/textures.ts`) for the game `ghost`, dataset
`build`, with no layer. The pipeline's side is SPEC-HD-TEXTURES section
6. The server indexes the dataset at start when the index does not hold
it, and again on a reload, as SC2 does. Its head names the bake reason,
so Bake Skin and Unbake Skin are disabled (R-VIEW-151).

- Asset of a slot (`textureAsset`): the file relative to the build, lower
  case, `\` between folders.
- Owner of an instance (`textureOwner`): an actor row gives
  `actor:<template>`; a model row and a bare model file give
  `model:<asset of the file>`.
- The blue grid glow: an instance that shows a texture of 2048 or more on
  a side, as SC2.

The texture window (operator 2026-11-24): the one window of core
(`page/core/texturewindow.ts`), the same as SC2's, on the texture page
(`/texture-viewer.html`, `page/texview`). It opens with the service: the
states, tiles, Upscale Texture, picks and Save to Skin… of SPEC-VIEWER
17.3; Ghost has no ground button. A double-click on a
gallery row (actors and models), an instance row or an instance in the
view opens it on that model. `page/textures.ts` hands the page every
texture file the model's materials name, decoded with core's DDS decode
(`page/core/ddsdecode.ts`): colour, and alpha when it is not one value.
Each entry carries one fact per material that uses it: shader, how it is
drawn (kind, both sides) or why not (`GroupLook.why`; "hidden by its
shader" for `sky` and the rest of that list), groups and triangles. The
format gives that data (`formats/nod/looks.ts`). A material without a
texture file, and a texture that does not load, are in the page's
problems. Test members: `scobaeditor.textureWindow()` and the page's
`hdtex.entries()`, `hdtex.problems()`, `hdtex.textures()`.

The model container that `/api/ghost/file` serves
(`server/container.ts`; the head constants in `src/shared/nodx.ts`, read
by the format too): `NODX`, uint32 version 1, uint32 JSON length (the
JSON padded with spaces to 4 bytes), the JSON `{model, materials}` or
`{error}`, then the binary of `NODExport nod`. The build also writes
`build/ghost-container.mjs` from it, so `ghost-look.spec` makes its
refused container with the server's code.

When `GHOST_PATH` is not set, when it has no `3D/Models`, or when
NODExport is not built, the game is listed as not available with the
reason. Its routes answer 503 `{error: "game not
available", game, reason}`; the tab is disabled (core specification, 13).

## 9. Tests

Each needs `GHOST_PATH`. Without it the run fails and names the setting;
it does not pass. `ghost-unavailable` is the one that runs without it, on
a second server.

Survey tools (R-VIEW-92), one per format, over every file:

| Tool | Reports |
| --- | --- |
| `nod-survey` | [today]: `NODSurvey nod`, in our fork (`src/tools/nodsurvey/`). Every file read to its last byte; counts per vertex type; the group fields of 4.1; every file refused, with the reason. |
| `nad-survey` | [today]: `NODSurvey nad`. Every clip read to its last byte; track kinds; NaN keys; key joins under three readings of `t`; clips refused. |
| `nsa-survey` | [today]: `NODSurvey nsa`. Every key and `shader` value with its count; comment lines; blocks not closed; nested blocks; properties dropped; names defined more than once; textures missing; for every NOD material name, the step of 4.4 that finds it |
| `nms-survey` | [today]: `NODSurvey nms`. Every flag with its count; entries without a clip or past 8 flags; the clip match class of every entry |
| `not-survey` | [today]: `NODSurvey not`. Every id with its count; templates refused; the model and motion set of every template and their match class |
| `dds-survey` | [today]: `NODSurvey dds`. Every format with its count; mip levels, cube faces, depth; files refused, short, or with bytes over |

The counts of sections 3 and 4 become assertions of these tools.
`webviewer/scripts/ghost-survey.sh` (`make viewer-ghost-survey`) runs the
six surveys and asserts the facts of 4.1, 4.2, 4.4, 4.5, 4.6 and 4.7: 45
assertions. Reports go to `webviewer/build/surveys/`. A survey exits 1
when it finds a file it cannot read, or a fact it reports as not clean
(`not`: the refused template and the ids past the table); the assertions
decide the run.

| Run | Result |
| --- | --- |
| `gs-1` (2026-11-24, fork at `6925432` plus the uncommitted survey) | 17 of 17 passed, exit 0 |
| `gs-neg` | a build folder of 3 models and 2 clips, one of each cut by bytes and one with bytes added: 6 failed, exit 1. Cut files refused, added bytes reported. |
| `gs-unset` | `GHOST_PATH=`: stops with the setting named, exit 1 |
| `gs-2` (2026-11-24, fork code of `f3d434c`) | 45 of 45 passed, exit 0 |
| `gs-neg-nms` | a copy of `3D/Motions` with a line of a name only and a line of 9 flags: the 4 NMS checks of entries and flags failed, exit 1 |
| `gs-neg-not` | `Global.not` cut to half: refused ("invalid NOT template offsets"); all 6 NOT checks failed, exit 1 |
| `ex-1` (2026-11-24, fork `3fce318`, `make viewer-ghost-export-check`) | 18 of 18 passed, exit 0: all 1401 models and 1551 clips export; binary sizes match; materials resolve; changed copies refused (version 9, vertex type 6, cut file, 4 extra bytes; clip version 3, 4 extra bytes), no binary written |
| `ex-2` (2026-11-24, fork `cdef57b`) | 26 of 26 passed, exit 0: the checks of `ex-1`, plus the catalog: 1223 templates and `scourge_track` refused, 858 with a model, 426 with a motion set, 163 sets with 2027 entries, 1401 models; a folder without `3D/Models` refused |
| `gs-neg-dds` | one texture cut to 40000 bytes: reported short (39872 of 87392 bytes); the DDS checks failed, exit 1 |
| `gh1` to `gh8` (2026-11-24) | the Ghost specs while building; their failures and fixes are in the core specification, section 13 |
| `full99` (2026-11-24, HEAD `b2ca220` with step 7 uncommitted, fork `cdef57b`) | the whole viewer suite, the Ghost specs of the table below among it: 349 of 349 passed, exit 0 |

On the server and in the page (Playwright, `webviewer/tests/`):

| Claim | Spec | Test | Negative |
| --- | --- | --- | --- |
| Contract | `ghost-api` | available; one dataset `build`, two categories with the counts of the catalog; filters and search; the shared model; the container; clips and materials as JSON | unknown ids give 404; unsafe paths and wrong kinds are refused |
| Not available | `ghost-unavailable`, `game-tabs` | a server without `GHOST_PATH` lists ghost as not available with the setting named; the tab is disabled with the reason | its routes answer 503; `sc2` still answers |
| Static model | `ghost-page` | `crate.nod`: 1 group, the triangle count of the file, textured; the pick finds it at its pixel | a pixel 300 px beside it, on the canvas, finds nothing |
| Axes | `ghost-page` | above 95% of the triangles of `crate`, `zergling`, `nova`, `lurker` face their vertex normals as drawn | unmirrored: below 5% |
| Rest pose | `ghost-page` | `zergling`, `lurker_alt`, `Zangakar` with no clip: skinned positions equal the file's to 1e-4 | the [docs] sign of `offset` moves bones by more than 0.01 |
| Palette | `ghost-mix` | each skinned vertex is nearer its main bone with the palette as read | read one bone off: the mean distance is above 1.25 times |
| Animation | `ghost-anim` | `zerg_critter`: its set's clips, rest sequence `stand`; the pose moves between two playheads; finite past the end | the same playhead gives the same pose; `crate` (`ghost-mix`) has no sequences and no bone moves |
| Key joins | `ghost-anim` | more joins hold with `t` in frames than in 0..1; raw counts logged | the 0..1 reading |
| Shared model | `ghost-anim` | `zerg_critter` and `zergling_burrowed`, one file: each lists its own set's motions | the two lists differ |
| Clips left out | `ghost-anim` | a clip answered 404 and the foreign `deathblown` are left out; the status says 2; the console names the 404 one. Alone, the foreign clip is named with the bone it lacks | one sequence of the dropped name fewer |
| Materials | `ghost-look` | a `cutout` group of `AR_Plant_Vine_01` is picked inside fewer of its triangles than the solid `crate` (5 points lower or more); `sky` is not drawn and not named (`undrawn` and `why` null) | an unknown shader (`dynamic`) and a material no step finds (`pCannon_collide`) are not drawn; the probe's `why` is the reason and `undrawn` is "material: why" |
| Material lookup | `ghost-mix` | `zergling` and `crate` draw every group with a texture; `undrawn` is empty | |
| Refusal | `ghost-look`; `ex-1` | a container with `{error}` fails to load with its message; the changed files of `ex-1` are refused by NODExport | another model of the game still loads |
| Texture window | `ghost-textures` | the shared window on `/texture-viewer.html`. A double-click on `crate` in the view: one texture, its colour plane first, the fact `material chestCrate2` "drawn solid, groups 0", the picture at the size listed, on the page's card. An actor row (`zerg_critter`) and a models row (`zergling`): `zergling.nod`, the same textures, each with its facts. An instance row of `AR_Plant_Vine_01`: the cutout texture has colour and alpha planes. `dynamic`, `pCannon_collide` and sky give their reasons in words. Layout, measured: the frame fills the window; the list rows have height and do not overlap; the card fits the page. Each entry names its service asset; the page holds the service's state of it; the `crate` instance's owner is `model:3d\models\crate.nod`, its first choice Original. The `crate` window shows the Upscale Texture tile and the rows format, kind, used by. In every entry of `nova`'s window each Details value is at least 60 px wide, and a material fact's value starts below its name (without the two-line rule a value was 33 px) | `SignBracket.dds` of `sign_armory` (16 px) shows "cannot be upscaled: smaller than 32 pixels" and no Upscale Texture tile; no ground button; no texture set choice; nothing is added; opening asks for no variant, skin, bake or removal; a material without a texture file has no entry, only its problem line; a texture answered 404 is named in the problems, and the instance keeps its own |
| Upscale | `ghost-upscale` | with the stand-in runner: `crate`'s texture asks `fast` at its largest allowed factor; the variant is a DXT1 DDS of the size that factor gives, served. Upscale Skin of `BorgoWelcomeSign` makes New Skin 1 naming its texture's variant; the instance that shows it holds an override per group of that texture, and its largest texture is the variant's size; Original again holds none. Upscale Texture from the window's tile, and Upscale Skin from the instance menu with the window open on the sign: the window shows the request tile, then the variant tile, with no reload; the launch output is in the worker's own `TEXTURE_LOGS`. The window on the sign showing New Skin 1: nothing is picked, the New Skin 1 variant has the outline; a click on Original is one pick, and Save to Skin… says "1 of 1 textures change in New Skin 1." with Save enabled. The trash of a variant New Skin 1 names is enabled once another tile is picked; its dialog says the skin uses the original after. Upscale Skin of `actor:Nova` with `novaface04`'s variant accepted: its slots hold overrides, each other texture is in `unshown` | a size no factor gives (8192) is refused with the reason and no variant; the second sign instance and a `crate` stay on Original with no override; a click on the variant New Skin 1 names is no pick; the trash of the variant picked now is disabled; `crate`'s variant misses the seam limit: New Skin 1 on it is shown with no override, the texture in `unshown`, said once on the status line, not again on a second apply, and no error is thrown |
| No bake | `ghost-bake-off` | the head's `bake` is "baking is not enabled for StarCraft: Ghost"; the menu of a `crate` instance on Original shows Unbake Skin disabled, that reason its title | bake and unbake, by owner and by asset, answer 400 with `ghost: <reason>`; `bakes.json` is not written; SC2's head names no reason; an SC2 Marine's menu keeps its own title, "nothing is baked" |
| Edit tools | `texture-edit-button` | the `crate` texture window has the edit tools and an Edit Texture button on its Original tile | opening it opens no edit session |
| Gallery | `ghost-gallery` | the preview names an actor and its model; its add button and a row dragged into the view add it; the `motion` and `skin` buttons give the server's counts; add all adds the listed actors with the landmark `Animated Ghost actors "zergling"`; the game's list names; a dataset reload with nothing changed keeps the signature and the summary | one click adds nothing; a cancelled add all adds nothing; no skinned model under `rigid`; no toast; the SC2 tab names its list its own way; GET and an unknown dataset are refused |
| Contract | `contract` (core) | the shared routes and the shared page flow, run for each available game | unknown ids, categories and datasets give 404 |
| Shader files | `ghost-look` | | `nod.frag` answered 404: the model fails with "nod: 404 /shaders/nod.frag" and is not added |
| Capabilities | `ghost-mix` | the SC2 unit's row has the team control, its state `hd`; the Ghost instance shows Original with no override, its owner its model file | the Ghost row has no team control, its state no `hd`; the SC2 unit's owner is its unit |
| Two games | `ghost-mix` | a unit and a model: selected together, moved, copied, pasted off the view, stored with their games, back after a reload | each comes back as its own game's file |

## 10. Operator checks

- Whether a model looks as it does in the game: colours, see-through
  parts, lighting.
- Whether an animation moves as it does in the game. This is also the
  only check of the angle order (4.2).
- The size of this game's models next to the other game's.
- Whether a `cutout`, `add` or `blend` group looks right: the tests prove
  only which groups are drawn and where the pick finds them.
- The game tabs, the gallery of this game and its filter buttons.
- The look of the texture window on this game's textures (the tests
  measure only that its parts do not overlap).

## 11. Deferred

Not in this change, each [plan] and not designed:

| Item | State |
| --- | --- |
| Icons in the gallery | The build's `UI` textures are not matched to templates; no rule is known. |
| Sky backdrops | Models with `sky` materials (O-GHOST-6). `/api/ghost/backdrops` answers an empty page. |
| Level props | The props of a level (`.nil`, `.nsd`, `.npd`) as a category (O-GHOST-6). |
| Other formats | Model bundles (`.nmb`, `.nnb`), packed textures (`.xpr`), collision meshes (`.noc`), terrain, sound. |
| Shader looks | Environment maps, detail, glow and bump layers of 4.4; `ghostsuit` and `cloak` are drawn solid. |
| Motion flags | Kept as data, not acted on (O-GHOST-4). |
| Foreign clips | Clips for another model's bones are left out and named (O-GHOST-15). |
| DXT2 | 10 textures refused by the library's reader (O-GHOST-5). A reader would be a commit in the library fork with its own test. |

The research points of section 12 (O-GHOST-1, 3, 7, 8, 10 to 14) are
open as written there; this change does not answer them.

## 12. Open points

| ID | Point |
| --- | --- |
| O-GHOST-1 | `nod-survey` passed over all 1401 files (4.1). The rest-pose test passed (section 9). The bytes at 0x1E (0 or 2) and 0x20 (0 to 255) are not understood; 0x1F and 0x37 are always 0. |
| O-GHOST-2 | Closed by the review: id 13 names the motion set (4.6). `not-survey` asserts it. |
| O-GHOST-3 | Closed by `nad-survey`: the 12-byte track header reads all 1551 clips to their last byte, and `t` is in frames (4.2). No clip has shape tracks. Open: 1791 key joins of 633369 miss in frames, not explained. |
| O-GHOST-4 | Motion flags are not acted on. `noloop` could set how a motion starts. Not decided. |
| O-GHOST-5 | 10 DXT2 textures are refused. DXT2 is the DXT3 layout with colour already multiplied by alpha; a reader for it would be a change to the library. Not planned. The 79 files without a code are expected to load; no test has loaded one. |
| O-GHOST-6 | More categories were asked for "where feasible". Candidates: backdrops from models with `sky` materials, and the props of a level. Neither is designed. |
| O-GHOST-7 | An actor's `kind` is a number. Its names are not known, so it is not a filter. |
| O-GHOST-8 | Two orders are this document's choice: the 41 archives that `shaderlist.txt` does not list, and the texture folders. A wrong order gives a model the wrong material or texture where a name is defined twice. Not testable without the game's picture. |
| O-GHOST-9 | The order of the three angles of a turn (4.2) has no programmatic test. |
| O-GHOST-10 | Template ids 166 and 172 hold model names. What they are for is not known. |
| O-GHOST-11 | 79 material names (163 slots) are found by no step of 4.4. They are not drawn. |
| O-GHOST-12 | 540 textures have bytes past their declared levels, most often one block. What they hold is not known. |
| O-GHOST-13 | 90 template properties use ids 177 to 184, past the engine table of [sdk]. `scourge_track` has an empty `basedon`. Both are reported; neither is read. |
| O-GHOST-16 | Every Ghost texture is taken to tile (SPEC-HD-TEXTURES 6.2), so each variant is held to the seam limit. With the tests' stand-in upscaler, 30 of the 31 textures with a role among 40 sampled on 2026-11-25 missed it (`BorgoWelcome.dds` did not). Whether a real upscale keeps the seams, and which Ghost textures do not tile, is not measured. |
| O-GHOST-14 | A bone's `position` is not `parent offset - offset` in 18 models, and its `orientation` is not the identity in some (`lurker_alt`, `Zangakar`, `Goliath_test`, `4_4_Free_Prison`). The rest pose fits the files only with both unread (4.2). What they are for is not known. |
| O-GHOST-15 | Motion sets list clips for another model's bones: the victim's side of a paired death (`zergling.nms`: `deathblown`). They are left out and named. Playing them on the other actor is not designed. |
