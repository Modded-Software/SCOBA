// What the server answers, as the page reads it. The server builds these
// from the catalogs (tools/build_catalog.py, tools/build_doodads.py) in
// src/games/sc2/server. Step 5 moves the unit and doodad records to games/sc2/shared.

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

/** What the unit and doodad data share: scale, speed and look. */
interface PlacedData {
  id: string;
  name: string;
  inMap: boolean;
  actorScale: Vec3;
  modelScaleMin: Vec3;
  modelScaleMax: Vec3;
  eventScale: Vec3;
  animSpeed: number;
  timeScale: number;
  radius: number;
  tint: Vec3 | null;
  /** The servable model file (a doodad's first variation). */
  file: string;
  /** The dataset the record was read from (the record route adds it). */
  dataset: string;
}

/** A unit record, /api/sc2/record/units. */
export interface UnitRecord extends PlacedData {
  doodad?: undefined;
  race: string;
  kind: string;
  family: string;
  icon: string | null;
  portrait: string | null;
  speed: number;
  walkAnimMoveSpeed: number | null;
  height: number;
  /** Its model is a skybox (games/sc2/server/skyboxes.ts). */
  skybox?: boolean;
}

/** A doodad record, /api/sc2/record/doodads. */
export interface DoodadRecord extends PlacedData {
  doodad: true;
  type: string;
  tilesets: string[];
  files: string[];
  variations: number;
  editorOnly: boolean;
  editorModel: string | null;
  /** RandomScaleRange: [low, high], or null for none. */
  scaleRange: [number, number] | null;
  autoRotate: boolean;
  footprint: string | null;
  height?: undefined;
}

export type PlacedRecord = UnitRecord | DoodadRecord;

/** A row of /api/sc2/records/units. */
export interface UnitSummary {
  id: string;
  name: string;
  race: string;
  kind: string;
  family: string;
  icon: string | null;
  inMap: boolean;
  skybox?: boolean;
}

/** A row of /api/sc2/records/doodads. */
export interface DoodadSummary {
  id: string;
  name: string;
  type: string;
  inMap: boolean;
  variations: number;
  editorOnly: boolean;
}

/** What the filters offer; the page builds it from /api/<game>/categories. */
export interface Facets {
  races: string[];
  kinds: string[];
  families: string[];
  doodadTypes: string[];
  tilesets: string[];
}

/** A row of /api/sc2/backdrops. */
export interface SkyboxInfo {
  id: string;
  name: string;
  file: string;
}

/** /api/sc2/x/textures: whether the texture viewer is built. */
export interface TexturesBody {
  built: boolean;
  build: string;
}

/** /api/sc2/x/hd-textures: in-model paths of the textures with an upscaled file. */
export interface HdTexturesBody {
  assets: string[];
}

/** An error answer. */
export interface ApiError {
  error?: string;
}
