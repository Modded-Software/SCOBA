// What an M3 model's materials and layers hold, for the tests: the M3
// part of scobaeditor.state() (m3Facts) and the material switches.

import type M3Model from '@renderer/viewer/handlers/m3/model';
import type M3ModelInstance from '@renderer/viewer/handlers/m3/modelinstance';
import type { M3StandardMaterial } from '@renderer/viewer/handlers/m3/standardmaterial';
import type { FeatureContext } from '../../page/core/context';
import type { Item } from '../../page/core/types';
import type { ViewerInstance } from '../../page/core/plugin';
import { eachLayer, m3Instance, m3Model } from './adapter';

function texturesLoaded(model: M3Model): number {
  return eachLayer(model).filter(({ layer }) => layer.active && layer.texture && layer.texture.texture).length;
}

/** Layers that name a texture file: active and not a constant colour. */
function texturesWanted(model: M3Model): number {
  return eachLayer(model).filter(({ layer }) => layer.active && !layer.constant).length;
}

/**
 * Constant colour layers (flag 0x400, no texture): the colour uploaded,
 * rgba with the multiply applied, and how many draws bound the layer.
 */
function constantLayers(model: M3Model): { material: string; type: string; color: number[]; binds: number }[] {
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
function uvLayers(model: M3Model): { material: string; type: string; driven: boolean; tilingDriven: boolean; transform: number[]; inputs: number[]; binds: number }[] {
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
function drawOrder(model: M3Model, instance: M3ModelInstance): { fileOrder: number; material: string; blendMode: number; priority: number }[] {
  const byFile = new Map(model.batches.map((b) => [b.fileOrder, b]));
  return instance.drawnOrder.map((fileOrder) => {
    const batch = byFile.get(fileOrder);
    if (!batch) throw new Error(`draw order: no batch at file position ${fileOrder}`);
    const m = batch.material;
    return { fileOrder, material: m.name, blendMode: m.blendMode, priority: m.priority };
  });
}

/** What only the M3 format knows of an instance: geometry layout, layers, engine look. */
export function m3Facts(view: ViewerInstance): Record<string, unknown> {
  const model = m3Model(view.model);
  const instance = m3Instance(view);
  return {
    texturesLoaded: texturesLoaded(model),
    texturesWanted: texturesWanted(model),
    batches: model.batches.length,
    engineTeam: instance.teamColor,
    tint: Array.from(instance.vertexColor),
    // Geometry layout as the renderer reads it.
    vertexStride: model.vertexSize,
    vertexCount: model.vertexCount,
    vertexBytes: model.vertexBytes,
    // Element indices: bytes each, and the largest stored (vertexCount - 1 unless they wrapped).
    elementBytes: model.elementBytes,
    elementMax: model.elementMax,
    // Edges in the edge buffer (renderEdges): 0 until the first edge draw.
    edgeCount: model.edgeCount,
    displacementBatches: model.displacementBatches.length,
    // Per region: the UV transform the renderer applies (scale, offset),
    // the stored range of the first UV set, and that range decoded.
    regionUv: model.regions.map((r) => ({
      scale: r.uvScale,
      offset: r.uvOffset,
      raw: [...r.rawUvRange],
      range: r.rawUvRange.map((c) => c * r.uvScale + r.uvOffset),
    })),
    uvLayers: uvLayers(model),
    constantLayers: constantLayers(model),
    drawOrder: drawOrder(model, instance),
  };
}

/** The layer test API, bound to the scene service. */
export function createLayersApi({ scene }: Pick<FeatureContext, 'scene'>) {
  function find(itemId: number): Item {
    const item = scene.items.find((i) => i.id === itemId);
    if (!item) throw new Error(`no item ${itemId}`);
    return item;
  }

  /**
   * Turn one model's constant colour layers on or off, so a test can
   * measure what they draw. Returns how many layers changed.
   */
  function setConstantLayers(itemId: number, on: boolean): number {
    let count = 0;
    for (const { layer } of eachLayer(m3Model(find(itemId).model))) {
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
  function alphaTests(itemId: number): { material: string; alphaTest: number }[] {
    return m3Model(find(itemId).model).materials[1].map((material) => ({ material: material.name, alphaTest: material.alphaTest }));
  }

  /** The alpha test each material was loaded with, kept while a test turns it off. */
  const ownAlphaTest = new WeakMap<M3StandardMaterial, number>();

  /**
   * Turn one model's alpha tests off, or back to the model's own, so a test
   * can measure what the cut-out removes. Returns how many materials have a test.
   */
  function setAlphaTest(itemId: number, on: boolean): number {
    let count = 0;
    for (const material of m3Model(find(itemId).model).materials[1]) {
      if (typeof material.alphaTest !== 'number') continue;
      const own = ownAlphaTest.get(material) ?? material.alphaTest;
      ownAlphaTest.set(material, own);
      material.alphaTest = on ? own : 0;
      if (own > 0) count++;
    }
    return count;
  }

  return { setConstantLayers, alphaTests, setAlphaTest };
}
