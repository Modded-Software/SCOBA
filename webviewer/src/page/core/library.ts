// The renderer library (ref/mdx-m3-viewer), as the page uses it.
// Only page/core and the formats import the library (SPEC-VIEWER section 3).

import ModelViewer from '@renderer/viewer/viewer';
import m3 from '@renderer/viewer/handlers/m3/handler';
import dds from '@renderer/viewer/handlers/dds/handler';
import tga from '@renderer/viewer/handlers/tga/handler';
import M3Model from '@renderer/viewer/handlers/m3/model';
import Texture from '@renderer/viewer/texture';
import { DdsImage } from '@renderer/parsers/dds/image';
import type { M3HandlerObject } from '@renderer/viewer/handlers/m3/handler';

export { ModelViewer, DdsImage, M3Model, Texture };
// The library's types the rest of the page names; it reaches them only through core.
export type { default as M3ModelInstance } from '@renderer/viewer/handlers/m3/modelinstance';
export type { default as M3Layer } from '@renderer/viewer/handlers/m3/layer';
export type { M3StandardMaterial } from '@renderer/viewer/handlers/m3/standardmaterial';
export type { default as Scene } from '@renderer/viewer/scene';
export type { M3HandlerObject };

/** The viewer and its handlers: SC2App.lib. */
export const viewerLib = { ModelViewer, handlers: { m3, dds, tga } };

/** The M3 handler's shared object: its shaders and the switches the tests turn. */
export function m3Shared(viewer: ModelViewer): M3HandlerObject {
  const shared = viewer.sharedCache.get('m3');
  if (!isM3Shared(shared)) throw new Error('the M3 handler is not loaded');
  return shared;
}

function isM3Shared(value: unknown): value is M3HandlerObject {
  return typeof value === 'object' && value !== null && 'particlesEnabled' in value && 'layerOptions' in value;
}

/** Load an M3 model file; null when the file is no M3 model the library can read. */
export async function loadM3(viewer: ModelViewer, url: string, solver: (src: unknown) => unknown): Promise<M3Model | null> {
  const resource = await viewer.load(url, solver);
  return resource instanceof M3Model ? resource : null;
}
