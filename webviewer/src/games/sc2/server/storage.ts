// The files the server can serve: the game storage (read with stormex,
// extracted on demand into the cache) and each dataset's map layer on disk.

import { execFile } from 'node:child_process';
import { readdir, readFile, rename, writeFile } from 'node:fs/promises';
import { join, sep } from 'node:path';
import { promisify } from 'node:util';
import type { Page } from '../../../shared/records';
import { errorCode, isFile } from '../../../server/core/http';

const run = promisify(execFile);

type Entry = { kind: 'casc' } | { kind: 'disk'; full: string };

/** Among several archives holding the same in-model path, base.sc2assets wins. */
const rankOf = (path: string): number => (path.includes('\\base.sc2assets\\') ? 0 : 1);

/** Model, texture and image files under `dir`, recursively; none when it does not exist. */
async function walk(dir: string, out: string[] = []): Promise<string[]> {
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
    else if (/\.(m3|dds|tga)$/i.test(entry.name)) out.push(full);
  }
  return out;
}

export interface Storage {
  /** Every servable path. */
  readonly size: number;
  /** In-model asset path (lower case, backslashes, from "assets\") -> storage path. The game storage alone. */
  readonly stored: ReadonlyMap<string, string>;
  /** Read the storage's file list. */
  index(): Promise<void>;
  /**
   * Put a map layer's Assets folder under the servable prefix `prefix`,
   * dropping what was there. Returns in-model asset path -> servable path.
   */
  addLayer(prefix: string, mapDir: string | null): Promise<Map<string, string>>;
  /** The file on disk for a servable path, or null. Extracts from the storage once. */
  locate(path: string): Promise<string | null>;
  /** Rebuild the sorted model list (after a layer changed). */
  refreshModels(): void;
  readonly modelCount: number;
  /** Model files with every query word in their path. */
  search(query: string, offset: number, limit: number): Page<string>;
}

export function createStorage(stormex: string, gameDir: string, cache: string): Storage {
  const files = new Map<string, Entry>();
  const stored = new Map<string, string>();
  let models: string[] = [];
  const extracting = new Map<string, Promise<string>>();

  /** The storage's file list, kept in the cache: built only when missing (operator 2026-11-25). Delete the file after a game update. */
  const LISTING = join(cache, 'storage-listing.txt');
  async function listing(): Promise<string> {
    try {
      return await readFile(LISTING, 'utf8');
    } catch (error) {
      if (errorCode(error) !== 'ENOENT') throw error;
    }
    const { stdout } = await run(stormex, ['-S', gameDir, '-I', '\\.(m3|dds|tga)$', '-l'], { maxBuffer: 256 * 1024 * 1024 });
    // Whole or not at all: a reader never sees half a list.
    await writeFile(`${LISTING}.${process.pid}`, stdout);
    await rename(`${LISTING}.${process.pid}`, LISTING);
    return stdout;
  }

  async function index(): Promise<void> {
    const stdout = await listing();
    for (const line of stdout.split('\n')) {
      const path = line.trim();
      if (!path) continue;
      files.set(path, { kind: 'casc' });
      const at = path.indexOf('\\assets\\');
      if (at < 0) continue;
      const key = path.slice(at + 1);
      const held = stored.get(key);
      if (held === undefined || rankOf(path) < rankOf(held)) stored.set(key, path);
    }
  }

  async function addLayer(prefix: string, mapDir: string | null): Promise<Map<string, string>> {
    for (const path of [...files.keys()]) if (path.startsWith(prefix)) files.delete(path);
    const overlay = new Map<string, string>();
    if (mapDir) {
      const root = join(mapDir, 'Assets');
      for (const full of await walk(root)) {
        const key = `assets\\${full.slice(root.length + 1).split(sep).join('\\').toLowerCase()}`;
        files.set(prefix + key, { kind: 'disk', full });
        overlay.set(key, prefix + key);
      }
    }
    return overlay;
  }

  async function locate(path: string): Promise<string | null> {
    const entry = files.get(path);
    if (!entry) return null;
    if (entry.kind === 'disk') return entry.full;
    const target = join(cache, ...path.split('\\'));
    if (await isFile(target)) return target;
    let job = extracting.get(path);
    if (!job) {
      job = run(stormex, ['-S', gameDir, '-X', path, '-o', cache])
        .then(async () => {
          if (!(await isFile(target))) throw new Error(`stormex did not extract ${path}`);
          return target;
        })
        .finally(() => extracting.delete(path));
      extracting.set(path, job);
    }
    return job;
  }

  function search(query: string, offset: number, limit: number): Page<string> {
    const words = query.toLowerCase().replaceAll('/', '\\').split(/\s+/).filter(Boolean);
    const hits = words.length ? models.filter((path) => words.every((word) => path.includes(word))) : models;
    return { total: hits.length, items: hits.slice(offset, offset + limit) };
  }

  return {
    get size() {
      return files.size;
    },
    stored,
    index,
    addLayer,
    locate,
    refreshModels: () => {
      models = [...files.keys()].filter((path) => path.endsWith('.m3')).sort();
    },
    get modelCount() {
      return models.length;
    },
    search,
  };
}
