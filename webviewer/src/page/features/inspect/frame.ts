// Frame hooks for the tests: draw one frame now, where a world point lands,
// and whether anything still loads. No pixel is read back: what a frame
// looks like is an operator check (SPEC-VIEWER 14).

import type { FeatureContext } from '../../core/context';

/** The frame hooks, bound to the render and status services. */
export function createInspectFrame({ render, status }: Pick<FeatureContext, 'render' | 'status'>) {
  /** Draw one frame now, without advancing time: the counters the formats keep (drawn, quads, binds) are then this frame's. */
  function drawOnce(): void {
    render.resize();
    render.draw(0);
  }

  /**
   * Where a world point lands on the canvas, in canvas pixels, as the
   * renderer's camera computes it: x from the left; y as the library gives
   * it (the framebuffer row).
   */
  function worldToCanvas(x: number, y: number, z = 0): number[] {
    render.resize();
    const scene = render.scene;
    const screen = new Float32Array(2);
    scene.camera.worldToScreen(screen, new Float32Array([x, y, z]), scene.viewport);
    return [screen[0] ?? 0, screen[1] ?? 0];
  }

  /** True when nothing is loading: no model being added, no texture in flight. */
  function idle(): boolean {
    return status.pending === 0 && render.viewer.promiseMap.size === 0;
  }

  return { drawOnce, worldToCanvas, idle };
}
