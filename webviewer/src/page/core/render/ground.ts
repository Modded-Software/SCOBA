// The ground: a green hexagonal grid on z = 0, drawn as one quad around the
// camera target, its size growing with the camera distance. The hexagons
// are computed per pixel in the fragment shader (shaders/ground.frag), so
// they stay sharp at any distance; seven make the next level's hexagon, and
// the level follows the zoom so cells never get arbitrarily small.
// The grid is faint, except around units (and the mouse): there it glows,
// fading out with the distance.

import type ModelViewer from '@renderer/viewer/viewer';
import type Camera from '@renderer/viewer/camera';
import type Shader from '@renderer/viewer/gl/shader';
import { attrib, loadShader, quadBuffer, uniform, type Rgb } from './gl';

/** Glow spots the shader takes at most; fewer when the GPU has fewer uniform vectors. */
const SPOT_CAP = 256;
/** Fragment uniform vectors the ground shader uses besides the spots, with room to spare. */
const OTHER_UNIFORMS = 32;
/** Rings the shader holds: the selected one, the mouse-over, and the other selected ones. */
const MAX_RINGS = 96;

/** Where the grid glows: x, y, radius, and 1 for a model with HD textures (blue). */
export type Spot = readonly [number, number, number, number];

/** A ring on the ground around a unit. */
export interface Ring {
  x: number;
  y: number;
  radius: number;
  width: number;
  color: Rgb;
}

/** [selected last, mouse-over, other selected ones...]. */
export type Rings = [Ring | null, Ring | null, ...Ring[]];

export interface Ground {
  enabled: boolean;
  cell: number;
  /** The quad's half size: at least `radius`, and `reach` times the camera distance. */
  radius: number;
  reach: number;
  /** The least on-screen cell width in pixels before the next level takes over (shaders/ground.frag). */
  minPx: number;
  /** The half size of the last drawn quad (for the tests). */
  drawnRadius: number;
  /** Glow spots the shader holds, and how many the last frame used (for the tests). */
  maxSpots: number;
  spotsDrawn: number;
  line: Rgb;
  fill: Rgb;
  /** The same two for the glow of a model that has HD textures: blue. */
  lineHd: Rgb;
  fillHd: Rgb;
  /**
   * Ring 1 has its own colour; all others take the selection colour.
   * Past maxRings, the ones nearest `center`.
   */
  rings: Rings;
  maxRings: number;
  ringsDrawn: number;
  ringColor: Rgb;
  /** Settles once the shaders have loaded; rejects with the reason when they cannot. */
  ready: Promise<void>;
  /**
   * Draw under everything else: no depth test, no depth write.
   * spots: where the grid glows; past maxSpots, the nearest to `center`.
   * distance: the camera's distance to `center`; the quad grows with it,
   * so the grid fills the same share of the view at any zoom.
   */
  draw(camera: Camera, center: ArrayLike<number>, spots?: readonly Spot[], distance?: number): void;
}

/** A ground for one viewer. It draws once its shaders have loaded. */
export function createGround(viewer: ModelViewer): Ground {
  const gl = viewer.gl;
  if (!viewer.webgl.ensureExtension('OES_standard_derivatives')) throw new Error('ground: OES_standard_derivatives is not available');
  let shader: Shader | null = null;
  // One vec4 uniform per spot: as many as the fragment stage can hold.
  const vectors = Number(gl.getParameter(gl.MAX_FRAGMENT_UNIFORM_VECTORS));
  const maxSpots = Math.max(1, Math.min(SPOT_CAP, vectors - OTHER_UNIFORMS - MAX_RINGS));
  const spotData = new Float32Array(maxSpots * 4);
  const ringData = new Float32Array(MAX_RINGS * 4);
  const ringColors = new Float32Array(6);
  const buffer = quadBuffer(gl);
  const defines = `#define MAX_SPOTS ${maxSpots}\n#define MAX_RINGS ${MAX_RINGS}\n`;

  const ground: Ground = {
    enabled: true,
    cell: 1,
    radius: 60,
    reach: 8,
    minPx: 24,
    drawnRadius: 0,
    maxSpots,
    spotsDrawn: 0,
    line: [0.4, 0.95, 0.58],
    fill: [0.1, 0.32, 0.18],
    lineHd: [0.4, 0.66, 1.0],
    fillHd: [0.1, 0.2, 0.38],
    rings: [null, null],
    maxRings: MAX_RINGS,
    ringsDrawn: 0,
    ringColor: [0.2, 1.0, 0.25],
    ready: loadShader(viewer, 'ground', '/shaders/ground.vert', '/shaders/ground.frag', defines).then((loaded) => {
      shader = loaded;
    }),

    draw(camera, center, spots = [], distance = 0) {
      if (!ground.enabled || shader === null) return;
      shader.use();
      const cx = center[0] ?? 0;
      const cy = center[1] ?? 0;
      const near = (x: number, y: number): number => (x - cx) ** 2 + (y - cy) ** 2;
      // More rings than the shader holds: the first two, then the ones nearest the view centre.
      let rings: readonly (Ring | null)[] = ground.rings;
      if (rings.length > MAX_RINGS) {
        const [selected, over, ...others] = ground.rings;
        rings = [selected, over, ...others.sort((a, b) => near(a.x, a.y) - near(b.x, b.y))].slice(0, MAX_RINGS);
      }
      ground.ringsDrawn = 0;
      rings.forEach((r, i) => {
        ringData.set(r ? [r.x, r.y, r.radius, r.width] : [0, 0, 0, 0], i * 4);
        if (r) ground.ringsDrawn++;
      });
      ringColors.set(ground.ringColor, 0);
      ringColors.set(rings[1] ? rings[1].color : [0, 0, 0], 3);
      gl.uniform1f(uniform(shader, 'u_ringCount'), rings.length);
      gl.uniform4fv(uniform(shader, 'u_rings[0]'), ringData);
      gl.uniform3fv(uniform(shader, 'u_ringColor[0]'), ringColors);
      // More spots than the shader holds: the ones nearest the view centre.
      const use = spots.length > maxSpots ? [...spots].sort((a, b) => near(a[0], a[1]) - near(b[0], b[1])) : spots;
      const count = Math.min(use.length, maxSpots);
      use.slice(0, count).forEach((spot, i) => spotData.set(spot, i * 4));
      ground.spotsDrawn = count;
      gl.uniform4fv(uniform(shader, 'u_spots[0]'), spotData);
      gl.uniform3fv(uniform(shader, 'u_lineHd'), ground.lineHd);
      gl.uniform3fv(uniform(shader, 'u_fillHd'), ground.fillHd);
      gl.uniform1f(uniform(shader, 'u_spotCount'), count);
      gl.uniformMatrix4fv(uniform(shader, 'u_VP'), false, camera.viewProjectionMatrix);
      gl.uniform2f(uniform(shader, 'u_center'), Math.round(cx), Math.round(cy));
      ground.drawnRadius = Math.max(ground.radius, ground.reach * distance);
      gl.uniform1f(uniform(shader, 'u_radius'), ground.drawnRadius);
      gl.uniform1f(uniform(shader, 'u_cell'), ground.cell);
      gl.uniform1f(uniform(shader, 'u_minPx'), ground.minPx);
      gl.uniform3fv(uniform(shader, 'u_line'), ground.line);
      gl.uniform3fv(uniform(shader, 'u_fill'), ground.fill);
      gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
      gl.vertexAttribPointer(attrib(shader, 'a_corner'), 2, gl.FLOAT, false, 0, 0);
      gl.disable(gl.DEPTH_TEST);
      gl.depthMask(false);
      gl.disable(gl.CULL_FACE);
      gl.enable(gl.BLEND);
      gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
      gl.disable(gl.BLEND);
      gl.enable(gl.CULL_FACE);
      gl.enable(gl.DEPTH_TEST);
      gl.depthMask(true);
    },
  };
  return ground;
}
