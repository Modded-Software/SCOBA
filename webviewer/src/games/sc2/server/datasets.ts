// Datasets of the viewer: where each one's game data and assets come from.
//
// A dataset is a stock data folder (mods/ and campaigns/, the game's own
// XML and strings, as stormex extracts them) and, on top, an optional map
// layer: a folder shaped like an SC2Map (Base.SC2Data/GameData,
// enUS.SC2Data/LocalizedData, Assets). The assets are the game storage,
// with the map layer's Assets over it.
//
// - "stock": the extracted stock data alone. No map layer.
// - "scoba": the stock data with this repo's map (src/SCOBA.SC2Map) on top.
// - any other: a folder <datasets>/<id>/ holding its own full stock data
//   (mods/, campaigns/), an optional map/ layer, and an optional
//   dataset.json { "label": "..." }. Made by scripts/dataset-new.sh.
//
// Used by the server and by src/tools/datasets.ts, which the shell
// scripts call, so both read the same rules.

import { createHash } from 'node:crypto';
import { readdir, readFile, stat } from 'node:fs/promises';
import { join, relative, resolve } from 'node:path';
import { errorCode, messageOf } from '../../../server/core/http';
import { requiredPath } from '../../../server/core/settings';

export const DEFAULT_DATASET = 'scoba';
export const BUILTIN: readonly string[] = ['scoba', 'stock'];
export const DATASET_ID = /^[a-z0-9][a-z0-9_-]{0,39}$/;
/** The parts of a map layer that count. */
const MAP_PARTS = ['Base.SC2Data', 'enUS.SC2Data', 'Assets'];
/** The parts of a stock data folder. */
const STOCK_PARTS = ['mods', 'campaigns'];

export interface Folders {
  data: string;
  stock: string;
  catalog: string;
  cache: string;
  datasets: string;
  map: string;
}

/** One dataset, as found on disk. */
export interface DatasetDef {
  id: string;
  label: string;
  builtin: boolean;
  stockDir: string;
  mapDir: string | null;
  catalogDir: string;
}

/** A folder under the datasets folder that is not a dataset. */
export interface DatasetProblem {
  dir: string;
  reason: string;
}

/**
 * The folders, from the environment. The scripts set WEBVIEWER_DATA from
 * webviewer/local.env, or below WEBVIEWER_WORK (SPEC-PATHS). `viewerDir`:
 * the webviewer folder.
 */
export function folders(viewerDir: string, env: NodeJS.ProcessEnv = process.env): Folders {
  const data = requiredPath(env, 'WEBVIEWER_DATA');
  return {
    data,
    stock: env['WEBVIEWER_STOCK'] || join(data, 'stock'),
    catalog: env['WEBVIEWER_CATALOG'] || join(data, 'catalog'),
    cache: env['WEBVIEWER_CACHE'] || join(data, 'cache'),
    datasets: env['WEBVIEWER_DATASETS'] || join(data, 'datasets'),
    map: env['WEBVIEWER_MAP'] || resolve(viewerDir, '..', 'src', 'SCOBA.SC2Map'),
  };
}

async function isDir(path: string): Promise<boolean> {
  try {
    return (await stat(path)).isDirectory();
  } catch (error) {
    if (errorCode(error) === 'ENOENT') return false;
    throw error;
  }
}

/** Subfolder names of `dir`, sorted; none when it does not exist. */
async function subfolders(dir: string): Promise<string[]> {
  try {
    const entries = await readdir(dir, { withFileTypes: true });
    return entries
      .filter((entry) => entry.isDirectory())
      .map((entry) => entry.name)
      .sort();
  } catch (error) {
    if (errorCode(error) === 'ENOENT') return [];
    throw error;
  }
}

async function label(dir: string, id: string): Promise<string> {
  let text: string;
  try {
    text = await readFile(join(dir, 'dataset.json'), 'utf8');
  } catch (error) {
    if (errorCode(error) === 'ENOENT') return id;
    throw error;
  }
  const data: unknown = JSON.parse(text);
  const value: unknown = typeof data === 'object' && data !== null ? Reflect.get(data, 'label') : undefined;
  if (typeof value !== 'string' || !value.trim()) throw new Error('dataset.json has no "label" text');
  return value.trim();
}

/** Every dataset, the built-in ones first; and the folders under <datasets> that are not one, each with the reason. */
export async function listDatasets(dirs: Folders): Promise<{ datasets: DatasetDef[]; problems: DatasetProblem[] }> {
  const datasets: DatasetDef[] = [
    { id: 'scoba', label: 'SCOBA (map over stock)', builtin: true, stockDir: dirs.stock, mapDir: dirs.map, catalogDir: dirs.catalog },
    { id: 'stock', label: 'Stock', builtin: true, stockDir: dirs.stock, mapDir: null, catalogDir: join(dirs.catalog, 'datasets', 'stock') },
  ];
  const problems: DatasetProblem[] = [];
  for (const id of await subfolders(dirs.datasets)) {
    const dir = join(dirs.datasets, id);
    if (!DATASET_ID.test(id) || BUILTIN.includes(id)) {
      problems.push({ dir, reason: BUILTIN.includes(id) ? `"${id}" is a built-in dataset name` : 'the folder name is not a dataset id (lower case letters, digits, "-", "_")' });
      continue;
    }
    if (!(await isDir(join(dir, 'mods')))) {
      problems.push({ dir, reason: 'no mods/ folder: the stock data is missing' });
      continue;
    }
    let name: string;
    try {
      name = await label(dir, id);
    } catch (error) {
      problems.push({ dir, reason: `dataset.json: ${messageOf(error)}` });
      continue;
    }
    const mapDir = join(dir, 'map');
    datasets.push({ id, label: name, builtin: false, stockDir: dir, mapDir: (await isDir(mapDir)) ? mapDir : null, catalogDir: join(dir, 'catalog') });
  }
  return { datasets, problems };
}

async function walk(dir: string, out: string[]): Promise<string[]> {
  let entries;
  try {
    entries = await readdir(dir, { withFileTypes: true });
  } catch (error) {
    if (errorCode(error) === 'ENOENT') return out;
    throw error;
  }
  for (const entry of entries) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) await walk(full, out);
    else if (entry.isFile()) out.push(full);
  }
  return out;
}

/**
 * A fingerprint of what a dataset is built from: the path, size and
 * change time of every file of its stock data and its map layer. It
 * changes when any of them is edited, added or removed.
 */
export async function signature(dataset: Pick<DatasetDef, 'stockDir' | 'mapDir'>): Promise<string> {
  const hash = createHash('sha1');
  const roots: [string, string][] = STOCK_PARTS.map((part) => [dataset.stockDir, part]);
  if (dataset.mapDir) for (const part of MAP_PARTS) roots.push([dataset.mapDir, part]);
  for (const [base, part] of roots) {
    const files = (await walk(join(base, part), [])).sort();
    hash.update(`[${part}]\n`);
    for (const full of files) {
      const info = await stat(full);
      hash.update(`${relative(base, full)}\t${info.size}\t${info.mtimeMs}\n`);
    }
  }
  return hash.digest('hex');
}

/** Where the signature a catalog was built from is kept. */
export const signatureFile = (dataset: Pick<DatasetDef, 'catalogDir'>): string => join(dataset.catalogDir, 'signature.txt');

/** The signature a dataset's catalog was built from, or null when none is recorded. */
export async function builtSignature(dataset: Pick<DatasetDef, 'catalogDir'>): Promise<string | null> {
  try {
    return (await readFile(signatureFile(dataset), 'utf8')).trim();
  } catch (error) {
    if (errorCode(error) === 'ENOENT') return null;
    throw error;
  }
}
