// Framing a ground box in the uncovered part of the view, and the names
// "add all" gives its landmarks.

import { app, type CameraState, type GroundBox, type Rect, type UnitQuery, type Vec3 } from '../../core/app';

const PAD = 0.04; // share of the visible area kept free around a framed box
const MIN_DISTANCE = 1;
const MAX_DISTANCE = 2000; // features/controls/zoom.ts

/** Whether every point lands inside the rect, PAD kept free. */
function fits(points: readonly Vec3[], r: Rect): boolean {
  const px = (r.right - r.left) * PAD;
  const py = (r.bottom - r.top) * PAD;
  return points.every((p) => {
    const s = app().screenOf(p);
    return s !== null && s[0] >= r.left + px && s[0] <= r.right - px && s[1] >= r.top + py && s[1] <= r.bottom - py;
  });
}

/** The least distance (binary search) at which the points fit; the camera is left there. */
function fitDistance(points: readonly Vec3[], r: Rect): number {
  let low = MIN_DISTANCE;
  let high = MAX_DISTANCE;
  app().view({ distance: high });
  if (!fits(points, r)) return high;
  for (let i = 0; i < 50; i++) {
    const mid = (low + high) / 2;
    app().view({ distance: mid });
    if (fits(points, r)) high = mid;
    else low = mid;
  }
  app().view({ distance: high });
  return high;
}

/**
 * Point the camera at a ground box (z: the height to keep in view), at the
 * current yaw and pitch, and back off until the box fits the uncovered
 * part of the canvas. Returns the view.
 */
export function frameBox(box: GroundBox): CameraState {
  const a = app();
  const camera = a.camera;
  const centre: Vec3 = [(box.x0 + box.x1) / 2, (box.y0 + box.y1) / 2, 0];
  const points: Vec3[] = [];
  for (const x of [box.x0, box.x1]) for (const y of [box.y0, box.y1]) for (const z of [0, box.z || 0]) points.push([x, y, z]);
  // The part of the canvas no open panel covers.
  const r = a.visibleRect();
  a.view({ target: centre });
  fitDistance(points, r);
  // The panel covers the left: move the target so the box centre lands
  // in the middle of the uncovered part, then fit again.
  const canvas = a.canvas.getBoundingClientRect();
  const under = a.groundAt((r.left + r.right) / 2 - canvas.left, (r.top + r.bottom) / 2 - canvas.top);
  if (under) {
    a.view({ target: [camera.target[0] + centre[0] - under[0], camera.target[1] + centre[1] - under[1], 0] });
    fitDistance(points, r);
  }
  return { target: [...camera.target], yaw: camera.yaw, pitch: camera.pitch, distance: camera.distance };
}

// Kinds as a plural noun; any other kind takes an "s".
const PLURAL: Record<string, string> = { Hero: 'Heroes', Other: 'Other Units', Unit: 'Units' };

/**
 * A human readable name for the unit list filters, read like a phrase:
 * race, family, kind (plural), then the search, e.g. 'Terran Campaign
 * Units', 'Zerg Melee Units "drone"', 'Structures (no family)'.
 */
export function filterName(query: UnitQuery): string {
  const words = [];
  if (query.race) words.push(query.race);
  if (query.family) words.push(query.family);
  words.push(query.kind ? (PLURAL[query.kind] ?? `${query.kind}s`) : 'Units');
  if (!query.race && !query.family && !query.kind && !query.q && query.family !== '') words.unshift('All');
  if (query.family === '') words.push('(no family)');
  if (query.q) words.push(`"${query.q}"`);
  return words.join(' ');
}
