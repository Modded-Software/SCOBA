// What a game gives the server (SPEC-VIEWER section 7). Core owns the
// HTTP side; a backend answers in values, and throws HttpError for a
// reply that is not a success.

import type { AssetKind, CategoryInfo, DatasetId, CategoryId, GameId } from '../../shared/protocol';
import type { Page } from '../../shared/records';
import type { Route } from './http';

/** An answer that is not a success: the status code and the ApiError body. */
export class HttpError extends Error {
  constructor(
    readonly status: number,
    readonly body: { error: string } & Record<string, unknown>,
  ) {
    super(body.error);
  }
}

/** Thrown by a game's start when its data is not on the machine (R-VIEW-8). */
export class GameUnavailable extends Error {}

/** A game that could not start: listed with `available: false`, its routes answer 503. */
export interface UnavailableGame {
  readonly id: GameId;
  readonly label: string;
  readonly tab: string;
  readonly reason: string;
}

export interface ListQuery {
  q: string;
  offset: number;
  limit: number;
  /** The other query parameters. A filter that is present with an empty value is a value of its own. */
  filters: Record<string, string>;
}

export interface GameBackend {
  readonly id: GameId;
  readonly label: string;
  readonly tab: string;
  /** The dataset a game shows first. */
  readonly defaultDataset: DatasetId;
  hasDataset(dataset: DatasetId): boolean;
  /** GET /api/<game>/datasets: { default, datasets, problems }. */
  datasets(): Promise<unknown>;
  /** POST /api/<game>/datasets/<id>/reload, for a known dataset. */
  reload(dataset: DatasetId): Promise<unknown>;
  categories(dataset: DatasetId): CategoryInfo[];
  /** The game's own counts. */
  summary(dataset: DatasetId): Record<string, unknown>;
  /** One page of a category; HttpError 404 for an unknown category. */
  list(dataset: DatasetId, category: CategoryId, query: ListQuery): Page<unknown>;
  /** One record; HttpError 404 for an unknown category or id. */
  record(dataset: DatasetId, category: CategoryId, id: string): unknown;
  /** A servable file on disk, or null. */
  file(dataset: DatasetId, path: string): Promise<string | null>;
  /** A reference a model uses, resolved for the dataset, on disk; or null. */
  asset(dataset: DatasetId, kind: AssetKind, reference: string): Promise<string | null>;
  /** An icon on disk, or null: only names the dataset's index lists. */
  icon(dataset: DatasetId, name: string): string | null;
  backdrops(query: ListQuery): Page<unknown>;
  /** Routes below /api/<game>/x/<name>; the route they get is the part after /x/. */
  readonly extensions: Readonly<Record<string, Route>>;
}
