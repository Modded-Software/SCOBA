// The triangle edges of chosen instances, drawn over them in thin green.
// - Ctrl+/ switches the edges of the selected instances, all the same way:
//   off when the one selected last shows them, on otherwise;
// - only the edges in front show: they are depth tested against the drawn
//   scene, so the instance itself and the others hide what is behind;
// - they follow the pose: the format draws them with its own vertex shader
//   (the `edges` capability, SPEC-VIEWER 6.2);
// - an instance farther from the eye than EDGE_RANGE shows none: far away
//   the lines run together into a green blot;
// - the choice belongs to the instance shown and is not kept: a reload, a
//   copy, a new model (variant, dataset) start without edges.
// The frame draws them after the units (the scene-drawn event), before
// the mouse-over outline.

import type { Feature } from '../../core/context';
import type { Item, Rect } from '../../core/types';
import type { ViewerInstance } from '../../core/plugin';
import type { Rgb } from '../../core/render/gl';

/** The line colour. */
const EDGE_COLOR: Rgb = [0.2, 1.0, 0.3];
/** Farther from the eye than this, in world units, an instance shows no edges. */
export const EDGE_RANGE = 40;
/**
 * The lines' depth is pulled towards the eye by this share, so a line
 * wins over the surface it lies on (lines take no polygon offset).
 */
const DEPTH_PULL = 5e-5;
/** edgePixels: an edge pixel farther than this, in pixels, from every drawn pixel is off the body. */
const OFF_BODY = 2;

/** What the tests read of the edges (sc2viewer.state().edges). */
export interface EdgesState {
  /** The items with edges on, by id. */
  on: number[];
  /** Of those, the ones too far to draw them in the last frame. */
  far: number[];
  /** Lines drawn in the last frame. */
  lines: number;
  range: number;
}

/** The ctrl + "/" key: the "/" key of a US layout, or any key that types "/". */
function isEdgesKey(e: KeyboardEvent): boolean {
  if (!e.ctrlKey || e.altKey || e.metaKey) return false;
  return e.key === '/' || (e.code === 'Slash' && !e.shiftKey);
}

export const edgesFeature: Feature = {
  id: 'edges',
  install({ render, scene, selection, camera, status, events, testApi }) {
    const shown = new WeakSet<ViewerInstance>();
    let lines = 0;
    let far: number[] = [];
    /** For edgePixels: one frame drawn without the edges. */
    let suppressed = false;

    const byId = (id: number): Item | undefined => scene.items.find((item) => item.id === id);
    const isOn = (item: Item): boolean => shown.has(item.instance);

    function draw(width: number, height: number): void {
      lines = 0;
      far = [];
      const chosen = scene.items.filter((item) => isOn(item) && item.capabilities.edges && item.instance.drawn);
      if (suppressed || !chosen.length) return;
      const gl = render.viewer.gl;
      const eye = camera.eye();
      gl.bindFramebuffer(gl.FRAMEBUFFER, null);
      gl.viewport(0, 0, width, height);
      gl.enable(gl.DEPTH_TEST);
      gl.depthFunc(gl.LEQUAL);
      gl.depthMask(false);
      gl.disable(gl.BLEND);
      gl.depthRange(0, 1 - DEPTH_PULL);
      try {
        for (const item of chosen) {
          const at = item.instance.location;
          if (Math.hypot((at[0] ?? 0) - eye[0], (at[1] ?? 0) - eye[1], (at[2] ?? 0) - eye[2]) > EDGE_RANGE) {
            far.push(item.id);
            continue;
          }
          lines += item.capabilities.edges?.draw(...EDGE_COLOR) ?? 0;
        }
      } finally {
        gl.depthRange(0, 1);
        gl.depthMask(true);
      }
    }

    events.on('scene-drawn', ({ width, height }) => draw(width, height));

    /** Ctrl+/: switch the selected items that can draw edges. */
    function toggleSelected(): void {
      const chosen = selection.selectedIds().flatMap((id) => {
        const item = byId(id);
        return item && item.capabilities.edges ? [item] : [];
      });
      const last = chosen[chosen.length - 1];
      if (!last) {
        status.setStatus('no edges for the selected');
        return;
      }
      const on = !isOn(last);
      for (const item of chosen) {
        if (on) shown.add(item.instance);
        else shown.delete(item.instance);
      }
      status.setStatus(`edges ${on ? 'on' : 'off'}: ${chosen.length} instance${chosen.length === 1 ? '' : 's'}`);
    }

    window.addEventListener('keydown', (e) => {
      if (!isEdgesKey(e)) return;
      // A field being edited keeps the key (R-VIEW-59).
      if (selection.editingText(e.target)) return;
      e.preventDefault();
      if (!selection.hasSelection()) {
        status.setStatus('Ctrl+/: select an instance first');
        return;
      }
      toggleSelected();
    });

    const edgesState = (): EdgesState => ({
      on: scene.items.filter(isOn).map((item) => item.id),
      far: [...far],
      lines,
      range: EDGE_RANGE,
    });

    /** One frame without time passing, read back. */
    function grab(): Uint8Array {
      render.resize();
      render.draw(0);
      const gl = render.viewer.gl;
      const data = new Uint8Array(render.canvas.width * render.canvas.height * 4);
      gl.readPixels(0, 0, render.canvas.width, render.canvas.height, gl.RGBA, gl.UNSIGNED_BYTE, data);
      return data;
    }

    /**
     * The pixels the edges change, from two frames at the same moment, one
     * without the edges: `count` of them are clearly green; `outside` of
     * those are farther than OFF_BODY pixels from every drawn pixel of the
     * frame without them (a line on the silhouette may cover the pixel
     * beside it); `inRect`
     * of those lie in `rect` (page pixels), when given.
     */
    function edgePixels(rect?: Rect): { count: number; outside: number; inRect: number } {
      suppressed = true;
      let off: Uint8Array;
      try {
        off = grab();
      } finally {
        suppressed = false;
      }
      const on = grab();
      const { width, height } = render.canvas;
      const bg = render.BACKGROUND.map((v) => Math.round(v * 255));
      const box = render.canvas.getBoundingClientRect();
      const k = width / render.canvas.clientWidth;
      const px = (i: number, data: Uint8Array): number => data[i] ?? 0;
      const isBackground = (x: number, y: number): boolean => {
        if (x < 0 || y < 0 || x >= width || y >= height) return true;
        const i = (y * width + x) * 4;
        return [0, 1, 2].every((c) => Math.abs(px(i + c, off) - (bg[c] ?? 0)) <= 1);
      };
      const offBody = (x: number, y: number): boolean => {
        for (let dy = -OFF_BODY; dy <= OFF_BODY; dy++) for (let dx = -OFF_BODY; dx <= OFF_BODY; dx++) if (!isBackground(x + dx, y + dy)) return false;
        return true;
      };
      let count = 0;
      let outside = 0;
      let inRect = 0;
      for (let i = 0, p = 0; i < on.length; i += 4, p++) {
        const [r, g, b] = [px(i, on), px(i + 1, on), px(i + 2, on)];
        const step = Math.max(Math.abs(r - px(i, off)), Math.abs(g - px(i + 1, off)), Math.abs(b - px(i + 2, off)));
        if (step <= 40 || g <= 60 || g <= 1.6 * r || g <= 1.6 * b) continue;
        count++;
        if (offBody(p % width, Math.floor(p / width))) outside++;
        if (rect) {
          // The framebuffer is read bottom row first.
          const x = box.left + (p % width) / k;
          const y = box.top + (height - 1 - Math.floor(p / width)) / k;
          if (x >= rect.left && x < rect.right && y >= rect.top && y < rect.bottom) inRect++;
        }
      }
      return { count, outside, inRect };
    }

    testApi.statePart('edges', edgesState);
    testApi.viewer({ edgesState, edgePixels });
  },
};
