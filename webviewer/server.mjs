// SC2 model viewer server.
// Lists .m3 models in the game storage and serves models and textures,
// extracted on demand with stormex. Also serves the map's own Assets.

import { execFile } from 'node:child_process';
import { createReadStream } from 'node:fs';
import { mkdir, readdir, readFile, stat } from 'node:fs/promises';
import { createServer } from 'node:http';
import { homedir } from 'node:os';
import { dirname, join, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { promisify } from 'node:util';

const run = promisify(execFile);
const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, '..');

const PORT = Number(process.env.PORT || 4517);
const HOST = process.env.HOST || '127.0.0.1';
const STORMEX = process.env.STORMEX || join(ROOT, 'tools', 'stormex');
const SC2 = process.env.SC2_PATH || process.env.SC2_INSTALL || join(homedir(), 'Games/battlenet-prefix/pfx/drive_c/Program Files (x86)/StarCraft II');
// Extracted game files live outside git: WEBVIEWER_DATA, default webviewer/data
// (gitignored). The scripts set it from webviewer/local.env.
const DATA = process.env.WEBVIEWER_DATA || join(HERE, 'data');
const CACHE = process.env.WEBVIEWER_CACHE || join(DATA, 'cache');
const MAP_ASSETS = process.env.MAP_ASSETS || join(ROOT, 'src', 'SCOBA.SC2Map', 'Assets');
const CATALOG = process.env.WEBVIEWER_CATALOG || join(DATA, 'catalog');
const MAP_PREFIX = 'map\\';
const STOCK = process.env.WEBVIEWER_STOCK || join(DATA, 'stock');
const MAP_MODEL_DATA = join(ROOT, 'src', 'SCOBA.SC2Map', 'Base.SC2Data', 'GameData', 'ModelData.xml');

const STATIC = new Map([
  ['/', ['public/index.html', 'text/html; charset=utf-8']],
  // The page modules, loaded in this order by index.html.
  ...['core', 'controls', 'scene', 'panels', 'drag', 'sky', 'inspect', 'main'].map((name) => [`/js/${name}.js`, [`public/js/${name}.js`, 'text/javascript; charset=utf-8']]),
  ['/components.js', ['public/components.js', 'text/javascript; charset=utf-8']],
  ['/ground.js', ['public/ground.js', 'text/javascript; charset=utf-8']],
  ['/shaders/ground.vert', ['public/shaders/ground.vert', 'text/plain; charset=utf-8']],
  ['/shaders/ground.frag', ['public/shaders/ground.frag', 'text/plain; charset=utf-8']],
  ['/style.css', ['public/style.css', 'text/css; charset=utf-8']],
  // Built by tools/build-renderer.mjs: mdx-m3-viewer with the M3 parser patches.
  ['/vendor/renderer.js', ['public/vendor/renderer.js', 'text/javascript; charset=utf-8']],
  ['/vendor/renderer.js.map', ['public/vendor/renderer.js.map', 'application/json; charset=utf-8']],
]);

/** Every servable path: storage path or map path -> where it comes from. */
const files = new Map();
/** Sorted .m3 paths, for search. */
let models = [];
/** In-model asset path (lower case, backslashes, from "assets\") -> servable path. */
const assets = new Map();

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

/** Lower rank wins when several archives hold the same in-model path. */
function rank(path) {
  if (path.startsWith(MAP_PREFIX)) return 0;
  if (path.includes('\\base.sc2assets\\')) return 1;
  return 2;
}

function indexAsset(path) {
  const at = path.indexOf('\\assets\\');
  if (at < 0) return;
  const key = path.slice(at + 1);
  const held = assets.get(key);
  if (held === undefined || rank(path) < rank(held)) assets.set(key, path);
}

async function buildIndex() {
  const { stdout } = await run(STORMEX, ['-S', SC2, '-I', '\\.(m3|dds|tga)$', '-l'], { maxBuffer: 256 * 1024 * 1024 });
  for (const line of stdout.split('\n')) {
    const path = line.trim();
    if (!path) continue;
    files.set(path, { kind: 'casc' });
    indexAsset(path);
  }
  for (const full of await walk(MAP_ASSETS)) {
    const rel = full.slice(MAP_ASSETS.length + 1).split(sep).join('\\').toLowerCase();
    const path = `${MAP_PREFIX}assets\\${rel}`;
    files.set(path, { kind: 'disk', full });
    indexAsset(path);
  }
  models = [...files.keys()].filter((path) => path.endsWith('.m3')).sort();
}

// ---- unit catalog ----

/** Unit id -> record. Only units whose model file can be served. */
const units = new Map();
/** Icon and portrait file names the catalog uses. Nothing else is served from icons/. */
const icons = new Set();
let unitList = [];
let unitsWithoutModelFile = 0;
let facets = { races: [], kinds: [] };

/** The servable path of a unit's model: the file itself, or its first variation. */
function modelFile(m3) {
  const key = m3.toLowerCase().replaceAll('/', '\\');
  return assets.get(key) ?? assets.get(key.replace(/\.m3$/, '_00.m3')) ?? null;
}

async function loadCatalog() {
  const full = join(CATALOG, 'units.json');
  let text;
  try {
    text = await readFile(full, 'utf8');
  } catch (error) {
    if (error.code === 'ENOENT') throw new Error(`unit catalog missing: ${full}. Run "make viewer-catalog".`);
    throw error;
  }
  for (const record of JSON.parse(text).units) {
    const file = modelFile(record.m3);
    if (!file) {
      unitsWithoutModelFile++;
      continue;
    }
    const unit = { ...record, file, text: `${record.name} ${record.id}`.toLowerCase() };
    units.set(unit.id, unit);
    for (const name of [unit.icon, unit.portrait]) if (name) icons.add(name);
  }
  unitList = [...units.values()].sort((a, b) => a.name.localeCompare(b.name) || a.id.localeCompare(b.id));
  const count = (field) => {
    const seen = new Map();
    for (const unit of unitList) seen.set(unit[field], (seen.get(unit[field]) || 0) + 1);
    return [...seen.entries()].sort((a, b) => b[1] - a[1]).map(([value]) => value);
  };
  facets = { races: count('race'), kinds: count('kind') };
}

/** Lower is better: the whole name, then a name that starts with it, then a word that does. */
function unitRank(unit, query) {
  const name = unit.name.toLowerCase();
  if (name === query) return 0;
  if (name.startsWith(query)) return 1;
  if (name.split(/\s+/).some((word) => word.startsWith(query))) return 2;
  if (unit.id.toLowerCase().startsWith(query)) return 3;
  return 4;
}

/** A whole-number query value, clamped to [low, high]; a missing or bad value gives `standard`. */
function intParam(params, name, standard, low, high) {
  const value = Number.parseInt(params.get(name) ?? '', 10);
  return Number.isFinite(value) ? Math.min(Math.max(value, low), high) : standard;
}

/** One page of an ordered list. */
const pageOf = (list, offset, limit) => list.slice(offset, offset + limit);

function searchUnits(query, race, kind, offset, limit) {
  const text = query.toLowerCase().trim();
  const words = text.split(/\s+/).filter(Boolean);
  let hits = unitList.filter((unit) => (!race || unit.race === race) && (!kind || unit.kind === kind) && words.every((word) => unit.text.includes(word)));
  if (words.length) {
    // The map's own units first among equals, then melee units, then the rest.
    const order = (unit) => unitRank(unit, text) * 4 + (unit.inMap ? 0 : unit.family === 'Melee' ? 1 : 2);
    hits = hits.map((unit) => [order(unit), unit]).sort((a, b) => a[0] - b[0]).map(([, unit]) => unit);
  }
  const brief = ({ id, name, race, kind, family, icon, inMap }) => ({ id, name, race, kind, family, icon, inMap });
  return { total: hits.length, items: pageOf(hits, offset, limit).map(brief) };
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
      names = (await readdir(join(STOCK, group))).sort();
    } catch (error) {
      if (error.code !== 'ENOENT') throw error;
    }
    for (const name of names) out.push(join(STOCK, group, name, 'base.sc2data', 'gamedata', 'modeldata.xml'));
  }
  out.push(MAP_MODEL_DATA);
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

async function loadSkyboxes() {
  const named = await skyboxModels();
  const seen = new Set();
  skyboxes = [];
  for (const [key, file] of assets) {
    if (!key.startsWith('assets\\skyboxes\\') || !key.endsWith('.m3')) continue;
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

async function serveStored(res, path) {
  const full = await locate(path);
  if (!full) return json(res, 404, { error: 'not found', path });
  sendFile(res, full, 'application/octet-stream', 'max-age=3600');
}

async function handle(req, res) {
  if (req.method !== 'GET') return json(res, 405, { error: 'method not allowed' });
  // The raw URL decides the route, so "/../x" and "/%2e%2e/x" never normalise onto a real one.
  const raw = req.url || '/';
  const cut = raw.indexOf('?');
  const route = cut < 0 ? raw : raw.slice(0, cut);
  const params = new URLSearchParams(cut < 0 ? '' : raw.slice(cut + 1));

  if (route === '/api/health') return json(res, 200, { models: models.length, files: files.size, units: units.size, unitsWithoutModelFile, skyboxes: skyboxes.length });

  if (route === '/api/facets') return json(res, 200, facets);

  if (route === '/api/units') {
    const limit = intParam(params, 'limit', 60, 1, 500);
    const offset = intParam(params, 'offset', 0, 0, Number.MAX_SAFE_INTEGER);
    return json(res, 200, searchUnits(params.get('q') || '', params.get('race') || '', params.get('kind') || '', offset, limit));
  }

  if (route === '/api/skyboxes') {
    const limit = intParam(params, 'limit', 500, 1, 500);
    const offset = intParam(params, 'offset', 0, 0, Number.MAX_SAFE_INTEGER);
    return json(res, 200, searchSkyboxes(params.get('q') || '', offset, limit));
  }

  if (route === '/api/unit') {
    const id = params.get('id');
    if (!id) return json(res, 400, { error: 'id is required' });
    const unit = units.get(id);
    if (!unit) return json(res, 404, { error: 'not found', id });
    const { text, ...record } = unit;
    return json(res, 200, record);
  }

  if (route.startsWith('/icon/')) {
    // Only names the catalog lists, so no path can leave the icon folder.
    const name = route.slice('/icon/'.length);
    if (!icons.has(name)) return json(res, 404, { error: 'not found' });
    return sendFile(res, join(CATALOG, 'icons', name), 'image/png', 'max-age=3600');
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
    const path = params.get('path');
    if (!path) return json(res, 400, { error: 'path is required' });
    const stored = assets.get(path.toLowerCase().replaceAll('/', '\\'));
    if (!stored) return json(res, 404, { error: 'not found', path });
    return serveStored(res, stored);
  }

  const entry = STATIC.get(route);
  if (entry) return sendFile(res, join(HERE, entry[0]), entry[1], 'no-store');
  return json(res, 404, { error: 'not found' });
}

await mkdir(CACHE, { recursive: true });
await buildIndex();
await loadCatalog();
await loadSkyboxes();

createServer((req, res) => {
  handle(req, res).catch((error) => {
    console.error(error);
    if (!res.headersSent) json(res, 500, { error: String(error.message || error) });
    else res.destroy();
  });
}).listen(PORT, HOST, () => {
  console.log(`sc2 webviewer: http://${HOST}:${PORT}/  (${models.length} models, ${units.size} units, ${unitsWithoutModelFile} units without a model file)`);
});
