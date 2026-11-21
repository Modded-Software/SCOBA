// Mouse-over outline (outline.js): one blur pass along u_step (one texel
// times the spread), 9 taps.
precision mediump float;
uniform sampler2D u_map;
uniform vec2 u_step;
uniform float u_first; // 1: the input is the raw mask
varying vec2 v_uv;

// Coverage of the mask: anything the unit drew.
float cover(vec4 c) {
  return max(c.a, max(c.r, max(c.g, c.b))) > 0.004 ? 1.0 : 0.0;
}

float at(vec2 uv) {
  vec4 c = texture2D(u_map, uv);
  return u_first > 0.5 ? cover(c) : c.r;
}

void main() {
  float s = at(v_uv) * 0.2270270;
  s += (at(v_uv + u_step * 1.0) + at(v_uv - u_step * 1.0)) * 0.1945946;
  s += (at(v_uv + u_step * 2.0) + at(v_uv - u_step * 2.0)) * 0.1216216;
  s += (at(v_uv + u_step * 3.0) + at(v_uv - u_step * 3.0)) * 0.0540541;
  s += (at(v_uv + u_step * 4.0) + at(v_uv - u_step * 4.0)) * 0.0162162;
  gl_FragColor = vec4(s, s, s, 1.0);
}
