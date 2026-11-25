// What SC2 adds to the shared page (SPEC-VIEWER 6.6): the texture window,
// the name of a texture for the texture service, the blue grid glow, and
// its part of the test API. The gallery is core's, built from the
// categories the server sends. main.ts installs this with the same context
// a feature gets.

import { noItemOptions, type GameContext, type GameParts } from '../../../page/core/context';
import type { Item } from '../../../page/core/types';
import { sc2SceneApi } from './api';
import { installTextures } from './textures';
import { assetOf } from './textures/originals';

/**
 * A texture this large on a side is an HD one: the grid glows blue around
 * an instance that shows one. Stock unit textures are mostly 1024. A small
 * shared texture (a decal, a reflection map) does not make a model HD
 * (operator 2026-11-22).
 */
const HD_SIZE = 2048;

/**
 * The texture owner of an instance (SPEC-VIEWER-SC2 8.2): a unit is its
 * unit, a doodad its actor, a bare model file the file. A model file with
 * variations is owned by its base path, so a variation file has no owner.
 */
function textureOwner(item: Item): string | null {
  if (item.source?.category === 'units') return `unit:${item.source.record.id}`;
  if (item.source?.category === 'doodads') return `actor:${item.source.record.id}`;
  return item.source === null || item.source.category === 'models' ? `model:${assetOf(item.path)}` : null;
}

export function installSc2Page(context: GameContext): GameParts {
  const textures = installTextures(context, textureOwner);
  // The SC2 adds (unit, doodad, variation), for the tests.
  context.testApi.viewer(sc2SceneApi(context.scene));
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
