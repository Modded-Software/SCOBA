// What the upscale dialog offers (SPEC-VIEWER 17.5), worked out from the
// states the pipeline wrote. The pipeline decides every refusal; this file
// only reads them (R-VIEW-116, 117).

import { asksFrom, isUsable, namedIn, ORIGINAL, type OwnerState, type TexturesHead, type TextureState } from '../../../shared/textures';

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

/** The factors of one model from one input, each with the side it gives and why it cannot be asked for. */
export function factorChoices(state: TextureState, head: TexturesHead, input: string, model: string): Choice[] {
  const factors = asksFrom(state, input)[model]?.factors ?? {};
  return head.factors.map((factor) => {
    const found = factors[String(factor)];
    return { value: String(factor), label: found ? `${factor}x: ${found.size}` : `${factor}x`, reason: found ? found.reason : 'not offered' };
  });
}

/** The factors of an owner upscale: each the dataset offers. Each texture's side shows in the plan's lines. */
export const ownerFactorChoices = (head: TexturesHead): Choice[] => head.factors.map((factor) => ({ value: String(factor), label: `${factor}x`, reason: '' }));

/** What an owner upscale would do with a model and a factor, read from each texture's state. */
export interface OwnerPlan {
  /** Data textures that get `fast` in place of the model. */
  data: number;
  /** Textures that cannot have the factor, or cannot be upscaled: they keep what the skin shows, each with why. */
  kept: { asset: string; reason: string }[];
  /** Textures that get a request, each with the side it gets. */
  asked: { asset: string; size: number }[];
}

export function ownerPlan(owner: OwnerState, skin: string, states: ReadonlyMap<string, TextureState>, model: string, factor: number): OwnerPlan {
  const plan: OwnerPlan = { data: 0, kept: [], asked: [] };
  for (const asset of owner.textures) {
    const state = states.get(asset);
    if (!state || !state.judged || state.reason) {
      plan.kept.push({ asset, reason: !state ? 'no state' : state.reason || 'not read yet' });
      continue;
    }
    const chosen = state.colour ? model : DATA_MODEL;
    const offered = asksFrom(state, namedIn(owner, skin, asset))[chosen];
    const found = offered?.factors[String(factor)];
    if (!offered || offered.reason || !found || found.reason) {
      plan.kept.push({ asset, reason: offered?.reason || found?.reason || `${chosen} is not offered` });
      continue;
    }
    if (!state.colour && model !== DATA_MODEL) plan.data += 1;
    plan.asked.push({ asset, size: found.size });
  }
  return plan;
}
