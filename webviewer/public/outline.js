// Mouse-over outline: a feathered green glow around the silhouette of one
// unit, as the game draws it. The unit is drawn alone into a mask, the mask
// is blurred in two passes, and the blur is added outside the silhouette.
// Shaders: shaders/outline.vert, outline-blur.frag, outline-compose.frag.
// Exposed as window.SC2Outline.
'use strict';

(() => {
  const SPREAD = 1.6; // texels between blur taps: the feather is about 13 px wide

  async function source(url) {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`outline: ${response.status} ${url}`);
    return response.text();
  }

  /**
   * An outline for one viewer. It draws once its shaders have loaded;
   * `ready` settles then, and rejects with the reason when they cannot.
   */
  function create(viewer) {
    const gl = viewer.gl;
    let blurShader = null;
    let composeShader = null;
    const ready = Promise.all(['/shaders/outline.vert', '/shaders/outline-blur.frag', '/shaders/outline-compose.frag'].map(source)).then(([vertex, blur, compose]) => {
      blurShader = viewer.webgl.createShader(vertex, blur);
      composeShader = viewer.webgl.createShader(vertex, compose);
    });
    const quad = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, quad);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);

    let width = 0;
    let height = 0;
    const targets = [0, 1, 2].map(() => ({ texture: gl.createTexture(), frame: gl.createFramebuffer() }));
    const depth = gl.createRenderbuffer();

    function resize(w, h) {
      if (w === width && h === height) return;
      width = w;
      height = h;
      for (const t of targets) {
        gl.bindTexture(gl.TEXTURE_2D, t.texture);
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, w, h, 0, gl.RGBA, gl.UNSIGNED_BYTE, null);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
        gl.bindFramebuffer(gl.FRAMEBUFFER, t.frame);
        gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, t.texture, 0);
      }
      // The mask keeps the unit's own depth order (a front part over a back part).
      gl.bindRenderbuffer(gl.RENDERBUFFER, depth);
      gl.renderbufferStorage(gl.RENDERBUFFER, gl.DEPTH_COMPONENT16, w, h);
      gl.bindFramebuffer(gl.FRAMEBUFFER, targets[0].frame);
      gl.framebufferRenderbuffer(gl.FRAMEBUFFER, gl.DEPTH_ATTACHMENT, gl.RENDERBUFFER, depth);
      const status = gl.checkFramebufferStatus(gl.FRAMEBUFFER);
      gl.bindFramebuffer(gl.FRAMEBUFFER, null);
      if (status !== gl.FRAMEBUFFER_COMPLETE) throw new Error('outline: mask framebuffer incomplete: ' + status);
    }

    function pass(shader, target) {
      gl.bindFramebuffer(gl.FRAMEBUFFER, target ? target.frame : null);
      gl.viewport(0, 0, width, height);
      gl.scissor(0, 0, width, height);
      shader.use();
      gl.bindBuffer(gl.ARRAY_BUFFER, quad);
      gl.vertexAttribPointer(shader.attribs.a_corner, 2, gl.FLOAT, false, 0, 0);
    }

    function bind(texture, unit, uniform) {
      gl.activeTexture(gl.TEXTURE0 + unit);
      gl.bindTexture(gl.TEXTURE_2D, texture);
      gl.uniform1i(uniform, unit);
    }

    const outline = {
      color: [0.25, 1.0, 0.3],
      gain: 2.2,
      ready,
      /** Draw the glow around `instance` onto the canvas. Call after the scene. Nothing until the shaders have loaded. */
      draw(instance, w, h) {
        if (!blurShader) return;
        resize(w, h);
        // 1. The unit alone into the mask.
        gl.bindFramebuffer(gl.FRAMEBUFFER, targets[0].frame);
        gl.viewport(0, 0, w, h);
        gl.scissor(0, 0, w, h);
        gl.depthMask(true);
        gl.clearColor(0, 0, 0, 0);
        gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
        instance.renderOpaque();
        gl.disable(gl.DEPTH_TEST);
        gl.depthMask(false);
        gl.disable(gl.CULL_FACE);
        gl.disable(gl.BLEND);
        // 2. Blur across, 3. blur down.
        pass(blurShader, targets[1]);
        bind(targets[0].texture, 0, blurShader.uniforms.u_map);
        gl.uniform2f(blurShader.uniforms.u_step, SPREAD / w, 0);
        gl.uniform1f(blurShader.uniforms.u_first, 1);
        gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
        pass(blurShader, targets[2]);
        bind(targets[1].texture, 0, blurShader.uniforms.u_map);
        gl.uniform2f(blurShader.uniforms.u_step, 0, SPREAD / h);
        gl.uniform1f(blurShader.uniforms.u_first, 0);
        gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
        // 4. Onto the canvas, outside the silhouette.
        pass(composeShader, null);
        bind(targets[2].texture, 0, composeShader.uniforms.u_blur);
        bind(targets[0].texture, 1, composeShader.uniforms.u_mask);
        gl.uniform3fv(composeShader.uniforms.u_color, outline.color);
        gl.uniform1f(composeShader.uniforms.u_gain, outline.gain);
        gl.enable(gl.BLEND);
        gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
        gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
        gl.disable(gl.BLEND);
        gl.enable(gl.CULL_FACE);
        gl.enable(gl.DEPTH_TEST);
        gl.depthMask(true);
        gl.activeTexture(gl.TEXTURE0);
      },
    };
    return outline;
  }

  window.SC2Outline = { create };
})();
