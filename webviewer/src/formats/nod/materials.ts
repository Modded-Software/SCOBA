// How a mesh group is drawn, from its material (SPEC-VIEWER-GHOST 4.4,
// the `shader` table). Whether it looks right is an operator check.

import type { NodMaterial } from './container';

/** solid: opaque, lit. cutout: opaque with an alpha cut. add: added, not lit. blend: blended, lit. */
export type DrawKind = 'solid' | 'cutout' | 'add' | 'blend';

/** `u_kind` of the fragment shader (public/shaders/nod.frag). */
export const KIND_CODE: Record<DrawKind, number> = { solid: 0, cutout: 1, add: 2, blend: 3 };

const SOLID = ['', 'default', 'normal', 'detail', 'glossenvmap', 'glossenvmapdetail', 'envmap', 'metalgloss', 'metalenvmap', 'bump', 'bumpenv', 'ghostsuit', 'cloak'];
const CUTOUT = ['masked', 'etchedmasked'];
const ADD = ['glow', 'add', 'fullbright', 'halo'];
const BLEND = ['alpha', 'alphablend', 'glass', 'etchedglass'];
/** Not drawn, as in the game [docs]; not named. */
const HIDDEN = ['sky', 'invis', 'video'];

export interface GroupLook {
  /** null: not drawn. */
  kind: DrawKind | null;
  /** The texture file, relative to the build; null when not drawn. */
  texture: string | null;
  /** Why it is not drawn, when it is named (R-VIEW-81); null otherwise. */
  undrawn: string | null;
  /** The `shader` value, lower case; '' when the material has none. */
  shader: string;
  /** `cull cull_off`: both sides drawn. Else back faces are culled. */
  twoSided: boolean;
}

/** The look of a group whose material is `name`; `material` is its export, undefined when the export has none. */
export function lookOf(name: string, material: NodMaterial | undefined): GroupLook {
  const named = (why: string, shader = ''): GroupLook => ({ kind: null, texture: null, undrawn: `${name}: ${why}`, shader, twoSided: false });
  if (!material) return named('no material in the export');
  if (material.step === 'none') return named('found by no step of the material lookup');
  const value = (key: string): string => (material.properties.find(([k]) => k.toLowerCase() === key)?.[1] ?? '').toLowerCase();
  const shader = value('shader');
  const twoSided = value('cull') === 'cull_off';
  if (shader.startsWith('constraint_') || HIDDEN.includes(shader)) return { kind: null, texture: null, undrawn: null, shader, twoSided };
  const kind: DrawKind | null = SOLID.includes(shader) ? 'solid' : CUTOUT.includes(shader) ? 'cutout' : ADD.includes(shader) ? 'add' : BLEND.includes(shader) ? 'blend' : null;
  if (kind === null) return named(`shader ${shader} is not drawn`, shader);
  const texture = material.textures['texture'];
  if (texture === undefined || texture === null) return named('its texture file is missing', shader);
  return { kind, texture, undrawn: null, shader, twoSided };
}
