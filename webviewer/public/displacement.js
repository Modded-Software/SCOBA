// Displacement materials (heat haze, cloak shimmer, warp ripples): after a
// scene is drawn, the frame so far is copied to a texture and every drawn
// instance with displacement batches draws them over it, showing the copy
// shifted along their normal maps (M3ModelInstance.renderDisplacement).
// Exposed as window.SC2Displacement.
'use strict';

(() => {
  function create(viewer) {
    const gl = viewer.gl;
    const texture = gl.createTexture();
    let width = 0;
    let height = 0;

    gl.bindTexture(gl.TEXTURE_2D, texture);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);

    return {
      /** Off: displacement batches are not drawn (for comparing frames). */
      enabled: true,

      /**
       * Draw the displacement of a scene's drawn instances. Call right after
       * the scene. Returns how many batches it drew.
       */
      draw(scene, w, h) {
        const instances = scene.instances.filter((i) => i.model.displacementBatches && i.model.displacementBatches.length);
        if (!this.enabled || !instances.length) return 0;
        let drawn = 0;
        // The canvas has no alpha (alpha: false), so the copy is RGB.
        gl.bindTexture(gl.TEXTURE_2D, texture);
        if (w !== width || h !== height) {
          gl.copyTexImage2D(gl.TEXTURE_2D, 0, gl.RGB, 0, 0, w, h, 0);
          width = w;
          height = h;
        } else {
          gl.copyTexSubImage2D(gl.TEXTURE_2D, 0, 0, 0, 0, 0, w, h);
        }
        gl.viewport(0, 0, w, h);
        gl.scissor(0, 0, w, h);
        for (const instance of instances) {
          instance.renderDisplacement(texture, w, h);
          drawn += instance.model.displacementBatches.length;
        }
        gl.depthMask(true);
        return drawn;
      },
    };
  }

  window.SC2Displacement = { create };
})();
