// SC2 model viewer server.
// Lists .m3 models in the game storage and serves models and textures,
// extracted on demand with stormex. Game data and the assets over the
// storage come per dataset (server-datasets.mjs): "scoba" (this repo's map
// over the stock data) when a request names none.

import { execFile } from 'node:child_process';
import { createReadStream } from 'node:fs';
import { mkdir, readdir, readFile, stat } from 'node:fs/promises';
import { createServer } from 'node:http';
import { homedir } from 'node:os';
import { dirname, join, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { promisify } from 'node:util';

import { builtSignature, DEFAULT_DATASET, folders, listDatasets, signature } from './server-datasets.mjs';
import { loadDoodads } from './server-doodads.mjs';
import { hdModelsRoot, serveHd, serveTextures, texturesRoot } from './server-textures.mjs';
import { loadUnits } from './server-units.mjs';

const run = promisify(execFile);
const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, '..');

const PORT = Number(process.env.PORT || 4517);
const HOST = process.env.HOST || '127.0.0.1';
const STORMEX = process.env.STORMEX || join(ROOT, 'tools', 'stormex');
const SC2 = process.env.SC2_PATH || process.env.SC2_INSTALL || join(homedir(), 'Games/battlenet-prefix/pfx/drive_c/Program Files (x86)/StarCraft II');
// Extracted game files live outside git: WEBVIEWER_DATA, default webviewer/data
// (gitignored). The scripts set it from webviewer/local.env.
const DIRS = folders();
const CACHE = DIRS.cache;
const MAP_PREFIX = 'map\\';
const TEXTURES = texturesRoot(ROOT);
const HD_MODELS = hdModelsRoot(ROOT);
/** How long a computed dataset signature is good for (the page polls). */
const SIGNATURE_AGE = 1000; // ms

const STATIC = new Map([
  ['/', ['public/index.html', 'text/html; charset=utf-8']],
  // The page modules (public/js) are not listed: serveModule reads them.
  ['/components.js', ['public/components.js', 'text/javascript; charset=utf-8']],
  ['/ground.js', ['public/ground.js', 'text/javascript; charset=utf-8']],
  ['/outline.js', ['public/outline.js', 'text/javascript; charset=utf-8']],
  ['/pickbuffer.js', ['public/pickbuffer.js', 'text/javascript; charset=utf-8']],
  ...['outline.vert', 'outline-blur.frag', 'outline-compose.frag'].map((name) => [`/shaders/${name}`, [`public/shaders/${name}`, 'text/plain; charset=utf-8']]),
  ['/displacement.js', ['public/displacement.js', 'text/javascript; charset=utf-8']],
  ['/shaders/ground.vert', ['public/shaders/ground.vert', 'text/plain; charset=utf-8']],
  ['/shaders/ground.frag', ['public/shaders/ground.frag', 'text/plain; charset=utf-8']],
  ['/theme.css', ['public/theme.css', 'text/css; charset=utf-8']],
  ['/style.css', ['public/style.css', 'text/css; charset=utf-8']],
  // Built by tools/build-renderer.mjs: mdx-m3-viewer with the M3 parser patches.
  ['/vendor/renderer.js', ['public/vendor/renderer.js', 'text/javascript; charset=utf-8']],
  ['/vendor/renderer.js.map', ['public/vendor/renderer.js.map', 'application/json; charset=utf-8']],
]);

/** Every servable path: storage path, or a dataset's map layer path -> where it comes from. */
const files = new Map();
/** Sorted .m3 paths, for search. */
let models = [];
/** In-model asset path (lower case, backslashes, from "assets\") -> storage path. The game storage alone. */
const stored = new Map();
/** Dataset id -> its loaded state (loadDataset). */
const datasets = new Map();
/** Folders under the datasets folder that are not a dataset: { dir, reason }. */
let datasetProblems = [];

async function walk(dir, out = []) {
  let entries;
  try {
    entries = await readdir(dir, { withFileTypes: true });
  } catch (error) {
    if (error.code === 'ENOENT') return out;
    throw error;
  }
  for (const entry of entries) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) await walk(full, out);
    else if (/\.(m3|dds|tga)$/i.test(entry.name)) out.push(full);
  }
  return out;
}

/** Among several archives holding the same in-model path, base.sc2assets wins. */
const rank = (path) => (path.includes('\\base.sc2assets\\') ? 0 : 1);

async function indexStorage() {
  const { stdout } = await run(STORMEX, ['-S', SC2, '-I', '\\.(m3|dds|tga)$', '-l'], { maxBuffer: 256 * 1024 * 1024 });
  for (const line of stdout.split('\n')) {
    const path = line.trim();
    if (!path) continue;
    files.set(path, { kind: 'casc' });
    const at = path.indexOf('\\assets\\');
    if (at < 0) continue;
    const key = path.slice(at + 1);
    const held = stored.get(key);
    if (held === undefined || rank(path) < rank(held)) stored.set(key, path);
  }
}

/** The servable path prefix of a dataset's map layer files. */
const layerPrefix = (id) => (id === DEFAULT_DATASET ? MAP_PREFIX : `ds\\${id}\\`);

/**
 * Load (or load again) one dataset: index its map layer's Assets over the
 * storage, then join its catalogs with the files that can be served.
 */
async function loadDataset(def) {
  const prefix = layerPrefix(def.id);
  for (const path of [...files.keys()]) if (path.startsWith(prefix)) files.delete(path);
  /** In-model asset path -> servable path, for the map layer's own files. */
  const overlay = new Map();
  if (def.mapDir) {
    const root = join(def.mapDir, 'Assets');
    for (const full of await walk(root)) {
      const key = `assets\\${full.slice(root.length + 1).split(sep).join('\\').toLowerCase()}`;
      files.set(prefix + key, { kind: 'disk', full });
      overlay.set(key, prefix + key);
    }
  }
  // The map layer first, then the game storage.
  const assets = { get: (key) => overlay.get(key) ?? stored.get(key), overlay };
  const state = { ...def, assets, units: await loadUnits(def.catalogDir, assets), doodads: await loadDoodads(def.catalogDir, assets), loaded: await builtSignature(def), checked: null };
  datasets.set(def.id, state);
  return state;
}

/** After any dataset load: the model list and the skyboxes follow the files. */
async function refreshShared() {
  models = [...files.keys()].filter((path) => path.endsWith('.m3')).sort();
  await loadSkyboxes();
}

/** The dataset's source fingerprint now; computed at most once per SIGNATURE_AGE. */
async function currentSignature(state) {
  const now = Date.now();
  if (!state.checked || now - state.checked.at > SIGNATURE_AGE) state.checked = { at: now, value: await signature(state) };
  return state.checked.value;
}

/** What the page shows of a dataset. `signature`: what is loaded; `current`: its sources now; `changed`: they differ. */
async function describe(state) {
  const current = await currentSignature(state);
  return { id: state.id, label: state.label, builtin: state.builtin, hasMap: Boolean(state.mapDir), units: state.units.size, doodads: state.doodads.size, signature: state.loaded, current, changed: current !== state.loaded };
}

/** One reload at a time: a catalog build is heavy. */
let reloading = Promise.resolve();

/** Rebuild a dataset's catalog when its sources changed since it was built, then load it again. */
function reloadDataset(id) {
  const job = reloading.then(async () => {
    const state = datasets.get(id);
    const current = await signature(state);
    if ((await builtSignature(state)) !== current) {
      await run('bash', [join(HERE, 'scripts', 'catalog.sh'), '--dataset', id], { cwd: HERE, env: { ...process.env, WEBVIEWER_DIR: HERE, REPO_ROOT: ROOT }, maxBuffer: 64 * 1024 * 1024 }).catch((error) => {
        throw new Error(`catalog build failed for "${id}": ${String(error.stderr || error.message).trim().split('\n').slice(-5).join(' | ')}`);
      });
    }
    const { datasets: defs } = await listDatasets(DIRS);
    const def = defs.find((d) => d.id === id);
    if (!def) throw new Error(`dataset "${id}" is gone`);
    const next = await loadDataset(def);
    await refreshShared();
    return describe(next);
  });
  // A failed reload must not block the next one. The caller gets the error from `job`;
  // the chain logs it.
  reloading = job.catch((error) => console.error(`viewer: reload of dataset "${id}" failed: ${error.message}`));
  return job;
}

// ---- skyboxes ----

/** Every skybox model file, with the CModel that names it when there is one. */
let skyboxes = [];

/** "AiurSkybox" -> "Aiur Skybox"; "korhal_skybox_falling" -> "Korhal Skybox Falling". */
function readable(id) {
  return id
    .replace(/_/g, ' ')
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .split(/\s+/)
    .filter(Boolean)
    .map((word) => word[0].toUpperCase() + word.slice(1))
    .join(' ');
}

/** The model data files: every stock mod and campaign, then the map. */
async function modelDataFiles() {
  const out = [];
  for (const group of ['mods', 'campaigns']) {
    let names = [];
    try {
      names = (await readdir(join(DIRS.stock, group))).sort();
    } catch (error) {
      if (error.code !== 'ENOENT') throw error;
    }
    for (const name of names) out.push(join(DIRS.stock, group, name, 'base.sc2data', 'gamedata', 'modeldata.xml'));
  }
  out.push(join(DIRS.map, 'Base.SC2Data', 'GameData', 'ModelData.xml'));
  return out;
}

/** CModel ids with parent "Skybox", by their model asset key (lower case, backslashes). */
async function skyboxModels() {
  const byKey = new Map();
  for (const file of await modelDataFiles()) {
    let text;
    try {
      text = await readFile(file, 'utf8');
    } catch (error) {
      if (error.code === 'ENOENT') continue;
      throw error;
    }
    for (const match of text.matchAll(/<CModel\s+id="([^"]+)"\s+parent="Skybox"\s*>([\s\S]*?)<\/CModel>/g)) {
      const model = /<Model\s+value="([^"]+)"/.exec(match[2]);
      if (!model) continue;
      const key = model[1].toLowerCase().replaceAll('/', '\\');
      if (!byKey.has(key)) byKey.set(key, match[1]);
    }
  }
  return byKey;
}

/** Skybox model folders: the stock skyboxes and the story mode backdrops. */
const SKYBOX_DIR = /^assets\\(storymode)?skyboxes\\/;

/**
 * The skyboxes: those of the stock data and this repo's map (the "scoba"
 * dataset), the same whatever dataset a unit comes from. Also marks, in
 * every dataset, the units whose model is a skybox (`skybox: true`): its
 * file lies in a skybox folder, or a CModel with parent "Skybox" names it.
 * Such a unit is a backdrop (SS_BackgroundSpace*), not something to stand
 * on the map.
 */
async function loadSkyboxes() {
  const named = await skyboxModels();
  for (const state of datasets.values()) {
    for (const unit of state.units.values()) {
      const key = unit.m3.toLowerCase().replaceAll('/', '\\');
      unit.skybox = SKYBOX_DIR.test(key) || named.has(key);
    }
  }
  const seen = new Set();
  skyboxes = [];
  const main = datasets.get(DEFAULT_DATASET).assets;
  for (const key of new Set([...main.overlay.keys(), ...stored.keys()])) {
    if (!key.startsWith('assets\\skyboxes\\') || !key.endsWith('.m3')) continue;
    const file = main.get(key);
    // A model with variations is stored as name_00.m3, name_01.m3, ...
    const variation = /_(\d\d)\.m3$/.exec(key);
    const model = named.get(key) ?? (variation ? named.get(key.slice(0, variation.index) + '.m3') : undefined) ?? null;
    const base = key.slice(key.lastIndexOf('\\') + 1, -'.m3'.length);
    const id = model ? (variation && !named.has(key) ? `${model}_${variation[1]}` : model) : base;
    if (seen.has(id)) continue;
    seen.add(id);
    skyboxes.push({ id, name: readable(id), model, file, inMap: file.startsWith(MAP_PREFIX) });
  }
  skyboxes.sort((a, b) => a.name.localeCompare(b.name) || a.id.localeCompare(b.id));
}

/** A whole-number query value, clamped to [low, high]; a missing or bad value gives `standard`. */
function intParam(params, name, standard, low, high) {
  const value = Number.parseInt(params.get(name) ?? '', 10);
  return Number.isFinite(value) ? Math.min(Math.max(value, low), high) : standard;
}

/** One page of an ordered list. */
const pageOf = (list, offset, limit) => list.slice(offset, offset + limit);

function searchSkyboxes(query, offset, limit) {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  const hits = skyboxes.filter((sky) => words.every((word) => `${sky.name} ${sky.id}`.toLowerCase().includes(word)));
  return { total: hits.length, items: pageOf(hits, offset, limit) };
}

const extracting = new Map();

/** The file on disk for a servable path. Extracts from the storage once. */
async function locate(path) {
  const entry = files.get(path);
  if (!entry) return null;
  if (entry.kind === 'disk') return entry.full;
  const target = join(CACHE, ...path.split('\\'));
  if (await isFile(target)) return target;
  if (!extracting.has(path)) {
    const job = run(STORMEX, ['-S', SC2, '-X', path, '-o', CACHE])
      .then(async () => {
        if (!(await isFile(target))) throw new Error(`stormex did not extract ${path}`);
        return target;
      })
      .finally(() => extracting.delete(path));
    extracting.set(path, job);
  }
  return extracting.get(path);
}

async function isFile(path) {
  try {
    return (await stat(path)).isFile();
  } catch (error) {
    if (error.code === 'ENOENT') return false;
    throw error;
  }
}

function search(query, offset, limit) {
  const words = query.toLowerCase().replaceAll('/', '\\').split(/\s+/).filter(Boolean);
  const hits = words.length ? models.filter((path) => words.every((word) => path.includes(word))) : models;
  return { total: hits.length, items: pageOf(hits, offset, limit) };
}

function json(res, code, body) {
  res.writeHead(code, { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' });
  res.end(JSON.stringify(body));
}

function sendFile(res, full, type, cache) {
  res.writeHead(200, { 'content-type': type, 'cache-control': cache });
  createReadStream(full)
    .on('error', (error) => res.destroy(error))
    .pipe(res);
}

/** A page module route: "/js/<name>.js", the name lower case letters, digits and dashes. */
const MODULE_ROUTE = /^\/js\/([a-z][a-z0-9-]*)\.js$/;

/**
 * Serve a page module from public/js, looked up at request time: a module
 * added after the server started is served too (a fixed list once left the
 * drawer tabs without their script on a long-running server). The name
 * pattern keeps the lookup inside public/js. False when `route` is no
 * module route or the file is missing.
 */
async function serveModule(res, route) {
  const match = MODULE_ROUTE.exec(route);
  if (!match) return false;
  const full = join(HERE, 'public', 'js', `${match[1]}.js`);
  const found = await stat(full).then(
    (s) => s.isFile(),
    (error) => {
      if (error.code === 'ENOENT') return false;
      throw error;
    },
  );
  if (!found) return false;
  sendFile(res, full, 'text/javascript; charset=utf-8', 'no-store');
  return true;
}

async function serveStored(res, path) {
  const full = await locate(path);
  if (!full) return json(res, 404, { error: 'not found', path });
  sendFile(res, full, 'application/octet-stream', 'max-age=3600');
}

async function handle(req, res) {
  // The raw URL decides the route, so "/../x" and "/%2e%2e/x" never normalise onto a real one.
  const raw = req.url || '/';
  const cut = raw.indexOf('?');
  const route = cut < 0 ? raw : raw.slice(0, cut);
  const params = new URLSearchParams(cut < 0 ? '' : raw.slice(cut + 1));

  if (route === '/api/dataset/reload') {
    if (req.method !== 'POST') return json(res, 405, { error: 'method not allowed' });
    const id = params.get('id');
    if (!id) return json(res, 400, { error: 'id is required' });
    if (!datasets.has(id)) return json(res, 404, { error: 'no such dataset', dataset: id });
    return json(res, 200, await reloadDataset(id));
  }
  if (req.method !== 'GET') return json(res, 405, { error: 'method not allowed' });
  if (await serveModule(res, route)) return undefined;
  if (await serveTextures(TEXTURES, route, res, { json, sendFile })) return undefined;
  if (await serveHd(HD_MODELS, route, params, res, { json, sendFile })) return undefined;

  // The dataset a request reads: "dataset=<id>", or the default one.
  const wanted = params.get('dataset') || DEFAULT_DATASET;
  const data = datasets.get(wanted);
  if (!data) return json(res, 404, { error: 'no such dataset', dataset: wanted });

  if (route === '/api/health') {
    return json(res, 200, { models: models.length, files: files.size, units: data.units.size, unitsWithoutModelFile: data.units.withoutFile, skyboxes: skyboxes.length, doodads: data.doodads.size, doodadsWithoutModelFile: data.doodads.withoutFile, datasets: datasets.size });
  }

  if (route === '/api/datasets') {
    const list = [];
    for (const state of datasets.values()) list.push(await describe(state));
    return json(res, 200, { default: DEFAULT_DATASET, datasets: list, problems: datasetProblems });
  }

  if (route === '/api/facets') return json(res, 200, { ...data.units.facets, doodadTypes: data.doodads.facets.types, tilesets: data.doodads.facets.tilesets });

  if (route === '/api/doodads') {
    const limit = intParam(params, 'limit', 60, 1, 500);
    const offset = intParam(params, 'offset', 0, 0, Number.MAX_SAFE_INTEGER);
    return json(res, 200, data.doodads.search(params.get('q') || '', params.get('type') || '', params.get('tileset') || '', offset, limit));
  }

  if (route === '/api/doodad' || route === '/api/unit') {
    const id = params.get('id');
    if (!id) return json(res, 400, { error: 'id is required' });
    const record = (route === '/api/unit' ? data.units : data.doodads).get(id);
    if (!record) return json(res, 404, { error: 'not found', id, dataset: data.id });
    return json(res, 200, { ...record, dataset: data.id });
  }

  if (route === '/api/units') {
    const limit = intParam(params, 'limit', 60, 1, 500);
    const offset = intParam(params, 'offset', 0, 0, Number.MAX_SAFE_INTEGER);
    return json(res, 200, data.units.search(params.get('q') || '', params.get('race') || '', params.get('kind') || '', params.has('family') ? params.get('family') : null, offset, limit));
  }

  if (route === '/api/skyboxes') {
    const limit = intParam(params, 'limit', 500, 1, 500);
    const offset = intParam(params, 'offset', 0, 0, Number.MAX_SAFE_INTEGER);
    return json(res, 200, searchSkyboxes(params.get('q') || '', offset, limit));
  }

  if (route.startsWith('/icon/')) {
    // Only names the dataset's catalog lists, so no path can leave the icon folder.
    const name = route.slice('/icon/'.length);
    if (!data.units.icons.has(name)) return json(res, 404, { error: 'not found' });
    return sendFile(res, join(data.catalogDir, 'icons', name), 'image/png', 'max-age=3600');
  }

  if (route === '/api/models') {
    const limit = intParam(params, 'limit', 50, 1, 500);
    const offset = intParam(params, 'offset', 0, 0, Number.MAX_SAFE_INTEGER);
    return json(res, 200, search(params.get('q') || '', offset, limit));
  }

  if (route === '/file') {
    const path = params.get('path');
    if (!path) return json(res, 400, { error: 'path is required' });
    return serveStored(res, path);
  }

  if (route === '/asset') {
    // An in-model path, as the dataset sees it: its map layer, then the storage.
    const path = params.get('path');
    if (!path) return json(res, 400, { error: 'path is required' });
    const servable = data.assets.get(path.toLowerCase().replaceAll('/', '\\'));
    if (!servable) return json(res, 404, { error: 'not found', path, dataset: data.id });
    return serveStored(res, servable);
  }

  const entry = STATIC.get(route);
  if (entry) return sendFile(res, join(HERE, entry[0]), entry[1], 'no-store');
  return json(res, 404, { error: 'not found' });
}

await mkdir(CACHE, { recursive: true });
await indexStorage();
const found = await listDatasets(DIRS);
datasetProblems = found.problems;
for (const problem of datasetProblems) console.warn(`sc2 webviewer: not a dataset: ${problem.dir}: ${problem.reason}`);
for (const def of found.datasets) await loadDataset(def);
await refreshShared();

createServer((req, res) => {
  handle(req, res).catch((error) => {
    console.error(error);
    if (!res.headersSent) json(res, 500, { error: String(error.message || error) });
    else res.destroy();
  });
}).listen(PORT, HOST, () => {
  const lines = [...datasets.values()].map((d) => `${d.id}: ${d.units.size} units (${d.units.withoutFile} without a model file), ${d.doodads.size} doodads (${d.doodads.withoutFile} without)`);
  console.log(`sc2 webviewer: http://${HOST}:${PORT}/  (${models.length} models; ${lines.join('; ')})`);
});
