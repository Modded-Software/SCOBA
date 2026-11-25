// The texture service over the pipeline (SPEC-VIEWER 17.1, 17.2).
//
// A state is read from the pipeline's state index, a SQLite file in the
// texture store (SPEC-HD-TEXTURES 4.9). The pipeline writes it whenever a
// state changes; this file reads rows and runs no pipeline code to show one
// (R-VIEW-111). The pipeline owns every rule: what a texture is, which
// models and sizes may be asked for, what a skin shows, where a file lies.
//
// What changes something runs a command of scripts/hd_textures.py: a
// request, a skin change, a bake, and `index`, which brings a dataset's rows
// up to date with its files and reads what a texture asked for by name
// needs. A request runs as a process of its own, so it goes on when the
// server stops (R-VIEW-121). The upscaler's one worker is started here when
// none runs, with the command the pipeline names (its GPU is the pipeline's
// rule).

import { existsSync, realpathSync } from 'node:fs';
import { mkdir } from 'node:fs/promises';
import { basename, join, sep } from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';
import { asksFrom, ORIGINAL, recipeOf, variantId, type BakeAsk, type BakeBody, type OwnerBody, type OwnerLookup, type SkinAsk, type SkinBody, type SkinUpscaled, type TextureRemoveAsk, type TextureRequestAsk, type TexturesBody, type TexturesHead, type TextureState, type UnbakeAsk } from '../../shared/textures';
import { HttpError } from './backend';
import { messageOf } from './http';
import { requiredPath } from './settings';
import { editSessions, type EditService } from './textureedits';
import { asObject, collect, detach, IndexReader, shown, texts, type Indexed } from './textureindex';

/** The most assets one states call asks for: one model's textures, with room. */
export const MAX_ASSETS = 200;
/** How long a request may take to show in the index after its process started, and how often the index is read meanwhile. */
const REQUEST_SEEN_MS = 30_000;
const REQUEST_POLL_MS = 100;

export interface TextureService {
  /** The states of these textures, read from the index. An asset without a row is listed as unknown. */
  states(dataset: string, assets: readonly string[]): TexturesBody;
  /** An owner's state; 404 when the index does not hold it. */
  owner(dataset: string, owner: string): OwnerBody;
  /** An owner's state, or null when the index does not hold it (the owner route). */
  lookup(dataset: string, owner: string): OwnerLookup;
  /** Every texture of one kind of the game's (SC2 "terrain"), in short. */
  listKind(dataset: string, kind: string): TextureListing[];
  /** Where the dataset's file of a texture lies, as the pipeline resolves it (R-VIEW-112); null: the pipeline does not know the asset. */
  origin(dataset: string, asset: string): string | null;
  /** A variant's file on disk; null when there is none. */
  file(dataset: string, asset: string, variant: string): string | null;
  /** The index holds the dataset: it was brought up to date at least once. */
  indexed(dataset: string): boolean;
  /** Bring the dataset's rows up to date with its files (its files changed, or the server starts). One at a time per dataset. */
  sync(dataset: string): Promise<void>;
  /** Have the pipeline read what these textures need to be asked for (their role, their size), and give their states. */
  judge(dataset: string, assets: readonly string[]): Promise<TexturesBody>;
  /** Queue one variant; refused when the state does not offer that input, model and size. */
  request(dataset: string, ask: TextureRequestAsk): Promise<TexturesBody>;
  /** Remove one variant (R-HD-146); refused while something still needs it. The texture's state. */
  remove(dataset: string, ask: TextureRemoveAsk): Promise<TexturesBody>;
  /** The log file of an open or failed request, as the index names it; null: the state has no such request. */
  requestLog(dataset: string, asset: string, recipe: string): string | null;
  /** A skin change; an upscale also starts a request per texture it names. */
  skin(dataset: string, ask: SkinAsk): Promise<SkinBody>;
  bake(dataset: string, ask: BakeAsk): Promise<BakeBody>;
  unbake(dataset: string, ask: UnbakeAsk): Promise<BakeBody>;
  /** The edit sessions of the game's textures (SPEC-PHOTOCRAFT 7). */
  readonly edits: EditService;
}

/** One texture of a listing. */
export interface TextureListing {
  asset: string;
  /** What the game says it is (SC2: diffuse, normal); null: it cannot be upscaled, or its role is not read yet. */
  role: string | null;
  users: string[];
  /** The game's data entries that name it. */
  entries: string[];
  /** Its variant ids, largest first within each recipe. */
  variants: string[];
  /** Its own bake; null: none. */
  bake: string | null;
  /** The dataset's package holds a file for it. */
  packaged: boolean;
}

export interface PipelineSettings {
  /** The game id of the pipeline (`--game`). */
  game: string;
  /** The project root: scripts/hd_textures.py is below it. */
  repoRoot: string;
  /** The texture store (`TEXTURE_STORE`, SPEC-PATHS). */
  storeDir: string;
  /** The folder of a dataset's own files (`--layer`), or null for a dataset without one. */
  layerOf(dataset: string): string | null;
  /** Where the worker's and the requests' launch output go. */
  logDir: string;
  env?: NodeJS.ProcessEnv;
}

/** The texture store, as the pipeline finds it (scripts/hdtex/core/store.py): TEXTURE_STORE. */
export const storeDirOf = (env: NodeJS.ProcessEnv): string => requiredPath(env, 'TEXTURE_STORE');

const text = (value: unknown, what: string): string => {
  if (typeof value !== 'string' || !value) throw new HttpError(400, { error: `${what} is required` });
  return value;
};

export function pipelineTextures(settings: PipelineSettings): TextureService {
  const env = { ...(settings.env ?? process.env) };
  // The pipeline's Python, not the caller's.
  delete env['VIRTUAL_ENV'];
  delete env['PYTHONPATH'];
  const index = new IndexReader(join(settings.storeDir, 'index.sqlite'), settings.game, join(settings.repoRoot, 'sql', 'texture-index'));
  /** The index's head of a dataset. The server indexes each dataset before it serves it; none yet is an error, not an empty head. */
  function headOf(dataset: string): TexturesHead {
    const head = index.head(dataset);
    if (head === null) throw new HttpError(503, { error: `the texture index holds no ${dataset} yet; it is indexed at the server start` });
    return head;
  }

  function states(dataset: string, assets: readonly string[]): TexturesBody {
    if (assets.length === 0) throw new HttpError(400, { error: 'asset is required' });
    if (assets.length > MAX_ASSETS) throw new HttpError(400, { error: `at most ${MAX_ASSETS} assets at once` });
    const found = index.textures(dataset, assets);
    const wanted = [...new Set(assets)];
    return { ...headOf(dataset), textures: wanted.flatMap((asset) => (found.has(asset) ? [shown(found.get(asset) as Indexed)] : [])), unknown: wanted.filter((asset) => !found.has(asset)) };
  }

  function owner(dataset: string, name: string): OwnerBody {
    const found = index.owner(dataset, text(name, 'owner'));
    if (!found) throw new HttpError(404, { error: `${dataset} has no owner ${name} with textures` });
    return { ...headOf(dataset), owner: found };
  }

  const lookup = (dataset: string, name: string): OwnerLookup => ({ ...headOf(dataset), owner: index.owner(dataset, text(name, 'owner')) });

  function listKind(dataset: string, kind: string): TextureListing[] {
    return index.ofKind(dataset, kind).map(({ described, state }) => ({
      asset: state.asset,
      role: typeof described['role'] === 'string' ? described['role'] : null,
      users: state.users,
      entries: texts(described['entries']),
      variants: state.variants.map((variant) => variant.id),
      bake: state.bake,
      packaged: state.packaged !== null,
    }));
  }

  const file = (dataset: string, asset: string, variant: string): string | null => index.textures(dataset, [asset]).get(asset)?.variants.find((one) => one.id === variant)?.path ?? null;

  /** The words of `uv` that run one command of the pipeline on a dataset. */
  function argsOf(name: string, dataset: string, words: readonly string[]): string[] {
    const layer = settings.layerOf(dataset);
    return ['run', '--project', settings.repoRoot, 'python', join(settings.repoRoot, 'scripts', 'hd_textures.py'), name, '--game', settings.game, '--dataset', dataset, ...(layer ? ['--layer', layer] : []), ...words];
  }

  async function command(name: string, dataset: string, words: readonly string[]): Promise<Record<string, unknown>> {
    const ran = await collect('uv', argsOf(name, dataset, words), settings.repoRoot, env);
    let answer: Record<string, unknown>;
    try {
      answer = asObject(JSON.parse(ran.out));
    } catch (error) {
      throw new Error(`hd_textures.py ${name} did not answer in JSON (exit status ${ran.code}: ${messageOf(error)}): ${ran.err.trim().split('\n').slice(-3).join(' | ')}`);
    }
    // A refusal of the pipeline: the request was wrong, and nothing changed (SPEC-VIEWER 17.2).
    if (ran.code !== 0 && typeof answer['error'] === 'string') throw new HttpError(400, { error: answer['error'] });
    if (ran.code !== 0) throw new Error(`hd_textures.py ${name} ended with exit status ${ran.code}: ${ran.err.trim().split('\n').slice(-3).join(' | ')}`);
    return answer;
  }

  // One `index` per dataset at a time: a second ask while one runs gets a run that starts after it.
  const syncing = new Map<string, Promise<void>>();
  function sync(dataset: string): Promise<void> {
    const before = syncing.get(dataset) ?? Promise.resolve();
    // The run before was answered to its own caller, failed or not; this one starts either way.
    const run = (): Promise<void> => command('index', dataset, []).then(() => undefined);
    const mine = before.then(run, run);
    syncing.set(dataset, mine);
    // Leave the queue when done; the outcome goes to the caller through `mine`.
    const forget = (): void => {
      if (syncing.get(dataset) === mine) syncing.delete(dataset);
    };
    mine.then(forget, forget);
    return mine;
  }

  async function judge(dataset: string, assets: readonly string[]): Promise<TexturesBody> {
    if (assets.length === 0) throw new HttpError(400, { error: 'asset is required' });
    if (assets.length > MAX_ASSETS) throw new HttpError(400, { error: `at most ${MAX_ASSETS} assets at once` });
    await command('index', dataset, [...new Set(assets)].flatMap((asset) => ['--asset', asset]));
    return states(dataset, assets);
  }

  /** Start the upscaler's worker when none runs. The pipeline names its command; the upscaler's lock keeps it to one. */
  async function ensureWorker(dataset: string): Promise<void> {
    await mkdir(settings.logDir, { recursive: true });
    const upscaler = asObject((await command('upscaler', dataset, ['--log', join(settings.logDir, 'worker.log')]))['upscaler']);
    const worker = asObject(upscaler['worker']);
    const [tool, ...args] = texts(worker['command']);
    if (typeof upscaler['idle'] !== 'string' || tool === undefined) throw new Error(`hd_textures.py upscaler named no worker: ${JSON.stringify(upscaler)}`);
    if (!upscaler['idle']) return;
    const extra: Record<string, string> = {};
    for (const [key, value] of Object.entries(asObject(worker['env']))) if (typeof value === 'string') extra[key] = value;
    await detach(tool, args, settings.repoRoot, { ...env, ...extra }, join(settings.logDir, 'worker.out'));
  }

  /** Start a command of the pipeline as a process that outlives the server. Returns the log that holds what its start printed. */
  async function start(name: string, dataset: string, words: readonly string[], log: string): Promise<string> {
    await mkdir(settings.logDir, { recursive: true });
    const full = join(settings.logDir, log);
    await detach('uv', argsOf(name, dataset, words), settings.repoRoot, env, full);
    return full;
  }

  /** Start `request` for one variant. Its state and log are in the store. */
  const startRequest = (dataset: string, asset: string, variant: string): Promise<string> => start('request', dataset, ['--asset', asset, '--variant', variant], 'requests.out');

  /** Why the state does not offer this request; empty: it does. */
  function refusal(state: TextureState, input: string, model: string, size: number): string {
    if (!state.judged) return `${state.asset} is not judged yet`;
    if (state.reason) return `${state.asset} cannot be upscaled: ${state.reason}`;
    const models = asksFrom(state, input);
    if (!(model in models)) return `${input} is no input ${state.asset} may take now; it may take: ${state.asks.map((ask) => ask.input).join(', ') || 'none'}`;
    const offered = models[model] as { reason: string; sizes: Record<string, string> };
    if (offered.reason) return offered.reason;
    const why = offered.sizes[String(size)];
    if (why === undefined) return `${size} is no size of ${model}; it may take: ${Object.keys(offered.sizes).join(', ')}`;
    return why;
  }

  async function request(dataset: string, ask: TextureRequestAsk): Promise<TexturesBody> {
    const asset = text(ask.asset, 'asset');
    const input = typeof ask.input === 'string' && ask.input ? ask.input : ORIGINAL;
    const model = text(ask.model, 'model');
    if (!Number.isInteger(ask.size) || ask.size <= 0) throw new HttpError(400, { error: 'a request names a whole size' });
    let texture = states(dataset, [asset]).textures[0];
    // Nobody asked for it by name yet: the pipeline reads what it needs to say what it may ask for.
    if (!texture || !texture.judged) texture = (await judge(dataset, [asset])).textures[0];
    if (!texture) throw new HttpError(400, { error: `${dataset} has no texture ${asset}` });
    const why = refusal(texture, input, model, ask.size);
    if (why) throw new HttpError(400, { error: why });
    await ensureWorker(dataset);
    await startSeen(dataset, asset, variantId(input, model, ask.size));
    return states(dataset, [asset]);
  }

  /** Start a request and wait until the index shows it or its variant: a reply after it shows the request, and the page polls only while it sees one. */
  async function startSeen(dataset: string, asset: string, variant: string): Promise<void> {
    const recipe = recipeOf(variant);
    // What the index holds of this recipe now: an attempt that failed, or a stale variant, is not the new request.
    const held = (): string | null => {
      const now = index.textures(dataset, [asset]).get(asset);
      const made = now?.variants.find((one) => one.id === variant) ?? null;
      const open = now?.requests[recipe] ?? null;
      return made || open ? JSON.stringify([open, made]) : null;
    };
    const before = held();
    await startRequest(dataset, asset, variant);
    const until = Date.now() + REQUEST_SEEN_MS;
    for (;;) {
      const now = held();
      if (now !== null && now !== before) return;
      if (Date.now() > until) throw new Error(`the request of ${variant} for ${asset} did not show in ${REQUEST_SEEN_MS / 1000} s; its start: ${join(settings.logDir, 'requests.out')}`);
      await delay(REQUEST_POLL_MS);
    }
  }

  async function remove(dataset: string, ask: TextureRemoveAsk): Promise<TexturesBody> {
    const asset = text(ask.asset, 'asset');
    await command('remove', dataset, ['--asset', asset, '--variant', text(ask.variant, 'variant')]);
    return states(dataset, [asset]);
  }

  /** Only a request.log in the store: the index names it, and nothing else is served by this route. */
  function requestLog(dataset: string, asset: string, recipe: string): string | null {
    const log = index.textures(dataset, [asset]).get(asset)?.requests[recipe]?.log ?? null;
    if (log === null || basename(log) !== 'request.log' || !existsSync(log)) return null;
    // Both sides resolved: the store may be named through a link.
    return realpathSync(log).startsWith(join(realpathSync(settings.storeDir), sep)) ? log : null;
  }

  function skinWords(ask: SkinAsk): string[] {
    const name = text(ask.name, 'name');
    switch (ask.action) {
      case 'copy':
        return ['copy', '--name', name, '--from', text(ask.from, 'from')];
      case 'rename':
        return ['rename', '--name', name, '--new', text(ask.new, 'new')];
      case 'delete':
        return ['delete', '--name', name];
      case 'set':
        return ['set', '--name', name, '--asset', text(ask.asset, 'asset'), ...(ask.variant === null ? ['--clear'] : ['--variant', text(ask.variant, 'variant')])];
      case 'upscale':
        if (!Number.isInteger(ask.size)) throw new HttpError(400, { error: 'an upscale names a whole size' });
        return ['upscale', '--name', name, '--from', text(ask.from, 'from'), '--model', text(ask.model, 'model'), '--size', String(ask.size), '--defer'];
      default:
        throw new HttpError(400, { error: 'action is copy, rename, delete, set or upscale' });
    }
  }

  async function skin(dataset: string, ask: SkinAsk): Promise<SkinBody> {
    const name = text(ask.owner, 'owner');
    const [action = '', ...words] = skinWords(ask);
    const answer = await command('skin', dataset, [action, '--owner', name, ...words]);
    let upscaled: SkinUpscaled | null = null;
    if (ask.action === 'upscale') {
      const requests = asObject(answer['requests']) as Record<string, string>;
      if (Object.keys(requests).length) await ensureWorker(dataset);
      // Started side by side; the reply waits until the index shows each (as the request route does).
      const started = await Promise.all(
        Object.entries(requests)
          .sort()
          .map(([asset, variant]) => startSeen(dataset, asset, variant).then(
            () => null,
            (error: unknown) => ({ asset, variant, error: messageOf(error) }),
          )),
      );
      const failed: SkinUpscaled['failed'] = started.filter((one): one is SkinUpscaled['failed'][number] => one !== null);
      upscaled = { requests, kept: asObject(answer['kept']) as Record<string, string>, failed };
    }
    return { ...owner(dataset, name), upscaled };
  }

  async function bake(dataset: string, ask: BakeAsk): Promise<BakeBody> {
    if ('owner' in ask) {
      await command('bake', dataset, ['--owner', text(ask.owner, 'owner'), '--skin', text(ask.skin, 'skin')]);
      return owner(dataset, ask.owner);
    }
    await command('bake', dataset, ['--asset', text(ask.asset, 'asset'), '--variant', text(ask.variant, 'variant')]);
    return states(dataset, [ask.asset]);
  }

  async function unbake(dataset: string, ask: UnbakeAsk): Promise<BakeBody> {
    if ('owner' in ask) {
      await command('unbake', dataset, ['--owner', text(ask.owner, 'owner')]);
      return owner(dataset, ask.owner);
    }
    await command('unbake', dataset, ['--asset', text(ask.asset, 'asset')]);
    return states(dataset, [ask.asset]);
  }

  const edits = editSessions({
    root: join(settings.storeDir, settings.game, 'edits'),
    index,
    command,
    start: (name, dataset, words) => start(name, dataset, words, 'transfers.out'),
    judge: (dataset, asset) => judge(dataset, [asset]).then(() => undefined),
  });

  return { states, owner, lookup, listKind, origin: (dataset, asset) => index.origin(dataset, asset), file, indexed: (dataset) => index.head(dataset) !== null, sync, judge, request, remove, requestLog, skin, bake, unbake, edits };
}
