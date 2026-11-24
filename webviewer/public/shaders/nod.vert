// The nod vertex shader (src/formats/nod). Skinning in the file's axes,
// then u_world: the instance's matrix times the Y mirror
// (SPEC-VIEWER-GHOST 4.8). Bone matrices are 4 RGBA texels each in
// u_boneMap, one row.
precision highp float;
attribute vec3 a_position;
attribute vec3 a_normal;
attribute vec2 a_uv;
attribute vec4 a_bones;
attribute vec4 a_weights;
uniform mat4 u_VP;
uniform mat4 u_world;
uniform sampler2D u_boneMap;
uniform float u_texel;
uniform float u_skinned;
varying vec3 v_normal;
varying vec3 v_position;
varying vec2 v_uv;

mat4 bone(float index) {
  float x = index * 4.0 * u_texel + 0.5 * u_texel;
  return mat4(texture2D(u_boneMap, vec2(x, 0.5)), texture2D(u_boneMap, vec2(x + u_texel, 0.5)), texture2D(u_boneMap, vec2(x + 2.0 * u_texel, 0.5)), texture2D(u_boneMap, vec2(x + 3.0 * u_texel, 0.5)));
}

void main() {
  mat4 skin = mat4(1.0);
  if (u_skinned > 0.5) {
    skin = bone(a_bones.x) * a_weights.x + bone(a_bones.y) * a_weights.y + bone(a_bones.z) * a_weights.z + bone(a_bones.w) * a_weights.w;
  }
  vec4 world = u_world * skin * vec4(a_position, 1.0);
  v_position = world.xyz;
  v_normal = normalize(mat3(u_world) * mat3(skin) * a_normal);
  v_uv = a_uv;
  gl_Position = u_VP * world;
}
