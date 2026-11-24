// Mouse-over outline: a feathered green glow around the silhouette of one
// unit, as the game draws it. The unit is drawn alone into a mask, the mask
// is blurred in two passes, and the blur is added outside the silhouette.
// Shaders: shaders/outline.vert, outline-blur.frag, outline-compose.frag.

import type ModelViewer from '@renderer/viewer/viewer';
import type Shader from '@renderer/viewer/gl/shader';
import type { ViewerInstance } from '../plugin';
import { attrib, quadBuffer, shaderSource, uniform, type Rgb } from './gl';

/** Texels between blur taps: the feather is about 13 px wide. */
const SPREAD = 1.6;

export interface Outline {
  color: Rgb;
  gain: number;
  /** Settles once the shaders have loaded; rejects with the reason when they cannot. */
  ready: Promise<void>;
  /** Draw the glow around `instance` onto the canvas. Call after the scene. Nothing until the shaders have loaded. */
  draw(instance: ViewerInstance, w: number, h: number): void;
}

interface Target {
  texture: WebGLTexture;
  frame: WebGLFramebuffer;
}

/** An outline for one viewer. It draws once its shaders have loaded. */
export function createOutline(viewer: ModelViewer): Outline {
  const gl = viewer.gl;
  let shaders: { blur: Shader; compose: Shader } | null = null;
  const files = ['/shaders/outline.vert', '/shaders/outline-blur.frag', '/shaders/outline-compose.frag'];
  const ready = Promise.all(files.map((url) => shaderSource('outline', url))).then(([vertex = '', blur = '', compose = '']) => {
    shaders = { blur: viewer.webgl.createShader(vertex, blur), compose: viewer.webgl.createShader(vertex, compose) };
  });
  const quad = quadBuffer(gl);

  let width = 0;
  let height = 0;
  const target = (): Target => ({ texture: gl.createTexture(), frame: gl.createFramebuffer() });
  const mask = target();
  const across = target();
  const down = target();
  const depth = gl.createRenderbuffer();

  function resize(w: number, h: number): void {
    if (w === width && h === height) return;
    width = w;
    height = h;
    for (const t of [mask, across, down]) {
      gl.bindTexture(gl.TEXTURE_2D, t.texture);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, w, h, 0, gl.RGBA, gl.UNSIGNED_BYTE, null);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      gl.bindFramebuffer(gl.FRAMEBUFFER, t.frame);
      gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, t.texture, 0);
    }
    // The mask keeps the unit's own depth order (a front part over a back part).
    gl.bindRenderbuffer(gl.RENDERBUFFER, depth);
    gl.renderbufferStorage(gl.RENDERBUFFER, gl.DEPTH_COMPONENT16, w, h);
    gl.bindFramebuffer(gl.FRAMEBUFFER, mask.frame);
    gl.framebufferRenderbuffer(gl.FRAMEBUFFER, gl.DEPTH_ATTACHMENT, gl.RENDERBUFFER, depth);
    const status = gl.checkFramebufferStatus(gl.FRAMEBUFFER);
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    if (status !== gl.FRAMEBUFFER_COMPLETE) throw new Error(`outline: mask framebuffer incomplete: ${status}`);
  }

  function pass(shader: Shader, to: Target | null): void {
    gl.bindFramebuffer(gl.FRAMEBUFFER, to ? to.frame : null);
    gl.viewport(0, 0, width, height);
    gl.scissor(0, 0, width, height);
    shader.use();
    gl.bindBuffer(gl.ARRAY_BUFFER, quad);
    gl.vertexAttribPointer(attrib(shader, 'a_corner'), 2, gl.FLOAT, false, 0, 0);
  }

  function bind(texture: WebGLTexture, unit: number, location: WebGLUniformLocation | null): void {
    gl.activeTexture(gl.TEXTURE0 + unit);
    gl.bindTexture(gl.TEXTURE_2D, texture);
    gl.uniform1i(location, unit);
  }

  const outline: Outline = {
    color: [0.25, 1.0, 0.3],
    gain: 2.2,
    ready,
    draw(instance, w, h) {
      if (shaders === null) return;
      const { blur, compose } = shaders;
      resize(w, h);
      // 1. The unit alone into the mask.
      gl.bindFramebuffer(gl.FRAMEBUFFER, mask.frame);
      gl.viewport(0, 0, w, h);
      gl.scissor(0, 0, w, h);
      gl.depthMask(true);
      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
      instance.renderOpaque();
      gl.disable(gl.DEPTH_TEST);
      gl.depthMask(false);
      gl.disable(gl.CULL_FACE);
      gl.disable(gl.BLEND);
      // 2. Blur across, 3. blur down.
      pass(blur, across);
      bind(mask.texture, 0, uniform(blur, 'u_map'));
      gl.uniform2f(uniform(blur, 'u_step'), SPREAD / w, 0);
      gl.uniform1f(uniform(blur, 'u_first'), 1);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
      pass(blur, down);
      bind(across.texture, 0, uniform(blur, 'u_map'));
      gl.uniform2f(uniform(blur, 'u_step'), 0, SPREAD / h);
      gl.uniform1f(uniform(blur, 'u_first'), 0);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
      // 4. Onto the canvas, outside the silhouette.
      pass(compose, null);
      bind(down.texture, 0, uniform(compose, 'u_blur'));
      bind(mask.texture, 1, uniform(compose, 'u_mask'));
      gl.uniform3fv(uniform(compose, 'u_color'), outline.color);
      gl.uniform1f(uniform(compose, 'u_gain'), outline.gain);
      gl.enable(gl.BLEND);
      gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
      gl.disable(gl.BLEND);
      gl.enable(gl.CULL_FACE);
      gl.enable(gl.DEPTH_TEST);
      gl.depthMask(true);
      gl.activeTexture(gl.TEXTURE0);
    },
  };
  return outline;
}
