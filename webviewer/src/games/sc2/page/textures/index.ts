// SC2 in the texture window (core/texturewindow.ts): the HD texture viewer
// page (scripts/hdtex/compare.html as built, with its HD pairs, served
// below /api/sc2/x/textures/). A double-click on a unit or doodad (a
// gallery row, an instance row, or an instance in the view) opens it on
// that unit's or doodad's textures:
// - the ones with an HD version, original beside upscaled (the page's own
//   entries, filtered by ?user=);
// - every other texture its model file names, the original alone (originals.ts).
// The viewer's "used by" chip drops the filter.

import type { Item } from '../../../../page/core/types';
import type { GameContext } from '../../../../page/core/context';
import type { TexturesBody } from '../../shared/records';
import { SC2 } from '../game';
import { originals } from './originals';

export interface Sc2Textures {
  /** The window on a record of the gallery: its record's model file (an SC2 doodad's first variation). */
  openTexturesFor(category: string, id: string): Promise<void>;
  /** The window on an instance of the scene: the model file it shows. */
  openTexturesOf(item: Item): Promise<void>;
}

export function installTextures(context: GameContext): Sc2Textures {
  const { api, textureWindow } = context;

  /**
   * Open the window on the textures of `user` (a unit or doodad id, or a
   * model file's name), called `name`, whose model file is `file` in `dataset`.
   */
  async function openTextures({ user, name, file, dataset }: { user: string; name: string; file: string; dataset: string }): Promise<void> {
    const built = await api.getJson<TexturesBody>(api.extensionUrl('textures', SC2));
    if (!built.built) throw new Error(`the texture viewer is not built; run: ${built.build}`);
    return textureWindow.open({ user, name, file, dataset, page: `${api.extensionUrl('textures', SC2)}/`, read: (urls) => originals(context, file, dataset, urls) });
  }

  async function openTexturesFor(category: string, id: string): Promise<void> {
    const dataset = api.requireDataset(api.currentDataset(SC2), SC2);
    const record = await api.record(category, id, dataset, SC2);
    if (!record.file) throw new Error(`${record.name} has no model file`);
    return openTextures({ user: id, name: record.name, file: record.file, dataset });
  }

  /** A bare model file goes by its file name. */
  function openTexturesOf(item: Item): Promise<void> {
    const fileName = item.path.split('\\').pop() ?? item.path;
    const record = item.source ? item.source.record : null;
    return openTextures({ user: record ? record.id : fileName, name: record ? record.name : fileName, file: item.path, dataset: item.dataset });
  }

  return { openTexturesFor, openTexturesOf };
}
