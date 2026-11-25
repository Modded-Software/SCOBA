// The windows that change skins (SPEC-VIEWER 17.3 to 17.6): the upscale
// dialog and the dialogs that ask before a skin changes (actions.ts). The
// instance menu reaches them through core/skins.ts; the texture window
// through the events "texture-upscale", "texture-save" and "texture-remove". Edit Skin and
// Add New Skin… open the texture window on the instance (R-VIEW-132).
// Ctrl+. held shows Original on the selected instances (R-VIEW-148).

import { NEW_SKIN, skinLabel } from '../../../shared/textures';
import type { Feature } from '../../core/context';
import type { Item } from '../../core/types';
import { createSkinActions } from './actions';
import { createUpscale } from './upscale';

export const skinsFeature: Feature = {
  id: 'skins',
  install(context) {
    const { skins, status, events, games, testApi, selection, scene } = context;
    const upscale = createUpscale(context);
    const actions = createSkinActions(context);
    /** The instance shows the skin first when it can; New Skin not made yet is made by Save to Skin…. */
    async function edit(item: Item, skin: string): Promise<void> {
      if (skin !== item.skin && skins.choices(item).includes(skin)) await skins.set(item, skin);
      await games.partsOf(item.game).openItem(item);
    }
    skins.setTools({
      edit: (item, skin) => edit(item, skin).catch(status.reportFailure),
      upscale: (item) => upscale.openOwner(item).catch(status.reportFailure),
      // The trash of the skin list: New Skin is discarded, a saved skin deleted; each asks first (R-VIEW-126).
      remove: (item, skin) => (skin === NEW_SKIN ? actions.discard(item) : actions.remove(item, skin)),
    });
    events.on('texture-upscale', ({ game, dataset, asset }) => upscale.openTexture(game, dataset, asset).catch(status.reportFailure));
    events.on('texture-save', ({ done, ...ask }) => {
      actions.saveTo({ ...ask, target: null }).then(
        (into) => {
          if (into !== null) status.setStatus(`${ask.picks.length} textures saved to ${skinLabel(into)}`);
          done(into);
        },
        (failure: unknown) => {
          done(null);
          status.reportFailure(failure);
        },
      );
    });
    events.on('texture-remove', ({ game, dataset, asset, variant, done }) => {
      actions.removeVariant(game, dataset, asset, variant).then(
        (removed) => {
          if (removed) status.setStatus(`variant ${variant} deleted`);
          done(removed);
        },
        (failure: unknown) => {
          done(failure instanceof Error ? failure : new Error(String(failure)));
          status.reportFailure(failure);
        },
      );
    });
    // Ctrl+. held: the selected instances show Original until "." or Ctrl is released, or the page loses the focus (R-VIEW-148).
    let held: Item[] = [];
    const release = (): void => {
      if (!held.length) return;
      const were = held;
      held = [];
      skins.peek(were, false).catch(status.reportFailure);
    };
    window.addEventListener('keydown', (e) => {
      if (!e.ctrlKey || e.altKey || e.metaKey || !(e.key === '.' || e.code === 'Period')) return;
      // A field being edited keeps the key (R-VIEW-59).
      if (selection.editingText(e.target)) return;
      e.preventDefault();
      if (e.repeat || held.length) return;
      const ids = new Set(selection.selectedIds());
      held = scene.items.filter((item) => ids.has(item.id));
      if (!held.length) {
        status.setStatus('Ctrl+.: select an instance first');
        return;
      }
      skins.peek(held, true).catch(status.reportFailure);
    });
    window.addEventListener('keyup', (e) => {
      if (e.key === 'Control' || e.key === '.' || e.code === 'Period') release();
    });
    window.addEventListener('blur', release);
    testApi.viewer({ upscaleDialog: upscale.state, skinDialog: actions.state, skinPeek: () => held.map((item) => item.id) });
  },
};
