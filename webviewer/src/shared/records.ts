// What the server answers for every game, as the page reads it. A game's
// own records are in its shared folder (src/games/sc2/shared/records.ts).

export type Vec3 = [number, number, number];

/** One page of a list (SPEC-VIEWER section 5). */
export interface Page<T> {
  total: number;
  items: T[];
}

/** A dataset as /api/<game>/datasets lists it. */
export interface DatasetInfo {
  id: string;
  label: string;
  builtin: boolean;
  /** What is loaded. */
  signature: string | null;
  /** Its sources now. */
  current: string;
  /** They differ. */
  changed: boolean;
}

export interface DatasetsBody {
  default: string;
  datasets: DatasetInfo[];
  problems: { dir: string; reason: string }[];
}

/** A row of /api/<game>/backdrops: a model shown as the sky. */
export interface Backdrop {
  id: string;
  name: string;
  file: string;
  game: string;
  dataset: string;
}

/** An error answer. */
export interface ApiError {
  error?: string;
}
