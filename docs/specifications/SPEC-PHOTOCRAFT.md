# SPEC-PHOTOCRAFT: Texture Editing in PhotoCraft

**Date:** 2026-11-25
**Status:** Built. PhotoCraft is built at its pin and installed on this
machine. Section 14 says what a test proved. Only targeted test runs were
made; no full suite was run. Section 3 holds what was read and what was
seen on this machine. Section 13 holds what the trials measured. The
operator checks O-PC-1 to O-PC-6 are open.
**Requirements:** [REQ-PHOTOCRAFT](../requirements/REQ-PHOTOCRAFT.md)
**Beside it:** [SPEC-VIEWER](SPEC-VIEWER.md) section 17,
[SPEC-HD-TEXTURES](SPEC-HD-TEXTURES.md) section 4,
[SPEC-PATHS](SPEC-PATHS.md).

Names and types of every interface are in the code. This document states
duties and rules.

## 1. Principle

- PhotoCraft is built from its source at a pin, twice: the editor site,
  with a small patch of ours, and the renderer, as upstream wrote it.
- The viewer's own service serves the site, on the viewer's own address.
  There is no second server.
- The texture window's tiles have an **Edit Texture** button. It opens the
  editor in a floating window of the page, on an edit session.
- A session is a folder in the texture store: the base, the scratch, the
  rendered planes and a record. Its files hold the truth.
- The scratch is one PSD. Each plane of the texture is a named group of
  layers in it.
- The pipeline makes a session and builds its scratch. It reads a changed
  scratch by rendering each plane group with the renderer. It makes the
  edited variant. The viewer's server only carries bytes and reads records.
- A save in the editor writes the scratch. A changed scratch is offered
  for transfer. A transfer makes a new variant and changes nothing else.

## 2. Labels

State: **[host]** a Python `unittest` passed. **[run]** a viewer spec
passed in a targeted run on 2026-11-25. **[built]** in the code, no
passing check. **[plan]** not in the code. **[operator]** only a person
can judge it.

Source of a fact: **[read]** read in PhotoCraft's source at the pin of
section 5.1, not run. **[machine]** seen on this machine on 2026-11-25.
**[trial]** measured by a trial of section 13. **[told]** said by a page
that is not PhotoCraft's own; not checked.

## 3. Facts

### 3.1 PhotoCraft, the editor

| ID | Fact | Source |
| --- | --- | --- |
| P1 | The project is `storytold/photocraft` on GitHub, in Rust, with the interface drawn by egui on wgpu. Its licence is MIT or Apache-2.0, at the user's choice. | [read] `README.md`, `Cargo.toml` |
| P2 | The newest release tag is `v0.23.1`, commit `45066c48292e92229ada3459a83453439514c83d`. A tag `v0.24.0-rc.1` exists. The project calls itself early alpha. | [machine] the remote's tags; [read] `README.md` |
| P3 | The browser app is `apps/photocraft-web`. It is the desktop app's code built for `wasm32-unknown-unknown`. | [read] `apps/photocraft-web/src/main.rs` |
| P4 | It is built with Trunk: `trunk build --release` in `apps/photocraft-web` writes `dist/web` with `index.html`, one script and one `.wasm`. Trunk fetches the matching `wasm-bindgen` and `wasm-opt` itself. | [read] `docs/development.md`, `Trunk.toml` |
| P5 | Upstream's builds use Trunk 0.21.14 and the stable Rust of the day. The workspace needs Rust 1.95 or newer. | [read] `.github/workflows/ci.yml`, `Cargo.toml` |
| P6 | The build profile is `wasm-release`: one codegen unit and full link-time optimisation. Upstream's container recipe uses thin link-time optimisation and one build job, to need less memory. | [read] `Cargo.toml`, `Dockerfile` |
| P7 | One dependency is fetched from git by revision (`storytold/craft-libs`). The interface translations are a second repository, at the revision in `craft-i18n.rev`. Without them the build is English only. | [read] `Cargo.toml`, `Dockerfile` |
| P8 | The site is static files. It has no server code. Every address in its page is relative, so it works below any path, and the packaging script says it works inside a frame. | [read] `packaging/web/README.md`, `packaging/web/package.sh` |
| P9 | The server must send `.wasm` as `application/wasm`. | [read] `packaging/web/README.md` |
| P10 | The app draws with WebGPU when the browser has it, else with WebGL2. The address flags `?webgl` and `?cpu` force WebGL2 and the CPU canvas. Upstream says WebGPU needs a secure context: `https://` or `http://localhost`. The viewer is opened at `127.0.0.1`. The site starts there in the test browser (S2). Which of the two it draws with there was not recorded. | [read] `apps/photocraft-web/src/web.rs`, `packaging/web/README.md`; [trial] S2 |
| P11 | The browser app runs on one thread. | [read] `docs/development.md` |
| P12 | The page has no script of its own, no `postMessage`, and no address flag that names a file to open. | [read] `apps/photocraft-web/index.html`, `web.rs` |
| P13 | A file reaches the app in two ways: the browser's file chooser, and a drop on the canvas. Both end in a queue of name and bytes, `Services::inbox`, that the app drains each frame and opens as documents. | [read] `web.rs`, `crates/ui-egui/src/app/frame.rs` |
| P14 | Every save and export ends in one function of the browser shell, `Services::write`, with a file name and the bytes. Today it starts a browser download. | [read] `web.rs` |
| P15 | The shell sets `write_unconfirmed`: a download reports nothing back, so a saved document stays marked as not saved and the leave-page question stays armed. | [read] `web.rs`, `crates/ui-egui/src/services.rs` |
| P16 | A document opened from the queue has no path. **File > Save** on it suggests the document's name with the extension `psd`. A PNG comes out of **Export As**. | [read] `crates/ui-egui/src/app/files.rs` |
| P17 | The shell holds the app, and through it the open document. | [read] `web.rs` |
| P18 | Preferences are kept in the browser's `localStorage` under `photocraft.preferences`; brush presets in IndexedDB. Both belong to the address the site is served from. | [read] `web.rs` |
| P19 | The app asks before the page is left with work that is not saved. A module that traps shows a "PhotoCraft stopped" message with a reload link. | [read] `web.rs`, `index.html` |
| P20 | The app reads and writes DDS, PSD and its own layered format. | [read] `web.rs`, `files.rs` |
| P21 | The release archives of the browser build from v0.17.0 to v0.23.1 are said not to start: the app's script imports a small helper that the archive holds in another folder. The packaging script copies the script and not the helper, which fits. A build straight from Trunk keeps them together. | [told] a community page; [read] `packaging/web/package.sh` |
| P22 | The `.wasm` of v0.23.1 is said to be 37.5 MiB, 15.2 MiB compressed. The one built here, English only and with the bridge, has 32,090,848 bytes. | [told]; [trial] S1 |

### 3.2 PhotoCraft, the renderer

| ID | Fact | Source |
| --- | --- | --- |
| P23 | `apps/photocraft-cli` builds a program `photocraft-cli` for this machine, with no window. Its commands include `info`, `convert` and `run`. | [read] `apps/photocraft-cli/Cargo.toml`, `src/args.rs` |
| P24 | `run` opens a file, or makes a new document, then runs engine commands in the order given, each with JSON parameters, and prints each result as one line of JSON. With `--out` it saves the document; the extension chooses the format. | [read] `src/args.rs`, `src/document.rs` |
| P25 | It composes on the CPU unless `--gpu` or the variable `PHOTOCRAFT_GPU=1` asks for the GPU. `--no-gpu` overrides the variable. The `gpu` feature is on in a plain build. | [read] `src/gpu.rs`, `Cargo.toml` |
| P26 | The engine command `file.scripts.loadFilesIntoStack` takes a list of paths and makes a new document with one pixel layer per file, the first file lowest. Each layer is named after its file. The document takes the largest width and height, and the mode, depth and colour profile of the first file. | [read] `crates/engine/src/cmd/file_cmds/processing.rs` |
| P27 | `layer.select` picks a layer by name. `layer.groupLayers` puts the picked layers into a new group with a given name. `layer.setProps` sets a layer's name and whether it shows. | [read] `crates/engine/src/cmd.rs` |
| P28 | `file.export.layersToFiles` writes one picture per top-level layer into a folder, top to bottom. A group is written merged. Each is composed alone: the others are left out, and it is made to show and not clipped. With `visibleOnly` off a hidden one is written too. A top-level adjustment layer is not written and is named in the result with the reason. A file is named by a prefix, a four-digit index and the layer's name with unsafe characters replaced. | [read] `crates/engine/src/cmd/file_cmds/export.rs` |
| P29 | `info` prints the document as JSON: its width, height, mode and depth, and its layers top to bottom. Each layer has its name, its kind (`Group`, `Pixel`, `Adjustment`), whether it shows, its blend mode and opacity, whether it has a mask, its layer effects and its adjustment's kind; a group has its children. `info` takes no `--no-gpu`. | [read] `src/document.rs`, `crates/engine/src/inspect.rs`; [trial] S8 |
| P30 | A document carries a colour profile. An opened file is converted to the document's pixel format when it becomes a layer. | [read] `processing.rs`, `crates/io/src/lib.rs` |
| P31 | A PSD written by PhotoCraft keeps groups, masks, blend modes, adjustment layers, layer styles and hidden layers. The PNG of a group with one layer holds exactly that layer's pixels. A PSD stores opacity in 8 bits: 0.5 is read back as 0.5019608. A rendered PNG is RGB with a colour profile inside. | [trial] S4, S6 |
| P32 | `layer.select` takes a name and an `occurrence`; layers of one name are counted from the bottom. A new layer goes above the picked one, in its group. A top-level layer with no pixels gets no file from `layersToFiles`. | [trial] S6, S8; the layer order as `info` printed it in the run of `texture-edit-window` |

### 3.3 This machine and this project

| ID | Fact | Source |
| --- | --- | --- |
| M1 | `cargo` and `rustc` 1.96.1 are on the path, from the workspace's shared tools. | [machine] |
| M2 | That toolchain has no standard library for `wasm32-unknown-unknown`. Its `rustup` has no toolchain chosen and refuses to list targets. | [machine] |
| M3 | Trunk, `wasm-bindgen` and `wasm-opt` are not installed. | [machine] |
| M4 | 32 processors, 94 GB of memory. | [machine] |
| M5 | The viewer runs as a systemd user service on port 4517, set up by Ansible (`deploy/ansible`). Its memory limit is 4 GB. Test runs use port 4518. | `deploy/ansible/roles/viewer_dev` |
| M6 | A tool built from source has a pattern here: `scripts/setup/deps.sh stormex` clones at a pinned tag, applies the patches of `scripts/setup/patches/`, builds below `SC2_BUILD/deps`, and records the pins beside the result. | `scripts/setup/deps.sh` |
| M7 | A texture's role splits it into planes named `color`, `alpha`, `data` and `normal`. `color`, `data` of a data texture and `normal` have three channels. `alpha`, and `data` of a normal map with a free red channel, have one. | `scripts/hdtex/core/roles.py` |
| M8 | A role's join takes a one-channel plane given with three channels as their mean. It makes a normal plane unit length again and rebuilds the stored layout. Given no source, it does not match the result to the original's coarse content. | `scripts/hdtex/core/roles.py` |

## 4. Decisions

| ID | Decision | Why | Not chosen |
| --- | --- | --- | --- |
| D1 | Build from source at the pin (R-PC-1). | The operator asked for a clone and a build. A patch needs the source. The release archive is said not to start (P21). | The release archive. |
| D2 | A patch to the browser shell, the bridge (section 6). | The app has no way in or out for a host (P12). With the patch the scratch opens by itself and a save is confirmed. | No patch: the page would drop a file on the frame's canvas by a made-up event and catch the download link the shell clicks (P13, P14). It leans on how the shell is written inside and gives no confirmed save. |
| D3 | The viewer's service serves the site, below `/photocraft/` (section 7). | One address: the bridge asks the server with no cross-address rule, and the page can reach the frame. One managed service, already in the background (R-PC-10, R-PC-11). | A second service on its own port. It would need its own unit, health check and port, and a cross-address rule on every session route. |
| D4 | The scratch is one PSD with one top-level group per plane (R-PC-70). | The operator's answer. A group keeps a plane's layers together, and the renderer writes a group as one picture (P28). PSD is what **File > Save** offers (P16) and what other editors read (R-PC-74). | One plane as a flat PNG: the operator asked for layers. PhotoCraft's own format: other editors do not read it. One layer per plane with no group: the person's own layers would have no plane. A plane as an alpha channel of the document (O-PC-18). |
| D5 | A session is a folder of files in the texture store. Its state is worked out from them (R-PC-32, R-PC-34). | The store's rule: the files hold the truth. | A table of the state index. The viewer's server writes the scratch, and only the pipeline writes the index. |
| D6 | A transfer is a pipeline command that makes an edited variant (R-PC-51). | The original is never written (R-HD-86). Skins and bakes already carry a variant into the game. | Writing over the input variant. |
| D7 | The build brings its own Rust toolchain, below `SC2_BUILD` (R-PC-6). Operator 2026-11-25: "own". | The shared one has no WebAssembly target (M2) and is not this project's to change. | Adding the target to the shared toolchain. |
| D8 | English only: the translations are not fetched. | One download and one pin fewer (P7). | Fetching `craft-i18n` at its revision. |
| D9 | PhotoCraft's own renderer builds the scratch and reads it back (R-PC-73). | One compositor for the editor and the transfer: blend modes, masks, adjustment layers and styles mean the same in both. The pipeline needs no PSD code of its own. | A PSD library in the pipeline: it would compose differently from the editor, or not at all. The bridge exporting each plane at save: a scratch written by another program would have no planes (R-PC-41). |
| D10 | The renderer is not patched and never uses a GPU (R-PC-59). | The bridge is a browser matter. GPU 0 is the desktop's and GPU 1 the queue's. | |
| D11 | Every plane enters the scratch as an 8-bit RGB picture, a one-channel plane spread to three. | A document has one mode (P26). A grey file would be converted on its way into an RGB document (P30), and a conversion may change values. | A grey document per one-channel plane. |

## 5. Provisioning

One command: `make install-photocraft`. It runs `scripts/setup/deps.sh
photocraft`, in the pattern of M6 (R-PC-2).

### 5.1 Pins

In `scripts/setup/deps.sh`, beside the other pins (R-PC-4).

| Pin | Value |
| --- | --- |
| Source | `https://github.com/storytold/photocraft.git`, tag `v0.23.1`, commit `45066c48292e92229ada3459a83453439514c83d` |
| Rust | 1.96.1 for `x86_64-unknown-linux-gnu`, with the target `wasm32-unknown-unknown` |
| Trunk | 0.21.14, the release binary for this machine, with its SHA-256 |
| Renderer build | the words given to `cargo build`: release, locked, the package `photocraft-cli`, no default features. So the renderer has no `gpu` feature (P25). |
| Fonts | none: the install serves no fonts (5.3) |
| Patches | every file of `scripts/setup/patches/photocraft/`, by its SHA-256 |

`wasm-bindgen` is pinned by the source's `Cargo.lock`. Both builds run
with `--locked`. The install's record `photocraft.pins` holds one line per
pin above.

### 5.2 Places

All below `SC2_BUILD`, so off the repository disk and outside git
(R-PC-5).

| Place | Holds |
| --- | --- |
| `SC2_BUILD/deps/photocraft` | the first clone, at the tag. No step writes into it after the clone. |
| `SC2_BUILD/deps/photocraft-tree` | the build tree: a fresh local clone of the first clone, with the patches applied; Trunk's `dist/web`. Made anew by each build. |
| `SC2_BUILD/deps/photocraft-tools` | the Rust toolchain (`RUSTUP_HOME`), Cargo's registry and git cache (`CARGO_HOME`), the Trunk archive and binary, and the tools Trunk fetches |
| `SC2_BUILD/deps/photocraft-target` | Cargo's build folder (`CARGO_TARGET_DIR`), and the folder of the renderer check |
| `SC2_BUILD/deps/photocraft-logs` | one log per step, named after the step |
| `PHOTOCRAFT_HOME` | the install: `site/`, `bin/photocraft-cli` and the pin record `photocraft.pins`. A new path of SPEC-PATHS: `SC2_BUILD/photocraft`, exported by `scripts/paths.sh`, listed in `workpaths.NAMES` as a path that may not exist yet |
| `scripts/setup/patches/photocraft/` | our patches, in the repository |

### 5.3 Steps

In `scripts/setup/photocraft.sh`, sourced by `deps.sh`. Each step writes
its own log. A failed step stops the command and names the step and the
log (R-PC-7). When the install's pin record equals the pins, the command
says "photocraft present" and runs no step (R-PC-3).

| Step | Does |
| --- | --- |
| `toolchain` | installs the pinned Rust toolchain with its WebAssembly target into the tools folder, with the machine's `rustup` and the two home variables set. The shared toolchain is not touched (R-PC-6). |
| `trunk` | fetches the pinned Trunk archive once, checks it against the pinned SHA-256, unpacks the binary into the tools folder. Another hash is an error that names the archive to delete. |
| `clone` | clones the source at the tag into the first clone, when it is not there. A clone that does not hold the pinned commit is an error. |
| `tree` | deletes the build tree and clones it from the first clone at the tag. A tag that names another commit is an error. Then applies each patch in name order, with git, inside the tree. A patch that does not apply is an error that names it. |
| `build-site` | `trunk build --release --locked` in the tree's `apps/photocraft-web` |
| `build-renderer` | `cargo build` with the pinned words, for this machine, with the same toolchain |
| `check-site` | `index.html`, a script, one `.wasm` of more than 1 MiB, no address in the page that starts at the root, and upstream's four licence files in the tree |
| `check-renderer` | the built renderer makes two pictures, builds a PSD with one group for each, and writes one PNG per group. The step checks that both files are there. Their pixels are compared by the host tests of section 12, not by this step. |
| `install` | copies both results to a new folder beside the install, adds upstream's licence, notice and attribution files (R-PC-8), a fonts manifest and the pin record, then renames the folder to the install. A step that failed before leaves the old install as it is (R-PC-7). |

- The builds run with a path of their own: the tools folder, the pinned
  toolchain, then `/usr/local/bin`, `/usr/bin` and `/bin`. The caller's
  path is not used: a compiler found there first linked against another
  C library and failed.
- The site asks for `fonts/manifest.txt` at each start. The install holds
  one of a single comment line, so the browser logs no failed request and
  no font is served.
- A first clone that was pulled or edited changes no build: only the tag
  is read from it.

### 5.4 Checks and service

- `make deps-check` reports the install: absent, present and pinned, or
  out of date with the pin that differs. It installs nothing (R-PC-9).
- `make install-deps` does not build PhotoCraft: the build is long. It
  reports it as `deps-check` does.
- The Ansible role of the viewer has a step that runs the same command,
  with its own step log, when `viewer_photocraft` is true
  (`make viewer-provision PHOTOCRAFT=1`). The step reports no change when
  the install is present and pinned. A failed build fails the role with
  the log in the message. The role then requires the install in the
  server's health answer. The build does not run inside the service, so
  the service's memory limit does not bind it (M5). [machine]: run once
  with a present install; it reported no change and did not restart the
  server. A build by the step, and a failed one, were not run.
- The first build took 9 min 16 s, with a peak resident size of
  8,980,160 kB. The install has 97 MB (S1).

## 6. The bridge

Our change to PhotoCraft, as one patch file,
`scripts/setup/patches/photocraft/0001-host-bridge.patch` (R-PC-5). It
touches the browser shell only: it adds
`apps/photocraft-web/src/host.rs` and changes that app's `web.rs`,
`main.rs` and `Cargo.toml`.
Without the address value below, the app is as upstream built it. The
renderer is built from the same tree; the patch does not reach its code
(D10).

| Part | Duty |
| --- | --- |
| Address value `host` | a path on the site's own address: the session's routes (section 7). It starts with one `/`, holds only letters, digits and `/`, `_`, `.`, `-`, holds no `..`, and does not end in `/`. Any other form stops the start, with the reason in the page's loading box. |
| Open | at start, ask `host/scratch`. The reply's header `x-photocraft-name` names the document. Its name and bytes go into the app's queue of files to open (P13). No file chooser is shown (R-PC-22). A reply that is no success, or has no name, is `failed`. |
| Save | `Services::write` with a name ending in `.psd` sends the bytes to `host/scratch` with `PUT` and waits for the answer, in place of the download (P14). The save is confirmed: `write_unconfirmed` is off while a host is named, and an answer that is no success is an error the app shows (R-PC-25). |
| Other writes | a write with any other name is a download, as upstream does it: an export is the person's own file. |
| Messages to the page | by `postMessage` to the parent, to the site's own address only, each marked with the source `photocraft`: `ready`, `opened` with the name, `saved` with the name, `failed` with the reason, `unsaved` with yes or no when it changes. |

- Requests are made in same-address mode. A request to another address
  fails in the browser.
- The bridge takes no message from the page. The page never drives the
  editor.
- The save waits for the server inside `write`: it is a synchronous
  request, as `write` must answer before it returns (S3). The app runs
  on one thread (P11), so it does nothing else until the answer.
- A refused save sends no `saved`, starts no download, and leaves the
  document marked as not saved (S3).
- The messages of a start, in the order seen: `ready`, `unsaved` no,
  `opened`. Of an edit and a save: `unsaved` yes, `saved`, `unsaved` no.
- The patch count is kept small on purpose: each patch must be applied
  again on a new pin.

## 7. Serving

The viewer's server, in core. No game is named. The site is
`server/core/photocraft.ts`; the edit routes are
`server/core/editroutes.ts` over `server/core/textureedits.ts`; their
shapes are `shared/edits.ts`.

| Method and route | Reply |
| --- | --- |
| `GET /photocraft/<file>` | a file of the site. `.wasm` as `application/wasm`. A file that is not there: 404, never the page. |
| `GET /api/health` | also `photocraft`: whether it is installed, the install's recorded pins, or why there is none |
| `GET /api/<game>/textures/edit?dataset=` | the sessions of the dataset's textures, each with its state (section 8) |
| `POST /api/<game>/textures/edit/open?dataset=` | takes an asset and a variant. Makes or resumes their session; its state. A texture not judged yet is judged first. |
| `GET /api/<game>/textures/edit/<session>?dataset=` | one session's state |
| `GET /api/<game>/textures/edit/<session>/scratch` | the scratch. The header `x-photocraft-name` holds its file name. It names no dataset: the bridge asks it. |
| `PUT /api/<game>/textures/edit/<session>/scratch` | writes the scratch. It names no dataset. |
| `GET /api/<game>/textures/edit/<session>/base/<plane>`, `/rendered/<plane>` | one plane's two pictures, as PNG, for the dialog. The browser may keep them for an hour; the page puts the plane's hash in the address. |
| `POST /api/<game>/textures/edit/<session>/transfer?dataset=` | starts the transfer; the session's state once the request or the variant shows |
| `POST /api/<game>/textures/edit/<session>/discard?dataset=` | deletes the session |

- A game without a texture service answers 404 on every edit route
  (R-VIEW-100, R-PC-28).
- While PhotoCraft is not installed, the server starts, `/photocraft/`
  answers 404, the edit routes answer 503 with the reason, and the health
  answer says so (R-PC-13). The reason names `make install-photocraft`.
  The page reads the health answer once; a read that failed is made
  again. Without an install it shows no edit control. A site without a
  renderer counts as not installed.
- The site is read from `PHOTOCRAFT_HOME` on each request. A new install
  needs no restart.
- The server sends files as they are, with no compression. The site
  started in 306 ms in the test browser (S2). No compressed copy is made.
- A session id is 16 hex digits (section 8). A plane is one of the
  session's plane names. Anything else: 400. A session that is not
  there: 404. Another method: 405.
- A written scratch is streamed to a new name and renamed. The server
  never holds it whole in memory (M5). A scratch may be at most 1 GiB;
  more is a 413 and no file changes. [agent]
- A write answers once the file is in place. It does not wait for the
  check (section 8).
- A state carries `checking` while a check of the scratch runs, and
  `checkError` with the reason when the check of the scratch as it is
  could not run.
- A transfer of a session with a reason, or one that changes no plane,
  is refused with 400 and the reason. A session that is transferred
  already answers at once and starts nothing.
- The site makes no request past this machine (R-PC-12): the test
  browser asked only the viewer's address while the editor loaded,
  opened a scratch and saved it (S2, section 12).

## 8. Sessions

`<TEXTURE_STORE>/<game>/edits/<session>/`. The session id is the first 16
hex digits of the SHA-256 of the origin and the input variant's id, as a
JSON list of the two. So
one origin and variant has one session, whichever plane's tile opened it
(R-PC-30), and datasets that share an origin share it (O-PC-16).

| File | Holds | Written by |
| --- | --- | --- |
| `session.json` | origin, the asset and dataset it was opened from, the input variant's id and file hash, the plane names in order, width and height, each base's pixel hash, each transfer's plane hashes with its variant id | the pipeline |
| `base/<plane>.png` | each plane of the input variant as it was opened, 8-bit RGB (D11). Never written again (R-PC-31). | the pipeline, once |
| `scratch.psd` | the scratch (R-PC-70). | the pipeline, once; then the server (the editor's save); any other program |
| `rendered/<plane>.png` | each plane group as the renderer last wrote it | the pipeline's check |
| `scratch.json` | what the check last read: the scratch's size and time, each rendered plane's pixel hash, the names of the layers left out, or why the scratch cannot give every plane | the pipeline's check |

The scratch as it is built (R-PC-71):

- Width and height of the input variant. RGB, 8 bits a channel.
- One top-level group per plane, named with the plane's name. The order,
  top to bottom: `color`, `normal`, `data`, `alpha`, those the texture
  has. So the editor opens showing the colour.
- In each group one pixel layer, named `base`, with the plane.
- Nothing else: no background layer, no hidden layer.
- To see or edit a lower plane the person hides the groups above it. A
  hidden group is still read (P28).

States (R-PC-34), from the files:

| State | When |
| --- | --- |
| stale | the input variant is not in the index, or its file hash is not the recorded one (R-PC-35) |
| unchanged | every rendered plane's hash is its base's (R-PC-42) |
| transferred | the rendered planes' hashes are those of the last transfer |
| edited | any other hashes; or the scratch cannot give every plane, with the reason (R-PC-75) |

- Stale is judged first. A stale session keeps its files and can be
  opened, to save the work elsewhere. Its transfer is refused.
- The scratch is checked when its size or time differ from
  `scratch.json`. The server then starts the pipeline's check (section
  10), one at a time per session, and does not wait for it. Until it
  ends, the session answers its last state and `checking`. A read of a
  state starts nothing when size and time agree. A check that could not
  run is kept as `checkError` for that scratch and is not started again
  until the scratch changes.
- Stale is read from the state index: the original's hash for the
  original, the variant's file hash and its stale mark otherwise.
- A scratch that is being written is not read half: the editor's save is
  renamed into place. Another program that writes in place may be read
  half written; the check then reports a file that cannot be read, and
  the next change is read whole.
- A transfer keeps the session. It is transferred until its scratch
  renders other planes; then it is edited, and offered again (R-PC-58).
- Nothing deletes a session but its discard (R-PC-32). A discard removes
  the folder. The edited variants it made stay.
- Two editors on one session: the last save holds. There is no lock.

## 9. The page

### 9.1 Edit Texture

- Each tile that shows a variant (In game, Original, each variant) has a
  pencil button at the bottom left of its preview, titled **Edit
  Texture** (R-PC-20). The list rows have none. The In game tile edits
  the variant it shows.
- A click does not reach the tile: nothing is picked (R-PC-23).
- The session is the texture's and the variant's. The tile's plane is
  not part of it: every plane is in the scratch.
- A tile whose variant has a session shows its state on the button: a
  dot, amber for edited, grey otherwise. The list row gets the badge
  EDIT while a session of that texture is edited (R-PC-37).
- The button is absent when the health answer has no install, and for a
  game without a texture service (R-PC-13, R-PC-28).
- A texture has planes once the pipeline has judged it (SPEC-VIEWER
  17.2). Until then the button is disabled and says "not read yet". A
  texture with a reason why it cannot be upscaled has no role, so no
  planes: its button is disabled and shows that reason (R-PC-29).
- The texture page sends the page event `texture-edit` with the game,
  dataset, asset and variant. The viewer page opens the session and the
  editor window, as it does for `texture-upscale`.

### 9.2 Editor window

- One floating window, `page/core/editorwindow.ts`, made as the texture
  window is: `ui.floatingWindow` with a frame in its body (R-PC-21). Its
  title is "edit", the texture and the input variant.
- The frame's address is the site's page with the value `host` set to the
  session's routes.
- A fresh frame for every session. One editor at a time: opening another
  session first asks as closing does.
- The window adds no key handler to the frame. Escape belongs to the
  editor (R-PC-24). The window closes by its close button.
- The window listens for the bridge's messages, from its own frame and
  its own address only. Until `opened` it shows "loading". `failed`, or
  no `ready` in 60 s, shows the reason and a **Reload Editor** button
  (R-PC-27).
- Closing while the last `unsaved` said yes asks: **Close Editor** (red,
  the work since the last save is lost), **Keep Editing** (R-PC-26).
- On `saved` the page reads the session's state at once.
- A closed window unloads the editor: it held the scratch in memory.
- **Reload Editor** loads a fresh frame on the same session.

### 9.3 Detecting

- While the texture window or the editor window is open, the page asks
  the sessions route every 2 s (R-PC-40, R-PC-41). The route stats each
  scratch; a changed one starts its check (section 8).
- With neither window open nothing is asked. A scratch changed meanwhile
  is found when a window opens.
- A session that turns edited, with rendered planes the page has not
  offered yet, opens the transfer dialog (R-PC-43, R-PC-44). The offered
  hashes are kept in the page's stored state, so a reload does not offer
  them again.
- The offered hashes are the page setting `viewer.edits.offered`: by
  session, its rendered planes' hashes. A discard removes the session's
  entry.
- A session that is being checked, or whose check could not run, is not
  offered.
- An edited session whose scratch cannot give every plane opens no
  dialog. When the page finds it, the status line says the texture, the
  variant and the reason, as a failure, once per reason. The session
  list shows the reason too, and offers no **Transfer Edit…** for it
  (R-PC-75). A check that could not run is said the same way.
- One dialog at a time: while a dialog of this section is open, no other
  session is offered.

### 9.4 Transfer dialog

One dialog (R-PC-50), by `ui/components/dialog.ts`.

- Title: **Transfer Edit to Texture**.
- The texture, the input variant and the size.
- Per changed plane: its name, the base and the rendered plane as two
  pictures, side by side.
- The unchanged planes by name: "not changed: normal, alpha".
- The layers left out by name: "not in a plane group, left out: Curves 1"
  (R-PC-76).
- "A new variant of <texture> will be made from your edit. <input> and
  the original stay as they are. No skin and no bake changes." When the
  input is the original: "The original stays as it is."
- **Transfer Edit** starts the transfer route. The new variant shows in
  the tiles as an open request, then as a variant (R-PC-56, R-PC-57).
  The dialog offers nothing about skins.
- **Keep Editing** closes the dialog. The session stays edited, with its
  mark and a **Transfer Edit…** entry in the session list.
- **Discard Edit** is red. It asks again, naming the texture, then calls
  the discard route.
- A refused transfer shows its reason in the dialog. Nothing changes
  (R-PC-53).

### 9.5 Session list

- The texture window has a button **Manage Edits…** while the dataset
  has a session. Its dialog lists each session: texture, input variant,
  state, the planes that changed, the layers left out, when the scratch
  last changed, and the scratch's path on disk, for another program
  (R-PC-33, R-PC-74, R-PC-76).
- Per session: **Resume Edit** opens the editor window on it; **Transfer
  Edit…** when it is edited, has no reason and changes a plane;
  **Discard Edit**, red, after a question.
- A discard of the session the editor window is open on closes the
  window first. With unsaved work that asks, and the session may stay.

### 9.6 Parts

| Part | File | Duty |
| --- | --- | --- |
| Tiles | `page/core/tiles.ts` | the button and its dot on each tile that shows a variant |
| Texture page | `page/texview/edits.ts`, `rows.ts`, `main.ts` | the sessions the window hands over; the badge EDIT on a list row; **Manage Edits…** |
| Texture window | `page/core/texturewindow.ts` | hands the edit tools to the page only for a game with the service and with an install; passes the sessions on |
| Editor window | `page/core/editorwindow.ts` | 9.2 |
| Feature | `page/features/edits/index.ts` | opens sessions, reads them every 2 s, offers, reports |
| Dialogs | `page/features/edits/dialogs.ts` | 9.4, 9.5 |

- Page events: `texture-edit` (game, dataset, asset, variant) and
  `edits-manage` (game, dataset).
- A floating window may refuse Escape and may ask before it closes. The
  editor window uses both.
- For the tests the page gives the state of the editor window, of the
  dialogs, the sessions read, what was offered and what was said; and a
  call that opens the editor on a session, as **Resume Edit** does.

## 10. The pipeline

`scripts/hdtex/core/edits.py`, with one command of `scripts/hd_textures.py`
(SPEC-HD-TEXTURES 4.8): `edit`, with four actions. It imports no game. It
runs the renderer from `PHOTOCRAFT_HOME`, always with `--no-gpu` (D10).

| Action | Does |
| --- | --- |
| `open` | resolves the asset to its origin; splits the variant into planes at its size; writes the bases; builds the scratch; checks it; writes the session folder. A session that is there is left as it is and answered. |
| `check` | renders the scratch's plane groups and writes `rendered/` and `scratch.json`: each plane's pixel hash, or the reason the scratch cannot give every plane (R-PC-75) |
| `transfer` | makes the edited variant, as a request (SPEC-HD-TEXTURES 4.7) with no runner job (R-PC-57, R-PC-59) |
| `discard` | removes the session folder |

Building the scratch, one `run` of the renderer:

- A new document of one pixel, then `file.scripts.loadFilesIntoStack`
  with the bases, the lowest plane first (P26).
- Per plane: `layer.select` of its layer by its file's name,
  `layer.setProps` to name it `base`, `layer.groupLayers` with the
  plane's name (P27).
- Save as `scratch.psd`, with `--no-gpu`.
- It took 0.16 s, 0.48 s and 1.57 s at 1024, 2048 and 4096 pixels a
  side, for scratches of 12.8 MB, 51 MB and 205 MB (S8).
- Then `open` runs the check. A fresh scratch whose rendered planes are
  not its bases, pixel for pixel, fails the open with the plane and the
  count of differing pixels. No session is left. There is no tolerance
  (S4).

The check:

1. `info` of the scratch (P29). Refused with what was found: a file the
   renderer cannot open; another width or height; another depth than 8
   bits a channel; a plane's group that is missing or there twice.
2. A top-level layer that is no group with a plane's name is left out
   (R-PC-76). It belongs to no plane, and a plane group is composed
   alone, so it changes no plane. Its name goes to `scratch.json`.
3. One `run` with `file.export.layersToFiles`, PNG, `visibleOnly` off,
   into a new folder (P28). So each plane group is composed alone, shown
   or hidden. A file is named by the prefix, the layer's place from the
   top in four digits, and the layer's name; a plane is found by its
   group's place. The pictures of the layers left out are deleted.
4. Each PNG is read as 8-bit RGBA. A pixel with alpha below 255 refuses
   the scratch, with the plane and the count.
5. The folder is renamed to `rendered/`, and `scratch.json` is written
   with the hash of each plane's RGB pixels.

The render of step 3 took 0.28 s, 0.39 s and 1.26 s at 1024, 2048 and
4096 pixels a side, for a fresh scratch (S8).

The edited variant:

- Its id is its input's id, `+`, the step `edit` with the first 12 hex
  digits of a hash, `@` and the size: `pbrify@2048+edit3fa9c1d2aa10@2048`.
  Made from the original it has no input part: `edit3fa9c1d2aa10@1024`.
  The hash is the SHA-256 of every plane's name and rendered pixel hash,
  in the session's plane order. The step fits the id rule the code has.
  Equal input and rendered planes give one id, so one variant (R-PC-54).
- It has one size: the input variant's.
- A plane whose rendered hash is its base's is the input variant's own
  plane. A changed plane is the rendered plane (R-PC-52).
- The planes are joined, given a mip chain and encoded as a variant is
  (SPEC-HD-TEXTURES 4.3), with no source: the result is not matched to
  the original's coarse content (M8). That step would take a part of the
  edit back.
- The join's own rules hold (M8): a one-channel plane painted in colour
  becomes the mean of its channels; a painted normal is made unit length.
- Its entry records, as `edit`, the input, the changed planes, the hash
  and the session; the models per plane (a changed one: `edit`; the
  others: the input's); no runner; and the numbers (R-PC-55).
- An input that is stale or gone refuses the transfer (R-PC-35). A
  scratch that cannot give every plane refuses it (R-PC-53).
- The transfer runs the check first when the scratch's size or time are
  not the recorded ones.
- After it, `session.json` records the transfer's plane hashes and
  variant id, and the index is written (SPEC-HD-TEXTURES 4.9).

Limits (R-PC-80 to R-PC-83, SPEC-HD-TEXTURES 4.5):

- A variant whose entry names a changed plane is user-made.
- All four numbers of a user-made variant are measured and recorded. None
  makes a problem: each has the band `none`. The viewer shows them with
  no colour band and no info mark.
- A bake does not look at the numbers of a user-made variant.
- A variant a model makes from a user-made one is a model's: the limits
  apply to it. Its reference is the nearest user-made variant among its
  inputs, not the original (R-PC-83). The reference is used where the
  original is used today: as the source the join matches the coarse
  content to, and as what the numbers compare with.
- A variant with no user-made variant among its inputs keeps the
  original as its reference.
- A request's entry names its reference, and so does the variant it
  makes.

The viewer's server runs `open` and `discard` and waits for them. It
starts `check` and does not wait. It starts `transfer` as it starts
`request`: it outlives the server. The route then waits up to 30 s
until the index shows the request or the variant. A discard and a
transfer wait for a running check first.

## 11. Effect on other documents

These documents say what this one adds to their subject. The sentences
added to the requirements are the agent's; the operator has not read
them.

| Document | Holds |
| --- | --- |
| REQ-HD-TEXTURES | section 2: a variant may also be made by a transfer. R-HD-121 and R-HD-124: a sentence for the edited variant (O-PC-14). R-HD-11 and R-HD-90: they bind a variant a model made; an edited variant has no problem and its bake is not refused (R-PC-80, R-PC-81). R-HD-11: a model's variant made from an edited one matches that one (R-PC-83). R-HD-85: the store holds the sessions. |
| SPEC-HD-TEXTURES | 4.1 the `edit` step in the variant id; 4.3 the edited variant; 4.4 the `edits` folder; 4.5 no limits on a user-made variant, and the reference; 4.7 a transfer as a request with no job; 4.8 the `edit` command |
| REQ-VIEWER | R-VIEW-132 names the button, with a pointer to REQ-PHOTOCRAFT |
| SPEC-VIEWER | 8 the routes; 10.3 the setting `edits.offered`; 17.1 the parts and the `edit` command; 17.2 the band `none`; 17.3 and 17.6.1 the button, the badge, **Manage Edits…**, numbers with no band; 17.8 the tests |
| SPEC-PATHS | `PHOTOCRAFT_HOME` and the places of 5.2 |
| `Makefile` | `install-photocraft`; `viewer-provision PHOTOCRAFT=1`; `host-test`, which runs named host test modules with no map rebuild |
| `deploy/ansible` | the role's step and `viewer_photocraft` |

## 12. Tests

Each with a negative case (R-PC-60). The tests that need PhotoCraft fail
without it and name `make install-photocraft`. No test is left out for a
missing install.

Host tests are under `scripts/testkit/tests/`; viewer specs under
`webviewer/tests/`. A scratch is changed by the renderer's own commands,
as another program would. The tests passed in targeted runs on
2026-11-25. No one has checked that they assert every clause.

| Area | Proves | Negative | Test |
| --- | --- | --- | --- |
| Pins | `deps.sh` holds every pin; the install's record equals them | a later patch: the check names the pin the install was built without; a record with a pin that is gone: out of date | host `deps/test_deps_photocraft` |
| Provisioning steps | the steps run in order, on the build tree; the install has the site, the renderer, the licence files, the fonts manifest and the record; a present install does no work; a stale one is built again | a Trunk archive of another hash, a patch that does not apply, a site with too small a module, a first clone at another commit: each stops the steps, names the step and its log, and leaves the old install | host `deps/test_deps_photocraft`, with the build's tools as stand-ins |
| Site routes | the page, the script and the `.wasm` are served, the `.wasm` as `application/wasm`; the health answer has the pins | a file that is not there: 404, not the page; no install: 404, the edit routes 503, and the health answer says why | e2e `photocraft-site`; unit `photocraft-absent` |
| Session open | the folder holds a base per plane, the scratch and the record; the scratch has one group per plane, in order, each with one layer `base`; a second open answers the same session | a variant that is no variant of the texture, a texture with no role: refused, no session | host `textures/test_edits`; unit `texture-edits-api` |
| States | unchanged, edited, transferred and stale each from files that make it | a scratch saved again with other bytes and the same planes is unchanged | host `textures/test_edits`, `test_edit_transfer` |
| Layers | a layer with a mask and a blend mode, and an adjustment layer, change their plane only; a hidden group is still read | a hidden added layer changes nothing | host `textures/test_edits` |
| Scratch rules | a layer outside the groups is left out and named | another size; another depth; a group renamed; a group deleted; a base erased in part; a file that is no document: each refused with what was found | host `textures/test_edits` |
| Scratch write | a `PUT` writes the file and answers | a bad session id: 400; a body past the bound: 413; no file changes | unit `texture-edits-api` |
| Detecting | a scratch written by another program turns the session edited after its check | a scratch written again with the same planes stays unchanged | unit `texture-edits-api` |
| Transfer | the variant has the id of section 10, the rendered plane where it changed, the input's own plane where it did not; the index lists it | the same scratch twice: one variant; a stale session makes no variant; a stopped transfer leaves no variant; a scratch that changes no plane is refused | host `textures/test_edit_transfer`, `test_edits` |
| Limits | a user-made variant far from its original has its numbers and no problem, and is baked; a model's variant made from it is compared with it | the same pixels as a model's variant have the problem and the bake is refused; a model's variant far from its user-made input has the problem | host `textures/test_edit_transfer` |
| No GPU | a transfer finishes with an upscaler that refuses every job, and the renderer is started with `--no-gpu` | | host `textures/test_edit_transfer` |
| Button | each tile that shows a variant has the button; a click opens the session in the editor window and picks nothing | no list row and no Upscale tile has one; no button without an install; none for a game without a texture service; a texture with a reason has it disabled, with the reason, and a click opens nothing | e2e `texture-edit-button` |
| Editor window | the window opens on the session, the bridge says `ready` then `opened`, the frame's canvas has a size | a session that is gone: the window shows the reason and **Reload Editor**; Escape leaves the window open; closing with unsaved work asks | e2e `texture-edit-window` |
| Bridge save | a save by the editor's own key writes the scratch on disk; its plane groups are as built; a scratch with a mask, a blend mode, an adjustment layer, a layer style and a hidden layer keeps them and its planes | no download starts; the keys do not reach the viewer page; a write the server refuses gives no `saved` and the work stays unsaved | e2e `texture-edit-window` |
| Offer | an edited session opens the dialog once, with the changed plane as two pictures and the others by name; **Transfer Edit** makes one variant and it shows in the tiles with no band; the badge and the dot follow the state | the dialog has no skin control; **Keep Editing** changes nothing and does not open again, also after a reload; a scratch that cannot give every plane is not offered, its reason is said, and its transfer is refused | e2e `texture-edit-offer` |
| Session list | lists the sessions with state, changed planes and the scratch's path; **Resume Edit** opens the window; **Discard Edit** asks again | Cancel keeps the folder; a discarded session is gone from the list and from disk, and its variant stays | e2e `texture-edit-offer` |
| No request past the machine | loading the editor asks only the viewer's address | | e2e `photocraft-site`, `texture-edit-window` |

Not proven by a test:

- The Ansible step of 5.4 has no test. It was run once by hand of the
  agent, with a present install (5.4).
- A request tile has no button: no test asserts it.
- **Discard Edit** inside the transfer dialog, and a refused transfer's
  reason shown in the dialog (R-PC-53), are not clicked by a test. The
  route's refusal is tested.
- A transfer from a session of a model's variant is a host test only.
- The edit specs were run one file at a time. They were not run in a
  full suite beside the other specs.

Not for a test (R-PC-61): O-PC-1 to O-PC-6 of the requirements. A
screenshot of the editor proves nothing here.

R-PC-74 has no test of its own with a program that is not PhotoCraft:
none is provisioned. The Detecting row writes the scratch with the
renderer. A scratch edited in another editor is an operator check until
one is provisioned (O-PCS-9).

## 13. Trials

Each trial was run on this machine on 2026-11-25, at the pin of 5.1. The
design rests on these results. A new pin means they are run again
(O-PCS-1).

| ID | Trial | Result | Rests on it |
| --- | --- | --- | --- |
| S1 | The steps of 5.3: do the site and the renderer build from the pinned source with the pinned tools; does the renderer build without its `gpu` feature; how long, how much memory, how large. | Both build. The renderer builds with no default features. First build: 9 min 16 s, peak resident size 8,980,160 kB, install 97 MB. A build again with the patch: site 320 s, renderer 199 s. The `.wasm` has 32,090,848 bytes. | section 5 |
| S2 | The site, served below a path by the viewer's server, in a frame of the page: does it start in the test browser; which requests does it make. | It starts, in 306 ms. Every request went to the viewer's address. The operator's browser is O-PC-1. | D3, R-PC-12 |
| S3 | The bridge: does a PSD asked from the server open; may `write` wait for the server's answer in the browser. | The scratch opens with no file chooser. `write` waits with a synchronous request. A save answered 507 gave no `saved`, no download, and the work stayed unsaved. The body sent for a 1024 scratch had 12,845,384 bytes and began with the PSD signature. | section 6, R-PC-25 |
| S4 | The round trip: planes built into a scratch and rendered back are the same pixels, for a colour, a normal, a data and a one-channel plane with every 8-bit value. Then the same scratch opened and saved by the editor with no edit of a plane. | 0 differing pixels in both. | D9, D11, R-PC-42 |
| S5 | Keys: with the frame in focus, do the editor's shortcuts arrive, and does the viewer page take none. | New layer, Enter and save by key work in the frame. The viewer page's camera, grid and items did not change. | R-PC-24 |
| S6 | What a PSD keeps: a scratch with an added layer, a layer mask, an adjustment layer, a layer style, a blend mode and a hidden layer, saved by the editor and rendered again. | Each is still there, and every plane renders to the same pixels. Opacity is stored in 8 bits (P31). | R-PC-72, R-PC-73 |
| S7 | Memory: the editor with a scratch of three 4096 by 4096 planes and a few layers, in the page beside the 3D view. | Not measured. | O-PC-2 |
| S8 | The renderer's commands: the list that builds the scratch; the file names `layersToFiles` gives; how long a build and a render take. | The list and the names of section 10. Build 0.16 s, 0.48 s, 1.57 s and render 0.28 s, 0.39 s, 1.26 s at 1024, 2048 and 4096 pixels a side. | section 10 |

- The editor's side of S3, S5 and S6 is now a test of section 12
  (`texture-edit-window`), on the session's own routes.
- How a plane group made see-through renders was not tried. The check
  refuses any pixel that is not opaque (section 10).

## 14. Requirement state

The state is that of the tests of section 12 that cover the group. A
group is [host] or [run] when its named tests passed; that is not a
claim for every clause of every requirement in it.

| Requirements | Section | State |
| --- | --- | --- |
| R-PC-1 to R-PC-9 | 5 | [host] the steps, with the build's tools as stand-ins. [machine] the real build and install (S1). |
| R-PC-10 to R-PC-13 | 5.4, 7 | [run]. The Ansible step: [machine], with a present install only. |
| R-PC-20 to R-PC-29 | 6, 9.1, 9.2 | [run]. How the editor looks and works: [operator], O-PC-1 to O-PC-6. |
| R-PC-70 to R-PC-76 | 8, 9.4, 9.5, 10 | [host], [run]. R-PC-74 with a program that is not PhotoCraft: [operator] (O-PCS-9). |
| R-PC-30 to R-PC-35, R-PC-37 | 8, 9.1, 9.5 | [host], [run] |
| R-PC-40 to R-PC-44 | 8, 9.3 | [run] |
| R-PC-50 to R-PC-59 | 9.4, 10 | [host], [run]. R-PC-53's reason in the dialog: [built]. |
| R-PC-80 to R-PC-83 | 10, 11 | [host]. The tile with no band: [run]. |
| R-PC-60, R-PC-61 | 12 | section 12 |

## 15. Open points

| ID | Point |
| --- | --- |
| O-PCS-1 | The pin is a release of a project in early alpha (P2). A new pin means the patches are applied again and S2 to S8 are run again. |
| O-PCS-2 | The bound of section 7 (1 GiB), the 2 s of 9.3 and the 60 s of 9.2 are the agent's numbers. |
| O-PCS-3 | Two editors on one session have no lock (section 8). |
| O-PCS-4 | An edited variant has one size. A smaller size of it would be its mip chain without the largest levels, as for other variants; not designed. |
| O-PCS-5 | The session list is per dataset. Sessions are shared by origin (O-PC-16), so one session can show in two datasets' lists. |
| O-PCS-6 | By its id an edited variant can be the input of an upscale request. Whether the request code takes it as one is not read and not designed. |
| O-PCS-7 | The session and transfer routes write into the texture store, as the request and skin routes do. The server listens on this machine only. No further guard is designed. |
| O-PCS-8 | The editor opens showing the colour group, whichever plane's tile was clicked. Showing the tile's plane would need the bridge to run an engine command at open; whether the shell can is not read. |
| O-PCS-9 | No editor but PhotoCraft is provisioned, so R-PC-74 is proven with PhotoCraft's own renderer only. |
| O-PCS-10 | A one-channel plane painted in colour becomes the mean of its channels, and a painted normal is made unit length (M8). The person is not told. The other way is to say so in the transfer dialog. |
| O-PCS-11 | A plane group's blend mode and opacity are the person's to change. A group made see-through is refused by the alpha rule. A group with another blend mode is composed alone, so the mode has nothing below it to act on; what the renderer writes then was not tried. |
| O-PCS-12 | A normal plane in the scratch is the map with Z rebuilt (M7), as the upscaler sees it. A normal map with a free red channel has that channel as its own `data` group. |
