// Mouse-over outline (outline.js): the blur outside the mask, in the
// outline colour.
precision mediump float;
uniform sampler2D u_blur;
uniform sampler2D u_mask;
uniform vec3 u_color;
uniform float u_gain;
varying vec2 v_uv;

// Coverage of the mask: anything the unit drew.
float cover(vec4 c) {
  return max(c.a, max(c.r, max(c.g, c.b))) > 0.004 ? 1.0 : 0.0;
}

void main() {
  float inside = cover(texture2D(u_mask, v_uv));
  float g = clamp(texture2D(u_blur, v_uv).r * u_gain, 0.0, 1.0) * (1.0 - inside);
  gl_FragColor = vec4(u_color, g);
}
