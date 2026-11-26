# SPEC-HD-TEXTURES: Upscaled Textures

**Date:** 2026-11-24
**Status:** Sections 4 to 7 are design. Variants, skins and bakes (4.3,
4.6, 4.8, 4.9, 5.2, 7) are [plan]. Section 8 gives the state of each
requirement. Sections 13 and 14 are built.
**Requirements:** [REQ-HD-TEXTURES](../requirements/REQ-HD-TEXTURES.md)
**Viewer side:** [SPEC-VIEWER](SPEC-VIEWER.md), section 17.

Names and types of every interface are in the code. This document states
duties and rules.

## 1. Principle

- A variant is made once, on request, on the GPU, and kept in the texture
  store. It is one input variant, one model and one size.
- Variants of one texture stand side by side. Datasets share them.
- A skin names a variant per texture of one owner: a unit, an actor or a
  model file. It lives in its dataset.
- A bake makes a skin the one the package holds for its owner. It is a
  copy of the skin at that moment.
- A package step copies the baked files into the game's data and points
  the game at them. For `scoba` it is the last step of the map build.
- A packaged file has the layout of its original and a new name.
- The core knows no game. A game is an adapter.

## 2. Labels

State: **[host]** a Python `unittest` passed. **[boot]** the map was
launched and the log check passed. **[built]** in the code, no passing
check. **[plan]** not in the code.

Source of an engine fact: **[stock]** read in the game's data.
**[measured]** computed from the game's files. **[boot]** seen in the game
logs of a launch of section 10.

## 3. Engine Facts

StarCraft II.

| ID | Fact | Source |
| --- | --- | --- |
| H1 | The map paints with tile set `Zerus`, textures `Zerus1` to `Zerus8`. | `t3Terrain.xml` |
| H2 | A terrain texture is a `CTerrainTex` entry: `Texture` names the colour file, `Normalmap` the normal map. A terrain set is a `CTerrain` entry; its `BlendTextures` name its terrain textures. | [stock] |
| H3 | The map's 16 terrain files are DXT5, 1024x1024, 11 mips. | [stock] |
| H4 | Colour files hold a specular mask in alpha, values 0 to about 97. | [measured] |
| H5 | Normal maps hold X in alpha and Y in green; red is 255, blue is 0. The file ends in the 4 bytes `_NXD` after the last mip. | [measured] |
| H6 | The game's mips fit averaging in linear light with gamma 2.2. | [measured] |
| H7 | The game keeps a table of texture sizes, keyed by file name alone (`texturereductionvalues.txt`). The meaning of its numbers is a guess. | [stock] |
| H8 | A map catalog that sets `Texture` and `Normalmap` makes the game open the files it names. | [boot] launch 1 |
| H9 | A map file with the name of a table entry and another size is logged as `Texture DB does not match file info`. | [boot] launch 1 |
| H10 | With names the table does not hold, no texture warning is logged. | [boot] launches 2 to 4 |
| H11 | A map with 16 files of 4096x4096 DXT5, about 22 MB each, loads. | [boot] launch 2 |
| H12 | The game data holds 703 `CTerrainTex` and 149 `CTerrain` entries in `core`, `liberty`, `swarm` and `void`. | [stock], 2026-11-24 |
| H13 | A `CModel` declares texture slots by file name: `TextureDeclares Prefix="Goliath_"` with `Adaptions TriggerOnSubstring="_Diffuse" Slot="main"`. 505 such declarations are in the game data. A texture whose name does not start with the prefix has no slot; the game logs "Could not find source texture with slot main". | [stock]; [boot] run `tps/20261124-185130` |

| H14 | An archive holds assets in `base.sc2assets` and in variant folders: one per language (`enus.sc2assets`, `dede.sc2assets`, ...), `teen.sc2assets` and `team.sc2assets`. Of the assets one archive holds: 123 are in base and teen, 12 in base and team, 133 in `enus` alone, 6 in teen alone. 10 base files were compared with their teen files: all 10 differ. The installed game is `enUS`. | [measured] 2026-11-24, build 5.0.17.98310 |

## 4. Core

`scripts/hdtex/core/`. It imports no game (R-HD-107).

### 4.1 Words

| Word | Is |
| --- | --- |
| asset | a texture's name in a dataset's data: lower case, `\` between folders |
| origin | where the original lies: its place in the game's storage, or dataset and asset for a file of the dataset's own layer |
| plane | one picture the upscaler takes: 8-bit RGB PNG |
| role | how a texture splits into planes and joins again |
| model | `pbrify`, `fast` or `seedvr2`: the model of `arc-upscale` the colour planes get |
| variant id | `original`, or the input's id and `model@size`, joined by `+`: `pbrify@2048`, `pbrify@4096+seedvr2@4096`. An edited variant's last part is `edit` with 12 hex digits, `@` and the size (4.3). A step may carry a revision, `model~n@size` with n from 2: `pbrify~2@512` (4.7, R-HD-158). |
| owner | `unit:<CUnit id>`, `actor:<CActor id>` or `model:<model file asset>` |
| skin | a name and a map from asset to variant id, for one owner of one dataset |
| bake | one owner's skin as it was when baked, or one terrain texture's variant |

### 4.2 Interfaces

`core/interfaces.py`. Each is registered by id; the core reaches it by id
only (R-HD-110).

| Interface | One per | Must |
| --- | --- | --- |
| Game adapter | game | name its datasets; take the folder of a dataset's own layer from the caller; list and describe a dataset's textures; give the role of one texture whose role needs its file; give an original as a file; name the origin of every texture file a dataset can show, listed or not; have the originals of many textures at hand in one go; list a dataset's owners, each with its layer, the owners below it and its textures; package the bakes into a target; check a package (R-HD-108) |
| Codec | compression format | decode one mip level to pixels; encode pixels to one level (R-HD-109) |
| Role | channel layout | name its planes, each colour or data; split a texture into them; join them into a mip chain |
| Runner | upscaler | give a version that changes when its pixels would; name the file a job leaves in its output folder; take a plane, a model and an output folder, and give the job's name; say of a job by name whether it waits, runs, is done, failed with a reason, or is lost; say why no waiting job can start |

A texture description holds: asset, origin, the game's kind word, role,
whether it tiles, flip book cells, and its users. A texture that cannot be
upscaled has no role and a reason (R-HD-53). A list may leave a role open
when it needs the texture's file. The role is found when that one texture
is asked for, so a list reads no texture file.

A job is known by the name the runner gave it. Every job has a state: one
the runner does not know is lost, with the queue named.

Second implementations, for tests only (R-HD-111): a made-up game with a
folder as storage, and a runner that enlarges inside the test, with no GPU
and no queue.

The runner `repeat` (`core/repeat.py`) is for the viewer's tests: it
enlarges by pixel repeat the moment a job is given, with no GPU, and its
worker does nothing. `HDTEX_RUNNER` chooses the runner, `arc` when unset;
any other value is refused with the ids. A tiling texture's variant of
`repeat` misses the seam limit: pixel repeat cuts the step between inner
neighbours to a quarter and keeps the step across the edge.

### 4.3 Variants

A variant is named by its id (4.1). Its input is the id before the last
`+`, or the original. Its last part names the model and the size
(R-HD-121, R-HD-124). The id without its last `@size` is the recipe: what
the GPU makes. The variants of one recipe differ only in size, and are
kept in one folder (4.4).

| Model | Colour planes | Data planes | Notes |
| --- | --- | --- | --- |
| `pbrify` | `pbrify` | `fast` | sharper on colour; draws a crosshatch into masks and normal maps (O-HD-10) |
| `fast` | `fast` | `fast` | softer; for dark colour of low contrast too |
| `seedvr2` | `seedvr2` | `fast` | invents detail, so colour only (R-HD-122) |

- A texture without a colour plane takes `fast` only. A request with
  `pbrify` or `seedvr2` for it is refused with the reason. A skin request
  for many textures (4.6) gives such a texture `fast` at the same size.
- Factors: 2x and 4x (operator 2026-11-26). A request names a factor; its
  size is the factor times the input's longest side, at most the largest
  side and at most the recipe's own size (`variants.factor_side`). The
  largest side is `TEXTURE_MAX_SIDE`: 1024, 2048 or 4096; unset, 4096;
  another value is an error. A factor whose size is not above the input's
  side is refused: it adds nothing. A size above the largest side is
  refused (R-HD-123).
- A recipe's own size is four times its input's longest side, at most
  4096. A request may ask for its own size, for each half down to the
  first of 1024 or less, and always for its own half: the 2x of a 4x
  model (`store.offered_sizes`). An odd side has no half.
- A request keeps the file of the size it asks for, and of no other size
  (R-HD-123, `[host]`, O-HDS-19). The planes are kept at the recipe's own
  size. A size asked for later is encoded from them and added beside the
  first: no job runs (R-HD-6), and no kept file changes (R-HD-158).
- A `pbrify` or `fast` step whose input already has a side of 4096 is
  refused: it can add nothing.
- The size rule needs the original's longest side. A side of 0 or below
  is an error, not a size. An original whose DDS header cannot be read
  has no size: it is a state with its reason (4.9), and no request of it
  is offered or made. The colour-plane rule needs no size
  (`model_refusal`).
- A variant whose input is not made yet makes the input first, as a
  variant of its own, at the size the id names.

One step, per plane:

1. The input is the plane of the input variant, or of the original.
2. An input above 2048 on a side is halved until it is not.
3. The runner upscales it four times. Only for a texture that tiles are
   its edges made to match (`--tiling`); for one that does not, its edges
   are taken as they come.
4. The output is halved until no side is above 4096: the recipe's own
   size.

Then the planes are joined (wrapped across the border only for a texture
that tiles), matched to the original's coarse content,
given a mip chain, and encoded. A variant at a smaller size is that mip
chain without its largest levels. Colour is halved and averaged in linear
light (H6). In each step a flip book gets a rim of 16 of its own edge
pixels around each cell before the runner. The rim is cut after it
(R-HD-56).

The input of a later step is the kept plane of its input recipe, halved
to the input's size. So a second size costs no GPU time (R-HD-6).

An edited variant is what the transfer of an edit makes
(SPEC-PHOTOCRAFT 10, `core/edittransfer.py`). The planes the edit
changed are the scratch's rendered planes; the others are the input's
own. They are joined with no source, so the result is not matched to the
original's coarse content; across the border only for a texture that
tiles. The entry keeps `tiles`. It has one size, its input's. No model and no
runner takes part, and `request` cannot make one. Its entry holds `edit`:
the input, the changed planes, the hash and the session.

### 4.4 Texture store

The folder named by `TEXTURE_STORE`. `scripts/paths.sh` derives it as
`SC2_BUILD/texture-store` (SPEC-PATHS); unset, the pipeline stops. Not in
git, not on the repository disk (R-HD-85). The store holds no queue: the queue is the runner's.

| Path | Holds |
| --- | --- |
| `format` | the layout version: 3. Every entry of 3 names `tiles`. A store of 2 is refused with the command that brings it to 3, `make texture-store-migrate` (`storemigrate.py`): it gives each entry without `tiles` the value true, since every upscale before the key matched edges; an entry of 2 that names `tiles` keeps its value. It checks every entry before it writes the first, writes the layout last, and refuses while a request is open |
| `<game>/planes/` | every plane a step takes or keeps, named by the hash of its pixels |
| `<game>/upscaled/<recipe>/` | the runner's output file for one upscale; `job.json`, the name of the job last asked to make it; an output that was no whole image, renamed with `.broken` |
| `<game>/variants/<origin>/<recipe>/` | `entry.json` (recipe, models per plane, own size, hashes, numbers) and one file per size a request asked for (4.3; an entry made before 2026-11-26 holds every size); `request.json` while it is made, or after that failed; `request.log` (4.7) |
| `<game>/edits/<session>/` | one edit session: its record, bases, scratch and rendered planes (SPEC-PHOTOCRAFT 8) |
| `<game>/datasets/<dataset>/skins/` | one file per owner: its skins (4.6) |
| `<game>/datasets/<dataset>/` | `bakes.json` (4.6), `package.json` (R-HD-105), and `package/` for a dataset no build packages |
| `<game>/index/` | the game's own caches |
| `index.sqlite` | the state index (4.9) |

- An upscale's recipe: the hash of the input plane, the model, the
  runner's version, and `edges as they come` for a texture that does not
  tile. Equal recipes share one folder, so a plane is upscaled once
  (R-HD-6, R-HD-86).
- Datasets that resolve an asset to the same origin share its variants
  (R-HD-87).
- A variant whose original now has another hash is stale (R-HD-88). The
  state gives the reason as `staleWhy`.
- A variant whose edges were made for the other rule is not stale: it is
  shown and may be baked (operator 2026-11-26). Its entry's `tiles`
  differs from the texture's; an entry without `tiles` is refused. The
  state marks it `edgesOff`; a request of it makes a new variant beside
  it (4.7, R-HD-158), and the viewer does not skip that request. An
  edited variant is never off (`results.edges_off`).
- A file is written under a temporary name and renamed. A variant's entry
  is written last and removed first, so half a variant is never read as
  one. A failed request leaves no variant. Upscaled planes stay
  (R-HD-100).
- The runner's version covers the tool's locked dependencies and the
  modules that decide pixels, not its queue or command line.
- An entry does not say whether its variant has a problem. That is worked
  out from the entry's numbers and the texture's description (4.5), and
  kept in the index (4.9).

### 4.5 Limits

Measured on the variant and kept with it (R-HD-13).

| Limit | Bound | Near (amber) | Measures | Applies to |
| --- | --- | --- | --- | --- |
| Encode PSNR | at least 35 dB | below 38 dB | loss of the encoding on the largest level | all |
| Correlation | at least 0.7 | below 0.8 | the variant shrunk to the original's size, against the original, per channel | all |
| Coarse RMSE | at most 1.5 levels | above 1.2 | a small mip of the variant against the same mip of the original | all |
| Seam growth | at most 1.5 times the original's | above 1.3 | the step across the wrap-around edge | textures that tile (R-HD-91) |

- A missed bound is a problem. The entry lists each with the number and
  the bound (R-HD-90). A problem hides nothing: the variant is listed,
  shown and can be named by a skin.
- A bake whose skin names a variant with a problem is refused, unless the
  variant is accepted (O-HD-9).
- The near bands are the agent's (O-VIEW-7). Each limit has an info text
  in the state: what it measures and what a miss looks like.
- An entry may hold `accepted`, the reason the problems do not refuse a
  bake. It is read; no command writes it.
- Only a person sets it (R-HD-161). `store.write_recipe` refuses
  an entry that holds `accepted` and keeps nothing: "only a person
  marks a variant accepted". A person writes it into `entry.json` by
  hand.
- The limits bind a variant a model made. A user-made variant, one whose
  entry holds `edit`, has its numbers measured and kept, each with the
  band `none`. It has no problem, and its numbers refuse no bake
  (R-PC-80 to R-PC-82).
- A model's variant is measured against its reference: the nearest
  user-made variant among its inputs, else the original. The join
  matches its coarse content to the same reference. The entry and the
  request name the reference (R-PC-83).

### 4.6 Skins and bakes

A skin file holds a format number and, per skin name, a map from asset
to variant id (R-HD-130, 131). A skin names no other skin: a copy or an
upscale reads its source once, and keeps no link to it.

- `original` is no entry: it names nothing (R-HD-132). A name is 1 to 40
  characters: words of letters, digits, `-` or `_`, one space between
  them. `original` is refused as a name, in any case. The rule's cases
  are data of `hdtex.core`, `skin_names.json`: `skins.check_name` and the
  viewer's `skinNameRefusal` are each tested against every row. The names
  of an owner are unique ignoring case (R-HD-138): a copy, an upscale or a rename to a
  name another skin holds is refused. A case change of one skin is no
  clash.
- A store file (skins, bakes) with a key given twice is refused; the
  reader does not keep the last one.
- Each skin entry holds `textures` only; the file holds `format`,
  `owner` and `skins`. A missing or unknown key refuses the file, with
  its place. A file in the skin folder that names no owner is refused.
- An asset a skin does not name shows its original (R-HD-131). A bake
  names `original` for each texture of the owner its skin does not name,
  so the game shows what the viewer previews.
- A bake of `original` is refused: `unbake` removes a bake.
- New Skin N (R-HD-137): a `copy` or an `upscale` without `--name` makes
  `New Skin N` (`skins.next_new`), N one above the highest N of the
  owner's skins named `New Skin <number>` (ignoring case), from 1. A
  deleted number below the highest is not taken again. The answer names
  the skin made (`skin`). It is stored, renamed, baked and deleted as any
  skin; any number of them may be there. Nothing is offered that was not
  made. The owner's state names the next one (`next`, 4.9).
- A skin is read under the name it is stored with. Reading renames
  nothing and writes nothing. A skin `new` stored before New Skin N is an
  ordinary skin of that name.
- A skin may name a variant that is not made yet. Until it is made, the
  texture shows its original, with the request's state.
- A skin may name `original` for a texture. Baked, it shows the original
  over the bakes of the layers below, and packages no file.
- A skin may only name assets of its owner (R-HD-135) and ids of the asset's
  own variants.
- Only `core/skins.py` writes the file. A refused change leaves it as it
  was.
- **Skin upscale** (R-HD-134): makes skin N from skin S, with one model
  and one factor. The viewer asks for no N: the next New Skin N. For each texture of the
  owner: the input is what S names for it, else `original`; the variant
  is the input's id joined with `model@size`, or `fast@size` for a
  texture without a colour plane (R-HD-122), where the size is the
  factor's for that input (4.3). N names it, and it is requested. A
  texture that cannot have the factor, has no role, or has an original
  whose header cannot be read, keeps what S names and is listed with the
  reason. When no texture gets a variant, the upscale is refused with
  each reason and no skin is written (`skinplan.refuse_empty`).
- **Revert** (R-HD-162). A variant that misses a limit without
  the accepted mark is not left in the upscale's skin.
  - At the plan: where the serving variant is made and a bake would
    refuse it, the texture keeps what S names, with that reason
    (`skinplan.plan`). Nothing is requested for it.
  - At the request: `request --owner O --skin N` names the skin the
    request is for. When the variant it made is one a bake would refuse,
    and N still names it, N names the variant's input again
    (`variants.input_of`; `original`: the line is cleared). The reply
    holds `reverted`: owner, skin, asset, `from`, `to`, `reason`.
    `Dataset.revert_refused` does it; `skin upscale` without `--defer`
    calls it after each request and lists the same under `reverted`.
  - Not changed: a skin that names another variant by then, a skin that
    is gone, a bake, and the variant itself. A request that fails keeps
    the name.
  - The viewer's server passes `--owner` and `--skin` with each request
    an Upscale Skin starts (SPEC-VIEWER 17.1).
- `bakes.json` holds a format number, per owner the skin's name and its
  map as it was when baked, and per terrain asset a variant id (R-HD-140,
  R-HD-145). A bake names the skin it was made from (R-HD-136):
  changing the skin does not change the bake's map; renaming it renames
  it in the bake; deleting it is refused while it is baked ("skin S is
  baked; unbake it or bake another skin first"). Only
  `core/skinbakes.py` renames or deletes a skin. A rename is checked
  first, then writes the bake, then the skins, so the owner's state never
  holds the new name beside the old bake name.
- Pins (R-HD-160). `bakes.json` may hold `pins`: under
  `owners`, per owner and asset, and under `textures`, per asset, the
  SHA-256 of the variant file the bake took (the entry's hash of that
  size). `original` has no pin. `bake` writes them; `unbake` removes
  them; a rename keeps them. The package (5.2) compares each pin with
  the entry's hash now. Where they differ it fails: "`<asset>`:
  `<variant>` is not the file N bakes took", with each such bake and
  its `bake` command. Baking again takes the file as it is. A bake
  without a pin (made before 2026-11-26) is not compared. The format
  number stays 1; a file without `pins` is read as before.
- Only `core/bakes.py` writes `bakes.json`. A bake is refused, and the
  file left, when a named variant is missing, stale, or has a problem and
  is not accepted (R-HD-102, O-HD-9). The refusal names each texture.
- No file: no bake (R-HD-22).
- A file with an unknown key or a wrong type is refused whole, with the
  fault's path.

### 4.7 Requests and the queue

A request is one texture and one variant id (R-HD-97).

Each state has one source. The index holds a copy of it for readers
(4.9).

| State | Read from |
| --- | --- |
| `queued` | `request.json` exists and no job of it runs or is done |
| `upscaling` | a job of it is in the runner's queue as running or done; step and plane counts come from `request.json` |
| `encoding` | `request.json` says so |
| `done` | the variant's entry exists and is not stale; there is no `request.json` |
| `failed` | `request.json` holds the reason, or the process it names is gone |

- A request runs in the program that was asked. Only that program writes
  `request.json`. It removes the file when the variant is kept. Any
  program may read it (R-HD-99).
- `request.json` names the process by its ID and its start time. Another
  process that got the same ID later is not taken for it.
- `request.json` names the upscale folders of the step. The job of a
  folder is read from the folder's `job.json`. So two requests for one
  plane wait for one job.
- `request.log` holds every step of every request for that variant: the
  time, the process, each call of the tool with its exit status, each
  job with each change of its state, and the trace of a failure. The
  state names the file.
- Whatever stops a request is written to `request.json` with its kind,
  and to the log with its trace. That holds for an error nobody
  expected, and for a program that is stopped from its keyboard.
- A refused request leaves nothing: a texture without a role, a model or
  size of 4.3 that is refused, an original that cannot be read.
- A request for a variant that exists and is sound is done at once.
- A request for a size that a sound kept recipe lacks adds that size
  (`store.add_size`, `[host]`, O-HDS-19). No job runs.
  - Kept with planes: the planes are encoded again, and the file of that
    size is kept. An entry of another encoder version is refused.
  - Kept without planes: the file is the mip chain of a larger kept file
    without its largest levels. No larger file: refused with the reason.
  - The entry gains the size's hash. Its other keys, its marks and its
    other files stay byte for byte. A size that is there is never
    written again.
  - A step before the last is not given a size: its planes are the input
    (below).
- Kept variants are never written again (R-HD-158). A request
  that would make a kept recipe again makes a new variant beside it,
  under a new id. The old folder, entry and marks stay; skins and bakes
  keep naming it. `store.write_recipe` refuses a recipe that has an
  entry. Until 2026-11-26 such a request made the recipe again in place
  (O-HDS-18).
  - The check and the write are one step (`test_store.py`,
    `test_requests_kept.py` `MeanwhileTest`, 2026-11-26): `write_recipe` holds
    the recipe's lock (`<game>/locks/<origin>.<recipe>.lock`, `flock`)
    from the check to the entry. The file is empty and stays. Of two programs that make one recipe at once, the second
    finds it kept and is refused; it removes no file. Its request takes
    the kept recipe as its result when that one serves it.
  - The new id is the old one with a revision on its last step:
    `pbrify~2@512`, recipe and folder `pbrify~2`. The first make has no
    revision; `~1`, `~0` and `~02` name nothing (`variants.STEP`). The
    model of `pbrify~2` is `pbrify`. Its title is `PBRify #2 at 512`.
  - Which id serves a request (`results.served`): from the revision
    asked for upward, the first recipe that is sound or not kept. Sound:
    kept, not stale, its edges of the texture's rule. So a second
    request of `pbrify@512` finds `pbrify~2@512` and makes no `~3`.
    `[agent]`
  - `request` names the id that served it as `variant`, and the id it
    was asked as `asked`. `request.json` lies in the folder of the
    serving recipe and names the serving id.
  - A skin upscale (4.6) names the serving id of each texture.
  - The transfer of an edit follows the same rule: an edit kept for
    another original gets a revision.
- Chain reuse (R-HD-159). A step before the last takes the kept
  variant its id names as input, as it is; it is not made again.
  - Kept with planes: its planes, halved to the step's size (4.3).
  - Kept without planes: the file of the step's size is read, checked
    against the entry's hash, decoded and split by the role. No file of
    that size: refused.
  - Edges of the other rule: used as it is. The last step is made by
    the texture's rule.
  - Stale: refused with the reason. A request of the input alone makes
    its next revision; the chain then names that one. `[agent]`
  - Not kept: made first, as before.
- The transfer of an edit reports its state as a request does, with no
  job in the queue: its `request.json` says `encoding` from the start,
  and holds the reason when it fails (SPEC-PHOTOCRAFT 10).
- Each plane enters the queue through `arc-upscale submit`, into the
  tool's own queue. The tool answers with the job's name. A plane whose
  job waits or runs, or whose upscale exists, is not submitted again.
- A job's state is the folder of the tool's queue its file is in. The
  pipeline reads that and writes nothing there.
- The pipeline starts no worker. The viewer's server starts the one
  worker, on GPU 1. One worker runs one plane at a time (R-HD-98). GPU 0
  also holds the desktop: a job that fills it stalls with no error.
- Whether a worker runs is asked of the tool (`arc-upscale queue`), every
  10 seconds while all jobs of a request wait. Jobs that wait 30 seconds
  with no worker fail the request, with the queue named. With a worker,
  a request waits as long as its jobs are behind others.
- Retries, the watch for a stalled GPU and the time limit of an image are
  the tool's: it tries a job again twice, ends a job whose GPU does no
  work for 60 seconds or that takes more than 5 minutes per 2048 x 2048
  pixels, and keeps it as failed with its error and the worker's log. A
  failed job fails its request with that error.
- A job that is done and wrote no output fails its request. So does a
  job that is lost.
- The tool writes an output under another name and renames it. An output
  that is still no whole image is renamed with `.broken`, and fails the
  request with each such file's error, size and hash.
- `arc-upscale` is found next to this project, or at `ARC_UPSCALE`. The
  runner hands the tool its project folder, and keeps this program's
  Python settings from it.

### 4.8 Command line

`scripts/hd_textures.py <command> --game G --dataset D`. Every command
prints JSON. The viewer's server calls the commands that change
something. It reads states from the index (4.9) and runs no command to
show one.

| Command | Does |
| --- | --- |
| `status` | the textures with descriptions, variants, requests; the owners with skins and bakes; `gaps` (below) |
| `index` | brings the dataset's part of the index up to date with its files (4.9). `--asset` also finds the role of those textures. `--states` writes the head and each state again from what the index holds, listing no file and reading no original: for a changed `TEXTURE_MAX_SIDE`; it takes no `--asset`. |
| `upscaler` | the runner's worker command and whether it is idle |
| `request` | makes one variant: `--asset`, then `--variant V`, or `--input` (a variant id or `original`), `--model` and `--factor` (2 or 4). `--owner O --skin N`, both or none: the skin the request is for (4.6, Revert); the reply then holds `reverted` when the input was put back |
| `remove` | removes one variant: `--asset A --variant V` (R-HD-146). Its file and its size in the entry go; the last size takes the recipe's folder with it. Each skin of this dataset that names `A` with `V` names the original for `A` after; its owner's state is written again. Refused while a bake of any dataset of the game, or a skin of another dataset, names `A` with `V`, a recipe of the origin starts with `V+`, a request of its recipe is open, or an edit session of the origin and `V` is there. `original` is refused. |
| `skin` | `list`, `copy --from S [--name N]`, `rename --name N --new M`, `delete`, `set --asset A --variant V` (or `--clear`), `upscale --from S [--name N] --model M --factor F`; each with `--owner O`. Without `--name`, `copy` and `upscale` make the next New Skin N and answer its name as `skin` (4.6). |
| `bake` | `--owner O --skin N`, or `--asset A --variant V` for a terrain texture |
| `unbake` | `--owner O`, or `--asset A` |
| `package` | packages a dataset no build packages (R-HD-106); `gaps` (below) |
| `edit` | an edit session (SPEC-PHOTOCRAFT 10): `open --asset A` with `--variant V` for a variant; `check`, `transfer`, `discard`, each with `--session S` |

`--layer <folder>` names the dataset's own layer, for a game that takes
it from the caller. The viewer's server and the map build pass it. A
refusal prints an object with `error` and ends with exit status 1.

By hand a command runs through `make hd-textures ARGS="<command> ..."`,
which sets the project's paths first (SPEC-PATHS). For `scoba` the layer
is the map source, as the viewer's server names it:
`--layer src/SCOBA.SC2Map`.

No command takes a tile size, a GPU or a force flag.

`gaps` is what the game data leaves out, found by the listings the
command did: kind -> one line per entry with the reason. Nothing is left
out without a line; nothing fails for it. A game without such gaps gives `{}`.
For SC2 (5.1) the kinds are:

| Kind | Found by |
| --- | --- |
| actors whose model cannot be read | the owner list: the actor's chain breaks (a parent in no catalog, a token without a value). It owns nothing. Stock: 2, `InfestedColonistTransportNova` and `MilitarizedColonistTransportNova` (parent `Unit`). |
| names the map shows that have no model | `sc2/shown.py` |
| terrain fields that cannot be read | the terrain listing |
| model entries that name no file | the model listing, of every entry |
| model files the data names that are not there | the model listing, of every entry |

### 4.9 State index

`index.sqlite` in the store, one file for every game and dataset
(R-HD-113). `core/index.py` knows the file; `core/dataset.py` decides
what is written. It is a copy: the files of 4.4 and the dataset hold the
truth, and `index` writes a dataset's part again from them, also when the
file was removed (R-HD-114).

Every statement on the file is a file of `sql/texture-index/` in the
repository, one statement per file, named by it; the schema is
`schema.sql`. `core/queries.py` reads them for the pipeline; the viewer's
reader reads its own from the same folder. A missing file is an error.
The host tests' statements are in `sql/texture-index/checks/`. Code holds
no statement text, except the pragmas and the transaction control.

| Table | One row per | Holds |
| --- | --- | --- |
| `dataset` | game and dataset | the factors, the largest side it was written with (`maxSide`), the hash of the pipeline code that wrote it (`code`, SPEC-VIEWER 17.1), the models, the limits with their bands and info texts |
| `text` | distinct JSON text | the text once, compressed (zlib); its SHA-256 as the key; how many fields name it |
| `texture` | game, dataset and asset | the origin, the kind, and as `text` ids: the listing, the description of 4.2, and the state |
| `original` | game and origin | the hash and the longest side of the original, why its header cannot be read (empty when it can; the side is then 0 and is not a size), and the size and time of its file when they were read |
| `origin` | game, dataset and asset | the origin of every texture file the dataset can show, listed or not (5.1) |
| `owner` | game, dataset and owner | its title, its layer, the owners below it, its textures, its skins (name and textures), the name of the next skin made without one (`next`), what it shows now (`shows`: its bake, else the nearest bake below, else `original`) and its bake; its description and state as `text` ids |

The state of a texture is what a reader shows of it, in the shape of
SPEC-VIEWER 17.2: its variants with input, models, size, numbers,
problems, stale and accepted; its open requests; the models and factors a
request may ask for, each factor with its size and the reason of each
refusal; the path and hash
of each variant file; per variant `remake`, the id that serves a
request of it (4.7, `results.served`; its own id when it is sound); the terrain bake and whether the package holds its
file; `namedBy` (R-HD-156): each owner of the dataset whose bake or skin
names a variant of it other than `original`, as `{owner, skin, variant,
baked}`, sorted by owner, the bake before the skins. It is worked out from
`bakes.json` and every skin file of the dataset, read once per change
(`statewriter.StateWriter`), beside the bakes. A skin that names the variant the bake
names is listed too: the two are separate facts.

| Change | Who writes | Rows written again |
| --- | --- | --- |
| a request starts, a job of it starts to run, it encodes, it is done, it fails | the program that runs the request | every `texture` row with that origin, in every dataset |
| a variant is removed | `remove` | every `texture` row with that origin, in every dataset |
| a skin | `skin` | that `owner` row; the `texture` row of each asset whose `namedBy` changed (the assets the skins name before or after the change) |
| a bake | `bake`, `unbake` | that `owner` row and the `texture` row of each asset the old or the new bake names; or that `texture` row |
| a rename of a baked skin | `skin rename` | that `owner` row; the `texture` row of each asset the skins or the bake name (`Dataset.names_changed`) |
| a package | the package step | the `owner` and `texture` rows of the dataset |
| the dataset's files or the installed game | `index` | every row of the dataset is worked out; those that differ are written; rows of textures and owners that are gone are removed; the `origin` rows when they differ |

- A state is worked out by `core/view.py` from the row's description,
  the entries, the skins, the bakes, the package record and the
  `original` row. It reads no file of a dataset. No row is worked out by
  a reader.
- A row of another dataset is written without that dataset's files: its
  description is in the row, and an origin two datasets share is a file
  of the game's storage, the same for both.
- Only `index` adds and removes rows of textures and owners nobody asked
  for. It is run with the layer the reader shows. A request, a skin or a
  bake adds the row of its own texture or owner. The package step of the
  map build has the build folder as its layer: it writes states and no
  new row.
- What needs a texture's file is read when the texture is asked for by
  name, by `index --asset` or a request: a role the listing leaves open,
  and the size of the original. Until then the state says "not judged"
  and names no model to ask for. A texture with a variant is read always:
  whether the variant is stale is a fact of the original.
- What was read is kept while the game lists the texture as before and
  the size and time of the original's file are as they were. `index`
  looks at the file of each kept `original` row and reads it again when
  it differs; a role read from the old file is dropped.
- An original whose header cannot be read: the state's `reason` is why
  ("its original's header cannot be read: ..."), and it asks for no
  model (`asks` is empty).
- A skin, a bake and a package read no original that is known.
- A package writes every row of the dataset again (`changed_all`). A row
  whose original file is gone since the last `index` is refused, not
  dropped: "its original cannot be read (...); the index is out of
  date: run index, then this again". The package itself is written
  then; the index is not.
- Once `index` wrote a dataset, a skin or a bake reads the owner and
  its textures from their rows. It does not list the game's owners or
  textures: on stock that takes seconds per command. The mark is the
  `origin` rows, which only `index` writes, with every owner in the same
  transaction. A row of one owner that a skin wrote before any `index`
  is no such mark. Before that, the game is listed. A change of the
  game's files shows in these commands after the next `index`.
- An open request's state holds the process and its start time
  (4.7). A reader takes a request whose process is gone as failed. That
  is the one rule a reader applies.
- The file is in WAL mode: a reader does not wait for a write. A change
  is one transaction. A process that ends as the file's last user folds
  the log into the file and holds the file whole meanwhile. A reader
  without a busy wait fails then ("database is locked"): measured, 163 of
  6828 reads beside a writer that opens and closes. A reader sets a busy
  wait.
- The file holds a schema number (4). The tooling empties a file with
  another number; each dataset's part comes back with its next `index`.
  A reader refuses a file with another number and says so.
- Schema 4 keeps each JSON text of a `texture` or `owner` row once, in
  `text`: datasets that share a game hold the same descriptions and
  states. A field holds the id of its text. A text's count is the number
  of fields that name it; a write that drops the last one removes the
  text. A row whose text is as before is not written again. Measured on
  the three test datasets: 79 MB, against 572 MB with the texts in the
  rows.

## 5. StarCraft II

`scripts/hdtex/sc2/`. Game id `sc2`. Datasets as in
[SPEC-VIEWER-SC2](SPEC-VIEWER-SC2.md), section 4. `stock` is the game's
own data and takes no folder. Any other dataset is that data with a map
folder on top. The caller names the folder; this code finds none itself.

### 5.1 Textures

| Kind | Found from | Users | Tiles |
| --- | --- | --- | --- |
| `terrain` | every `CTerrainTex` of the dataset's catalogs in load order, its own layer last | the terrain sets that name the entry | yes |
| `model` | every texture a material of a model file names; the files are those of every `CModel` entry of the dataset's catalogs (the game's and the map's own), with variations | the model files | when a layer of one of its users repeats it (below) |

- Every dataset lists every `CModel` of its catalogs, shown or not, so an
  unplaced unit or doodad has textures and a skin (operator 2026-11-25).
- What the map shows decides only what the package copies into the map
  (R-HD-54, 5.2). `stock` shows every `CModel`. A dataset with a map folder
  shows those the map shows. `sc2/shown.py` reads them from the folder: the
  doodads and units the map places, the units and actors of its own
  catalogs, and the model entries its own catalog gives a model file. A
  placed type, a unit and an actor count with the model of the actor of
  that name, and with each model the actor's entry in the map's catalog
  links. A line the pack step wrote does not count.
- Not found: a unit the map only makes by script and that none of its
  own catalogs names.
- An original is read from the dataset's own layer first, then from the
  game's storage with `tools/stormex` (R-HD-4). Only this code resolves an
  asset. The index holds the answer for every texture file the dataset
  can show (4.9); the viewer reads it there (SPEC-VIEWER 17.1).
- Where the storage holds an asset more than once (H14, R-HD-112): a file
  at an archive's root or in its `base.sc2assets` wins. Without one, the
  file in `enus.sc2assets` wins. Among files of one standing the archive
  loaded last wins, then the path that sorts last. `sc2/storage.py` owns
  the rule.
- Roles: `diffuse` (colour, mask in alpha, H4), `normal` (H5), `normal_red`
  (a normal map with a red channel of its own), `data` (amounts in every
  channel). A model texture's role comes from the material slots that
  name it and from its file, so it is found when the texture is asked for.
- No role, with the reason: a cube map, DXT3, under 32 pixels, a normal
  layer of a displacement material, a flip book without usable cells,
  slots that disagree. SC2 takes the core's DXT1 and DXT5 only
  (`sc2/game.py` `FORMATS`): a codec another game registers (Ghost's DXT3,
  RGBA32, 6.3) is not one of SC2's.
- Model files may read one texture with different flip book cells. The
  cells most model files use hold. A file that reads it another way, or
  with unknown cells, is not among its users: the pack step leaves that
  file on the original. A flip book is without usable cells when no file
  reads it with known cells, or as many files read it one way as another
  (R-HD-56). For `scoba`, 5 textures have such files.
- Codecs: DXT5, and DXT1 without transparent pixels.
- A model texture tiles (`sc2/modelindex.py` `repeating`) when a layer
  of a model file among its users moves, or when at least 1% of the
  triangles drawn with its layers, over all those files, span a line
  (`m3tex.TILE_SHARE`).
  - A layer moves (`m3tex.moves`) when its sampler wraps on an axis
    (`textureWrapX` or `Y`) and its `uvTiling` is above 1 (0.02 of
    slack) or animated, or its `uvOffset` is animated (it scrolls).
  - A triangle spans a line when its coordinates of the layer's
    `uvSource` (0 to 3: `uv0` to `uv3`) cross a whole number of u or v
    by more than 0.02. A coordinate is stored × `uvwMult` / 16 / 2048 +
    `uvwOffset` of its region. A composite batch draws the materials of
    its sections. A triangle of no area in texture space counts for
    nothing. A layer that wraps on no axis clamps: its triangles span
    nothing.
  - The wrap bits alone say nothing: 97% of the 200990 layers of the
    cache set both. An animation reference counts as animated when its
    `animFlags` hold 6; whether its keys move is not read.
  - The share 1% is a choice (2026-11-26). In the cache, 3426 batches
    of 2370 model files have a triangle that spans a line of `uv0`;
    their shares run from 0.002% to 100%: 72 at most 0.1%, 430 at most
    1%, 1627 at most 10%. A texture drawn only by the 430 no longer
    tiles. `thorbirth.m3` spans 3 of 4152 triangles; over Thor's two
    files `Thor_Diffuse` spans 3 of 10090.
  - Measured 2026-11-26: on `battlecruiser_remastered.m3` the hull
    textures (0 of 4644) and the particle textures do not tile;
    `FireTile4`, `WarpLine2_Orange` (they scroll), `grad3` (tiling 3)
    and `BigWaves` (tiling 2 by 5, scrolling) do; the decal clamps. Of
    `thorex1.m3` and `thorbirth.m3` none tiles. Was: no model texture
    tiled.
  - Ghost (6.2) counts any one spanning triangle, without the share.
- The textures each model file names are cached by the file's hash, in
  format 3 (`moves`, `spans` and `triangles` of each layer); a cache of
  another format is read again whole. The first list of `stock` took 17773 model files out of the
  storage in 132 s. A later list takes 3 to 12 s.
- A model file the map build makes itself is read from the built map.


Owners (R-HD-130):

- `unit:<id>`: a `CUnit` of the dataset's catalogs, the game's and the
  map's own, placed or not (operator 2026-11-25). Its actor is the actor
  of that id, as in `sc2/shown.py`. Its models are that actor's model and
  each model its lines link: death, placement, portrait, parts.
- `actor:<id>`: a `CActor` of the dataset's catalogs, the same way. The
  viewer's doodads are this layer.
- A unit or actor whose model names no model file is no owner.
- `model:<asset>`: one model file, with its variations. The viewer's
  model files are this layer.
- The textures of an owner are those its model files name, with the
  flip book rule above. The list is in the `owner` row (4.9).

### 5.2 Package

The map build calls it last, for `scoba`, on the build folder (R-HD-101).

What a model file shows, per texture, is decided by layer: the unit's
bake, then the actor's, then the model's, then the original (R-HD-131).
The package writes one copy for each distinct result.

| Bake on | Package writes | Others |
| --- | --- | --- |
| `model:<file>` | a copy of the file at `Assets\Models\scoba_hd\<path>`, naming the baked files; every `CModel` that shows the file points at the copy (R-HD-143) | every unit and actor that shows the file shows the bake |
| `actor:<id>` | for the `CModel` of the actor's `Model` field, when its textures differ from what the model layer shows: a copy of each of its files at `Assets\Models\scoba_hd\<actor>\<file>`, and a new `CModel` `<CModel>_hd_<actor>` whose parent is the old entry and whose `Model` is the copy; the actor's `Model` names the new entry (R-HD-142) | other actors keep the old entry |
| `unit:<id>` | the same for the unit's actor, the actor of the unit's id, with the unit's bake over the actor's: entry `<CModel>_hd_<actor>` (R-HD-141) | other actors and units keep their entries |

- Placed instances name the unit or doodad type, so they show its bake.
- [plan] An actor that serves more than one unit is not copied apart: a
  unit bake changes that actor for every unit that has it. Models the
  actor names in its event lines (death, placement, portrait) keep what
  the model layer shows (R-HD-144).
- A copy for an actor lies in a folder of the actor's name, so two copies
  may share a file name. `sc2/check.py` reads those folders too.
- A baked variant that no catalog line and no model copy names is not
  packaged, and the log says so: an actor's bake under its unit's
  `original` is one.
- A packaged texture is `Assets\Textures\scoba_hd\<stem>_scoba_hd.<ext>`.
  The mark is needed: the game sizes a texture by its file name (H7, H9).
  A texture only model files name is `<stem>_scoba_hd_m.<ext>`. Where the
  bakes of a dataset name more than one variant of a texture, one keeps
  that name: the texture's own bake, else the variant whose id sorts
  first (`pack.packaged_paths`). Each other is
  `<stem>_scoba_hd_<h>_m.<ext>`, `<h>` the first 6 hex digits of the
  hash of its variant id. The check takes the three forms and no other
  (`sources.is_marked`; `test_sc2_check.py` `MarkTest`, `test_sc2_owners.py`
  a unit bake of another variant than its model's). Until 2026-11-26 it
  refused the third: no build had packaged two variants of one texture
  before the bake of `unit:MengskBC` (section 10).
- The mark stands at the end. A `CModel` finds its texture slots by the
  start of a file name and by words inside it (H13). A mark in front made
  the game lose the slot of the Goliath copy (run `tps/20261124-185130`).
- A packaged file keeps the file name as the catalog spells it: a terrain
  texture that of its catalog field, a model copy that of its `CModel`.
  `validate_slow_deaths.py` names model copies that way.
- A texture the terrain and a model file both name is a terrain texture.
  It is packaged once, and the model's copy names that file.
- Each baked file is copied after a hash check.
- Terrain: each terrain bake sets the entry's `Texture` or `Normalmap` in
  the map's `TerrainTexData.xml` (R-HD-145). What the file holds is kept.
- Each model copy is changed to name the packaged files, read back and
  compared. All files of a `CModel` are copied: variations share a base
  path (R-HD-54).
- The package record lists each packaged asset with its owner, skin,
  variant, path and hash, and the bakes nothing uses (R-HD-103, R-HD-105).
- A bake of a missing or stale variant, or of a problem not accepted,
  fails the build. The message names the texture and the command
  (R-HD-102). One line per (texture, variant): the reason, then
  "baked by <n> owners:" and each owner with its skin and its `unbake
  --owner` command, one per line (R-HD-157). A texture baked on its own
  is listed as "its own bake" with `unbake --asset`. Before 2026-11-26 it
  named the first owner only, and quoted the owner by `repr`, which
  doubled each backslash of a model path: the command named no owner.
- With no bake, it says so and copies nothing (R-HD-22).
- Unknown engine facts (E-1, E-2, section 8): whether a `CModel` entry the
  map makes, with the fields of a stock one, shows as the stock one; and
  whether an actor copy with the unit's events replaces the stock actor
  for that unit. Both are checked in the game before a unit or actor bake
  is reported as working.

`sc2/packaged.py` owns what the pack step writes into a map folder, and
the reading of that folder without it.

- Every catalog line that names a packaged file or a made entry is set
  through it. It notes in the folder's `.hd_prior` what each line
  replaced: the value that stood there, or that the field was absent, or
  that the entry was made, or that the catalog file was made.
- A catalog of a packaged folder is read as it was before from that note
  alone. Nothing is guessed from file names. Layout and comments of a
  catalog the step wrote are not kept.
- A folder is packaged once. A second package is refused.
- A catalog line that names a packaged file and is not in the note is
  refused, with the advice to build the map again.
- The texture pipeline lists a dataset from the folder as it was before.
  So does the hit volume data (`hitvolumes/resolve.py`,
  `hitvolumes/fresh.py`): `scripts/data/hit_volumes.json` names the
  original models, and a bake does not make it stale.

`validate-map.py` reads the built map only. It fails when a catalog names
a packaged file that is absent, a packaged file is named by nothing, a
packaged file lacks the prefix, a packaged texture has a side that is
not a power of two, a short mip chain, or more than 16 bytes after the
last mip, or a catalog does not read back through the note.

A partly upscaled terrain mixes sharp and soft ground. So when one
terrain texture the map paints with is baked, each of them must be,
colour and normal map (R-HD-104). `sc2/check.py` owns the rule. The pack
step asks it before a file is written and names what is missing;
`validate-map.py` asks it of the built map. A terrain texture the map
does not paint with is outside the rule.

A build check that demands a model the build makes itself (a slow death,
a slow simulation, fast clips) accepts the packaged copy of that model by
its file name. For a slow simulation and for fast clips it checks the
copy as well: the game shows the copy (`validate_slow_deaths.py`).

The log checks fail on a texture warning in a new `Graphics.txt` (H9).

## 6. StarCraft: Ghost

`scripts/hdtex/ghost/`. Game id `ghost`. R-HD-150 to R-HD-155. The game,
its files and NODExport are those of
[SPEC-VIEWER-GHOST](SPEC-VIEWER-GHOST.md).

### 6.1 Settings and dataset

- `GHOST_PATH`: the extracted build, a viewer setting of
  `webviewer/local.env` (SPEC-VIEWER-GHOST 3), not a work path of
  SPEC-PATHS. `NODSDK_EXPORT`: the NODExport program; unset,
  `build/nodsdk/cmake/NODExport` below `WEBVIEWER_WORK`
  (`workpaths.path`), where the viewer's link points. Both are read
  when a command runs, never at import. Unset `GHOST_PATH`, a build
  without `3D/Models`, or no NODExport: every command of the game is
  refused and names the setting.
- One dataset, `build`. It takes no layer: `use` refuses one.
- Nothing is written into the build (R-HD-150). NODExport writes to a
  temporary folder below the game's index folder.

### 6.2 Textures

| Kind | Found from | Users | Tiles |
| --- | --- | --- | --- |
| `model` | the texture files of the materials of every model file the catalog lists | the model files | yes |

- The catalog is NODExport `catalog`. The material names of one model are
  NODExport `nod` (its `materials`). The materials are one NODExport
  `materials` call for every name at once. So the lookup of
  SPEC-VIEWER-GHOST 4.4 is NODExport's alone (R-HD-151).
- The names of each model are cached by the hash of its file, in
  `<store>/ghost/index/models.json`. The materials are cached by the
  hash of every `.nsa`, `.nas`, `shaderlist.txt` and `MaterialDirs.txt`
  and of the list of texture files.
- A texture key is `texture`, `texture2`, `glow`, `envmap` or `detail`,
  as NODExport exports them. Each names a file relative to the build.
- Asset: that path, lower case, `\` between folders:
  `3d\materials\chestcrate2.dds`. The page builds the same name from
  the path the container gives (SPEC-VIEWER-GHOST 8).
- Origin: the path as it is on disk, with `/`. `origins` names every
  `.dds` of `3D/Materials` and of the folders under `Materials`.
- A Ghost texture tiles when it repeats on a model: a triangle of a
  material that names it spans a whole-number line of u or v, with 0.02
  of slack (`ghost/export.py` `repeating`, from the UVs of `NODExport
  nod`). A triangle moved whole by a whole number samples no border and
  is no repeat. One model that repeats it is enough. The listing keeps
  each model's repeating materials (`repeats`, listing format 2).
  Measured 2026-11-26: no triangle of Nova's 9 materials spans one;
  `crate`'s `chestCrate2` (20 of 76) and the terrain pieces' materials
  (most triangles) do. Was: every Ghost texture taken to tile, so Nova's
  textures missed the seam limit and were upscaled with matched edges
  (operator 2026-11-26).
- No role, with the reason, before the file is read: a file that is not
  `.dds`; a material whose shader is `sky`, `invis` or `video`, or starts
  with `constraint_`, when no other material names the file.
- No role, with the reason, from the file: a cube map, a volume, a format
  no codec reads (DXT2), DXT1 with transparent pixels, a side under 32
  pixels.
- Roles: `diffuse` for a file named by `texture`, `texture2`, `glow` or
  `detail` (colour, alpha a data plane). `envmap` alone: `data`. Keys
  that disagree: the colour key wins; the users say which keys.
- `gaps`: model files NODExport refused, materials found by no step,
  material texture files that are missing.

### 6.3 Codecs

Registered by the adapter in `CODECS` (R-HD-109). No core codec changes.

| Id | Layout | Encode |
| --- | --- | --- |
| `DXT3` | 16 bytes a block: 4-bit alpha per pixel, then a DXT1 colour block in four-colour mode | alpha rounded to 4 bits; colour by the core's DXT1 block encoder |
| `RGBA32` | 4 bytes a pixel, B G R A in memory: masks `FF0000`, `FF00`, `FF`, `FF000000` | the bytes as they are |

- `core/dds.py` names an uncompressed format `RGB<bits>` or
  `RGBA<bits>` (`describe`). A codec may give `masks`: the red, green,
  blue and alpha masks of an uncompressed layout. `parse` then takes a
  file without a FourCC whose name and masks are the codec's, and
  `build` writes such a header. A file with other masks is refused. This
  is a change of the container, for any game; the core names no format.
- DXT1 with transparent pixels is refused (R-HD-153): the core's DXT1
  encoder writes no alpha.

### 6.4 Owners

- `model:<asset>`: one model file, `3d\models\<file>` lower case. Its
  textures are those its materials name.
- `actor:<template>`: a template of the catalog with a model file the
  catalog lists. Its `below` is that model's owner; its textures are the
  model's. A template whose model is missing or refused is no owner.
- Ghost has no `unit:` layer.

### 6.5 No bake

- The adapter's `bakes` is the reason "baking is not enabled for
  StarCraft: Ghost" (R-HD-154). SC2's is empty.
- `Dataset.bake`, `bake_texture` and `unbake` and `package.package` refuse
  a game with a reason, before a file is read or written (R-HD-115).
- The head of each dataset (4.9, `dataset.head`) holds `bake`: the reason,
  or empty. It is JSON in the row, so the schema number stays 4.
- The adapter's `package` and `check` raise the same reason.
- The interface gained `bakes` with this change. That is one core edit
  for a new rule of every game, not for Ghost alone (R-HD-110).

## 7. Requirement State

The host tests are in `scripts/testkit/tests/textures/`. A row names the
files that hold the tests of its requirements; it does not say that every
sentence of a requirement has a test. Rows of 2026-11-24 before variants
passed on that day.

| ID | State | Backing |
| --- | --- | --- |
| R-HD-1, 2 | [host] | `test_sc2_check.py` (`MapSourceTest`, `BuiltMapTest`); the build of 2026-11-24 |
| R-HD-3, 4, 112 | [host] | `test_sc2_game.py`, `test_sc2_sources.py` (`ArchiveTest`) |
| R-HD-113, 114 | [host] for textures; [plan] for owners, skins, bakes | `test_index.py`, `test_index_write.py` |
| R-HD-5, 6 | [host] | `test_runner.py`, `test_arc_queue.py`, `test_requests.py`; no request has run on the real GPU queue |
| R-HD-10 to 13, 52, 91 | [host] | `test_codec.py`, `test_encode.py` |
| R-HD-90 | [plan] | problems no longer hide; bake refusal |
| R-HD-53, 56 | [host] | `test_sc2_sources.py` (`RoleTest`), `test_sc2_game.py` (`ModelTest`), `test_steps.py` |
| R-HD-120 to 124 | [host] for ids, models per plane, sizes, refusals; [host] for factors, the largest side, one size per request and `index --states`; [e2e] for the viewer | `test_variants.py`, run 2026-11-25; `test_cli.py` (`--factor`, the cap, a factor that adds nothing), `test_store.py`, `test_encode.py`, `test_index.py`, run 2026-11-26; `texture-max-side` (e2e, `TEXTURE_MAX_SIDE=1024`), run 2026-11-26; one size per request: `test_requests_kept.py` (`OneSizeTest`), `test_store.py` (`add_size`), `texture-service-api` (viewer unit), run "One size 2026-11-26" |
| R-HD-85 to 88 | [host] for results; [plan] for variants | `test_store.py`, `test_dataset.py`; layout 2 to 3: `test_storemigrate.py` |
| R-HD-130 to 133, 135, 136 | [host] for the skin and bake files and skin changes; [plan] for the viewer | `test_skins.py`, run 2026-11-25 |
| R-HD-134 | [host]; [e2e] for the viewer | `test_dataset.py` (by factor, kept with reason, nothing asked: refused and nothing stored), `test_cli_skins.py`, run 2026-11-26; an upscale without a name makes New Skin 1 then New Skin 2 (`test_dataset.py`); `texture-max-side`, `texture-variants` (e2e) |
| R-HD-137 | [host]; [e2e] for the viewer | `test_skins.py` (next_new counts up from the highest, a name that only starts so is none; every row of `skin_names.json`; a stored `new` read as `new`, nothing written), `test_new_skin.py` (copies count up and stand side by side, a deleted number is not taken again; a New Skin N bakes and renames, the bake follows; taken and reserved names refused, nothing requested), `test_dataset.py`, `test_dataset_bakes.py`, `test_index.py` (negative: nothing offered above a bake); `texture-new-skins` (e2e); run 2026-11-26 (host 526 OK, e2e 47 passed) |
| R-HD-97 to 100 | [host] for chains; [plan] for variant ids | `test_requests.py`, `test_requests_kept.py`, `test_arc_queue.py`; R-HD-98 on GPU 1 is not run |
| R-HD-140 to 143 | [host] for what the package writes; not in game | `test_sc2_owners.py`, run 2026-11-25; E-1, E-2 need a game run |
| R-HD-144 | [plan] | event-line models are not copied (section 5.2) |
| R-HD-145 | [host] | `test_sc2_game.py` (`PackageTest`, terrain tests) |
| R-HD-101 to 106, 54, 22 | [host] for picks; [plan] for bakes | `test_package.py`, `test_sc2_game.py` (`PackageTest`), `test_sc2_packaged.py`, `test_cli_bake.py`, `test_sc2_check.py` (`BuiltMapTest`) |
| R-HD-24 | [host] | `test_sc2_check.py` (`CheckTest`) |
| R-HD-21, 55 | [boot] | run `tps/20261124-220055`, picks; not run with bakes |
| R-HD-107 to 111 | [host] | `test_registry.py`, `doubles.py`: a second game, a second format, a stand-in upscaler |
| R-HD-115, 150 to 155 | [host] [viewer], run 2026-11-25; not on the GPU queue (O-HDS-17) | `test_ghost_game.py` (a made-up build, a stand-in NODExport), `test_ghost_codecs.py`, `test_ghost_bake.py`; SC2 keeps refusing DXT3 with Ghost's codecs loaded (`test_sc2_sources.py`); viewer `ghost-upscale`, `ghost-bake-off`, `ghost-textures`, `ghost-mix`, `texture-edit-button` |
| R-HD-160 | [host], run 2026-11-26 (section 10, Guards); the 145 live bakes hold no pin until baked again | `test_dataset_bakes.py`: a bake pins each named variant's hash, not the original; an unbake removes the pins; a rename keeps them; a terrain bake pins too. `test_package.py`: a pinned bake whose variant has another file now fails the package and names each such bake with its `bake` command; baked again, it packages. Negative: a bake of the same variant by an owner whose pin matches is not named; a bake without pins packages as before; nothing is written by a refused package |
| R-HD-161 | [host] | Run 2026-11-26 (section 10, Guards, accepted; Old mark removed). `test_store.py`: a write of an entry that holds `accepted` is refused and leaves no file; a mark set by hand is read |
| R-HD-162 | [host]; [unit] for the viewer's server; no controlled run on the live store (section 10, Live store), none with a real upscaler | Run 2026-11-26 (section 10, Guards, revert). `test_dataset.py`: an upscale over a made variant with a problem keeps the input with the reason and names nothing for it; with the mark it is named. `test_cli_skins.py`: `request --owner --skin` whose result misses a limit puts the input back and says `reverted`; over a variant, that variant is put back; the variant stays; `skin upscale` without `--defer` does the same. Negative: a sound result reverts nothing; a skin that names another variant by then is not changed; a skin that is gone changes nothing; a failed request keeps the name; `--owner` without `--skin` is a usage error and makes nothing. Viewer, `texture-service-api.spec.mjs`: an Upscale Skin of `unit:Battlecruiser` ends with the three tiling textures whose seam the tests' runner breaks back on the original, and each sound variant named; the variants stay listed |
| R-HD-156 | [host]; [e2e] for the badge and the "named by" row (R-VIEW-160, 161) and for the Delete Variant dialog (R-VIEW-162) | Run 2026-11-26 (section 10, Named by). `test_index_named.py` `NamedByTest`: two owners name variants of one texture, one baked: the bake's line stands before the skin's, the owners in order; a skin change, a bake, a rename of the baked skin, an unbake and a delete each write the texture's row again; a bake keeps its line when its skin names another variant since; an index made anew gives the same lines. Negative: a made variant nobody names, a texture no owner names and a skin back on the original have no line |
| R-HD-157 | [host] | `test_package.py`, run 2026-11-26: one failing variant baked by three owners names the three, their number and each `unbake` command; another variant of the texture lists its one owner; a path owner keeps single backslashes; a texture's own bake is listed with `--asset`. Negative: no owner twice, none under another variant, a sound texture is not named. Not seen in a failing build since |
| R-HD-158 | [host]; [unit] for the viewer; no controlled run on the live store (section 10, Live store) | Run 2026-11-26 (section 10, Immutable). `test_variants.py` `RevisionTest`: `pbrify~2@512` splits to recipe `pbrify~2`, its model is `pbrify`; `~1`, `~0`, `~02`, `~` are refused. `test_store.py`: `write_recipe` on a kept recipe is refused and changes no byte. `test_requests_kept.py` `ImmutableTest`: a request on a kept variant that is stale or has edges of the other rule makes `~2`; a second request finds `~2` and runs no job; an original that is back is served by the first; a failed revision is asked again under its id. `test_cli.py`: the reply names `variant` and `asked`. `test_dataset.py`: a skin upscale names the revision; a bake of a skin that names the stale one is still refused. `test_index.py`: `remake`. `test_edit_transfer.py`: an edit kept for another original gets a revision. Viewer, `texture-service-api.spec.mjs`: the request route follows `remake`, the kept folder keeps its hashes, asked again no third is made; `skin-choices.spec.mjs`: Ask Again drops the revision from the model. Negative in each: the kept entry, files and `accepted` are the same byte for byte, no `~3` appears |
| R-HD-159 | [host]; no controlled run on the live store (section 10, Live store) | Run 2026-11-26 (section 10, Immutable). `test_requests_kept.py` `ChainTest`: a chain over a first step kept without planes takes the colour of its decoded file and runs no job for that step; one with edges of the other rule is used as it is; a stale first step refuses the chain and leaves no request; a first step without planes and without the file of its size is refused; a file that is not the entry's fails the chain. Negative: the runner sees no call for the kept step, the kept folder is the same byte for byte, no revision of it appears |
| R-HD-60 to 65 | section 12 | |
| R-HD-70 to 72 | section 13 | |

## 8. Open Points

| ID | Point |
| --- | --- |
| E-1 | Not known: whether a `CModel` entry the map makes, holding every field of a stock entry, shows in the game as the stock one does (5.2). A game run decides it. |
| E-2 | Not known: whether an actor copy with a unit's events, with those events taken from the stock actor, shows that unit and no other (5.2). A game run decides it. |
| O-HDS-2 | The results taken in from the old caches name the upscaler version of those caches. Whether the tool's current version gives the same pixels is not compared. A result is made again only when its original changes. |
| O-HDS-4 | Until 2026-11-26, 18 variants that skins and bakes named missed a limit and were packaged as accepted. Since the fix of O-HDS-18 every skin and bake names `original` for them (operator 2026-11-26). The variants stay in the store, still marked accepted. Open: whether each is made again, and what becomes of the mark. |
| O-HDS-5 | The map shows 201 model entries; 159 of them name a picked texture. Their 287 model copies take 76 MB. The map of the variant code held 167 copies of 44 entries, 19 MB; its folder was 1134 MB and is 1186 MB now. The package step takes 18 s of the build. Whether the larger map costs load time or memory in the game is not measured. |
| O-HDS-6 | Whether the game loads a 4096 texture named by a model file is not known. The terrain ones load (H11). |
| O-HDS-8 | Why GPU 0 stalls on a SeedVR2 tile that fills it is not known. GPU 1 reports "out of memory" for the same tile, also while another process holds 1.3 GiB there. The tool's watch ends the stall; it does not explain it. |
| O-HDS-9 | Two requests that ask for one plane in the same instant may both submit it. The plane is then upscaled twice, with the same pixels. No lock prevents it. |
| O-HDS-12 | Which asset folder the running game reads is not checked: whether `teen.sc2assets` ever wins over `base.sc2assets`, and which language folder an install of another language reads. The rule of 5.1 names `enus` in the code. |
| O-HDS-13 | `newgoosculpted_diffuseblood.dds` misses the correlation limit with Upscale 4x (0.477) and with Soft 4x (0.447), so the build packages its original. Whether another model reaches the limit is not tried. |
| O-HDS-14 | Three items of an audit of 2026-11-24 were kept in session notes only and are lost but for their titles: "encode profile", "intermediate sizes", "batch `judge`". What each asked for is not known. |
| O-HDS-15 | Ghost: a texture tiles when its UVs repeat it (6.2). A material key for a wrap or clamp mode was not found in what NODExport exports; the game's material format was not searched for one. A texture named only by `envmap` is judged by the UVs too, though an environment map is not sampled by them. |
| O-HDS-16 | Ghost: a texture several model files name, where one material reads it as colour and another as `envmap`, takes `diffuse`. Whether the environment map then looks right is not checked. |
| O-HDS-17 | Ghost: no request has run on the real GPU queue; the host and viewer tests use the stand-in runners. |
| O-HDS-18 | 2026-11-26, 14:50: a request of `pbrify@256+seedvr2` for `glow_haze1.dds` and `glow_red1.dds` found `pbrify` kept without planes and with edges of the other rule, so its first step made `pbrify` again in place (4.7, `requests._make`). The new entry has no `accepted` mark; its `coarse_rmse` is 4.172 and 1.635 against 1.5. 18 bakes named `glow_haze1` `pbrify@512`, 8 named `glow_red1`; the build failed on them. Fix (operator 2026-11-26, "Original everywhere"), done once by a scratch script over `skin set` and `bake`, not by a command of the pipeline: each skin and bake that named a failing variant names `original`. That was 20 variants: the two remade glows and the 18 of O-HDS-4; 118 skin lines of 52 owners, 52 bakes made again (section 10). Two of the skins were not baked: `unit:Battlecruiser` `Test` and `unit:Thor` `New Skin 1`. Two owners are model files only the built map holds (`battlecruiserlokideathslow.m3`, `goliathdeathslow.m3`); the index, synced from the map source, did not know them, so `index` ran with the built map before their commands and with the map source after. The four variants the operator remade and kept were not touched. The broken variants stay in the store. The store's bakes, skins, package record and the two packaged files of the last good build, with the scripts and logs of the fix, are kept in `$SC2_WORK/scratch/hd-fix-20261126/`. Lasting rule: R-HD-158 and R-HD-159 (4.7), built 2026-11-26: a request writes no kept recipe again, and a chain reads a first step kept without planes from its file. Measured 2026-11-26, 22:22 (section 10, Live store): 244 of the store's 285 entries hold no planes, and the same 244 hold the `accepted` text "the map had it before the store had limits". Requests ran on the store that evening. Not known: which change wrote that text into those 244 entries; no code of this repository holds it. |
| O-HDS-19 | Defect against R-HD-123, seen by the operator 2026-11-26: one request kept a file of every size of its recipe (`encode.encode` wrote each size a request may ask for), and each showed as a variant: `pbrify@1024`, `@2048` and `@4096` after one Upscale. The spec said so until that day (4.3). Fix: 4.3 and 4.7, built 2026-11-26 (section 10, "One size"). The sizes already in the store stay and stay listed (operator 2026-11-26: what is generated is not touched). Until 22:22 no file of the live store's variants was newer than 20:56; the fix's first red run is of 21:02. The 11 entries made there after it, 22:37 to 23:15, hold one size file each (section 10, Live store). |
| O-HDS-11 | The waterfall model `ZerusWaterfall` names the terrain texture `zerus_4`. It now shows the terrain's pick of it (Soft 4x at 4096). The map of the variant code gave the model a file of its own (Upscale 4x at 2048). Not seen in the game. |

## 9. Not Tested

- That the game shows the largest level of a packaged file on screen.
- That the game shows a packaged model copy, and takes a model override
  with variations below a new base path.
- Memory use and frame rate with packaged files.
- Texture quality settings other than the test machine's.

## 10. Runs

Launches 1 to 4 and the model launch are with the code of 2026-11-15.

| Name | What | Result |
| --- | --- | --- |
| Launch 1 | `launch-check`, files named like the originals | 16 texture warnings (H9) |
| Launch 2 | `launch-check`, files with the prefix | stamp matched, no script error, no texture warning |
| Launch 3 | the Generative 4x variant: `host-tests`, `launch-check` | 215 host tests passed; clean log |
| Launch 4 | the Upscale 4x variant, the same | the same |
| Model launch | 2026-11-20, doodads, Command Center, psi destroyer | no texture warning; not launched with the later units |
| `tps/20261124-185130` | the store's package, mark in front of the name | failures 0, but the Goliath copy lost its slot `main` (H13); the log check did not fail on it then |
| Build 2026-11-26 | `scripts/playtest.sh build` after the remake of O-HDS-18 | failed: "2 baked textures of scoba cannot be packaged", `glow_haze1` and `glow_red1` `pbrify@512`; the message named Barracks only |
| Fix 2026-11-26 | the fix of O-HDS-18, first on a copy of the store, then on the store | each: 172 commands (118 `skin set`, 52 `bake`, 2 `index`), none failed; against the backup, no change the plan did not name. `status` after: 227 named variants, none refused, none with a problem |
| Build 2026-11-26, 2 | `scripts/playtest.sh build` after the fix | failed in the check: `battlecruiser_diffuse_scoba_hd_edb63b_m.dds` "must end with _scoba_hd". The first build with two baked variants of one texture (5.2) |
| Build 2026-11-26, 3 | the same, with `sources.is_marked` taking the tagged name | passed: 225 files, 145 owners, 16 textures, 0 bakes unused; stamp `04c0c150339e-5d3d092e8802f3b9` |
| Host 2026-11-26 | `scripts/playtest.sh host-tests` on that build | 1379 tests, 1 failure, not of the texture code: `test_workpaths` `CallerTest` on `test_install_dock_icon.py:216` |
| Launch 2026-11-26 | `scripts/playtest.sh launch-check` on that build | exit 0: runtime stamp `04c0c150339e-5d3d092e8802f3b9` matched, no script error, no load failure; the run's Graphics log (18.08.24) holds no texture warning and no `scoba_hd` line. Not checked: that a unit with a tagged file (`unit:MengskBC`) was on screen |
| Immutable 2026-11-26 | R-HD-158 and R-HD-159: `make host-test` over every module of `testkit.tests.textures`; `make viewer-test ARGS="texture-service-api skin-choices"` | host: 546 tests, all passed; the 26 new ones were red before the code. Viewer: 16 passed; the 2 new ones were red before. `make viewer-test-e2e ARGS="texture- ghost-upscale"`: 39 passed, no new e2e test. Not run after this change: the map build, the full host suite, the other e2e specs, and no controlled request on the live store (Live store) |
| Guards 2026-11-26, pins | R-HD-160: `make host-test` over every module of `testkit.tests.textures` | 550 tests, all passed; the 4 new ones were red before the code (2 errors, 2 failures). Not run after this change: the map build, the full host suite, the viewer tests. The live `bakes.json` holds no pin |
| Guards 2026-11-26, accepted | R-HD-161: the same host modules; `make viewer-test ARGS="skin-choices texture-service-api"` | host: 553 tests, all passed; of the 3 new ones 2 were red before the code, as was the changed `list` test; the package one passed before too. Viewer: 17 passed; the new one was red with its word taken back. Not run: e2e, the map build, the full host suite. The label for the old store's blanket mark, built in this run, was deleted the same day (Old mark removed) |
| Guards 2026-11-26, revert | R-HD-162: the same host modules; `make viewer-test ARGS="texture-service-api skin-choices"` | host: 558 tests, all passed; the 5 new ones were red before the code. Viewer: 18 passed; the new one was red before the server passed the skin (the skin kept `firetile4`, `grad3` and `warpline2_orange` at `fast`). A first try on `unit:Thor` proved nothing: none of its variants missed a limit with the tests' runner. `make viewer-test-e2e ARGS="texture- ghost-"`: 72 passed, 1 failed, `ghost-upscale.spec.mjs:308`: it made its skin by an Upscale Skin over the crate's variant that misses the seam limit, which R-HD-162 now refuses. Its setup became a skin set by hand, with the refusal asserted; `make viewer-test-e2e ARGS="ghost-upscale"` after: 8 passed. The full `texture- ghost-` set was not run again after that change |
| Named by 2026-11-26 | R-HD-156: `make host-test` over every module of `testkit.tests.textures`; `make viewer-test` (every unit spec) | host: 560 tests, all passed; the 2 new ones were red before the code (`KeyError: 'namedBy'`). Viewer unit: 139 passed, with the state's new `namedBy`; no page reads `namedBy` yet. Not run after this change: e2e, the map build, the full host suite |
| Shared 2026-11-26 | R-VIEW-160, 161 and the tile line of R-HD-161: `make viewer-test ARGS="skin-choices"`; `make viewer-test-e2e ARGS="texture-shared"` | unit: 10 passed; the new one was red before the code (`usersBadge is not a function`). e2e: 2 passed; both were red before: the badge was undefined, and the tile said "4096" with the mark's words taken back for that run. A first setup looked for a Corruptor texture one model file reads; there is none, so that negative is the unit test's |
| Full 2026-11-26 | after R-HD-156 and R-HD-158 to 162, R-VIEW-160 and 161, with StarCraft II closed: `scripts/playtest.sh build`; `scripts/playtest.sh host-tests`; `make viewer-test`; `make viewer-test-e2e` | Build: passed, 225 files, 145 owners, 16 textures, 0 bakes unused; stamp `04c0c150339e-5d3d092e8802f3b9`, as before. Host: 1423 tests, 2 failures and 6 errors, none of the texture code: 7 in `test_loading_screen` (untracked work of another task; its tests call `read_document_header`, `check_document_header`, `sync_document_header` and `expand_document_header`, which are not there) and `test_workpaths` `CallerTest` on `test_install_dock_icon.py:216`, as on the earlier run. Viewer unit: 140 passed. Viewer e2e, every spec: 321 passed. Not run: `launch-check`, and no request, bake or package with a pin on the live store (its 145 bakes hold none) |
| One size 2026-11-26 | the fix of O-HDS-19, with StarCraft II closed: `make host-test` over every module of `testkit.tests.textures`; `make viewer-test`; `make viewer-test-e2e`; `scripts/playtest.sh host-tests` (it builds the map first) | Host, texture modules: 574 tests, all passed. The 16 new ones were red before the code (`add_size` and `Encoded.file` were not there); 14 older tests relied on a size nobody asked for; each asks for it now, or asserts its absence. Viewer unit: 140 passed; the new check in `texture-service-api` (one request, one listed variant) was red with the old line back for one run: the state listed `fast@2048` and `fast@1024` beside `fast@4096`. Viewer e2e, every spec, before that check was added: 321 passed. Build: passed, 225 files, 145 owners, 16 textures, 0 bakes unused; stamp `04c0c150339e-f67c488649676c4e`. Full host suite: 1443 tests, 1 failure, not of the texture code: `test_workpaths` `CallerTest` on `test_install_dock_icon.py:216`, as before. Not run: `launch-check`, and no controlled request on the live store (Live store) or with a real upscaler |
| Delete dialog 2026-11-26 | R-VIEW-162, the Delete Variant dialog only (the Upscale dialog's line was dropped, operator 2026-11-26): `make viewer-test`; `make viewer-test-e2e` | Unit: 141 passed; the new one in `skin-choices` was red before the code (`removalWarning is not a function`). e2e, every spec: 321 passed; the changed `texture-shared` test was red before (the dialog had no `.variant-named-head`). One start of the unit run failed before any test: the files of `webviewer/patches` were being written again at that moment; started again, it ran. Not run after this change: the host suite and the map build (no Python changed) |
| Old mark removed 2026-11-26 | The label for the old store's blanket mark and its code path deleted, in the pipeline and the viewer, with their 4 tests; the mark in the store is not touched. Files over 512 lines split: `keptrecipe.py` from `requests.py`, `statewriter.py` from `dataset.py`, `test_requests_kept.py`, `test_index_named.py`, `test_dataset_bakes.py`, `test_cli_skins.py`. `store.kept_sizes` is now `offered_sizes`. `make host-test` over every module of `testkit.tests.textures`; `make viewer-test`; `make viewer-test-e2e`; the commit hook's checks, each alone | Host: 572 tests, all passed. Viewer unit: 140 passed. Viewer e2e, every spec: 320 passed. Hook: file length and banned words pass, as do all others but one: the rule `py-subprocess-pipe-no-progress` fails on `scripts/testkit/tests/test_launch_dialog.py:170`, a file of another task. `ruff`: 11 findings, each at HEAD too (6 files unchanged; `cli.py`, `test_edit_transfer.py`, `test_dataset.py` checked at HEAD). Then `scripts/playtest.sh host-tests` (operator 2026-11-26, 23:34): the build passed, 225 files and 155 model entries packaged, stamp `04c0c150339e-f67c488649676c4e` as before; 1441 tests, all passed. By file times under the store's `sc2`, the build wrote `datasets/scoba/package.json` and nothing else there. Not run: `launch-check` |
| Live store 2026-11-26 | Read only, 22:22: file times under the store's `sc2/variants` and `sc2/locks`; entries by content | 285 `entry.json`. 257 were last written at 13:44; 12 between 14:51 and 15:01; 16 between 20:30 and 20:56, with 16 lock files of those times. So requests ran on the live store that day, through the working tree's code of the hour, not through a controlled run. The evening's Thor entries hold two or three sizes each (`thor_diffuse` `pbrify@2048+seedvr2`: 1024, 2048, 4096): made before the fix of O-HDS-19. At 22:22 no file there was newer than 20:56. 244 entries hold `accepted`, each with the blanket text; the same 244 hold no planes. Read again at 23:39: 296 entries. 11 are new, of 22:37 to 22:42 (the Command Center's textures) and of 23:15 (three Marine textures, dataset `stock`), with 11 lock files and upscaler jobs of those times; no run of the agent was going then. Each new entry holds one size file. 6 are revisions (`pbrify~2`, `fast~2`); the kept recipes beside them hold no file newer than 20:56. That is what the fix of O-HDS-19 and R-HD-158 ask for, seen in the store's files; it is not a controlled run, and R-HD-159 to 162 are not shown there |

One 1024x1024 plane on one Arc A770 took about 72 s with `seedvr2`, 27 s
with `pbrify`, 7 s with `fast`.

## 11. Setup

- `make install-hdtex` clones `upscale-on-arc` next to this project if
  absent, checks its pinned commit, and installs it. The pin must hold the
  tool's queue with job names, its worker list, its stall watch and its
  stand-in worker.
- The host tests run the tool's submit, queue and worker commands with a
  stand-in model and no GPU, on a queue of their own. They need the tool
  installed.
- `make install-deps` builds `tools/stormex` against CascLib `3.0`, which
  holds the Nova Covert Ops keys.
- Paths come from SPEC-PATHS. The store, the old caches (`SC2_BUILD/hdtex`)
  and the hdbake test copy (`SC2_TESTKIT/hdbake`) are below `SC2_WORK`, on
  the fast disk. The hdbake copy hard-links the store's planes, upscaled
  files, variants and index, so it writes no file data; it copies the index
  database and the datasets, which the bake changes. A file the bake makes
  lands in the copy only.
- `make classic-skins` runs section 12's tool.

## 12. Classic Skins

**Built, not seen in the game.** R-HD-60 to 62, R-HD-65.

- The game swaps a skin in by model entry: a `CSkin` lists pairs of
  `CModel` ids. `classic_skins.py` reads the pairs from the game data and
  writes them into the map's `ModelData.xml`: each From entry takes the
  fields of its To entry that differ, and keeps its id.
- So the map's own fields stay (R-HD-61), and hit volumes, camera heights
  and packaged textures find the classic model by the usual chain.
- 62 entries are written. A second run changes nothing.
- The Orbital Command and the Planetary Fortress show the Command Center's
  model and change with it. The hall footprint is measured on the classic
  model (SPEC-SCALED-FOOTPRINTS).
- The SCV is drawn at 200%: its actor's `Scale` is 2. Its unit data is
  unchanged.
- `Ultralisk` drops `RequiredAnims`, as the skin's entry has none.
- Left out: `CommandCenterDeathUnderConstruction` (not in the game data),
  and `Flags` of portrait entries. `--list` prints each pair left out.
- A field with a `##token##` no entry of its chain gives a value is open
  in the game data. It is kept as written and `--list` prints it: 10
  ragdoll `LowQualityModel` fields hold `##low##`, on both sides of their
  pair, so they are no change. Every other catalog error stops the tool.
  So does a catalog text that is not XML or not UTF-8: none of the 1097
  texts is either.
- A packaged map holds `.hd_prior`: what each catalog line named before
  the pack step set it (section 5.2). A read of the map puts it back.
- The tool reads the game install. Its result is committed in `src/`; the
  build does not read the install.
- Camera heights after the swap: Ultralisk 4.8761, Command Center and its
  forms 14.1710, SCV 2.0345.
- Not known: whether a player who does not own a skin sees its models.

Backing: [host] `test_classic_skins.py` (`SwapTest`, `MapDataTest`,
`MergeTest`). The look is O-HD-6.

## 13. Back Faces

**Built, not seen in the game.** R-HD-70 to 72.

- The game draws a triangle from its front only. The psi destroyer is made
  for a camera above it: pipes are open tubes, plates have no underside.
- `model_backfaces.py` runs in the map build. It writes a changed copy of
  the model at the game's own path, so no catalog changes.
- The hull is one region of 12800 triangles in 57 pieces. 54 are open,
  with 1250 open edges. The other 8 regions are glass and energy and are
  left (R-HD-71).
- Every triangle of a solid, one-sided region gets a back: the same
  triangle with two corners swapped, on copied vertices with negated
  normals. The model grows from 19417 to 37139 vertices.
- The back shows the front's texture, mirrored. Its material is a copy of
  the front's with two flags added: no shadows cast, no hit test.
- A front and its back are never drawn for the same eye.
- Not known: how the engine lights the backs, and whether fronts now
  receive new shadows.

Backing: [host] `test_model_backfaces.py`. [built] the model in the built
map was read back with those counts. The look is O-HD-7.
