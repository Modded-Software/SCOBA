// What an M3 model's materials and layers hold, for the tests. Step 5 makes
// these format probes (SPEC-VIEWER 6.3).

import { app, type Item } from '../../core/app';
import type { M3Layer, M3Model, M3StandardMaterial } from '../../core/library';

/** Every layer of the model's standard materials, with its material. */
function eachLayer(model: M3Model): { material: M3StandardMaterial; layer: M3Layer }[] {
  return model.materials[1].flatMap((material) => material.layers.map((layer) => ({ material, layer })));
}

export function texturesLoaded(model: M3Model): number {
  return eachLayer(model).filter(({ layer }) => layer.active && layer.texture && layer.texture.texture).length;
}

/** Layers that name a texture file: active and not a constant colour. */
export function texturesWanted(model: M3Model): number {
  return eachLayer(model).filter(({ layer }) => layer.active && !layer.constant).length;
}

/**
 * Constant colour layers (flag 0x400, no texture): the colour uploaded,
 * rgba with the multiply applied, and how many draws bound the layer.
 */
export function constantLayers(model: M3Model): { material: string; type: string; color: number[]; binds: number }[] {
  return eachLayer(model)
    .filter(({ layer }) => layer.active && layer.constant)
    .map(({ material, layer }) => ({ material: material.name, type: layer.type, color: Array.from(layer.constantColor), binds: layer.binds }));
}

/**
 * Per active standard-material layer: the UV transform the last draw
 * uploaded (rows of a 2x3 matrix), its inputs, whether a sequence
 * drives the offset, angle or tiling track, and how many draws bound it.
 * The layer object is shared by every instance of the model.
 */
export function uvLayers(model: M3Model): { material: string; type: string; driven: boolean; tilingDriven: boolean; transform: number[]; inputs: number[]; binds: number }[] {
  return eachLayer(model)
    .filter(({ layer }) => layer.active)
    .map(({ material, layer }) => ({
      material: material.name,
      type: layer.type,
      driven: layer.uvDriven,
      tilingDriven: layer.uvTilingDriven,
      transform: Array.from(layer.uvTransform),
      inputs: Array.from(layer.uvInputs),
      binds: layer.binds,
    }));
}

/**
 * The standard batches the last frame drew for this instance, in the order
 * it drew them: file position, material, blend mode, priority.
 */
export function drawOrder(item: Item): { fileOrder: number; material: string; blendMode: number; priority: number }[] {
  const byFile = new Map(item.model.batches.map((b) => [b.fileOrder, b]));
  return item.instance.drawnOrder.map((fileOrder) => {
    const batch = byFile.get(fileOrder);
    if (!batch) throw new Error(`draw order: no batch at file position ${fileOrder}`);
    const m = batch.material;
    return { fileOrder, material: m.name, blendMode: m.blendMode, priority: m.priority };
  });
}

function find(itemId: number): Item {
  const item = app().items.find((i) => i.id === itemId);
  if (!item) throw new Error(`no item ${itemId}`);
  return item;
}

/**
 * Turn one model's constant colour layers on or off, so a test can
 * measure what they draw. Returns how many layers changed.
 */
export function setConstantLayers(itemId: number, on: boolean): number {
  let count = 0;
  for (const { layer } of eachLayer(find(itemId).model)) {
    if (!layer.constant) continue;
    layer.active = on ? 1 : 0;
    count++;
  }
  return count;
}

/**
 * Each material of one model: its name and its alpha test (the material's
 * alphaTestThreshold / 255; 0 is no test), as the renderer draws it.
 */
export function alphaTests(itemId: number): { material: string; alphaTest: number }[] {
  return find(itemId).model.materials[1].map((material) => ({ material: material.name, alphaTest: material.alphaTest }));
}

/** The alpha test each material was loaded with, kept while a test turns it off. */
const ownAlphaTest = new WeakMap<M3StandardMaterial, number>();

/**
 * Turn one model's alpha tests off, or back to the model's own, so a test
 * can measure what the cut-out removes. Returns how many materials have a test.
 */
export function setAlphaTest(itemId: number, on: boolean): number {
  let count = 0;
  for (const material of find(itemId).model.materials[1]) {
    if (typeof material.alphaTest !== 'number') continue;
    const own = ownAlphaTest.get(material) ?? material.alphaTest;
    ownAlphaTest.set(material, own);
    material.alphaTest = on ? own : 0;
    if (own > 0) count++;
  }
  return count;
}
