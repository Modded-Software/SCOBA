// The core of the page: the renderer, the two scenes, the camera, shared
// state and small helpers (the old js/core.js, without the status toast,
// which is page/ui/status.ts).

import type M3Model from '@renderer/viewer/handlers/m3/model';
import { vec3 } from 'gl-matrix';
import { app, type CoreApi, type Rect, type Vec3 } from './app';
import { createCamera } from './camera';
import { byId, byIdAs, make, messageOf } from './dom';
import { ModelViewer, viewerLib } from './library';
import { createGround } from './render/ground';
import { createOutline } from './render/outline';
import { createPickBuffer } from './render/pickbuffer';
import { baseHeight, dataScale, defaultSequence, playRate } from './rules';

const BACKGROUND: Vec3 = [26 / 255, 26 / 255, 31 / 255];
const LIGHT: Vec3 = [3000, -6000, 8000];

/** A library error event: what failed, and the file. */
interface ViewerError {
  error?: unknown;
  fetchUrl?: unknown;
  reason?: unknown;
}

const text = (value: unknown): string => (typeof value === 'string' ? value : value === undefined || value === null ? '' : String(value));

/** The core part. `displacement` is the M3 format's post pass (formats/m3). */
export function createCore(displacementOf: (viewer: ModelViewer) => CoreApi['displacement']): CoreApi {
  const canvas = byIdAs('view', HTMLCanvasElement);

  const viewer = new ModelViewer(canvas, { alpha: false, antialias: true });
  viewer.addHandler(viewerLib.handlers.m3);
  viewer.addHandler(viewerLib.handlers.dds);
  viewer.addHandler(viewerLib.handlers.tga);
  // The library reports failures as events. Show them; never drop them.
  viewer.on('error', (e: ViewerError) => {
    console.warn('viewer:', e.error, e.fetchUrl || '', e.reason || '');
    const url = text(e.fetchUrl);
    app().setStatus(`${text(e.error)} ${url ? decodeURIComponent(url) : ''}`, { failure: true });
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

  /** The part of the canvas no open panel covers, in page pixels. */
  function visibleRect(): Rect {
    const box = canvas.getBoundingClientRect();
    let left = box.left;
    for (const id of ['panel', 'instances']) {
      const node = byId(id);
      if (!node.classList.contains('closed')) left = Math.max(left, node.getBoundingClientRect().right);
    }
    return { left, right: box.right, top: box.top, bottom: box.bottom };
  }

  /**
   * End of the line for a failed user action (add, drop, pick a sky): the
   * action already put the message in the status line; this also logs it.
   */
  function reportFailure(error: unknown): void {
    console.warn('sc2viewer:', error);
    app().setStatus(messageOf(error), { failure: true });
  }

  /** Say so when a loaded model has parts the renderer cannot draw. */
  function reportUndrawn(name: string, model: M3Model): void {
    if (!model.undrawnBatches.length) return;
    console.warn(`sc2viewer: ${name}: not drawn: ${model.undrawnBatches.join('; ')}`);
    app().setStatus(`${name}: ${model.undrawnBatches.length} part(s) not drawn (${model.undrawnBatches[0] ?? ''})`, { failure: true });
  }

  /** A server answer as JSON. The server is this viewer's own (src/shared/records.ts has its shapes). */
  async function getJson<T>(url: string): Promise<T> {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`${response.status} ${url}`);
    const body: unknown = await response.json();
    return body as T;
  }

  /** A unit icon from a dataset (default: the current one), or an empty box when the unit has none. */
  function iconNode(name: string | null, dataset?: string): HTMLElement {
    return name ? make('img', { className: 'icon', src: app().iconUrl(name, dataset), alt: '', draggable: false }) : make('span', { className: 'icon none' });
  }

  return {
    lib: viewerLib,
    viewer,
    scene,
    skyScene,
    ground: createGround(viewer),
    outline: createOutline(viewer),
    pickBuffer: createPickBuffer(viewer),
    displacement: displacementOf(viewer),
    canvas,
    BACKGROUND,
    TEAMS: 14,
    camera: rig.camera,
    cameraRestore: rig.cameraRestore,
    items: [],
    pending: 0,
    pointer: null,
    $: byId,
    visibleRect,
    reportFailure,
    reportUndrawn,
    getJson,
    el: make,
    iconNode,
    shown: (value) => String(Math.round(value * 1000) / 1000),
    eye: rig.eye,
    applyCamera: rig.applyCamera,
    resize: rig.resize,
    groundAt: rig.groundAt,
    eventGround: rig.eventGround,
    rayAt: rig.rayAt,
    screenOf: rig.screenOf,
    dataScale,
    baseHeight,
    playRate,
    defaultSequence,
  };
}
