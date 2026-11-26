// Triangle picking and the triangle glow of edges mode (features/edges,
// R-VIEW-153).
// - pick: which triangle of one instance is drawn at a canvas pixel. The
//   triangles are drawn in flat colours into a buffer of one pixel, with
//   depth, and the pixel is read back, as pickbuffer.ts does for
//   instances. Two passes keep the draws few: runs of `step` triangles
//   first, then the triangles of the run found, one by one (about 2 x the
//   square root of the count).
// - draw: each glowing triangle added in the glow colour at its own
//   strength, over its surface (the depth is pulled as for the edge
//   lines). The hovered one is marked in the stencil, and the glass
//   shimmer (shaders/glass.frag) is added inside that mark only.

import type ModelViewer from '@renderer/viewer/viewer';
import type Shader from '@renderer/viewer/gl/shader';
import type { Capabilities, TriangleRun } from '../plugin';
import { attrib, quadBuffer, shaderSource, uniform, type Rgb } from './gl';

type Edges = NonNullable<Capabilities['edges']>;

/** The glow colour, added. */
const GLOW_COLOR: Rgb = [0.35, 0.9, 0.45];
/** The strength of a hovered triangle's glow; a fading one goes from this to 0. */
export const GLOW_FULL = 0.55;
/** The glass shimmer's strength. */
const GLASS_GAIN = 0.9;
/** The edge lines' depth pull (features/edges): the glow wins over the surface it lies on too. */
const DEPTH_PULL = 5e-5;

/** One glowing triangle: whose, which, how strong, and whether it is the hovered one. */
export interface Glowing {
  readonly edges: Edges;
  readonly triangle: number;
  readonly strength: number;
  readonly hovered: boolean;
}

export interface TriangleGlow {
  /** Settles once the glass shader has loaded; rejects with the reason when it cannot. */
  readonly ready: Promise<void>;
  /** The canvas has a stencil buffer (the shimmer needs it). */
  readonly stencil: boolean;
  /** The triangle of `edges` drawn at drawing-buffer pixel (x, y) from the top left, or null. */
  pick(edges: Edges, x: number, y: number, w: number, h: number): number | null;
  /** Whether triangle `k` alone covers pixel (x, y): the tests' check of a pick. */
  covers(edges: Edges, k: number, x: number, y: number, w: number, h: number): boolean;
  /** Draw the glows onto the canvas, after the scene. Returns the triangles glowing and the shimmer passes drawn. */
  draw(list: readonly Glowing[], w: number, h: number, seconds: number): { glow: number; shimmer: number };
}

/** Colour n (from 1) over three bytes; 0 is "nothing". */
const code = (n: number): TriangleRun['color'] => [(n & 255) / 255, ((n >> 8) & 255) / 255, ((n >> 16) & 255) / 255, 1];

export function createTriangleGlow(viewer: ModelViewer): TriangleGlow {
  const gl = viewer.gl;
  const stencil = gl.getContextAttributes()?.stencil === true;
  let glass: Shader | null = null;
  const ready = Promise.all([shaderSource('glass', '/shaders/outline.vert'), shaderSource('glass', '/shaders/glass.frag')]).then(([vertex, fragment]) => {
    glass = viewer.webgl.createShader(vertex, fragment);
  });
  const quad = quadBuffer(gl);

  // The one-pixel pick buffer: colour and depth.
  const texture = gl.createTexture();
  const depth = gl.createRenderbuffer();
  const frame = gl.createFramebuffer();
  gl.bindTexture(gl.TEXTURE_2D, texture);
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 1, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE, null);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
  gl.bindRenderbuffer(gl.RENDERBUFFER, depth);
  gl.renderbufferStorage(gl.RENDERBUFFER, gl.DEPTH_COMPONENT16, 1, 1);
  gl.bindFramebuffer(gl.FRAMEBUFFER, frame);
  gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, texture, 0);
  gl.framebufferRenderbuffer(gl.FRAMEBUFFER, gl.DEPTH_ATTACHMENT, gl.RENDERBUFFER, depth);
  const status = gl.checkFramebufferStatus(gl.FRAMEBUFFER);
  gl.bindFramebuffer(gl.FRAMEBUFFER, null);
  if (status !== gl.FRAMEBUFFER_COMPLETE) throw new Error(`triangle pick buffer: framebuffer incomplete: ${status}`);
  const pixel = new Uint8Array(4);

  /** Draw `runs` into the pick buffer at pixel (x, y); the colour number read there, 0 for none. */
  function readAt(edges: Edges, runs: readonly TriangleRun[], x: number, y: number, w: number, h: number): number {
    gl.bindFramebuffer(gl.FRAMEBUFFER, frame);
    gl.viewport(-x, -(h - 1 - y), w, h);
    gl.scissor(0, 0, 1, 1);
    gl.enable(gl.DEPTH_TEST);
    gl.depthFunc(gl.LEQUAL);
    gl.depthMask(true);
    gl.disable(gl.BLEND);
    gl.disable(gl.CULL_FACE);
    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    edges.drawTriangles(runs);
    gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixel);
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    gl.viewport(0, 0, w, h);
    gl.scissor(0, 0, w, h);
    gl.enable(gl.CULL_FACE);
    gl.activeTexture(gl.TEXTURE0);
    const [r = 0, g = 0, b = 0] = pixel;
    return r + (g << 8) + (b << 16);
  }

  function pick(edges: Edges, x: number, y: number, w: number, h: number): number | null {
    const count = edges.triangles();
    if (count <= 0) return null;
    const step = Math.ceil(Math.sqrt(count));
    const chunks: TriangleRun[] = [];
    for (let first = 0, n = 1; first < count; first += step, n++) chunks.push({ first, count: Math.min(step, count - first), color: code(n) });
    const chunk = readAt(edges, chunks, x, y, w, h);
    if (chunk === 0) return null;
    const start = (chunk - 1) * step;
    const ones: TriangleRun[] = [];
    for (let k = start; k < Math.min(start + step, count); k++) ones.push({ first: k, count: 1, color: code(k - start + 1) });
    const one = readAt(edges, ones, x, y, w, h);
    return one === 0 ? null : start + one - 1;
  }

  function covers(edges: Edges, k: number, x: number, y: number, w: number, h: number): boolean {
    return readAt(edges, [{ first: k, count: 1, color: code(1) }], x, y, w, h) === 1;
  }

  function shimmer(w: number, h: number, seconds: number): number {
    if (glass === null || !stencil) return 0;
    gl.stencilFunc(gl.EQUAL, 1, 0xff);
    gl.stencilOp(gl.KEEP, gl.KEEP, gl.KEEP);
    gl.disable(gl.DEPTH_TEST);
    glass.use();
    gl.bindBuffer(gl.ARRAY_BUFFER, quad);
    gl.vertexAttribPointer(attrib(glass, 'a_corner'), 2, gl.FLOAT, false, 0, 0);
    gl.uniform1f(uniform(glass, 'u_time'), seconds);
    gl.uniform2f(uniform(glass, 'u_size'), w, h);
    gl.uniform1f(uniform(glass, 'u_gain'), GLASS_GAIN);
    gl.blendFunc(gl.ONE, gl.ONE);
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    gl.enable(gl.DEPTH_TEST);
    return 1;
  }

  function draw(list: readonly Glowing[], w: number, h: number, seconds: number): { glow: number; shimmer: number } {
    if (!list.length) return { glow: 0, shimmer: 0 };
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    gl.viewport(0, 0, w, h);
    gl.scissor(0, 0, w, h);
    gl.enable(gl.DEPTH_TEST);
    gl.depthFunc(gl.LEQUAL);
    gl.depthMask(false);
    gl.depthRange(0, 1 - DEPTH_PULL);
    gl.disable(gl.CULL_FACE);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE);
    let glow = 0;
    let shimmered = 0;
    try {
      for (const one of list) {
        if (one.strength <= 0) continue;
        const run: TriangleRun = { first: one.triangle, count: 1, color: [...GLOW_COLOR, one.strength] };
        if (!one.hovered || !stencil) {
          glow += one.edges.drawTriangles([run]);
          continue;
        }
        // The hovered one: its glow marks the stencil, the shimmer fills the mark.
        gl.clearStencil(0);
        gl.stencilMask(0xff);
        gl.clear(gl.STENCIL_BUFFER_BIT);
        gl.enable(gl.STENCIL_TEST);
        gl.stencilFunc(gl.ALWAYS, 1, 0xff);
        gl.stencilOp(gl.KEEP, gl.KEEP, gl.REPLACE);
        const drawn = one.edges.drawTriangles([run]);
        glow += drawn;
        if (drawn) shimmered += shimmer(w, h, seconds);
        gl.disable(gl.STENCIL_TEST);
        gl.blendFunc(gl.SRC_ALPHA, gl.ONE);
      }
    } finally {
      gl.disable(gl.STENCIL_TEST);
      gl.disable(gl.BLEND);
      gl.depthRange(0, 1);
      gl.depthMask(true);
      gl.enable(gl.CULL_FACE);
      gl.enable(gl.DEPTH_TEST);
    }
    return { glow, shimmer: shimmered };
  }

  return { ready, stencil, pick, covers, draw };
}
