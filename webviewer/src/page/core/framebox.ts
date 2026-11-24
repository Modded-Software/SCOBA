// Framing a ground box in the uncovered part of the view (core/view.ts).

import type { CameraState, GroundBox, Rect, Vec2, Vec3 } from './types';

const PAD = 0.04; // share of the visible area kept free around a framed box
const MIN_DISTANCE = 1;
const MAX_DISTANCE = 2000; // core/zoom.ts

/** What framing needs of the camera and the page. */
export interface FrameRig {
  readonly camera: CameraState;
  readonly canvas: HTMLCanvasElement;
  screenOf(point: Vec3): Vec2 | null;
  groundAt(px: number, py: number): Vec2 | null;
  view(next: Partial<CameraState>): void;
  visibleRect(): Rect;
}

/**
 * Point the camera at a ground box (z: the height to keep in view), at the
 * current yaw and pitch, and back off until the box fits the uncovered
 * part of the canvas. Returns the view.
 */
export function frameBox(rig: FrameRig, box: GroundBox): CameraState {
  /** Whether every point lands inside the rect, PAD kept free. */
  function fits(points: readonly Vec3[], r: Rect): boolean {
    const px = (r.right - r.left) * PAD;
    const py = (r.bottom - r.top) * PAD;
    return points.every((p) => {
      const s = rig.screenOf(p);
      return s !== null && s[0] >= r.left + px && s[0] <= r.right - px && s[1] >= r.top + py && s[1] <= r.bottom - py;
    });
  }

  /** The least distance (binary search) at which the points fit; the camera is left there. */
  function fitDistance(points: readonly Vec3[], r: Rect): number {
    let low = MIN_DISTANCE;
    let high = MAX_DISTANCE;
    rig.view({ distance: high });
    if (!fits(points, r)) return high;
    for (let i = 0; i < 50; i++) {
      const mid = (low + high) / 2;
      rig.view({ distance: mid });
      if (fits(points, r)) high = mid;
      else low = mid;
    }
    rig.view({ distance: high });
    return high;
  }

  const camera = rig.camera;
  const centre: Vec3 = [(box.x0 + box.x1) / 2, (box.y0 + box.y1) / 2, 0];
  const points: Vec3[] = [];
  for (const x of [box.x0, box.x1]) for (const y of [box.y0, box.y1]) for (const z of [0, box.z || 0]) points.push([x, y, z]);
  // The part of the canvas no open panel covers.
  const r = rig.visibleRect();
  rig.view({ target: centre });
  fitDistance(points, r);
  // The panel covers the left: move the target so the box centre lands
  // in the middle of the uncovered part, then fit again.
  const canvas = rig.canvas.getBoundingClientRect();
  const under = rig.groundAt((r.left + r.right) / 2 - canvas.left, (r.top + r.bottom) / 2 - canvas.top);
  if (under) {
    rig.view({ target: [camera.target[0] + centre[0] - under[0], camera.target[1] + centre[1] - under[1], 0] });
    fitDistance(points, r);
  }
  return { target: [...camera.target], yaw: camera.yaw, pitch: camera.pitch, distance: camera.distance };
}
