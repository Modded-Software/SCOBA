// HD textures in the view. The upscaled model textures (scripts/hdtex,
// served by /hd-asset) stand in for the standard ones, per instance:
// - a model "has both sets" when a layer of it names a texture that has an
//   upscaled file (/api/hd-textures lists them, by in-model path);
// - such an instance shows the HD set from the start (item.hd, default on);
// - the right-click menu has an "hd" checkbox for it (pick.js);
// - Ctrl+H switches the selected instances between the two sets;
// - Ctrl+L switches the menu's "loop" choice (pick.js toggleLoop);
// - the grid glows blue around a model with a texture of 2048 or more on a
//   side, standard or upscaled (isHd), green around the others.
// The standard textures stay the model's own; HD is an override on the
// instance (the renderer's setTexture), so two instances of one model can differ.
'use strict';

(() => {
  const app = window.SC2App;
  const { viewer, items } = app;

  /** A texture this large on a side is an HD one. Stock unit textures are mostly 1024. */
  const HD_SIZE = 2048;
  /** In-model paths (lower case, backslashes) of the textures with an upscaled file. */
  const assets = new Set();
  const key = (source) => source.toLowerCase().replaceAll('/', '\\');
  const hdUrl = (source) => `/hd-asset?${new URLSearchParams({ path: key(source) })}`;

  async function setupHd() {
    const body = await app.getJson('/api/hd-textures');
    for (const asset of body.assets) assets.add(asset);
  }

  /** The layers of a model whose texture has an upscaled file. */
  function hdLayers(model) {
    const found = [];
    for (const material of model.materials[1]) {
      for (const layer of material.layers) {
        if (layer.active && !layer.constant && layer.source && assets.has(key(layer.source))) found.push(layer);
      }
    }
    return found;
  }

  /**
   * Give an item's instance the texture set item.hd asks for. Sets
   * item.hdLayers, the number of layers that have both sets (0: the choice
   * does nothing for this model), and item.largestTexture, the longest side
   * in pixels of any texture the model has, standard or upscaled.
   */
  async function applyHd(item) {
    const layers = hdLayers(item.model);
    const { instance, model } = item;
    item.hdLayers = layers.length;
    app.pending++;
    try {
      // The HD files are read with the choice off too: their size counts for largestTexture.
      let largest = 0;
      for (const layer of layers) {
        const texture = await viewer.load(layer.source, hdUrl);
        if (!texture) throw new Error(`cannot load the HD texture of ${layer.source}`);
        largest = Math.max(largest, texture.width, texture.height);
        // Swapped while it loaded: leave the new instance alone.
        if (item.instance === instance) instance.setTexture(layer.material.index, layer.index, item.hd ? texture : undefined);
      }
      // The model's own textures, once they are in.
      await viewer.whenAllLoaded();
      for (const material of model.materials[1]) {
        for (const layer of material.layers) {
          const own = layer.active && layer.texture ? layer.texture.texture : null;
          if (own) largest = Math.max(largest, own.width, own.height);
        }
      }
      if (item.instance === instance) item.largestTexture = largest;
    } finally {
      app.pending--;
    }
  }

  /**
   * Whether an item's model counts as HD, for the blue grid glow: one of
   * its textures, standard or upscaled, is HD_SIZE or more on a side. A
   * small shared texture with an upscaled file (a decal, a reflection map)
   * does not make a model HD (operator 2026-11-22).
   */
  const isHd = (item) => item.largestTexture >= HD_SIZE;

  /** Switch an item to the HD set (true) or the standard one. False when its model has one set only. */
  async function setHd(item, on) {
    if (!item.hdLayers) return false;
    item.hd = Boolean(on);
    app.saveHash();
    await applyHd(item);
    return true;
  }

  /** Ctrl+H: switch every selected instance that has both sets. */
  async function toggleSelectedHd() {
    const chosen = app.selectedIds().map((id) => items.find((item) => item.id === id));
    const both = chosen.filter((item) => item && item.hdLayers);
    if (!both.length) {
      app.setStatus(chosen.length ? 'no HD textures for the selected' : '');
      return;
    }
    // All go the same way: off when the last selected one shows HD.
    const on = !both[both.length - 1].hd;
    for (const item of both) await setHd(item, on);
    app.setStatus(`${on ? 'HD' : 'standard'} textures: ${both.length} instance${both.length === 1 ? '' : 's'}`);
    app.refreshMenu();
  }

  window.addEventListener('keydown', (e) => {
    if (!e.ctrlKey || e.altKey || e.metaKey || e.shiftKey) return;
    const letter = e.key.toLowerCase();
    if (letter !== 'h' && letter !== 'l') return;
    // The viewer owns these keys everywhere on the page: the browser's own
    // Ctrl+H (history) and Ctrl+L (address bar) never open, with or without
    // a selection, in a text field too (operator 2026-11-22).
    e.preventDefault();
    const t = e.target;
    // A field being edited: the key is consumed and does nothing.
    if (t instanceof HTMLElement && (t.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(t.tagName))) return;
    if (!app.hasSelection()) {
      app.setStatus(`Ctrl+${letter.toUpperCase()}: select an instance first`);
      return;
    }
    if (letter === 'h') toggleSelectedHd().catch(app.reportFailure);
    else app.setStatus(`loop ${app.toggleLoop() ? 'on' : 'off'}`);
  });

  Object.assign(app, { setupHd, applyHd, setHd, isHd, toggleSelectedHd, hdAssets: () => [...assets] });
})();
