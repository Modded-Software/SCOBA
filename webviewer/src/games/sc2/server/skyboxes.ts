// The skyboxes: those of the stock data and this repo's map (the "scoba"
// dataset), the same whatever dataset a unit comes from. Also which unit
// models are skyboxes: a file in a skybox folder, or one a CModel with
// parent "Skybox" names. Such a unit is a backdrop (SS_BackgroundSpace*),
// not something to stand on the map.

import { readdir, readFile } from 'node:fs/promises';
import { join } from 'node:path';
import type { Page } from '../../../shared/records';
import { errorCode } from '../../../server/core/http';

export interface Skybox {
  id: string;
  name: string;
  /** The CModel that names it, or null. */
  model: string | null;
  file: string;
  inMap: boolean;
}

/** "AiurSkybox" -> "Aiur Skybox"; "korhal_skybox_falling" -> "Korhal Skybox Falling". */
export function readable(id: string): string {
  return id
    .replace(/_/g, ' ')
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .split(/\s+/)
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

/** The model data files: every stock mod and campaign, then the map. */
async function modelDataFiles(stockDir: string, mapDir: string): Promise<string[]> {
  const out: string[] = [];
  for (const group of ['mods', 'campaigns']) {
    let names: string[] = [];
    try {
      names = (await readdir(join(stockDir, group))).sort();
    } catch (error) {
      if (errorCode(error) !== 'ENOENT') throw error;
    }
    for (const name of names) out.push(join(stockDir, group, name, 'base.sc2data', 'gamedata', 'modeldata.xml'));
  }
  out.push(join(mapDir, 'Base.SC2Data', 'GameData', 'ModelData.xml'));
  return out;
}

/** CModel ids with parent "Skybox", by their model asset key (lower case, backslashes). */
export async function skyboxModels(stockDir: string, mapDir: string): Promise<Map<string, string>> {
  const byKey = new Map<string, string>();
  for (const file of await modelDataFiles(stockDir, mapDir)) {
    let body: string;
    try {
      body = await readFile(file, 'utf8');
    } catch (error) {
      if (errorCode(error) === 'ENOENT') continue;
      throw error;
    }
    for (const match of body.matchAll(/<CModel\s+id="([^"]+)"\s+parent="Skybox"\s*>([\s\S]*?)<\/CModel>/g)) {
      const [, id, inner] = match;
      const model = /<Model\s+value="([^"]+)"/.exec(inner ?? '');
      if (!id || !model || model[1] === undefined) continue;
      const key = model[1].toLowerCase().replaceAll('/', '\\');
      if (!byKey.has(key)) byKey.set(key, id);
    }
  }
  return byKey;
}

/** Skybox model folders: the stock skyboxes and the story mode backdrops. */
const SKYBOX_DIR = /^assets\\(storymode)?skyboxes\\/;

/** Whether a model asset key is a skybox's. */
export const isSkyboxKey = (named: ReadonlyMap<string, string>, key: string): boolean => SKYBOX_DIR.test(key) || named.has(key);

/**
 * The skybox list from the asset keys of the default dataset (its map
 * layer and the storage). `servable`: asset key -> servable path.
 */
export function listSkyboxes(keys: Iterable<string>, servable: (key: string) => string | undefined, named: ReadonlyMap<string, string>, mapPrefix: string): Skybox[] {
  const seen = new Set<string>();
  const out: Skybox[] = [];
  for (const key of keys) {
    if (!key.startsWith('assets\\skyboxes\\') || !key.endsWith('.m3')) continue;
    const file = servable(key);
    if (file === undefined) continue;
    // A model with variations is stored as name_00.m3, name_01.m3, ...
    const variation = /_(\d\d)\.m3$/.exec(key);
    // The model entry that names the file itself; a variation file is named by its model's base file.
    const ownName = named.get(key);
    const baseName = variation ? named.get(key.slice(0, variation.index) + '.m3') : undefined;
    const model = ownName !== undefined ? ownName : baseName !== undefined ? baseName : null;
    const base = key.slice(key.lastIndexOf('\\') + 1, -'.m3'.length);
    const id = model ? (variation && !named.has(key) ? `${model}_${variation[1] ?? ''}` : model) : base;
    if (seen.has(id)) continue;
    seen.add(id);
    out.push({ id, name: readable(id), model, file, inMap: file.startsWith(mapPrefix) });
  }
  return out.sort((a, b) => a.name.localeCompare(b.name) || a.id.localeCompare(b.id));
}

export function searchSkyboxes(list: readonly Skybox[], query: string, offset: number, limit: number): Page<Skybox> {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  const hits = list.filter((sky) => words.every((word) => `${sky.name} ${sky.id}`.toLowerCase().includes(word)));
  return { total: hits.length, items: hits.slice(offset, offset + limit) };
}
