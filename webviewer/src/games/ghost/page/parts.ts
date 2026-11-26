// What Ghost adds to the shared page (SPEC-VIEWER 6.6, SPEC-VIEWER-GHOST
// 8): its textures in the shared texture window (textures.ts), opened by a
// double-click; the name of a texture and of an owner for the texture
// service (R-VIEW-152); the blue grid glow, as SC2's. No item options.
// main.ts installs this.

import { noItemOptions, type GameContext, type GameParts } from '../../../page/core/context';
import type { Item } from '../../../page/core/types';
import { assetOf, installGhostTextures } from './textures';

/** A texture this large on a side is an HD one: the grid glows blue around an instance that shows one (as SC2). */
const HD_SIZE = 2048;

/** The texture owner of an instance: an actor row its template, a model row or a bare file its model file. */
export function textureOwner(item: Item): string | null {
  if (item.source?.category === 'actors') return `actor:${item.source.record.id}`;
  return item.source === null || item.source.category === 'models' ? `model:${assetOf(item.path)}` : null;
}

export function installGhostPage(context: GameContext): GameParts {
  const textures = installGhostTextures(context, textureOwner);
  return {
    glowOf: (item) => (item.largestTexture >= HD_SIZE ? 1 : 0),
    itemFacts: (item) => ({ blueGlow: item.largestTexture >= HD_SIZE }),
    itemOptions: noItemOptions,
    textureAsset: assetOf,
    textureOwner,
    openItem: textures.openTexturesOf,
    openRecord: textures.openTexturesFor,
  };
}
