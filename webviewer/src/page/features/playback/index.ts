// The play/pause key (R-VIEW-159). With instances selected it holds their
// animations at the frame they show; pressed again it lets them run on
// from there. The selection acts as one: while any selected instance
// plays, the key pauses them all; with all of them paused, it plays them
// all. With nothing selected it pauses nothing and the status line says
// to select first. A field being edited keeps its key (R-VIEW-59); else
// the key never reaches the browser. A key held down counts once.
// The pause itself is the scene's (core/scene.ts setPaused); an animation
// started after ends it.
// The key is the input map's `playPause` (core/input.ts, R-VIEW-154):
// Ctrl+E when nothing is stored.

import type { Feature } from '../../core/context';
import { bindingText, keyMatches, resolveInput } from '../../core/input';
import { settings } from '../../core/settings';

export const playbackFeature: Feature = {
  id: 'playback',
  install({ scene, selection, status, store }) {
    window.addEventListener('keydown', (e) => {
      const key = resolveInput(store.read(settings.input)).keys.playPause;
      if (!keyMatches(key, e)) return;
      if (selection.editingText(e.target)) return;
      e.preventDefault();
      if (e.repeat) return;
      const ids = selection.selectedIds();
      const chosen = scene.items.filter((item) => ids.includes(item.id));
      if (!chosen.length) {
        status.setStatus(`${bindingText(key)}: select an instance first`);
        return;
      }
      const pause = chosen.some((item) => !item.paused);
      for (const item of chosen) scene.setPaused(item, pause);
      status.setStatus(`${pause ? 'paused' : 'playing'} ${chosen.length} instance${chosen.length === 1 ? '' : 's'}`);
    });
  },
};
