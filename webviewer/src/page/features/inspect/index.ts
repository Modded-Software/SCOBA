// Inspection used by the tests: scene state, framebuffer reads and pixel
// statistics, and the material switches the tests turn.

import { alphaTests, setAlphaTest, setConstantLayers } from './layers';
import { changedSinceMark, colorStats, drawnAt, gridLines, groundPeaks, groundPixel, groundPixels, idle, mark, pixels, setSolidOnly, whiteShare, worldToCanvas } from './frame';
import { state } from './state';

export const inspectApi = {
  state,
  setConstantLayers,
  alphaTests,
  setAlphaTest,
  whiteShare,
  drawnAt,
  setSolidOnly,
  groundPixel,
  groundPixels,
  groundPeaks,
  worldToCanvas,
  mark,
  changedSinceMark,
  pixels,
  colorStats,
  gridLines,
  idle,
};

export type InspectApi = typeof inspectApi;

export function installInspect(): InspectApi {
  return { ...inspectApi };
}
