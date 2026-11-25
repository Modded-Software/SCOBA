// The StarCraft: Ghost build on disk (SPEC-VIEWER-GHOST 3): where it is,
// the index of the files the viewer reads, found without regard to case,
// and the signature of the dataset.

import { createHash } from 'node:crypto';
import { access, constants, readdir, stat } from 'node:fs/promises';
import { join } from 'node:path';
import { GameUnavailable } from '../../../server/core/backend';
import { errorCode } from '../../../server/core/http';
import { requiredPath } from '../../../server/core/settings';

/** The folders the viewer reads, relative to the build (SPEC-VIEWER-GHOST 3). */
export const READ_FOLDERS = ['3D/Models', '3D/Anims', '3D/Motions', '3D/Materials', 'Materials', 'Misc/Templates'] as const;
/** Files of the build's top folder that are read. */
const READ_FILES = ['MaterialDirs.txt'];

export interface GhostSettings {
  readonly root: string;
  readonly exporter: string;
  readonly cache: string;
}

/** The settings, or GameUnavailable with the reason (R-VIEW-8). */
export async function ghostSettings(viewerDir: string, env: NodeJS.ProcessEnv): Promise<GhostSettings> {
  const root = env['GHOST_PATH'] ?? '';
  if (!root) throw new GameUnavailable('GHOST_PATH is not set');
  if (!(await isDir(join(root, '3D', 'Models')))) throw new GameUnavailable(`GHOST_PATH (${root}) has no 3D/Models`);
  const exporter = env['NODSDK_EXPORT'] || join(viewerDir, 'build', 'nodsdk', 'cmake', 'NODExport');
  try {
    await access(exporter, constants.X_OK);
  } catch (error) {
    if (errorCode(error) !== 'ENOENT' && errorCode(error) !== 'EACCES') throw error;
    throw new GameUnavailable(`NODExport is not built (${exporter}): run make install-deps`);
  }
  const data = requiredPath(env, 'WEBVIEWER_DATA');
  return { root, exporter, cache: join(env['WEBVIEWER_CACHE'] || join(data, 'cache'), 'ghost') };
}

async function isDir(path: string): Promise<boolean> {
  try {
    return (await stat(path)).isDirectory();
  } catch (error) {
    if (errorCode(error) === 'ENOENT') return false;
    throw error;
  }
}

/** Every file below `dir`, as paths relative to `base` with "/". */
async function walk(base: string, dir: string, out: string[]): Promise<void> {
  let entries;
  try {
    entries = await readdir(join(base, dir), { withFileTypes: true });
  } catch (error) {
    if (errorCode(error) === 'ENOENT') return;
    throw error;
  }
  for (const entry of entries) {
    const rel = `${dir}/${entry.name}`;
    if (entry.isDirectory()) await walk(base, rel, out);
    else if (entry.isFile()) out.push(rel);
  }
}

export interface BuildIndex {
  /** Lower-case relative path to the path on disk. */
  readonly byLower: ReadonlyMap<string, string>;
  /** Paths that differ only by case: the lower-case path and every spelling. */
  readonly caseTwins: readonly string[][];
  readonly signature: string;
  readonly files: number;
}

/** Index the files the viewer reads; the signature hashes their paths, sizes and change times. */
export async function indexBuild(root: string): Promise<BuildIndex> {
  const paths: string[] = [];
  for (const folder of READ_FOLDERS) await walk(root, folder, paths);
  for (const file of READ_FILES) {
    try {
      if ((await stat(join(root, file))).isFile()) paths.push(file);
    } catch (error) {
      if (errorCode(error) !== 'ENOENT') throw error;
    }
  }
  paths.sort();
  const hash = createHash('sha1');
  const spellings = new Map<string, string[]>();
  for (const rel of paths) {
    const info = await stat(join(root, rel));
    hash.update(`${rel}\t${info.size}\t${info.mtimeMs}\n`);
    const key = rel.toLowerCase();
    spellings.set(key, [...(spellings.get(key) ?? []), rel]);
  }
  const byLower = new Map<string, string>();
  const caseTwins: string[][] = [];
  for (const [key, names] of spellings) {
    const [first] = names;
    if (first !== undefined) byLower.set(key, first);
    if (names.length > 1) caseTwins.push([key, ...names]);
  }
  return { byLower, caseTwins, signature: hash.digest('hex'), files: paths.length };
}

/**
 * A file named by another file, in `folder`, without regard to case; with
 * `ext` appended when the name has no extension (SPEC-VIEWER-GHOST 4.5, 4.6).
 * The relative path on disk, or null.
 */
export function findIn(index: BuildIndex, folder: string, name: string, ext: string): string | null {
  const base = `${folder}/${name}`.toLowerCase();
  const exact = index.byLower.get(base);
  if (exact !== undefined) return exact;
  if (/\.[^./\\]*$/.test(name)) return null;
  return index.byLower.get(base + ext) ?? null;
}
