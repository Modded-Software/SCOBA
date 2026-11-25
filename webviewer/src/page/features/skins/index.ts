// The windows that change skins (SPEC-VIEWER 17.3 to 17.6): the upscale
// dialog, the skin editor, and the dialogs that ask before a skin changes
// (actions.ts). The instance menu reaches them through core/skins.ts; the
// texture window through the events "texture-upscale" and "texture-save".

import { NEW_SKIN, skinLabel } from '../../../shared/textures';
import type { Feature } from '../../core/context';
import { createSkinActions } from './actions';
import { createEditor } from './editor';
import { createUpscale } from './upscale';

export const skinsFeature: Feature = {
  id: 'skins',
  install(context) {
    const { skins, status, events, testApi } = context;
    const upscale = createUpscale(context);
    const actions = createSkinActions(context);
    const editor = createEditor(context, actions, upscale.openTexture);
    skins.setTools({
      edit: (item, skin) => editor.open(item, skin).catch(status.reportFailure),
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
    testApi.viewer({ upscaleDialog: upscale.state, skinEditor: editor.state, skinDialog: actions.state });
  },
};
