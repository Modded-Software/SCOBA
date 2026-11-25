// The reader of the pipeline's state index (SPEC-HD-TEXTURES 4.9,
// SPEC-VIEWER 17.1), and the processes the texture service starts.
//
// The file is opened read-only for each read, so a file the pipeline made
// anew is seen. Nothing is kept between reads.

import { spawn } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { open } from 'node:fs/promises';
import { join } from 'node:path';
import { DatabaseSync } from 'node:sqlite';
import { inflateSync } from 'node:zlib';
import type { OwnerState, TextureRequest, TexturesHead, TextureState, TextureVariant } from '../../shared/textures';
import { errorCode, messageOf } from './http';

/** The schema this reader knows (scripts/hdtex/core/index.py). */
export const INDEX_SCHEMA = 4;
/**
 * How long a read waits for the file when a writer holds it whole. A reader of a WAL file does not wait for a
 * write, but a pipeline process that ends as the file's last user folds the log into the file and holds it
 * meanwhile. Measured: 163 of 6828 reads failed with "database is locked" without a wait; none with one, the
 * longest read 3.5 ms. Under the bound of R-VIEW-111: a read that cannot be made in time fails, and says so.
 */
const INDEX_BUSY_MS = 200;

/** A text of the index: zlib-compressed JSON (scripts/hdtex/core/index.py `text`). */
function textOf(data: unknown): unknown {
  if (!(data instanceof Uint8Array)) throw new Error(`a text of the texture state index is no compressed body: ${typeof data}`);
  return JSON.parse(inflateSync(data).toString('utf8'));
}

export const asObject = (value: unknown): Record<string, unknown> => (typeof value === 'object' && value !== null && !Array.isArray(value) ? (value as Record<string, unknown>) : {});
export const texts = (value: unknown): string[] => (Array.isArray(value) ? value.filter((one): one is string => typeof one === 'string') : []);

/** A state as the index holds it: each variant with its file, each open request with its program. */
export type Indexed = Omit<TextureState, 'variants' | 'requests'> & {
  variants: (TextureVariant & { path: string })[];
  requests: Record<string, Partial<Pick<TextureRequest, 'done' | 'variant' | 'since'>> & Omit<TextureRequest, 'done' | 'variant' | 'since'> & { pid?: number; started?: number; log?: string }>;
};

/** When a process began, in clock ticks since the host started (field 22 of its stat); null: there is no such process. */
function startedAt(pid: number): number | null {
  let stat: string;
  try {
    stat = readFileSync(`/proc/${pid}/stat`, 'utf8');
  } catch (error) {
    if (errorCode(error) === 'ENOENT' || errorCode(error) === 'ESRCH') return null;
    throw error;
  }
  // The process name, in brackets, may hold spaces: the fields are counted after it.
  return Number(stat.slice(stat.lastIndexOf(')') + 1).trim().split(/\s+/)[19]);
}

/**
 * The state the page gets: no file path, no program. The one rule this
 * reader applies (SPEC-HD-TEXTURES 4.9): a request whose program is gone has
 * failed, and its variant may be asked for again. The index cannot say so:
 * nobody was left to write it.
 */
export function shown(indexed: Indexed): TextureState {
  const { variants, requests, ...state } = indexed;
  const open: Record<string, TextureRequest> = {};
  for (const [recipe, { pid, started, log: _log, ...held }] of Object.entries(requests)) {
    // A row written before these fields were kept has none of them.
    const request: TextureRequest = { ...held, done: held.done ?? 0, variant: held.variant ?? '', since: held.since ?? null };
    const gone = request.state !== 'failed' && pid !== undefined && startedAt(pid) !== started;
    open[recipe] = gone ? { ...request, state: 'failed', reason: `the program that made it (process ${pid}) stopped before it was done; ask again` } : request;
  }
  return { ...state, variants: variants.map(({ path: _path, ...variant }) => variant), requests: open };
}

/** The statements this reader runs: files of the repository's SQL tree, sql/texture-index/ (scripts/hdtex/core/queries.py). */
const READS = ['dataset_head', 'reader_texture_state', 'reader_of_kind', 'reader_owner_state', 'origin_of', 'reader_original_hash'] as const;
type Read = (typeof READS)[number];

export class IndexReader {
  private readonly sql: Record<Read, string>;

  /** `sqlDir`: the folder sql/texture-index/ of the repository. A missing statement file throws here. */
  constructor(
    readonly file: string,
    readonly game: string,
    sqlDir: string,
  ) {
    this.sql = Object.fromEntries(READS.map((name) => [name, readFileSync(join(sqlDir, `${name}.sql`), 'utf8')])) as Record<Read, string>;
  }

  /** `absent`: the answer when there is no index yet. */
  private reading<T>(absent: T, read: (db: DatabaseSync) => T): T {
    if (!existsSync(this.file)) return absent;
    const db = new DatabaseSync(this.file, { readOnly: true, timeout: INDEX_BUSY_MS });
    try {
      const schema = Number(asObject(db.prepare('PRAGMA user_version').get())['user_version']);
      // 0: the file is there and the pipeline's first change is not: nobody wrote a table yet.
      if (schema === 0) return absent;
      if (schema !== INDEX_SCHEMA) throw new Error(`the texture state index ${this.file} has schema ${schema}; this viewer reads schema ${INDEX_SCHEMA}`);
      return read(db);
    } catch (error) {
      if (errorCode(error) === 'ERR_SQLITE_ERROR' && messageOf(error).includes('locked')) throw new Error(`the texture state index ${this.file} was held by a writer for more than ${INDEX_BUSY_MS} ms`, { cause: error });
      throw error;
    } finally {
      db.close();
    }
  }

  /** The dataset's head; null: the index does not hold the dataset. */
  head(dataset: string): TexturesHead | null {
    return this.reading(null, (db) => {
      const row = db.prepare(this.sql.dataset_head).get(this.game, dataset);
      return row === undefined ? null : (JSON.parse(String(row['head'])) as TexturesHead);
    });
  }

  textures(dataset: string, assets: readonly string[]): Map<string, Indexed> {
    return this.reading(new Map<string, Indexed>(), (db) => {
      const found = new Map<string, Indexed>();
      const ask = db.prepare(this.sql.reader_texture_state);
      for (const asset of new Set(assets)) {
        const row = ask.get(this.game, dataset, asset);
        if (row !== undefined) found.set(asset, textOf(row['state']) as Indexed);
      }
      return found;
    });
  }

  ofKind(dataset: string, kind: string): { described: Record<string, unknown>; state: Indexed }[] {
    return this.reading([], (db) =>
      db
        .prepare(this.sql.reader_of_kind)
        .all(this.game, dataset, kind)
        .map((row) => ({ described: asObject(textOf(row['description'])), state: textOf(row['state']) as Indexed })),
    );
  }

  owner(dataset: string, owner: string): OwnerState | null {
    return this.reading(null, (db) => {
      const row = db.prepare(this.sql.reader_owner_state).get(this.game, dataset, owner);
      return row === undefined ? null : (textOf(row['state']) as OwnerState);
    });
  }

  origin(dataset: string, asset: string): string | null {
    return this.reading(null, (db) => {
      const row = db.prepare(this.sql.origin_of).get(this.game, dataset, asset);
      return row === undefined ? null : String(row['origin']);
    });
  }

  /** The hash of the original at an origin, as the pipeline last read its file; null: it was never read. */
  originalHash(origin: string): string | null {
    return this.reading(null, (db) => {
      const row = db.prepare(this.sql.reader_original_hash).get(this.game, origin);
      return row === undefined ? null : String(row['sha256']);
    });
  }
}

/** What a command printed, and how it ended. */
export interface Ran {
  code: number;
  out: string;
  err: string;
}

export function collect(command: string, args: readonly string[], cwd: string, env: NodeJS.ProcessEnv): Promise<Ran> {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { cwd, env, stdio: ['ignore', 'pipe', 'pipe'] });
    let out = '';
    let err = '';
    child.stdout.setEncoding('utf8').on('data', (part: string) => (out += part));
    child.stderr.setEncoding('utf8').on('data', (part: string) => (err += part));
    child.on('error', reject);
    child.on('close', (code) => resolve({ code: code ?? 1, out, err }));
  });
}

/** Start a process that outlives the server; its output goes to `log`. */
export async function detach(command: string, args: readonly string[], cwd: string, env: NodeJS.ProcessEnv, log: string): Promise<void> {
  const handle = await open(log, 'a');
  try {
    const child = spawn(command, args, { cwd, env, detached: true, stdio: ['ignore', handle.fd, handle.fd] });
    await new Promise<void>((resolve, reject) => {
      child.once('spawn', resolve);
      child.once('error', reject);
    });
    child.unref();
  } finally {
    await handle.close();
  }
}
