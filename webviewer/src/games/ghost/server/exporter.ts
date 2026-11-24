// NODExport of our nodsdk-scghost fork, run as a child process
// (SPEC-VIEWER-GHOST 2, 7). Every export is written once per dataset
// signature below the cache folder and served from there.
//
// A model is served as one container the nod format reads (container.ts).
// The JSON is { model, materials }: the model description and the
// materials export of its material names. A model NODExport refuses is a
// container whose JSON is { error }: the page names it (R-VIEW-82).

import { execFile } from 'node:child_process';
import { createHash } from 'node:crypto';
import { mkdir, readdir, readFile, rename, rm, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { promisify } from 'node:util';
import { isFile } from '../../../server/core/http';
import { packContainer } from './container';

const run = promisify(execFile);
/** The parsers log every file they read: room for a model's worth of lines. */
const OUTPUT = 64 * 1024 * 1024;

/** An exit code of a child process, when it has one. */
function exitCode(error: unknown): number | null {
  if (typeof error !== 'object' || error === null) return null;
  const code: unknown = Reflect.get(error, 'code');
  return typeof code === 'number' ? code : null;
}

/** A JSON object out of a file NODExport wrote. */
async function readJson(path: string): Promise<Record<string, unknown>> {
  const data: unknown = JSON.parse(await readFile(path, 'utf8'));
  if (typeof data !== 'object' || data === null || Array.isArray(data)) throw new Error(`${path}: not a JSON object`);
  return Object.fromEntries(Object.entries(data));
}

const key = (text: string): string => createHash('sha1').update(text.toLowerCase()).digest('hex').slice(0, 16);

export interface Exporter {
  /** The catalog of the build: templates, motion sets, model headers. */
  catalog(signature: string): Promise<Record<string, unknown>>;
  /** The container of a model, by its relative path on disk. */
  model(signature: string, rel: string): Promise<string>;
  /** The JSON export of a clip, by its relative path on disk. */
  clip(signature: string, rel: string): Promise<string>;
  /** The materials export of one material name. */
  material(signature: string, name: string): Promise<string>;
  /** Drop the exports of every other signature. */
  keepOnly(signature: string): Promise<void>;
}

export function createExporter(exe: string, root: string, cache: string): Exporter {
  const pending = new Map<string, Promise<string>>();

  /** Run NODExport. True when exported; false when it refused the input (exit 1). */
  async function nodExport(args: readonly string[]): Promise<boolean> {
    try {
      await run(exe, [...args], { maxBuffer: OUTPUT });
      return true;
    } catch (error) {
      if (exitCode(error) === 1) return false;
      throw error;
    }
  }

  /** `make` writes `out` once; a second ask while it runs waits for the first. */
  function once(out: string, make: (tmp: string) => Promise<void>): Promise<string> {
    const running = pending.get(out);
    if (running) return running;
    const job = (async () => {
      if (await isFile(out)) return out;
      const tmp = `${out}.part`;
      await rm(tmp, { recursive: true, force: true });
      await mkdir(tmp, { recursive: true });
      try {
        await make(tmp);
      } finally {
        await rm(tmp, { recursive: true, force: true });
      }
      return out;
    })().finally(() => pending.delete(out));
    pending.set(out, job);
    return job;
  }

  /** Write `data` to `out` through a temporary file, so a reader never sees half of it. */
  async function put(out: string, data: string | Uint8Array): Promise<void> {
    await writeFile(`${out}.new`, data);
    await rename(`${out}.new`, out);
  }

  async function materialsOf(tmp: string, names: readonly string[]): Promise<unknown> {
    const list = join(tmp, 'names.txt');
    const out = join(tmp, 'materials.json');
    await writeFile(list, names.map((name) => `${name}\n`).join(''));
    if (!(await nodExport(['materials', root, list, out]))) throw new Error(`NODExport materials refused: ${JSON.stringify(await readJson(out))}`);
    return (await readJson(out))['materials'];
  }

  const dirOf = async (signature: string, kind: string): Promise<string> => {
    const dir = join(cache, signature, kind);
    await mkdir(dir, { recursive: true });
    return dir;
  };

  return {
    async catalog(signature) {
      const out = join(await dirOf(signature, '.'), 'catalog.json');
      await once(out, async (tmp) => {
        const written = join(tmp, 'catalog.json');
        if (!(await nodExport(['catalog', root, written]))) throw new Error(`NODExport catalog refused: ${JSON.stringify(await readJson(written))}`);
        await put(out, await readFile(written));
      });
      return readJson(out);
    },
    async model(signature, rel) {
      const out = join(await dirOf(signature, 'models'), `${key(rel)}.nodx`);
      return once(out, async (tmp) => {
        const json = join(tmp, 'model.json');
        const bin = join(tmp, 'model.bin');
        const exported = await nodExport(['nod', join(root, rel), json, bin]);
        const model = await readJson(json);
        let body: Record<string, unknown>;
        let binary = new Uint8Array(0);
        if (exported) {
          const names = model['materials'];
          if (!Array.isArray(names) || !names.every((n): n is string => typeof n === 'string')) throw new Error(`${rel}: the export has no material names`);
          body = { model, materials: await materialsOf(tmp, names) };
          binary = new Uint8Array(await readFile(bin));
        } else {
          body = { error: `${rel}: ${String(model['error'])}` };
        }
        await put(out, packContainer(body, binary));
      });
    },
    async clip(signature, rel) {
      const out = join(await dirOf(signature, 'clips'), `${key(rel)}.json`);
      return once(out, async (tmp) => {
        const json = join(tmp, 'clip.json');
        const exported = await nodExport(['nad', join(root, rel), json]);
        const clip = await readJson(json);
        await put(out, JSON.stringify(exported ? clip : { error: `${rel}: ${String(clip['error'])}` }));
      });
    },
    async material(signature, name) {
      const out = join(await dirOf(signature, 'materials'), `${key(name)}.json`);
      return once(out, async (tmp) => {
        const list = await materialsOf(tmp, [name]);
        if (!Array.isArray(list) || list.length !== 1) throw new Error(`NODExport materials: not one material for ${name}`);
        await put(out, JSON.stringify(list[0]));
      });
    },
    async keepOnly(signature) {
      await mkdir(cache, { recursive: true });
      for (const entry of await readdir(cache)) if (entry !== signature) await rm(join(cache, entry), { recursive: true, force: true });
    },
  };
}
