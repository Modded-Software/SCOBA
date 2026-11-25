// Edit sessions (SPEC-PHOTOCRAFT sections 7 and 8): what the server says of
// one, what the page asks, and the routes. A session is a folder of files in
// the texture store; the pipeline writes it (scripts/hdtex/core/edits.py).

import type { DatasetId, GameId } from './protocol';
import type { TextureState } from './textures';

/** A session id: 16 hex digits. */
export const SESSION_RULE = /^[0-9a-f]{16}$/;
/** The reply header of the scratch route that names the document. */
export const SCRATCH_NAME_HEADER = 'x-photocraft-name';
/** The name the editor gets for a scratch. A save under a name ending in `.psd` goes back to the session. */
export const SCRATCH_NAME = 'scratch.psd';
/** The largest scratch the server takes: 1 GiB. */
export const SCRATCH_LIMIT = 1024 * 1024 * 1024;

/** A session's state, from its files (SPEC-PHOTOCRAFT 8). */
export type EditStateName = 'stale' | 'unchanged' | 'transferred' | 'edited';

/** One edit session. */
export interface EditSession {
  session: string;
  asset: string;
  /** The variant that was opened: `original`, or an id. */
  variant: string;
  /** Width and height. */
  size: [number, number];
  /** The plane names, in the order of the scratch's groups, top first. */
  planes: string[];
  state: EditStateName;
  /** Why it is stale, or why the scratch cannot give every plane; empty otherwise. */
  reason: string;
  /** The planes whose rendered pixels are not their base's. */
  changed: string[];
  /** The top-level layers that are no plane's group: left out of every plane. */
  leftOut: string[];
  /** By plane: the pixel hash of the last check. An offer is told from another by these. */
  rendered: Record<string, string>;
  /** The scratch is not the file the last check read, and a check runs. The state is that of the last check. */
  checking: boolean;
  /** Why the check of the scratch as it is could not run; empty: it ran, or runs. */
  checkError: string;
  /** The variants its transfers made, oldest first. */
  transfers: string[];
  /** The scratch on disk, for another program. */
  scratch: string;
  /** When the scratch last changed, in ms since 1970; null: it is not there. */
  scratchChanged: number | null;
}

/** GET /api/<game>/textures/edit. */
export interface EditsBody {
  sessions: EditSession[];
}

/** POST .../edit/open, GET .../edit/<session>. */
export interface EditBody {
  session: EditSession;
}

/** POST .../edit/open: the texture and the variant to edit. */
export interface EditOpenAsk {
  asset: string;
  variant: string;
}

/** PUT .../edit/<session>/scratch. */
export interface EditWrittenBody {
  bytes: number;
}

/** POST .../edit/<session>/transfer: the session, and the texture with the request or the new variant. */
export interface EditTransferBody {
  session: EditSession;
  texture: TextureState | null;
}

/** POST .../edit/<session>/discard. */
export interface EditDiscardBody {
  session: string;
  discarded: true;
}

const base = (game: GameId): string => `/api/${game}/textures/edit`;
const query = (dataset: DatasetId): string => `?${new URLSearchParams({ dataset })}`;

/** The edit routes, as the page builds them. `host` is what the editor's bridge gets: it adds `/scratch`. */
export const editRoutes = {
  list: (game: GameId, dataset: DatasetId): string => `${base(game)}${query(dataset)}`,
  open: (game: GameId, dataset: DatasetId): string => `${base(game)}/open${query(dataset)}`,
  one: (game: GameId, dataset: DatasetId, session: string): string => `${base(game)}/${session}${query(dataset)}`,
  host: (game: GameId, session: string): string => `${base(game)}/${session}`,
  picture: (game: GameId, session: string, kind: 'base' | 'rendered', plane: string, version: string): string => `${base(game)}/${session}/${kind}/${plane}?${new URLSearchParams({ v: version })}`,
  transfer: (game: GameId, dataset: DatasetId, session: string): string => `${base(game)}/${session}/transfer${query(dataset)}`,
  discard: (game: GameId, dataset: DatasetId, session: string): string => `${base(game)}/${session}/discard${query(dataset)}`,
};
