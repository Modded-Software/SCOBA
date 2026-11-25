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
  /** The game offers a texture service (SPEC-VIEWER 17, R-VIEW-100). */
  textures: boolean;
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
  /** 'records': rows are RecordSummary, previewed and placed by record; 'files': rows are model file paths, added as bare files. */
  rows: 'records' | 'files';
  /** Its rows and preview show the record's icon box. */
  icons: boolean;
}

/** A row of GET /api/<game>/records/<category> for a 'records' category. A game may add its own fields. */
export interface RecordSummary {
  id: string;
  name: string;
  /** The grey line under the name. */
  sub: string;
  icon: string | null;
  /** False: "add all" leaves it out (an SC2 skybox unit). */
  placeable: boolean;
  /** The word for it when not placeable: "skybox unit". */
  notPlaceableAs: string | null;
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
  // `v` is the dataset's signature, so a reloaded dataset is fetched anew; a dataset with no signature has no `v`.
  file: (game: GameId, dataset: DatasetId, path: string, version: string | null): string => `/api/${game}/file?${new URLSearchParams({ dataset, path, ...(version === null ? {} : { v: version }) })}`,
  asset: (game: GameId, dataset: DatasetId, kind: AssetKind, ref: string, version: string | null): string => `/api/${game}/asset?${new URLSearchParams({ dataset, kind, ref, ...(version === null ? {} : { v: version }) })}`,
  icon: (game: GameId, dataset: DatasetId, name: string): string => `/api/${game}/icon/${name}?${new URLSearchParams({ dataset })}`,
  backdrops: (game: GameId, query: Record<string, string>): string => `/api/${game}/backdrops?${new URLSearchParams(query)}`,
  extension: (game: GameId, name: string): string => `/api/${game}/x/${name}`,
};
