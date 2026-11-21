// The ground: a green hexagonal grid on z = 0, drawn as one quad around the
// camera target. The hexagons are computed per pixel in the fragment
// shader (shaders/ground.frag), so they stay sharp at any distance.
// Exposed as window.SC2Ground.
'use strict';

(() => {
  /** Glow spots the shader takes: the mouse plus up to 31 units. */
  const MAX_SPOTS = 32;

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
    const spotData = new Float32Array(MAX_SPOTS * 3);
    const ringData = new Float32Array(8);
    const ringColors = new Float32Array(6);
    const buffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);

    const ground = {
      enabled: true,
      cell: 1,
      radius: 60,
      line: [0.4, 0.95, 0.58],
      fill: [0.1, 0.32, 0.18],
      /** [selection, mouse-over]: { x, y, radius, width, color } or null. */
      rings: [null, null],
      ready: Promise.all([source('/shaders/ground.vert'), source('/shaders/ground.frag')]).then(([vertex, fragment]) => {
        shader = viewer.webgl.createShader(vertex, `#define MAX_SPOTS ${MAX_SPOTS}\n${fragment}`);
      }),

      /**
       * Draw under everything else: no depth test, no depth write.
       * spots: [[x, y, radius], ...], where the grid glows; the first MAX_SPOTS count.
       */
      draw(camera, center, spots = []) {
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
        const count = Math.min(spots.length, MAX_SPOTS);
        for (let i = 0; i < count; i++) spotData.set(spots[i], i * 3);
        gl.uniform3fv(uniforms['u_spots[0]'], spotData);
        gl.uniform1f(uniforms.u_spotCount, count);
        gl.uniformMatrix4fv(uniforms.u_VP, false, camera.viewProjectionMatrix);
        gl.uniform2f(uniforms.u_center, Math.round(center[0]), Math.round(center[1]));
        gl.uniform1f(uniforms.u_radius, ground.radius);
        gl.uniform1f(uniforms.u_cell, ground.cell);
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
