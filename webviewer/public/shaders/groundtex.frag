// The ground texture under the grid (render/ground.ts): its colour,
// repeated every u_tile world units, not lit. It fades out towards the rim
// of the quad as the grid does.
precision highp float;

uniform sampler2D u_texture;
uniform float u_tile;
uniform vec2 u_center;
uniform float u_radius;
varying vec2 v_world;

void main() {
  vec3 color = texture2D(u_texture, v_world / u_tile).rgb;
  float fade = 1.0 - smoothstep(0.45, 1.0, length(v_world - u_center) / u_radius);
  gl_FragColor = vec4(color, fade);
}
