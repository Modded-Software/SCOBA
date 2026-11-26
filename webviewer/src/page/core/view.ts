// The camera service (SPEC-VIEWER 6.6): the rig of core/camera.ts, the
// zoom glide, framing a box, focusing an item, and the ground point under
// the mouse. The mouse controls that move it are features/controls.

import type { CameraService, Store } from './context';
import { createLandmarks } from './landmarks';
import type { EventBus, ViewerEvents } from './bus';
import { focusItem } from './focus';
import { frameBox } from './framebox';
import type { Host } from './host';
import { resolveInput } from './input';
import type { CameraState, Vec2 } from './types';
import { settings } from './settings';
import { createZoom } from './zoom';

export function createView(host: Host, store: Store, events: EventBus<ViewerEvents>): CameraService {
  const { rig, canvas } = host;
  const { camera } = rig;
  let pointer: Vec2 | null = null;

  /** Apply the camera, and say so. */
  function applyCamera(): void {
    rig.applyCamera();
    events.emit('camera-changed', { camera });
  }

  const zoom = createZoom(camera, {
    eye: rig.eye,
    applyCamera,
    sensitivity: () => store.read(settings.mouseSensitivity),
    pointerGround: rig.eventGround,
    flags: () => resolveInput(store.read(settings.input)).rates,
  });

  function view(next: Partial<CameraState>): void {
    zoom.stop();
    Object.assign(camera, next);
    if (next.target) camera.target = [...next.target];
    applyCamera();
  }

  canvas.addEventListener('mousemove', (e) => {
    pointer = rig.eventGround(e);
  });
  canvas.addEventListener('mouseleave', () => {
    pointer = null;
  });

  const frameRig = { camera, canvas, screenOf: rig.screenOf, groundAt: rig.groundAt, view, visibleRect: host.visibleRect };

  return {
    ...createLandmarks(store, events, view),
    camera,
    cameraStart: rig.cameraStart,
    pointer: () => pointer,
    setPointer(point) {
      pointer = point;
    },
    eye: rig.eye,
    applyCamera,
    groundAt: rig.groundAt,
    eventGround: rig.eventGround,
    rayAt: rig.rayAt,
    screenOf: rig.screenOf,
    view,
    zoomGoal: () => zoom.goal(),
    notchShare: (ctrl = false) => zoom.notchShare(camera.distance, ctrl),
    wheel: (e) => zoom.wheel(e),
    stopGlide: () => zoom.stop(),
    frameBox: (box) => frameBox(frameRig, box),
    focusItem: (item) => focusItem(view, item),
  };
}
