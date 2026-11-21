// Ground quad: a square of half-size u_radius around u_center on z = 0.
attribute vec2 a_corner;
uniform mat4 u_VP;
uniform vec2 u_center;
uniform float u_radius;
varying vec2 v_world;

void main() {
  v_world = u_center + a_corner * u_radius;
  gl_Position = u_VP * vec4(v_world, 0.0, 1.0);
}
