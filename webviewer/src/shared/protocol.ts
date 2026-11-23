// The protocol of SPEC-VIEWER section 8: what both sides read and write.
// The routes are below /api/<game>/; the id rule is section 8's.

export type GameId = string;
export type DatasetId = string;
export type CategoryId = string;

/** Game, dataset, category and format ids: 1 to 40 of a-z, 0-9, "_", "-", not starting with "_" or "-". */
export const ID_RULE = /^[a-z0-9][a-z0-9_-]{0,39}$/;

/** `limit` of a list route: 1 to 500, 60 when absent. */
export const LIMIT = { standard: 60, max: 500 } as const;

export interface GameInfo {
  id: GameId;
  /** Full name. */
  label: string;
  /** Short text of the game tab. */
  tab: string;
  available: boolean;
  /** Why not, when not available. */
  reason: string | null;
}

/** GET /api/games. */
export interface GamesBody {
  default: GameId;
  games: GameInfo[];
}

/** GET /api/health: the games and whether each is available. No counts. */
export interface HealthBody {
  games: { id: GameId; available: boolean }[];
}

export interface FilterInfo {
  /** The query parameter. */
  id: string;
  label: string;
  kind: 'buttons' | 'select';
  values: { value: string; label: string }[];
}

/** GET /api/<game>/categories: one gallery tab each. */
export interface CategoryInfo {
  id: CategoryId;
  /** Tab text. */
  label: string;
  /** "unit": for counts and questions. */
  noun: string;
  filters: FilterInfo[];
  addAll: boolean;
}

export type AssetKind = 'model' | 'texture' | 'animation' | 'material';
export const ASSET_KINDS: readonly AssetKind[] = ['model', 'texture', 'animation', 'material'];

/** The routes, as the page builds them. Every route that reads a dataset names it. */
export const routes = {
  games: (): string => '/api/games',
  datasets: (game: GameId): string => `/api/${game}/datasets`,
  reload: (game: GameId, dataset: DatasetId): string => `/api/${game}/datasets/${dataset}/reload`,
  categories: (game: GameId, dataset: DatasetId): string => `/api/${game}/categories?${new URLSearchParams({ dataset })}`,
  summary: (game: GameId, dataset: DatasetId): string => `/api/${game}/summary?${new URLSearchParams({ dataset })}`,
  records: (game: GameId, category: CategoryId, dataset: DatasetId, query: Record<string, string>): string => `/api/${game}/records/${category}?${new URLSearchParams({ dataset, ...query })}`,
  record: (game: GameId, category: CategoryId, dataset: DatasetId, id: string): string => `/api/${game}/record/${category}?${new URLSearchParams({ dataset, id })}`,
  file: (game: GameId, dataset: DatasetId, path: string, version: string): string => `/api/${game}/file?${new URLSearchParams({ dataset, path, v: version })}`,
  asset: (game: GameId, dataset: DatasetId, kind: AssetKind, ref: string, version: string): string => `/api/${game}/asset?${new URLSearchParams({ dataset, kind, ref, v: version })}`,
  icon: (game: GameId, dataset: DatasetId, name: string): string => `/api/${game}/icon/${name}?${new URLSearchParams({ dataset })}`,
  backdrops: (game: GameId, query: Record<string, string>): string => `/api/${game}/backdrops?${new URLSearchParams(query)}`,
  extension: (game: GameId, name: string): string => `/api/${game}/x/${name}`,
};
