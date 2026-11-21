// Hex grid ground. Pointy-top hexagons, one world unit from side to side
// (along x). Two offset rectangular lattices; the nearer centre owns the
// pixel. MAX_SPOTS is defined by ground.js before this source.
//
// Levels (aperture 7): level n is the level 0 grid scaled by sqrt(7)^n and
// turned by n * atan(sqrt(3) / 5) (19.1 degrees). Each hexagon of level
// n + 1 is centred on a hexagon of level n and covers the area of seven,
// and every level's centres are level 0 centres. Per pixel, the finest
// level whose cells are at least u_minPx pixels wide is drawn, fading out
// as it shrinks towards that size over sqrt(7), with the next level over it
// as the group outline. So cells never get arbitrarily small on screen.
#extension GL_OES_standard_derivatives : enable
precision highp float;

uniform vec2 u_center;
uniform float u_radius;
uniform float u_cell;
// The least cell width in pixels before the next level takes over.
uniform float u_minPx;
uniform vec3 u_line;
uniform vec3 u_fill;
// Glow spots: x, y, radius. Units and the mouse.
uniform vec3 u_spots[MAX_SPOTS];
uniform float u_spotCount;
// Unit rings: x, y, radius, width (world units). 0 width: no ring.
// Ring 0 is the selection, ring 1 the mouse-over.
uniform vec4 u_rings[2];
uniform vec3 u_ringColor[2];
varying vec2 v_world;

// 1 on a ring's circle, smooth over one pixel at its edges.
float ring(vec4 r) {
  if (r.w <= 0.0) return 0.0;
  float d = abs(distance(v_world, r.xy) - r.z);
  float px = length(vec2(dFdx(v_world.x), dFdy(v_world.x)));
  return 1.0 - smoothstep(0.5 * r.w, 0.5 * r.w + px, d);
}

// The least glow radius, in pixels: a spot stays visible when zoomed out.
const float MIN_GLOW_PX = 60.0;

// 1 at a spot, dropping smoothly to 0 at its radius; the strongest spot wins.
float glow(float perPx) {
  float g = 0.0;
  for (int i = 0; i < MAX_SPOTS; i++) {
    if (float(i) >= u_spotCount) break;
    vec3 s = u_spots[i];
    float k = 1.0 - smoothstep(0.0, max(s.z, MIN_GLOW_PX * perPx), distance(v_world, s.xy));
    g = max(g, k);
  }
  return g;
}

const vec2 LATTICE = vec2(1.0, 1.7320508);

// Offset of p from the centre of its hexagon.
vec2 hexOffset(vec2 p) {
  vec2 h = LATTICE * 0.5; // "half" is a reserved word in GLSL ES
  vec2 a = mod(p, LATTICE) - h;
  vec2 b = mod(p - h, LATTICE) - h;
  return dot(a, a) < dot(b, b) ? a : b;
}

// 0.5 on the border, 0 at the centre.
float hexRadius(vec2 offset) {
  offset = abs(offset);
  return max(dot(offset, vec2(0.5, 0.8660254)), offset.x);
}

// Unit normal of the nearest border side, pointing out of the cell.
vec2 hexNormal(vec2 offset) {
  vec2 s = vec2(offset.x < 0.0 ? -1.0 : 1.0, offset.y < 0.0 ? -1.0 : 1.0);
  vec2 o = abs(offset);
  return dot(o, vec2(0.5, 0.8660254)) > o.x ? s * vec2(0.5, 0.8660254) : vec2(s.x, 0.0);
}

const float SQRT7 = 2.6457513;
const float TURN = 0.3334731; // atan(sqrt(3) / 5): the turn from one level to the next

// 1 on a border of the level `level` grid, smooth over a pixel.
float levelLine(float level) {
  float a = -level * TURN;
  float c = cos(a);
  float s = sin(a);
  vec2 w = v_world / (u_cell * pow(SQRT7, level));
  vec2 p = vec2(c * w.x - s * w.y, s * w.x + c * w.y);
  vec2 offset = hexOffset(p);
  float edge = 0.5 - hexRadius(offset); // distance to the border, in cells
  // One pixel in cells, across the border. From the derivatives of the
  // position, which are smooth: the derivatives of `edge` cancel where a
  // 2x2 pixel block straddles a border (edge rises on both sides), and the
  // line then vanished there, which made it look dashed.
  vec2 n = hexNormal(offset);
  float width = length(vec2(dot(n, dFdx(p)), dot(n, dFdy(p))));
  // Solid within 0.75 px of the border, so every border covers at least one
  // whole pixel wherever it falls on the pixel grid.
  return 1.0 - smoothstep(0.75 * width, 1.5 * width, edge);
}

void main() {
  // World units per pixel here, by area (the square root of the pixel's
  // footprint on the ground), and the level whose cell is u_minPx pixels.
  // By area, a cell seen at a grazing angle (wide, but flat on screen)
  // keeps its level until it is small both ways.
  float perPx = sqrt(abs(dFdx(v_world.x) * dFdy(v_world.y) - dFdx(v_world.y) * dFdy(v_world.x)));
  float t = max(0.0, log(u_minPx * perPx / u_cell) / log(SQRT7));
  float fine = floor(t);
  // Level `fine` is u_minPx / sqrt(7)^fract(t) pixels wide: full at
  // u_minPx, gone at u_minPx / sqrt(7). Level fine + 1, always drawn, is
  // between u_minPx and sqrt(7) * u_minPx. Close up (t clamped at 0) both
  // are larger and both show.
  float keep = 1.0 - fract(t);
  float line = max(levelLine(fine) * keep, levelLine(fine + 1.0));

  // Fade out towards the rim of the quad.
  float fade = 1.0 - smoothstep(0.45, 1.0, length(v_world - u_center) / u_radius);
  float lit = glow(perPx);

  // Faint away from units (operator 2026-11-21); full strength near them.
  vec3 color = mix(u_fill, u_line, line);
  float alpha = mix(0.015 + 0.085 * lit, 0.07 + 0.75 * lit, line) * fade;
  // Rings draw over the grid, unfaded: the mouse-over first, the selection on top.
  for (int i = 1; i >= 0; i--) {
    float k = ring(u_rings[i]);
    color = mix(color, u_ringColor[i], k);
    alpha = mix(alpha, 1.0, k);
  }
  gl_FragColor = vec4(color, alpha);
}
