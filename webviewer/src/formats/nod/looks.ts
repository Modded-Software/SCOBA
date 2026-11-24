// What a nod model draws with, per mesh group, for the texture window
// (SPEC-VIEWER-GHOST 8): the material, its shader, how the group is drawn
// or why not, and its texture file.

import type { ViewerModel } from '../../page/core/plugin';
import { NodView } from './adapter';

export interface NodLook {
  group: number;
  material: string;
  shader: string;
  /** solid, cutout, add, blend; null when the group is not drawn. */
  kind: string | null;
  /** Why it is not drawn, when it is named (materials.ts); null when drawn or left out unnamed. */
  why: string | null;
  twoSided: boolean;
  triangles: number;
  /** The material's texture file, relative to the build, drawn or not; null when it has none. */
  texture: string | null;
}

/** The looks of a loaded nod model, in group order; an error for a model of another format. */
export function nodLooks(model: ViewerModel): NodLook[] {
  if (!(model instanceof NodView)) throw new Error(`not a nod model: ${model.format}`);
  return model.nod.groups.map((g) => ({
    group: g.index,
    material: g.material,
    shader: g.look.shader,
    kind: g.look.kind,
    why: g.look.why,
    twoSided: g.look.twoSided,
    triangles: g.indexCount / 3,
    texture: g.look.textureFile,
  }));
}
