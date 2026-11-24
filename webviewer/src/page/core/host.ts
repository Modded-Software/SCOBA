// The renderer, the two scenes and the camera rig (the old js/core.js,
// without the status toast, which is page/ui/status.ts). The frame adds
// the draw to this to make the RenderHost (core/context.ts).

import { vec3 } from 'gl-matrix';
import type { Rect, Vec3 } from './types';
import { createCamera, type CameraRig } from './camera';
import { byId, byIdAs } from './dom';
import { ModelViewer } from './library';
import type { RenderHost } from './context';
import type { FormatModule, ViewerModel } from './plugin';
import { createGround } from './render/ground';
import { createOutline } from './render/outline';
import { createPickBuffer } from './render/pickbuffer';

const BACKGROUND: Vec3 = [26 / 255, 26 / 255, 31 / 255];
const LIGHT: Vec3 = [3000, -6000, 8000];

/** A library error event: what failed, and the file. */
interface ViewerError {
  error?: unknown;
  fetchUrl?: unknown;
  reason?: unknown;
}

const text = (value: unknown): string => (typeof value === 'string' ? value : value === undefined || value === null ? '' : String(value));

/** The part of the canvas no open panel covers, in page pixels. */
export function visibleRect(): Rect {
  const box = byId('view').getBoundingClientRect();
  let left = box.left;
  for (const id of ['gallery', 'instances']) {
    const node = byId(id);
    if (!node.classList.contains('closed')) left = Math.max(left, node.getBoundingClientRect().right);
  }
  return { left, right: box.right, top: box.top, bottom: box.bottom };
}

/** The render host without the frame's members. */
export type Host = Omit<RenderHost, 'draw' | 'setPostPass' | 'displacedBatches'> & { readonly rig: CameraRig };

/** The renderer with the model formats main.ts registered (SPEC-VIEWER 6.3). */
export function createHost(formats: readonly FormatModule[], setStatus: (text: string, options: { failure: boolean }) => void): Host {
  const canvas = byIdAs('view', HTMLCanvasElement);

  const viewer = new ModelViewer(canvas, { alpha: false, antialias: true });
  for (const format of formats) for (const handler of format.handlers) viewer.addHandler(handler);
  // The library reports failures as events. Show them; never drop them.
  // A format that refuses a file throws an Error with the reason; loadModel
  // throws it on. A fetch that fails gives a Response, not a reason.
  const reasons = new Map<string, string>();
  viewer.on('error', (e: ViewerError) => {
    console.warn('viewer:', e.error, e.fetchUrl || '', e.reason || '');
    const url = text(e.fetchUrl);
    if (url && e.reason instanceof Error) reasons.set(url, e.reason.message);
    setStatus(`${text(e.error)} ${url ? decodeURIComponent(url) : ''}`, { failure: true });
  });
  // Two scenes: the sky, drawn first around a camera at the origin, and the
  // units. draw() clears once, so neither scene clears (alpha = true).
  const skyScene = viewer.addScene();
  skyScene.alpha = true;
  const scene = viewer.addScene();
  scene.alpha = true;
  vec3.copy(scene.color, BACKGROUND);
  // A far light above and in front of the default camera, a bit to the right.
  vec3.copy(scene.lightPosition, LIGHT);
  vec3.copy(skyScene.lightPosition, LIGHT);

  const rig = createCamera(canvas, scene, skyScene);

  /** Say so when a loaded model has parts the renderer cannot draw. */
  function reportUndrawn(name: string, model: ViewerModel): void {
    if (!model.undrawn.length) return;
    console.warn(`sc2viewer: ${name}: not drawn: ${model.undrawn.join('; ')}`);
    setStatus(`${name}: ${model.undrawn.length} part(s) not drawn (${model.undrawn[0] ?? ''})`, { failure: true });
  }

  /** The format that took a loaded resource, with its model; null when none did. */
  function adopted(resource: unknown): { format: FormatModule; model: ViewerModel } | null {
    for (const format of formats) {
      const model = format.adopt(resource);
      if (model) return { format, model };
    }
    return null;
  }

  /** The model at `url`; null when no format took it; its format's reason as an error when it refused it. */
  async function loadModel(url: string, solver: (src: unknown) => unknown): Promise<ViewerModel | null> {
    reasons.delete(url);
    const found = adopted(await viewer.load(url, solver));
    if (found) return found.model;
    const reason = reasons.get(url);
    reasons.delete(url);
    if (reason) throw new Error(reason);
    return null;
  }

  function formatOf(model: ViewerModel): FormatModule {
    const format = formats.find((f) => f.id === model.format);
    if (!format) throw new Error(`no format ${model.format}`);
    return format;
  }

  return {
    viewer,
    scene,
    skyScene,
    ground: createGround(viewer),
    outline: createOutline(viewer),
    pickBuffer: createPickBuffer(viewer),
    formats,
    postPasses: formats.flatMap((format) => (format.postPasses ? format.postPasses(viewer) : [])),
    canvas,
    BACKGROUND,
    rig,
    loadModel,
    formatOf,
    reportUndrawn,
    resize: rig.resize,
    visibleRect,
  };
}
