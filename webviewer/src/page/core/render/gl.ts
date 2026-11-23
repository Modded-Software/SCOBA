// Small WebGL helpers for the page's own shaders (ground, outline).

import type Shader from '@renderer/viewer/gl/shader';
import type ModelViewer from '@renderer/viewer/viewer';

/** An rgb colour, each channel 0 to 1. */
export type Rgb = [number, number, number];

/** A uniform of a shader. Null when the compiler dropped it: WebGL then ignores the set. */
export function uniform(shader: Shader, name: string): WebGLUniformLocation | null {
  return shader.uniforms[name] ?? null;
}

/** A vertex attribute of a shader. The page's shaders all use theirs, so a missing one is an error. */
export function attrib(shader: Shader, name: string): number {
  const location = shader.attribs[name];
  if (location === undefined) throw new Error(`shader has no attribute ${name}`);
  return location;
}

/** The text of a shader file the server serves. `who` names the caller in the error. */
export async function shaderSource(who: string, url: string): Promise<string> {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${who}: ${response.status} ${url}`);
  return response.text();
}

/** Compile a shader from two files the server serves; `prefix` goes before the fragment source. */
export async function loadShader(viewer: ModelViewer, who: string, vertexUrl: string, fragmentUrl: string, prefix = ''): Promise<Shader> {
  const [vertex, fragment] = await Promise.all([shaderSource(who, vertexUrl), shaderSource(who, fragmentUrl)]);
  return viewer.webgl.createShader(vertex, prefix + fragment);
}

/** A buffer holding the four corners of the unit square, for a TRIANGLE_STRIP. */
export function quadBuffer(gl: WebGLRenderingContext): WebGLBuffer {
  const buffer = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
  return buffer;
}
