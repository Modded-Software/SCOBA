// The grid is faint, except around units (and the mouse): there it glows,
// fading out with the distance.
// The ground: a green hexagonal grid on z = 0, drawn as one quad around the
// camera target, its size growing with the camera distance. The hexagons
// are computed per pixel in the fragment shader (shaders/ground.frag), so
// they stay sharp at any distance; seven make the next level's hexagon, and
// the level follows the zoom so cells never get arbitrarily small.
// Exposed as window.SC2Ground.
'use strict';

(() => {
  /** Glow spots the shader takes at most; fewer when the GPU has fewer uniform vectors. */
  const SPOT_CAP = 256;
  /** Fragment uniform vectors the ground shader uses besides the spots, with room to spare. */
  const OTHER_UNIFORMS = 32;

  async function source(url) {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`ground: ${response.status} ${url}`);
    return response.text();
  }

  /**
   * A ground for one viewer. It draws once its shaders have loaded;
   * `ready` settles then, and rejects with the reason when they cannot.
   */
  function create(viewer) {
    const gl = viewer.gl;
    if (!viewer.webgl.ensureExtension('OES_standard_derivatives')) throw new Error('ground: OES_standard_derivatives is not available');
    let shader = null;
    // One vec3 uniform per spot: as many as the fragment stage can hold.
    const MAX_SPOTS = Math.max(1, Math.min(SPOT_CAP, gl.getParameter(gl.MAX_FRAGMENT_UNIFORM_VECTORS) - OTHER_UNIFORMS));
    const spotData = new Float32Array(MAX_SPOTS * 3);
    const ringData = new Float32Array(8);
    const ringColors = new Float32Array(6);
    const buffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);

    const ground = {
      enabled: true,
      cell: 1,
      /** The quad's half size: at least `radius`, and `reach` times the camera distance. */
      radius: 60,
      reach: 8,
      /** The least on-screen cell width in pixels before the next level takes over (shaders/ground.frag). */
      minPx: 24,
      /** The half size of the last drawn quad (for the tests). */
      drawnRadius: 0,
      /** Glow spots the shader holds, and how many the last frame used (for the tests). */
      maxSpots: MAX_SPOTS,
      spotsDrawn: 0,
      line: [0.4, 0.95, 0.58],
      fill: [0.1, 0.32, 0.18],
      /** [selection, mouse-over]: { x, y, radius, width, color } or null. */
      rings: [null, null],
      ready: Promise.all([source('/shaders/ground.vert'), source('/shaders/ground.frag')]).then(([vertex, fragment]) => {
        shader = viewer.webgl.createShader(vertex, `#define MAX_SPOTS ${MAX_SPOTS}\n${fragment}`);
      }),

      /**
       * Draw under everything else: no depth test, no depth write.
       * spots: [[x, y, radius], ...], where the grid glows; past MAX_SPOTS, the nearest to `center`.
       * distance: the camera's distance to `center`; the quad grows with it,
       * so the grid fills the same share of the view at any zoom.
       */
      draw(camera, center, spots = [], distance = 0) {
        if (!ground.enabled || !shader) return;
        shader.use();
        const uniforms = shader.uniforms;
        for (let i = 0; i < 2; i++) {
          const r = ground.rings[i];
          ringData.set(r ? [r.x, r.y, r.radius, r.width] : [0, 0, 0, 0], i * 4);
          ringColors.set(r ? r.color : [0, 0, 0], i * 3);
        }
        gl.uniform4fv(uniforms['u_rings[0]'], ringData);
        gl.uniform3fv(uniforms['u_ringColor[0]'], ringColors);
        // More spots than the shader holds: the ones nearest the view centre.
        let use = spots;
        if (spots.length > MAX_SPOTS) {
          const d = (s) => (s[0] - center[0]) ** 2 + (s[1] - center[1]) ** 2;
          use = [...spots].sort((a, b) => d(a) - d(b));
        }
        const count = Math.min(use.length, MAX_SPOTS);
        for (let i = 0; i < count; i++) spotData.set(use[i], i * 3);
        ground.spotsDrawn = count;
        gl.uniform3fv(uniforms['u_spots[0]'], spotData);
        gl.uniform1f(uniforms.u_spotCount, count);
        gl.uniformMatrix4fv(uniforms.u_VP, false, camera.viewProjectionMatrix);
        gl.uniform2f(uniforms.u_center, Math.round(center[0]), Math.round(center[1]));
        ground.drawnRadius = Math.max(ground.radius, ground.reach * distance);
        gl.uniform1f(uniforms.u_radius, ground.drawnRadius);
        gl.uniform1f(uniforms.u_cell, ground.cell);
        gl.uniform1f(uniforms.u_minPx, ground.minPx);
        gl.uniform3fv(uniforms.u_line, ground.line);
        gl.uniform3fv(uniforms.u_fill, ground.fill);
        gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
        gl.vertexAttribPointer(shader.attribs.a_corner, 2, gl.FLOAT, false, 0, 0);
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

  window.SC2Ground = { create };
})();
