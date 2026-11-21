// Mouse-over outline (outline.js): a full-screen quad.
attribute vec2 a_corner;
varying vec2 v_uv;

void main() {
  v_uv = a_corner * 0.5 + 0.5;
  gl_Position = vec4(a_corner, 0.0, 1.0);
}
