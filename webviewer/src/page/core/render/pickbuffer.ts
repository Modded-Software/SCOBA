// Picking by pixel: which instance is drawn at one canvas pixel.
// The instances are drawn in flat colours, one per instance, into a buffer
// of a single pixel (the viewport is shifted so that the asked pixel lands
// on it), with depth, and the pixel is read back: the nearest solid surface
// wins, exactly as on screen. The flat-colour draw is the instance's
// renderPick (SPEC-VIEWER 6.1).

import type ModelViewer from '@renderer/viewer/viewer';
import type { ViewerInstance } from '../plugin';

export interface PickBuffer {
  /**
   * The index in `instances` of the one drawn at canvas pixel (x, y), or -1.
   * x, y count drawing-buffer pixels from the top left; w, h is the buffer size.
   */
  read(instances: readonly ViewerInstance[], x: number, y: number, w: number, h: number): number;
}

export function createPickBuffer(viewer: ModelViewer): PickBuffer {
  const gl = viewer.gl;
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
  if (status !== gl.FRAMEBUFFER_COMPLETE) throw new Error(`pick buffer: framebuffer incomplete: ${status}`);

  const pixel = new Uint8Array(4);

  return {
    read(instances, x, y, w, h) {
      if (instances.length === 0) return -1;
      gl.bindFramebuffer(gl.FRAMEBUFFER, frame);
      // The asked pixel lands on the buffer's only pixel (GL counts rows from the bottom).
      gl.viewport(-x, -(h - 1 - y), w, h);
      gl.scissor(0, 0, 1, 1);
      gl.enable(gl.DEPTH_TEST);
      gl.depthMask(true);
      gl.disable(gl.BLEND);
      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
      instances.forEach((instance, i) => {
        // Colour 0 is "nothing": instance i is colour i + 1, over three bytes.
        const n = i + 1;
        instance.renderPick((n & 255) / 255, ((n >> 8) & 255) / 255, ((n >> 16) & 255) / 255);
      });
      gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixel);
      gl.bindFramebuffer(gl.FRAMEBUFFER, null);
      gl.viewport(0, 0, w, h);
      gl.scissor(0, 0, w, h);
      gl.activeTexture(gl.TEXTURE0);
      const [r = 0, g = 0, b = 0] = pixel;
      return r + (g << 8) + (b << 16) - 1;
    },
  };
}
