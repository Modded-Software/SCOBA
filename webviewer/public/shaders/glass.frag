// The glass shimmer over the triangle under the mouse (core/render/triangleglow.ts):
// a full-screen quad (outline.vert) that the stencil keeps to that triangle.
// Two bright bands sweep across, a fine ripple and a faint rainbow tint
// move with them. Added onto the canvas (blend ONE, ONE).
precision mediump float;

uniform float u_time; // seconds
uniform vec2 u_size; // drawing buffer, pixels
uniform float u_gain;
varying vec2 v_uv;

void main() {
  vec2 p = gl_FragCoord.xy / u_size.y;
  float d = p.x * 0.8 + p.y * 0.6;
  float sweep = pow(max(0.0, sin(d * 14.0 - u_time * 2.6)), 28.0);
  float glint = pow(max(0.0, sin(d * 5.0 + p.y * 3.0 - u_time * 1.4)), 48.0) * 0.7;
  float ripple = 0.5 + 0.5 * sin(p.x * 90.0 + u_time * 3.1) * sin(p.y * 83.0 - u_time * 2.3);
  vec3 tint = 0.5 + 0.5 * cos(6.2831 * (d * 1.7 + u_time * 0.12 + vec3(0.0, 0.33, 0.67)));
  vec3 color = vec3(0.85, 1.0, 0.92) * (sweep + glint) + tint * (0.06 + 0.06 * ripple);
  gl_FragColor = vec4(color * u_gain, 1.0);
}
