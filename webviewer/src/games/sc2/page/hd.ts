// SC2 HD textures in the view. The upscaled model textures (scripts/hdtex,
// served by /api/sc2/x/hd-asset) stand in for the standard ones, per instance:
// - a model "has both sets" when a layer of it names a texture that has an
//   upscaled file (/api/sc2/x/hd-textures lists them, by in-model path);
// - such an instance shows the HD set from the start (the item option
//   `hd`, default on);
// - the right-click menu has an "hd" checkbox for it (a menu toggle);
// - Ctrl+H switches the selected instances between the two sets;
// - the grid glows blue around a model with a texture of 2048 or more on a
//   side, standard or upscaled (isHd, the glow rule), green around the others.
// The standard textures stay the model's own; HD is an override on the
// instance (the textureOverride capability, SPEC-VIEWER 6.2), so two
// instances of one model can differ. An instance without it has no HD set.

import type { Item } from '../../../page/core/types';
import type { GameContext, MenuToggle } from '../../../page/core/context';
import { Texture } from '../../../page/core/library';
import type { TextureSlot } from '../../../page/core/plugin';
import type { HdTexturesBody } from '../shared/records';
import { SC2 } from './game';

/** A texture this large on a side is an HD one. Stock unit textures are mostly 1024. */
const HD_SIZE = 2048;

const key = (source: string): string => source.toLowerCase().replaceAll('/', '\\');

/** What applyHd found of an item's model. */
interface HdFacts {
  /** The layers that have both sets (0: the choice does nothing for this model). */
  layers: number;
  /** The longest side in pixels of any texture the model has, standard or upscaled. */
  largest: number;
}

export interface Hd {
  setupHd(): Promise<void>;
  applyHd(item: Item): Promise<void>;
  /** The HD choice of an item (its option `hd`). */
  hdOn(item: Item): boolean;
  hdLayers(item: Item): number;
  largestTexture(item: Item): number;
  isHd(item: Item): boolean;
  setHd(item: Item, on: boolean): Promise<boolean>;
  readonly toggle: MenuToggle;
  hdAssets(): string[];
}

export function installHd({ api, render, scene, selection, status, events }: GameContext): Hd {
  const hdUrl = (source: unknown): string => `${api.extensionUrl('hd-asset', SC2)}?${new URLSearchParams({ path: key(String(source)) })}`;
  /** In-model paths (lower case, backslashes) of the textures with an upscaled file. */
  const assets = new Set<string>();
  const facts = new WeakMap<Item, HdFacts>();
  const factsOf = (item: Item): HdFacts => facts.get(item) ?? { layers: 0, largest: 0 };

  async function setupHd(): Promise<void> {
    const body = await api.getJson<HdTexturesBody>(api.extensionUrl('hd-textures', SC2));
    for (const asset of body.assets) assets.add(asset);
  }

  const hdOn = (item: Item): boolean => item.options['hd'] !== false;

  /** The texture slots of an item whose texture has an upscaled file. */
  function hdSlots(slots: readonly TextureSlot[]): TextureSlot[] {
    return slots.filter((slot) => assets.has(key(slot.source)));
  }

  /** Give an item's instance the texture set its `hd` option asks for, and note its facts. */
  async function applyHd(item: Item): Promise<void> {
    const { instance, capabilities } = item;
    const override = capabilities.textureOverride;
    const slots = override ? override.slots() : [];
    const chosen = hdSlots(slots);
    facts.set(item, { layers: chosen.length, largest: factsOf(item).largest });
    status.pending++;
    try {
      // The HD files are read with the choice off too: their size counts for largestTexture.
      let largest = 0;
      for (const slot of chosen) {
        const texture = await render.viewer.load(slot.source, hdUrl);
        if (!(texture instanceof Texture)) throw new Error(`cannot load the HD texture of ${slot.source}`);
        largest = Math.max(largest, texture.width, texture.height);
        // Swapped while it loaded: leave the new instance alone.
        if (override && item.instance === instance) override.set(slot, hdOn(item) ? texture : null);
      }
      // The model's own textures, once they are in.
      await render.viewer.whenAllLoaded();
      for (const slot of slots) largest = Math.max(largest, slot.ownSize());
      if (item.instance === instance) facts.set(item, { layers: chosen.length, largest });
    } finally {
      status.pending--;
    }
  }

  /**
   * Whether an item's model counts as HD, for the blue grid glow: one of
   * its textures, standard or upscaled, is HD_SIZE or more on a side. A
   * small shared texture with an upscaled file (a decal, a reflection map)
   * does not make a model HD (operator 2026-11-22).
   */
  const isHd = (item: Item): boolean => factsOf(item).largest >= HD_SIZE;

  /** Switch an item to the HD set (true) or the standard one. False when its model has one set only. */
  async function setHd(item: Item, on: boolean): Promise<boolean> {
    if (!factsOf(item).layers) return false;
    item.options['hd'] = Boolean(on);
    events.emit('scene-edited', { what: 'hd' });
    await applyHd(item);
    return true;
  }

  /** Ctrl+H: switch every selected instance that has both sets. */
  async function toggleSelectedHd(): Promise<void> {
    const chosen = selection.selectedIds().map((id) => scene.items.find((item) => item.id === id));
    const both = chosen.filter((item): item is Item => Boolean(item && factsOf(item).layers));
    const last = both[both.length - 1];
    if (!last) {
      status.setStatus(chosen.length ? 'no HD textures for the selected' : '');
      return;
    }
    // All go the same way: off when the last selected one shows HD.
    const on = !hdOn(last);
    for (const item of both) await setHd(item, on);
    status.setStatus(`${on ? 'HD' : 'standard'} textures: ${both.length} instance${both.length === 1 ? '' : 's'}`);
  }

  window.addEventListener('keydown', (e) => {
    if (!e.ctrlKey || e.altKey || e.metaKey || e.shiftKey || e.key.toLowerCase() !== 'h') return;
    // The viewer owns Ctrl+H everywhere on the page: the browser's history
    // never opens, with or without a selection, in a text field too (operator 2026-11-22).
    e.preventDefault();
    // A field being edited: the key is consumed and does nothing.
    if (selection.editingText(e.target)) return;
    if (!selection.hasSelection()) {
      status.setStatus('Ctrl+H: select an instance first');
      return;
    }
    toggleSelectedHd().catch(status.reportFailure);
  });

  /** The instance menu's "hd" check box: on a model with both texture sets. */
  const toggle: MenuToggle = {
    className: 'hd',
    label: 'hd',
    title: 'checked: the upscaled HD textures; unchecked: the standard ones (Ctrl+H)',
    when: (item) => factsOf(item).layers > 0,
    checked: hdOn,
    set: setHd,
  };

  return {
    setupHd,
    applyHd,
    hdOn,
    hdLayers: (item) => factsOf(item).layers,
    largestTexture: (item) => factsOf(item).largest,
    isHd,
    setHd,
    toggle,
    hdAssets: () => [...assets],
  };
}
