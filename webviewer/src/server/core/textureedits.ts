// The edit sessions of a texture service (SPEC-PHOTOCRAFT sections 7, 8, 10).
//
// A session is a folder of files in the texture store. The pipeline writes
// it (scripts/hdtex/core/edits.py); this file reads session.json and
// scratch.json to show a state, and runs no pipeline code for that. The
// rules it applies are those of SPEC-PHOTOCRAFT 8: which state the recorded
// hashes make, and that a scratch whose size or time differ from
// scratch.json is checked. Whether the input is stale is read from the state
// index; the pipeline reads the file itself when it transfers.
//
// What changes something runs `hd_textures.py edit`: `open` and `discard`
// are waited for, `check` is started and not waited for, one at a time per
// session, and `transfer` runs as a process of its own.

import { readdir, readFile, stat } from 'node:fs/promises';
import { join } from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';
import { SCRATCH_LIMIT, SESSION_RULE, type EditDiscardBody, type EditOpenAsk, type EditSession, type EditStateName, type EditTransferBody, type EditWrittenBody } from '../../shared/edits';
import { ORIGINAL, type TextureState } from '../../shared/textures';
import { HttpError } from './backend';
import { errorCode, isFile, messageOf, TooLarge, type Request } from './http';
import { asObject, shown, texts, type IndexReader } from './textureindex';

/** The files of a session folder (scripts/hdtex/core/edits.py). */
const SESSION = 'session.json';
const SCRATCH = 'scratch.psd';
const SCRATCH_RECORD = 'scratch.json';
/** The format of session.json and scratch.json this reader knows. */
const FORMAT = 1;
/** How long a transfer may take to show after its process started, and how often the files are read meanwhile. */
const TRANSFER_SEEN_MS = 30_000;
const TRANSFER_POLL_MS = 100;

export interface EditService {
  /** The sessions of the dataset's textures. A scratch that changed since its check starts one. */
  list(dataset: string): Promise<EditSession[]>;
  one(dataset: string, session: string): Promise<EditSession>;
  /** Make the session of a texture and a variant, or answer the one that is there. */
  open(dataset: string, ask: EditOpenAsk): Promise<EditSession>;
  /** The scratch on disk; 404 when the session or its scratch is not there. */
  scratch(session: string): Promise<string>;
  /** One plane's picture on disk: as it was opened (`base`), or as the last check rendered it. */
  picture(session: string, kind: 'base' | 'rendered', plane: string): Promise<string>;
  /** Write the request's body as the scratch. It does not wait for the check. */
  write(session: string, request: Request): Promise<EditWrittenBody>;
  /** Start the transfer; the reply shows its request, or its variant. A refusal changes nothing. */
  transfer(dataset: string, session: string): Promise<EditTransferBody>;
  discard(dataset: string, session: string): Promise<EditDiscardBody>;
}

export interface EditParts {
  /** `<TEXTURE_STORE>/<game>/edits`. */
  root: string;
  index: IndexReader;
  /** Run a pipeline command and wait for its JSON answer. A refusal of the pipeline is an HttpError 400. */
  command(name: string, dataset: string, words: readonly string[]): Promise<Record<string, unknown>>;
  /** Start a pipeline command as a process that outlives the server. Returns the file its start output goes to. */
  start(name: string, dataset: string, words: readonly string[]): Promise<string>;
  /** Have the pipeline read what a texture needs to be asked for. */
  judge(dataset: string, asset: string): Promise<void>;
}

/** session.json, the parts this reader uses. */
interface Kept {
  asset: string;
  origin: string;
  variant: string;
  /** The hash of the input variant's file when it was opened. */
  input: string;
  width: number;
  height: number;
  planes: string[];
  bases: Record<string, string>;
  transfers: { variant: string; planes: Record<string, string> }[];
}

/** scratch.json: what the last check read. */
interface Said {
  bytes: number;
  changed: string;
  planes: Record<string, string>;
  leftOut: string[];
  refused: string;
}

const gone = (error: unknown): boolean => errorCode(error) === 'ENOENT' || errorCode(error) === 'ENOTDIR';

/** A JSON object of a file; null: the file is not there. */
async function jsonFile(path: string): Promise<Record<string, unknown> | null> {
  let text: string;
  try {
    text = await readFile(path, 'utf8');
  } catch (error) {
    if (gone(error)) return null;
    throw error;
  }
  const found = asObject(JSON.parse(text));
  if (found['format'] !== FORMAT) throw new Error(`${path} is not in format ${FORMAT}`);
  return found;
}

const hashes = (value: unknown): Record<string, string> => Object.fromEntries(Object.entries(asObject(value)).filter((pair): pair is [string, string] => typeof pair[1] === 'string'));

function same(one: Record<string, string>, other: Record<string, string>): boolean {
  const names = Object.keys(one);
  return names.length === Object.keys(other).length && names.every((name) => one[name] === other[name]);
}

const text = (value: unknown, what: string): string => {
  if (typeof value !== 'string' || !value) throw new HttpError(400, { error: `${what} is required` });
  return value;
};

export function editSessions(parts: EditParts): EditService {
  const { root, index } = parts;
  /** The check that runs, by session. */
  const checking = new Map<string, Promise<void>>();
  /** A check that could not run, by session: the scratch it was started for, and why. It is not started again for that scratch. */
  const failed = new Map<string, { scratch: string; reason: string }>();

  function folderOf(session: string): string {
    if (!SESSION_RULE.test(session)) throw new HttpError(400, { error: 'a session is named by 16 hex digits' });
    return join(root, session);
  }

  async function kept(session: string): Promise<Kept> {
    const found = await jsonFile(join(folderOf(session), SESSION));
    if (!found) throw new HttpError(404, { error: `there is no edit session ${session}` });
    const transfers = Array.isArray(found['transfers']) ? found['transfers'].map((one) => ({ variant: String(asObject(one)['variant']), planes: hashes(asObject(one)['planes']) })) : [];
    return {
      asset: String(found['asset']),
      origin: String(found['origin']),
      variant: String(found['variant']),
      input: String(asObject(found['input'])['sha256']),
      width: Number(found['width']),
      height: Number(found['height']),
      planes: texts(found['planes']),
      bases: hashes(found['bases']),
      transfers,
    };
  }

  async function saidOf(session: string): Promise<Said> {
    const path = join(folderOf(session), SCRATCH_RECORD);
    const found = await jsonFile(path);
    if (!found) throw new Error(`${path} is not there: the scratch of session ${session} was never checked`);
    return { bytes: Number(found['bytes']), changed: String(found['changed']), planes: hashes(found['planes']), leftOut: texts(found['left_out']), refused: String(found['refused']) };
  }

  /** The scratch's size and time, as the check records them (the time in ns, as text); `at`: the time in ms, null when it is not there. */
  async function stampOf(session: string): Promise<{ bytes: number; changed: string; at: number | null }> {
    try {
      const found = await stat(join(folderOf(session), SCRATCH), { bigint: true });
      return { bytes: Number(found.size), changed: String(found.mtimeNs), at: Number(found.mtimeMs) };
    } catch (error) {
      if (gone(error)) return { bytes: 0, changed: '', at: null };
      throw error;
    }
  }

  /** Why the session's input is not the file that was opened, as the state index has it (R-PC-35). Empty: it is. */
  function staleReason(dataset: string, record: Kept): string {
    const state = index.textures(dataset, [record.asset]).get(record.asset);
    if (!state) return `its input is gone: ${dataset} has no texture ${record.asset}`;
    const other = `${record.variant} is another file now than the one that was opened`;
    if (record.variant === ORIGINAL) {
      const hash = index.originalHash(record.origin);
      if (hash === null) return `its input is gone: the original of ${record.asset} was never read`;
      return hash === record.input ? '' : other;
    }
    const made = state.variants.find((one) => one.id === record.variant);
    if (!made) return `its input is gone: ${record.asset} has no variant ${record.variant}`;
    if (made.stale) return `${record.variant} is stale: the original changed since it was made`;
    return made.sha256 === record.input ? '' : other;
  }

  /** Start the pipeline's check of a session. A check that cannot run is logged and kept as the session's `checkError`. */
  function check(dataset: string, session: string, scratch: string): void {
    const run = parts
      .command('edit', dataset, ['check', '--session', session])
      .then(
        () => {
          failed.delete(session);
        },
        (error: unknown) => {
          console.error(error);
          failed.set(session, { scratch, reason: messageOf(error) });
        },
      )
      .finally(() => checking.delete(session));
    checking.set(session, run);
  }

  async function shownSession(dataset: string, session: string, record: Kept): Promise<EditSession> {
    const stamp = await stampOf(session);
    const said = await saidOf(session);
    const scratch = `${stamp.bytes}:${stamp.changed}`;
    const checked = said.bytes === stamp.bytes && said.changed === stamp.changed;
    if (!checked && !checking.has(session) && failed.get(session)?.scratch !== scratch) check(dataset, session, scratch);
    const stale = staleReason(dataset, record);
    const last = record.transfers[record.transfers.length - 1];
    let state: EditStateName = 'edited';
    if (stale) state = 'stale';
    else if (!said.refused && same(said.planes, record.bases)) state = 'unchanged';
    else if (!said.refused && last && same(said.planes, last.planes)) state = 'transferred';
    return {
      session,
      asset: record.asset,
      variant: record.variant,
      size: [record.width, record.height],
      planes: record.planes,
      state,
      reason: stale || said.refused,
      changed: record.planes.filter((name) => name in said.planes && said.planes[name] !== record.bases[name]),
      leftOut: said.leftOut,
      rendered: said.planes,
      checking: checking.has(session),
      checkError: !checked && failed.get(session)?.scratch === scratch ? (failed.get(session)?.reason ?? '') : '',
      transfers: record.transfers.map((one) => one.variant),
      scratch: join(folderOf(session), SCRATCH),
      scratchChanged: stamp.at,
    };
  }

  const one = async (dataset: string, session: string): Promise<EditSession> => shownSession(dataset, session, await kept(session));

  async function list(dataset: string): Promise<EditSession[]> {
    let names: string[];
    try {
      names = await readdir(root);
    } catch (error) {
      if (gone(error)) return [];
      throw error;
    }
    const found: EditSession[] = [];
    for (const name of names.filter((one) => SESSION_RULE.test(one)).sort()) {
      // A folder without its record is a session that was discarded since the folder was listed.
      const record = (await isFile(join(root, name, SESSION))) ? await kept(name) : null;
      // Datasets that share the origin share the session (SPEC-PHOTOCRAFT 8).
      if (record && index.origin(dataset, record.asset) === record.origin) found.push(await shownSession(dataset, name, record));
    }
    return found.sort((a, b) => (a.asset === b.asset ? a.variant.localeCompare(b.variant) : a.asset.localeCompare(b.asset)));
  }

  async function open(dataset: string, ask: EditOpenAsk): Promise<EditSession> {
    const asset = text(ask.asset, 'asset');
    const variant = text(ask.variant, 'variant');
    // Nobody asked for it by name yet: the pipeline reads its role and its original first.
    if (!index.textures(dataset, [asset]).get(asset)?.judged) await parts.judge(dataset, asset);
    const answer = await parts.command('edit', dataset, ['open', '--asset', asset, '--variant', variant]);
    const session = asObject(answer['session'])['session'];
    if (typeof session !== 'string') throw new Error(`hd_textures.py edit open named no session: ${JSON.stringify(answer)}`);
    return one(dataset, session);
  }

  async function scratch(session: string): Promise<string> {
    await kept(session);
    const full = join(folderOf(session), SCRATCH);
    if (!(await isFile(full))) throw new HttpError(404, { error: `the session ${session} has no scratch` });
    return full;
  }

  async function picture(session: string, kind: 'base' | 'rendered', plane: string): Promise<string> {
    const record = await kept(session);
    if (!record.planes.includes(plane)) throw new HttpError(400, { error: `${plane} is no plane of the session; it has ${record.planes.join(', ')}` });
    const full = join(folderOf(session), kind, `${plane}.png`);
    if (!(await isFile(full))) throw new HttpError(404, { error: `the session ${session} has no ${kind} picture of ${plane}` });
    return full;
  }

  async function write(session: string, request: Request): Promise<EditWrittenBody> {
    await kept(session);
    try {
      return { bytes: await request.save(join(folderOf(session), SCRATCH), SCRATCH_LIMIT) };
    } catch (error) {
      if (error instanceof TooLarge) throw new HttpError(413, { error: `a scratch is at most ${SCRATCH_LIMIT} bytes` });
      throw error;
    }
  }

  /** The session once no check of it runs: its scratch is the one its state was read from. */
  async function settled(dataset: string, session: string): Promise<EditSession> {
    for (;;) {
      const now = await one(dataset, session);
      const run = checking.get(session);
      if (!run) {
        if (now.checkError) throw new Error(`the scratch of session ${session} could not be checked: ${now.checkError}`);
        return now;
      }
      await run;
    }
  }

  const textureOf = (dataset: string, asset: string): TextureState | null => {
    const found = index.textures(dataset, [asset]).get(asset);
    return found ? shown(found) : null;
  };

  async function transfer(dataset: string, session: string): Promise<EditTransferBody> {
    const now = await settled(dataset, session);
    if (now.reason) throw new HttpError(400, { error: `the edit of ${now.asset} cannot be transferred: ${now.reason}` });
    // The same planes as the last transfer: its variant is the one (R-PC-54). Nothing is started.
    if (now.state === 'transferred') return { session: now, texture: textureOf(dataset, now.asset) };
    if (now.changed.length === 0) throw new HttpError(400, { error: `the edit of ${now.asset} changes no plane: there is nothing to transfer` });
    // What a transfer changes first: its request in the index, or its entry in the session's record.
    const held = async (): Promise<string> => {
      const found = index.textures(dataset, [now.asset]).get(now.asset);
      return JSON.stringify([(await kept(session)).transfers.length, found?.requests ?? {}, found?.variants.map((made) => made.id) ?? []]);
    };
    const before = await held();
    const log = await parts.start('edit', dataset, ['transfer', '--session', session]);
    const until = Date.now() + TRANSFER_SEEN_MS;
    while ((await held()) === before) {
      if (Date.now() > until) throw new Error(`the transfer of session ${session} did not show in ${TRANSFER_SEEN_MS / 1000} s; its start: ${log}`);
      await delay(TRANSFER_POLL_MS);
    }
    return { session: await one(dataset, session), texture: textureOf(dataset, now.asset) };
  }

  async function discard(dataset: string, session: string): Promise<EditDiscardBody> {
    await kept(session);
    // A check that runs reads the folder: it ends first.
    await checking.get(session);
    await parts.command('edit', dataset, ['discard', '--session', session]);
    failed.delete(session);
    return { session, discarded: true };
  }

  return { list, one, open, scratch, picture, write, transfer, discard };
}
