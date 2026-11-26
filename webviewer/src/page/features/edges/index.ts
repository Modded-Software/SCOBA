// The triangle edges of chosen instances, drawn over them in thin green.
// - Ctrl+/ (the edges key of the input map, core/input.ts) switches the edges of the selected instances, all the same way:
//   off when the one selected last shows them, on otherwise;
// - only the edges in front show: they are depth tested against the drawn
//   scene, so the instance itself and the others hide what is behind;
// - they follow the pose: the format draws them with its own vertex shader
//   (the `edges` capability, SPEC-VIEWER 6.2);
// - an instance farther from the eye than EDGE_RANGE shows none: far away
//   the lines run together into a green blot;
// - the choice belongs to the instance shown and is not kept: a reload, a
//   copy, a new model (variant, dataset) start without edges.
// - the triangle under the mouse of an instance showing edges glows and
//   shimmers like glass; one the mouse left keeps its glow and fades out
//   over FADE_MS (R-VIEW-153, core/render/triangleglow.ts).
// The frame draws them after the units (the scene-drawn event), before
// the mouse-over outline: the glows first, the lines over them.

import type { Feature } from '../../core/context';
import { bindingText, keyMatches, resolveInput, type KeyBinding } from '../../core/input';
import { settings } from '../../core/settings';
import type { Item } from '../../core/types';
import type { ViewerInstance } from '../../core/plugin';
import type { Rgb } from '../../core/render/gl';
import { createTriangleGlow, GLOW_FULL, type Glowing } from '../../core/render/triangleglow';

/** The line colour. */
const EDGE_COLOR: Rgb = [0.2, 1.0, 0.3];
/** Farther from the eye than this, in world units, an instance shows no edges. */
export const EDGE_RANGE = 100;
/**
 * The lines' depth is pulled towards the eye by this share, so a line
 * wins over the surface it lies on (lines take no polygon offset).
 */
const DEPTH_PULL = 5e-5;
/** How long a triangle the mouse left takes to fade out, in ms. */
export const FADE_MS = 500;

/** One triangle of one item. */
interface Spot {
  item: number;
  triangle: number;
}

/** What the tests read of the edges (scobaeditor.state().edges). */
export interface EdgesState {
  /** The items with edges on, by id. */
  on: number[];
  /** Of those, the ones too far to draw them in the last frame. */
  far: number[];
  /** Lines drawn in the last frame. */
  lines: number;
  range: number;
  /** The triangle under the mouse, of an item showing edges, in the last frame. */
  hover: Spot | null;
  /** Triangles the mouse left that still glow, with their strength now (GLOW_FULL down to 0). */
  fading: (Spot & { strength: number })[];
  /** Triangles glowing and glass shimmer passes drawn in the last frame. */
  glow: number;
  shimmer: number;
  /** The canvas has the stencil buffer the shimmer needs. */
  stencil: boolean;
  fadeMs: number;
  full: number;
}

export const edgesFeature: Feature = {
  id: 'edges',
  install({ render, scene, selection, camera, status, events, testApi, store }) {
    // Ctrl + "/" by default: the "/" key of a US layout, or any key that types "/" (core/input.ts, R-VIEW-154).
    const edgesKey = (): KeyBinding => resolveInput(store.read(settings.input)).keys.edges;
    const shown = new WeakSet<ViewerInstance>();
    const glow = createTriangleGlow(render.viewer);
    glow.ready.catch(status.reportFailure);
    let lines = 0;
    let far: number[] = [];
    let glowing = 0;
    let shimmering = 0;
    /** The last [clientX, clientY] over the canvas; null off it. */
    let mouse: [number, number] | null = null;
    let hover: Spot | null = null;
    /** Triangles the mouse left, by "item:triangle", with the time it left (performance.now). */
    const fading = new Map<string, Spot & { left: number }>();

    const byId = (id: number): Item | undefined => scene.items.find((item) => item.id === id);
    const isOn = (item: Item): boolean => shown.has(item.instance);
    const keyOf = (spot: Spot): string => `${spot.item}:${spot.triangle}`;
    const strengthAt = (left: number, now: number): number => GLOW_FULL * Math.max(0, 1 - (now - left) / FADE_MS);

    render.canvas.addEventListener('mousemove', (e) => {
      mouse = [e.clientX, e.clientY];
    });
    render.canvas.addEventListener('mouseleave', () => {
      mouse = null;
    });

    /** A page pixel as a drawing-buffer pixel from the top left, or null off the canvas. */
    function bufferPixel(clientX: number, clientY: number): [number, number] | null {
      const { canvas } = render;
      const box = canvas.getBoundingClientRect();
      if (clientX < box.left || clientY < box.top || clientX >= box.right || clientY >= box.bottom) return null;
      const k = canvas.width / canvas.clientWidth;
      return [Math.min(canvas.width - 1, Math.floor((clientX - box.left) * k)), Math.min(canvas.height - 1, Math.floor((clientY - box.top) * k))];
    }

    /** The triangle under the mouse now: of the item under it, when that one shows edges and is near. */
    function pickHover(near: readonly Item[], width: number, height: number): Spot | null {
      const item = selection.hovered();
      const edges = item?.capabilities.edges;
      const at = mouse ? bufferPixel(mouse[0], mouse[1]) : null;
      if (!item || !edges || !at || !near.includes(item)) return null;
      const triangle = glow.pick(edges, at[0], at[1], width, height);
      return triangle === null ? null : { item: item.id, triangle };
    }

    /** The hover of this frame: the one left starts to fade, one come back stops fading. */
    function moveHover(next: Spot | null, now: number): void {
      if (hover && (!next || keyOf(next) !== keyOf(hover))) fading.set(keyOf(hover), { ...hover, left: now });
      if (next) fading.delete(keyOf(next));
      hover = next;
      for (const [key, spot] of fading) {
        const item = byId(spot.item);
        if (now - spot.left >= FADE_MS || !item || !isOn(item)) fading.delete(key);
      }
    }

    function draw(width: number, height: number): void {
      lines = 0;
      far = [];
      glowing = 0;
      shimmering = 0;
      const now = performance.now();
      const chosen = scene.items.filter((item) => isOn(item) && item.capabilities.edges && item.instance.drawn);
      const eye = camera.eye();
      const near = chosen.filter((item) => {
        const at = item.instance.location;
        const inRange = Math.hypot((at[0] ?? 0) - eye[0], (at[1] ?? 0) - eye[1], (at[2] ?? 0) - eye[2]) <= EDGE_RANGE;
        if (!inRange) far.push(item.id);
        return inRange;
      });
      moveHover(pickHover(near, width, height), now);
      if (!near.length) return;
      const list: Glowing[] = [];
      for (const spot of [...fading.values(), ...(hover ? [{ ...hover, left: null }] : [])]) {
        const item = byId(spot.item);
        const edges = item?.capabilities.edges;
        if (!item || !edges || !near.includes(item)) continue;
        list.push({ edges, triangle: spot.triangle, strength: spot.left === null ? GLOW_FULL : strengthAt(spot.left, now), hovered: spot.left === null });
      }
      const drawn = glow.draw(list, width, height, now / 1000);
      glowing = drawn.glow;
      shimmering = drawn.shimmer;
      const gl = render.viewer.gl;
      gl.bindFramebuffer(gl.FRAMEBUFFER, null);
      gl.viewport(0, 0, width, height);
      gl.enable(gl.DEPTH_TEST);
      gl.depthFunc(gl.LEQUAL);
      gl.depthMask(false);
      gl.disable(gl.BLEND);
      gl.depthRange(0, 1 - DEPTH_PULL);
      try {
        for (const item of near) lines += item.capabilities.edges?.draw(...EDGE_COLOR) ?? 0;
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
      const key = edgesKey();
      if (!keyMatches(key, e)) return;
      // A field being edited keeps the key (R-VIEW-59).
      if (selection.editingText(e.target)) return;
      e.preventDefault();
      if (!selection.hasSelection()) {
        status.setStatus(`${bindingText(key)}: select an instance first`);
        return;
      }
      toggleSelected();
    });

    const edgesState = (): EdgesState => {
      const now = performance.now();
      return {
        on: scene.items.filter(isOn).map((item) => item.id),
        far: [...far],
        lines,
        range: EDGE_RANGE,
        hover: hover ? { ...hover } : null,
        fading: [...fading.values()].map(({ item, triangle, left }) => ({ item, triangle, strength: strengthAt(left, now) })),
        glow: glowing,
        shimmer: shimmering,
        stencil: glow.stencil,
        fadeMs: FADE_MS,
        full: GLOW_FULL,
      };
    };

    /** For the tests: whether triangle `triangle` of item `id` alone covers a page pixel, as drawn now. */
    function edgesCovers(id: number, triangle: number, clientX: number, clientY: number): boolean {
      const edges = byId(id)?.capabilities.edges;
      const at = bufferPixel(clientX, clientY);
      if (!edges) throw new Error(`item ${id} cannot draw edges`);
      if (!at) throw new Error(`(${clientX}, ${clientY}) is off the canvas`);
      return glow.covers(edges, triangle, at[0], at[1], render.canvas.width, render.canvas.height);
    }

    testApi.statePart('edges', edgesState);
    testApi.viewer({ edgesState, edgesCovers });
  },
};
