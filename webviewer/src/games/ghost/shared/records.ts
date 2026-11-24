// What the Ghost backend answers, as the Ghost page reads it
// (SPEC-VIEWER-GHOST 5). The server builds these from the catalog that
// NODExport writes (src/games/ghost/server/catalog.ts).

/** One motion of a motion set whose clip is in 3D/Anims. */
export interface GhostMotion {
  name: string;
  /** The clip's file name on disk, in 3D/Anims. */
  clip: string;
  flags: string[];
}

/** What an actor and a model record share. */
interface GhostPlaced {
  id: string;
  name: string;
  sub: string;
  icon: null;
  placeable: true;
  notPlaceableAs: null;
  /** The servable model file: 3D/Models/<name on disk>. */
  file: string;
  /** The motion set file on disk, in 3D/Motions; null for none. */
  motionSet: string | null;
  motions: GhostMotion[];
  /** Clips the motion set names that are not in 3D/Anims. */
  missingClips: string[];
  /** The dataset the record was read from (the record route adds it). */
  dataset: string;
}

/** A template of Global.not, /api/ghost/record/actors. */
export interface ActorRecord extends GhostPlaced {
  category: 'actors';
  template: string;
  /** The model name as the template gives it. */
  model: string;
  /** Model scale (id 143); null when the template has none. */
  scale: number | null;
  /** Type (id 20); its names are not known (O-GHOST-7). */
  kind: number | null;
  script: string | null;
}

/** A model file of 3D/Models, /api/ghost/record/models. */
export interface ModelRecord extends GhostPlaced {
  category: 'models';
  materials: number;
  bones: number;
  groups: number;
  vertexTypes: number[];
  /** A vertex set has bones to animate (type 1, 2, 4 or 5). */
  skinned: boolean;
}

export type GhostRecord = ActorRecord | ModelRecord;
