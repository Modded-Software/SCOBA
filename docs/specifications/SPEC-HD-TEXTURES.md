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
| variant id | `original`, or the input's id and `model@size`, joined by `+`: `pbrify@2048`, `pbrify@4096+seedvr2@4096` |
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
- Sizes: 1024, 2048, 4096. A recipe's own size is four times its input's
  longest side, at most 4096. A size above it is refused (R-HD-123). A
  recipe whose own size is below 1024 has that size only.
- A `pbrify` or `fast` step whose input already has a side of 4096 is
  refused: it can add nothing.
- The size rule needs the original's longest side. A side of 0 or below
  is an error, not a size. An original whose DDS header cannot be read
  has no size: it is a state with its reason (4.9), and no request of it
  is offered or made. The colour-plane rule needs no size
  (`model_refusal`).
- A variant whose input is not made yet makes the input first, as a
  variant of its own.

One step, per plane:

1. The input is the plane of the input variant, or of the original.
2. An input above 2048 on a side is halved until it is not.
3. The runner upscales it four times, with edges made to match.
4. The output is halved until no side is above 4096: the recipe's own
   size.

Then the planes are joined, matched to the original's coarse content,
given a mip chain, and encoded. A variant at a smaller size is that mip
chain without its largest levels. Colour is halved and averaged in linear
light (H6). In each step a flip book gets a rim of 16 of its own edge
pixels around each cell before the runner. The rim is cut after it
(R-HD-56).

The input of a later step is the kept plane of its input recipe, halved
to the input's size. So a second size costs no GPU time (R-HD-6).

### 4.4 Texture store

The folder named by `TEXTURE_STORE`. `scripts/paths.sh` derives it as
`SC2_BUILD/texture-store` (SPEC-PATHS); unset, the pipeline stops. Not in
git, not on the repository disk (R-HD-85). The store holds no queue: the queue is the runner's.

| Path | Holds |
| --- | --- |
| `format` | the layout version |
| `<game>/planes/` | every plane a step takes or keeps, named by the hash of its pixels |
| `<game>/upscaled/<recipe>/` | the runner's output file for one upscale; `job.json`, the name of the job last asked to make it; an output that was no whole image, renamed with `.broken` |
| `<game>/variants/<origin>/<recipe>/` | `entry.json` (recipe, models per plane, own size, hashes, numbers) and one file per size; `request.json` while it is made, or after that failed; `request.log` (4.7) |
| `<game>/datasets/<dataset>/skins/` | one file per owner: its skins (4.6) |
| `<game>/datasets/<dataset>/` | `bakes.json` (4.6), `package.json` (R-HD-105), and `package/` for a dataset no build packages |
| `<game>/index/` | the game's own caches |
| `index.sqlite` | the state index (4.9) |

- An upscale's recipe: the hash of the input plane, the model, and the
  runner's version. Equal recipes share one folder, so a plane is upscaled
  once (R-HD-6, R-HD-86).
- Datasets that resolve an asset to the same origin share its variants
  (R-HD-87).
- A variant whose original now has another hash is stale (R-HD-88).
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

### 4.6 Skins and bakes

A skin file holds a format number and, per skin name, a map from asset
to variant id (R-HD-130, 131). A skin names no other skin: a copy or an
upscale reads its source once, and keeps no link to it.

- `original` is no entry: it names nothing (R-HD-132). A name is 1 to 40
  letters, digits, `-` or `_`. `original` is refused as a name, `new` as
  a name to save under; both in any case. The names of an owner are
  unique ignoring case (R-HD-138): a copy, an upscale or a rename to a
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
- `new` is New Skin (R-HD-137). It is stored like any skin. `set` or
  `rename` on an owner without a stored `new` stores it first: as the
  offered New Skin below, else empty. `rename --name new --new N` saves
  it. `delete --name new` discards it. A bake of `new` is refused. `copy`
  and `upscale` to `new` are refused while `new` is stored. `rename` to
  `new` is refused.
- The offered New Skin: when the owner holds no `new`, and what it shows
  (4.9 `shows`) names a variant other than `original`, and no saved skin
  names exactly those variants (the rest `original`), the owner's state
  lists `new` with them and `"stored": false`. Nothing is written.
- A skin may name a variant that is not made yet. Until it is made, the
  texture shows its original, with the request's state.
- A skin may name `original` for a texture. Baked, it shows the original
  over the bakes of the layers below, and packages no file.
- A skin may only name assets of its owner (R-HD-135) and ids of the asset's
  own variants.
- Only `core/skins.py` writes the file. A refused change leaves it as it
  was.
- **Skin upscale** (R-HD-134): makes skin N from skin S, with one model
  and one size. The viewer asks for N = `new`. For each texture of the
  owner: the input is what S names for it, else `original`; the variant
  is the input's id joined with `model@size`, or `fast@size` for a
  texture without a colour plane (R-HD-122). N names it, and it is
  requested. A texture that cannot reach the size, has no role, or has an
  original whose header cannot be read, keeps what S names and is listed
  with the reason.
- `bakes.json` holds a format number, per owner the skin's name and its
  map as it was when baked, and per terrain asset a variant id (R-HD-140,
  R-HD-145). A bake names the skin it was made from (R-HD-136):
  changing the skin does not change the bake's map; renaming it renames
  it in the bake; deleting it is refused while it is baked ("skin S is
  baked; unbake it or bake another skin first"). Only
  `core/skinbakes.py` renames or deletes a skin.
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
- A request for a variant that exists and is not stale is done at once.
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
| `index` | brings the dataset's part of the index up to date with its files (4.9). `--asset` also finds the role of those textures. |
| `upscaler` | the runner's worker command and whether it is idle |
| `request` | makes one variant: `--asset`, `--input` (a variant id or `original`), `--model`, `--size` |
| `skin` | `list`, `copy --from S --name N`, `rename --name N --new M` (from `new`: save), `delete` (of `new`: discard), `set --asset A --variant V` (or `--clear`), `upscale --from S --name N --model M --size Z`; each with `--owner O`. `new` is New Skin (4.6). |
| `bake` | `--owner O --skin N`, or `--asset A --variant V` for a terrain texture |
| `unbake` | `--owner O`, or `--asset A` |
| `package` | packages a dataset no build packages (R-HD-106); `gaps` (below) |

`--layer <folder>` names the dataset's own layer, for a game that takes
it from the caller. The viewer's server and the map build pass it. A
refusal prints an object with `error` and ends with exit status 1.

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
| `dataset` | game and dataset | the sizes, the models, the limits with their bands and info texts |
| `text` | distinct JSON text | the text once, compressed (zlib); its SHA-256 as the key; how many fields name it |
| `texture` | game, dataset and asset | the origin, the kind, and as `text` ids: the listing, the description of 4.2, and the state |
| `original` | game and origin | the hash and the longest side of the original, why its header cannot be read (empty when it can; the side is then 0 and is not a size), and the size and time of its file when they were read |
| `origin` | game, dataset and asset | the origin of every texture file the dataset can show, listed or not (5.1) |
| `owner` | game, dataset and owner | its title, its layer, the owners below it, its textures, its skins (with the offered New Skin of 4.6), what it shows now (`shows`: its bake, else the nearest bake below, else `original`) and its bake; its description and state as `text` ids |

The state of a texture is what a reader shows of it, in the shape of
SPEC-VIEWER 17.2: its variants with input, models, size, numbers,
problems, stale and accepted; its open requests; the models and sizes a
request may ask for, with the reason of each refusal; the path and hash
of each variant file; the terrain bake and whether the package holds its
file.

| Change | Who writes | Rows written again |
| --- | --- | --- |
| a request starts, a job of it starts to run, it encodes, it is done, it fails | the program that runs the request | every `texture` row with that origin, in every dataset |
| a skin | `skin` | that `owner` row |
| a bake | `bake`, `unbake` | that `owner` row, or that `texture` row |
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
| `model` | every texture a material of a model file names; the files are those of every `CModel` entry of the dataset's catalogs (the game's and the map's own), with variations | the model files | no |

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
  slots that disagree.
- Model files may read one texture with different flip book cells. The
  cells most model files use hold. A file that reads it another way, or
  with unknown cells, is not among its users: the pack step leaves that
  file on the original. A flip book is without usable cells when no file
  reads it with known cells, or as many files read it one way as another
  (R-HD-56). For `scoba`, 5 textures have such files.
- Codecs: DXT5, and DXT1 without transparent pixels.
- The textures each model file names are cached by the file's hash. The
  first list of `stock` took 17773 model files out of the storage in
  132 s. A later list takes 3 to 12 s.
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
  bakes of a dataset name more than one variant of a texture, the one the
  model layer names keeps that name; each other is
  `<stem>_scoba_hd_<h>_m.<ext>`, `<h>` the first 6 hex digits of the
  hash of its variant id.
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
  (R-HD-102).
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

## 6. Second Game

Not built (R-HD-111). It takes an adapter under `scripts/hdtex/<game>/`, a
codec for each format the core lacks, and one registration line. No core
file changes.

## 7. Requirement State

The host tests are in `scripts/testkit/tests/textures/`. A row names the
files that hold the tests of its requirements; it does not say that every
sentence of a requirement has a test. Rows of 2026-11-24 before variants
passed on that day.

| ID | State | Backing |
| --- | --- | --- |
| R-HD-1, 2 | [host] | `test_sc2_check.py` (`MapSourceTest`, `BuiltMapTest`); the build of 2026-11-24 |
| R-HD-3, 4, 112 | [host] | `test_sc2_game.py`, `test_sc2_sources.py` (`ArchiveTest`) |
| R-HD-113, 114 | [host] for textures; [plan] for owners, skins, bakes | `test_index.py` |
| R-HD-5, 6 | [host] | `test_runner.py`, `test_arc_queue.py`, `test_requests.py`; no request has run on the real GPU queue |
| R-HD-10 to 13, 52, 91 | [host] | `test_codec.py`, `test_encode.py` |
| R-HD-90 | [plan] | problems no longer hide; bake refusal |
| R-HD-53, 56 | [host] | `test_sc2_sources.py` (`RoleTest`), `test_sc2_game.py` (`ModelTest`), `test_steps.py` |
| R-HD-120 to 124 | [host] for ids, models per plane, sizes, refusals; [plan] for the viewer | `test_variants.py`, run 2026-11-25 |
| R-HD-85 to 88 | [host] for results; [plan] for variants | `test_store.py`, `test_dataset.py` |
| R-HD-130 to 133, 135, 136 | [host] for the skin and bake files and skin changes; [plan] for the viewer | `test_skins.py`, run 2026-11-25 |
| R-HD-134 | [plan] | skin upscale has no host test; the refusal while `new` is stored is in `test_skins.py` |
| R-HD-137 | [plan] until `test_skins.py` and `test_dataset.py` pass on New Skin | New Skin and its offer, 2026-11-25 |
| R-HD-97 to 100 | [host] for chains; [plan] for variant ids | `test_requests.py`, `test_arc_queue.py`; R-HD-98 on GPU 1 is not run |
| R-HD-140 to 143 | [host] for what the package writes; not in game | `test_sc2_owners.py`, run 2026-11-25; E-1, E-2 need a game run |
| R-HD-144 | [plan] | event-line models are not copied (section 5.2) |
| R-HD-145 | [host] | `test_sc2_game.py` (`PackageTest`, terrain tests) |
| R-HD-101 to 106, 54, 22 | [host] for picks; [plan] for bakes | `test_package.py`, `test_sc2_game.py` (`PackageTest`), `test_sc2_packaged.py`, `test_cli.py`, `test_sc2_check.py` (`BuiltMapTest`) |
| R-HD-24 | [host] | `test_sc2_check.py` (`CheckTest`) |
| R-HD-21, 55 | [boot] | run `tps/20261124-220055`, picks; not run with bakes |
| R-HD-107 to 111 | [host] | `test_registry.py`, `doubles.py`: a second game, a second format, a stand-in upscaler |
| R-HD-60 to 65 | section 12 | |
| R-HD-70 to 72 | section 13 | |

## 8. Open Points

| ID | Point |
| --- | --- |
| E-1 | Not known: whether a `CModel` entry the map makes, holding every field of a stock entry, shows in the game as the stock one does (5.2). A game run decides it. |
| E-2 | Not known: whether an actor copy with a unit's events, with those events taken from the stock actor, shows that unit and no other (5.2). A game run decides it. |
| O-HDS-2 | The results taken in from the old caches name the upscaler version of those caches. Whether the tool's current version gives the same pixels is not compared. A result is made again only when its original changes. |
| O-HDS-4 | 18 model textures of today's map miss a limit and are packaged as accepted. Whether each should be made again or go back to its original is not decided. |
| O-HDS-5 | The map shows 201 model entries; 159 of them name a picked texture. Their 287 model copies take 76 MB. The map of the variant code held 167 copies of 44 entries, 19 MB; its folder was 1134 MB and is 1186 MB now. The package step takes 18 s of the build. Whether the larger map costs load time or memory in the game is not measured. |
| O-HDS-6 | Whether the game loads a 4096 texture named by a model file is not known. The terrain ones load (H11). |
| O-HDS-8 | Why GPU 0 stalls on a SeedVR2 tile that fills it is not known. GPU 1 reports "out of memory" for the same tile, also while another process holds 1.3 GiB there. The tool's watch ends the stall; it does not explain it. |
| O-HDS-9 | Two requests that ask for one plane in the same instant may both submit it. The plane is then upscaled twice, with the same pixels. No lock prevents it. |
| O-HDS-12 | Which asset folder the running game reads is not checked: whether `teen.sc2assets` ever wins over `base.sc2assets`, and which language folder an install of another language reads. The rule of 5.1 names `enus` in the code. |
| O-HDS-13 | `newgoosculpted_diffuseblood.dds` misses the correlation limit with Upscale 4x (0.477) and with Soft 4x (0.447), so the build packages its original. Whether another model reaches the limit is not tried. |
| O-HDS-14 | Three items of an audit of 2026-11-24 were kept in session notes only and are lost but for their titles: "encode profile", "intermediate sizes", "batch `judge`". What each asked for is not known. |
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
