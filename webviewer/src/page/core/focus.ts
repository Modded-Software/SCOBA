// Camera focus: point the camera at an item (ctrl + click on its row; core/view.ts).

import { restBox } from './geometry';
import type { CameraState, Item } from './types';

const HALF_FOV = Math.PI / 8; // half the vertical field of view (core/camera.ts FOV)
const FOCUS_MARGIN = 1.3; // the instance's sphere fills 1 / 1.3 of the view height
const FOCUS_MIN = 2;
const FOCUS_MIN_REACH = 0.25;

/**
 * Point the camera at the middle of the item's rest-pose vertex box
 * (restBox), from where the box's sphere fits the view. Yaw and pitch
 * stay; the camera jumps.
 */
export function focusItem(view: (next: Partial<CameraState>) => void, item: Item): void {
  const { centre, reach } = restBox(item);
  view({ target: centre, distance: Math.max(FOCUS_MIN, (FOCUS_MARGIN * Math.max(FOCUS_MIN_REACH, reach)) / Math.sin(HALF_FOV)) });
}
