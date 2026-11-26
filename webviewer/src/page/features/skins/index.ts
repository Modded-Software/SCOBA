// The windows that change skins (SPEC-VIEWER 17.3 to 17.6): the upscale
// dialog and the dialogs that ask before a skin changes (actions.ts). The
// instance menu reaches them through core/skins.ts; the texture window
// through the events "texture-upscale", "texture-save" and "texture-remove". Edit Skin and
// Add New Skin… open the texture window on the instance (R-VIEW-132).
// Ctrl+. held shows Original on the selected instances (R-VIEW-148).

import { skinLabel } from '../../../shared/textures';
import type { Feature } from '../../core/context';
import { bindingText, keyMatches, releasesKey, resolveInput, type KeyBinding } from '../../core/input';
import { settings } from '../../core/settings';
import type { Item } from '../../core/types';
import { createSkinActions } from './actions';
import { createUpscale } from './upscale';

export const skinsFeature: Feature = {
  id: 'skins',
  install(context) {
    const { skins, status, events, games, testApi, selection, scene, store } = context;
    const upscale = createUpscale(context);
    const actions = createSkinActions(context);
    /** The instance shows the skin first when it can. */
    async function edit(item: Item, skin: string): Promise<void> {
      if (skin !== item.skin && skins.choices(item).includes(skin)) await skins.set(item, skin);
      await games.partsOf(item.game).openItem(item);
    }
    /** Make the next New Skin N from what the instance's skin names, show it on the instance, then open the texture window (R-HD-137). */
    async function create(item: Item): Promise<void> {
      const from = item.skin;
      const made = await actions.create(item);
      // Set at once: the change read the owner again, so the item can show it (as the upscale does).
      await skins.set(item, made);
      status.setStatus(`${made} made from ${skinLabel(from)}`);
      await games.partsOf(item.game).openItem(item);
    }
    skins.setTools({
      edit: (item, skin) => edit(item, skin).catch(status.reportFailure),
      create: (item) => create(item).catch(status.reportFailure),
      upscale: (item) => upscale.openOwner(item).catch(status.reportFailure),
      // The trash of the skin list: a skin is deleted after the question (R-VIEW-126).
      remove: (item, skin) => actions.remove(item, skin),
    });
    events.on('texture-upscale', ({ game, dataset, asset }) => upscale.openTexture(game, dataset, asset).catch(status.reportFailure));
    events.on('texture-save', ({ done, ...ask }) => {
      actions.saveTo(ask).then(
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
    events.on('texture-rename', ({ item: id, done }) => {
      const item = scene.items.find((one) => one.id === id);
      if (!item) {
        done(new Error('the instance of the texture window is gone'));
        return;
      }
      const from = item.skin;
      actions.rename(item).then(
        (to) => {
          if (to !== null) status.setStatus(`skin ${from} renamed to ${to}`);
          done(to);
        },
        (failure: unknown) => {
          done(failure instanceof Error ? failure : new Error(String(failure)));
          status.reportFailure(failure);
        },
      );
    });
    events.on('texture-remove', ({ game, dataset, asset, variant, owner, done }) => {
      actions.removeVariant(game, dataset, asset, variant, owner).then(
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
    // The key is the input map's "original" (core/input.ts, R-VIEW-154).
    const originalKey = (): KeyBinding => resolveInput(store.read(settings.input)).keys.original;
    window.addEventListener('keydown', (e) => {
      const key = originalKey();
      if (!keyMatches(key, e)) return;
      // A field being edited keeps the key (R-VIEW-59).
      if (selection.editingText(e.target)) return;
      e.preventDefault();
      if (e.repeat || held.length) return;
      const ids = new Set(selection.selectedIds());
      held = scene.items.filter((item) => ids.has(item.id));
      if (!held.length) {
        status.setStatus(`${bindingText(key)}: select an instance first`);
        return;
      }
      skins.peek(held, true).catch(status.reportFailure);
    });
    window.addEventListener('keyup', (e) => {
      if (releasesKey(originalKey(), e)) release();
    });
    window.addEventListener('blur', release);
    testApi.viewer({ upscaleDialog: upscale.state, skinDialog: actions.state, skinPeek: () => held.map((item) => item.id) });
  },
};
