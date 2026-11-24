// The nod fragment shader (src/formats/nod). u_kind: 0 solid, 1 cutout,
// 2 added, 3 blended (materials.ts). u_pick above 0 alpha: the pick draw.
precision mediump float;
uniform sampler2D u_texture;
uniform float u_kind;
uniform vec3 u_lightPos;
uniform float u_highlight;
uniform vec4 u_pick;
varying vec3 v_normal;
varying vec3 v_position;
varying vec2 v_uv;

void main() {
  vec4 color = texture2D(u_texture, v_uv);
  if (u_kind > 0.5 && u_kind < 1.5 && color.a < 0.5) discard;
  if (u_pick.a > 0.0) {
    gl_FragColor = u_pick;
    return;
  }
  if (u_kind > 1.5 && u_kind < 2.5) {
    gl_FragColor = vec4(color.rgb, 1.0);
    return;
  }
  float lambert = max(dot(normalize(v_normal), normalize(u_lightPos - v_position)), 0.0);
  vec3 lit = color.rgb * (0.35 + 0.75 * lambert);
  lit += (lit * 0.5 + vec3(0.06)) * u_highlight;
  gl_FragColor = vec4(lit, u_kind > 2.5 ? color.a : 1.0);
}
