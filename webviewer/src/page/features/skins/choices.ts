// What the upscale dialog offers (SPEC-VIEWER 17.5), worked out from the
// states the pipeline wrote. The pipeline decides every refusal; this file
// only reads them (R-VIEW-116, 117).

import { asksFrom, isUsable, ORIGINAL, type OwnerState, type TexturesHead, type TextureState } from '../../../shared/textures';
import { shownVariant } from '../../core/skins';

/** The model of a texture without a colour plane (R-HD-122). */
export const DATA_MODEL = 'fast';

export interface Choice {
  value: string;
  label: string;
  /** Why it cannot be chosen; empty: it can. */
  reason: string;
}

/** The inputs of one texture: the original first, then each variant that may be shown. */
export const inputsOf = (state: TextureState): string[] => [ORIGINAL, ...state.variants.filter(isUsable).map((variant) => variant.id)];

/** The models from one input, each with why the state refuses it. */
export function modelChoices(state: TextureState, head: TexturesHead, input: string): Choice[] {
  const offered = asksFrom(state, input);
  return head.models.map((model) => {
    const found = offered[model.id];
    const reason = !state.judged ? 'not read yet' : state.reason || (found ? found.reason : `not offered from ${input}`);
    return { value: model.id, label: model.title, reason };
  });
}

/** The sizes of one model from one input: the dataset's sizes, then any smaller own size; each with why it cannot be reached. */
export function sizeChoices(state: TextureState, head: TexturesHead, input: string, model: string): Choice[] {
  const sizes = asksFrom(state, input)[model]?.sizes ?? {};
  const all = [...new Set([...head.sizes, ...Object.keys(sizes).map(Number)])].sort((a, b) => a - b);
  return all.map((size) => {
    const why = sizes[String(size)];
    return { value: String(size), label: String(size), reason: why === undefined ? 'cannot be reached' : why };
  });
}

/** What an owner upscale would do with a model and a size, read from each texture's state. */
export interface OwnerPlan {
  /** Data textures that get `fast` in place of the model. */
  data: number;
  /** Textures that cannot reach the size, or cannot be upscaled: they keep what the skin shows. */
  kept: string[];
  /** Textures that get a request. */
  asked: number;
}

export function ownerPlan(owner: OwnerState, skin: string, states: ReadonlyMap<string, TextureState>, model: string, size: number): OwnerPlan {
  const plan: OwnerPlan = { data: 0, kept: [], asked: 0 };
  for (const asset of owner.textures) {
    const state = states.get(asset);
    if (!state || !state.judged || state.reason) {
      plan.kept.push(asset);
      continue;
    }
    const chosen = state.colour ? model : DATA_MODEL;
    const offered = asksFrom(state, shownVariant(owner, skin, asset))[chosen];
    if (!offered || offered.reason || offered.sizes[String(size)] !== '') {
      plan.kept.push(asset);
      continue;
    }
    if (!state.colour && model !== DATA_MODEL) plan.data += 1;
    plan.asked += 1;
  }
  return plan;
}
