// The texture service as the texture page reads it (SPEC-VIEWER 17.2): the
// states of the textures shown, by asset, and what holds for all of them.
// main.ts decides when to read and what a reply means for the page; this
// makes the calls and holds what they answered.

import { textureRoutes, type TexturesBody, type TexturesHead, type TextureState } from '../../shared/textures';

/** The states by asset, from the service. main.ts clears them for a new show request. */
export const states = new Map<string, TextureState>();
let head: TexturesHead = { sizes: [], models: [], limits: [] };

/** What holds for every texture, as the last reply said: the sizes, the models, the limits. */
export const headOf = (): TexturesHead => head;

/** POST to a texture route. A refusal throws with the service's reason. */
export async function call(url: string, body: unknown): Promise<TexturesBody> {
  const response = await fetch(url, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
  const answer: unknown = await response.json();
  if (!response.ok) throw new Error(typeof answer === 'object' && answer !== null && typeof Reflect.get(answer, 'error') === 'string' ? String(Reflect.get(answer, 'error')) : `${response.status}`);
  return answer as TexturesBody;
}

/** GET the states of these assets. A refusal throws with the service's reason. */
export async function readStates(game: string, dataset: string, assets: readonly string[]): Promise<TexturesBody> {
  const response = await fetch(textureRoutes.states(game, dataset, [...assets]));
  const answer: unknown = await response.json();
  if (!response.ok) throw new Error(String(Reflect.get(Object(answer), 'error') ?? response.status));
  return answer as TexturesBody;
}

const variantsKey = (state: TextureState): string => state.variants.map((variant) => `${variant.id}:${variant.sha256}`).join() + `|${state.bake ?? ''}`;

/** Take a reply of the service; true when a texture shown before has other variants or another bake. */
export function take(body: TexturesBody): boolean {
  let changed = false;
  head = { sizes: body.sizes, models: body.models, limits: body.limits };
  for (const state of body.textures) {
    const before = states.get(state.asset);
    if (before && variantsKey(before) !== variantsKey(state)) changed = true;
    states.set(state.asset, state);
  }
  return changed;
}

/** A request of a texture shown is queued or being made: the page polls. */
export const busy = (): boolean => [...states.values()].some((state) => Object.values(state.requests).some((request) => request.state !== 'failed'));
