// SC2 in the texture window (core/texturewindow.ts), with the texture
// service (SPEC-VIEWER 17). A double-click on a unit or doodad (a gallery
// row, an instance row, or an instance in the view) opens it on every
// texture its model file names (originals.ts); on a ground texture, on its
// colour file and its normal map. The page reads their results and picks
// from the service.

import type { Item } from '../../../../page/core/types';
import type { GameContext } from '../../../../page/core/context';
import { SC2 } from '../game';
import { TERRAIN, terrainRecord } from '../records';
import { decodeAll, originals } from './originals';

export interface Sc2Textures {
  /** The window on a record of the gallery: its record's model file (an SC2 doodad's first variation), or a ground texture's files. */
  openTexturesFor(category: string, id: string): Promise<void>;
  /** The window on an instance of the scene: the model file it shows. */
  openTexturesOf(item: Item): Promise<void>;
}

export function installTextures(context: GameContext, ownerOf: (item: Item) => string | null): Sc2Textures {
  const { api, textureWindow } = context;

  /**
   * Open the window on the textures of `user` (a unit, doodad or ground
   * texture id, or a model file's name), called `name`, in `dataset`.
   */
  /** `owner`: the texture owner whose skins Save to Skin… changes (R-VIEW-133); `item`: the instance, if any. */
  /** `skin`: the skin the instance shows, for the title; null: none. */
  function openTextures(user: string, name: string, file: string, dataset: string, read: (urls: string[]) => ReturnType<typeof originals>, owner: string | null, item: number | null = null, skin: string | null = null): Promise<void> {
    return textureWindow.open({ user, name, file, dataset, game: SC2, service: true, read, owner, item, skin });
  }

  async function openTexturesFor(category: string, id: string): Promise<void> {
    const dataset = api.requireDataset(api.currentDataset(SC2), SC2);
    const record = await api.record(category, id, dataset, SC2);
    if (category === TERRAIN) {
      const ground = terrainRecord(record);
      const files = ground.normal === null ? [ground.file] : [ground.file, ground.normal];
      // A ground texture has no owner: it is baked on its own (R-HD-145).
      return openTextures(id, record.name, ground.file, dataset, (urls) => decodeAll(context, files, dataset, urls), null);
    }
    if (!record.file) throw new Error(`${record.name} has no model file`);
    const owner = category === 'units' ? `unit:${id}` : category === 'doodads' ? `actor:${id}` : null;
    return openTextures(id, record.name, record.file, dataset, (urls) => originals(context, record.file, dataset, urls), owner);
  }

  /** A bare model file goes by its file name. */
  function openTexturesOf(item: Item): Promise<void> {
    const fileName = item.path.split('\\').pop() ?? item.path;
    const record = item.source ? item.source.record : null;
    const owner = ownerOf(item);
    return openTextures(record ? record.id : fileName, record ? record.name : fileName, item.path, item.dataset, (urls) => originals(context, item.path, item.dataset, urls), owner, item.id, owner === null ? null : item.skin);
  }

  return { openTexturesFor, openTexturesOf };
}
