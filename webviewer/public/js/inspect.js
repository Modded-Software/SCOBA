// Inspection used by the tests: scene state, framebuffer reads and pixel
// statistics.
'use strict';

(() => {
  const app = window.SC2App;
  const { viewer, scene, canvas, camera, items, BACKGROUND } = app;

  function texturesLoaded(model) {
    let count = 0;
    for (const material of model.materials[1]) {
      for (const layer of material.layers) if (layer.active && layer.texture && layer.texture.texture) count++;
    }
    return count;
  }

  /** Layers that name a texture file (the library marks them active). */
  function texturesWanted(model) {
    let count = 0;
    for (const material of model.materials[1]) {
      for (const layer of material.layers) if (layer.active) count++;
    }
    return count;
  }

  function itemState(item) {
    return {
      id: item.id,
      path: item.path,
      unit: item.unit ? item.unit.id : null,
      name: item.unit ? item.unit.name : null,
      // Loaded means the model has geometry to draw.
      loaded: item.model.batches.length > 0,
      x: item.x,
      y: item.y,
      rot: item.rot,
      scale: item.scale,
      team: item.team,
      dataScale: [...item.dataScale],
      sequence: item.instance.sequence,
      sequenceName: item.instance.sequence >= 0 ? item.model.sequences[item.instance.sequence].name : null,
      sequences: item.model.sequences.map((s) => s.name),
      // What the renderer holds.
      frame: item.instance.frame,
      rate: item.instance.timeScale,
      highlight: item.instance.highlight,
      // The animation from the menu while it plays once, by name; else null.
      oneShot: item.oneShot !== null ? item.model.sequences[item.oneShot].name : null,
      // The playing sequence's length in ms.
      sequenceLength: item.instance.sequence >= 0 ? item.model.sequences[item.instance.sequence].interval[1] - item.model.sequences[item.instance.sequence].interval[0] : 0,
      location: Array.from(item.instance.localLocation),
      rotation: Array.from(item.instance.localRotation),
      engineScale: Array.from(item.instance.localScale),
      engineTeam: item.instance.teamColor,
      tint: Array.from(item.instance.vertexColor),
      texturesLoaded: texturesLoaded(item.model),
      // Geometry layout as the renderer reads it.
      vertexStride: item.model.vertexSize,
      vertexCount: item.model.vertexCount,
      vertexBytes: item.model.vertexBytes,
      // Culling: the model's bounding sphere radius, and whether the last
      // frame drew the instance (false when it was culled).
      boundsRadius: item.model.bounds.r,
      undrawn: [...item.model.undrawnBatches],
      displacementBatches: item.model.displacementBatches.length,
      // Per region: the UV transform the renderer applies (scale, offset),
      // the stored range of the first UV set, and that range decoded.
      regionUv: item.model.regions.map((r) => ({
        scale: r.uvScale,
        offset: r.uvOffset,
        raw: [...r.rawUvRange],
        range: r.rawUvRange.map((c) => c * r.uvScale + r.uvOffset),
      })),
      uvLayers: uvLayers(item.model),
      drawn: scene.instances.includes(item.instance),
    };
  }

  /**
   * Per active standard-material layer: the UV transform the last draw
   * uploaded (rows of a 2x3 matrix), its inputs, whether a sequence
   * drives the offset, angle or tiling track, and how many draws bound it.
   * The layer object is shared by every instance of the model.
   */
  function uvLayers(model) {
    const out = [];
    for (const material of model.materials[1]) {
      for (const layer of material.layers) {
        if (!layer.active) continue;
        out.push({
          material: material.name,
          type: layer.type,
          driven: layer.uvDriven,
          tilingDriven: layer.uvTilingDriven,
          transform: Array.from(layer.uvTransform),
          inputs: Array.from(layer.uvInputs),
          binds: layer.binds,
        });
      }
    }
    return out;
  }

  function state() {
    const sky = app.sky;
    return {
      items: items.map(itemState),
      sceneInstances: scene.grid.cells.reduce((n, cell) => n + cell.instances.length, 0),
      grid: app.ground.enabled,
      pointer: app.pointer ? [...app.pointer] : null,
      ghost: app.ghostState(),
      pick: app.pickState(),
      // Displacement batches the last frame drew (sky and units).
      displacedBatches: app.displacedBatches,
      rings: app.ground.rings.map((r) => (r ? { x: r.x, y: r.y, radius: r.radius, width: r.width } : null)),
      sky: sky ? { id: sky.id, name: sky.name, file: sky.file } : null,
      // Loaded: the sky model has geometry to draw.
      skyLoaded: Boolean(sky && sky.model && sky.model.batches.length > 0),
      skyTextures: sky && sky.model ? texturesLoaded(sky.model) : 0,
      skyTexturesWanted: sky && sky.model ? texturesWanted(sky.model) : 0,
      // What the sky file holds: vertices, batches drawn, batches not drawn.
      skyVertices: sky && sky.model ? sky.model.vertexCount : 0,
      skyBatches: sky && sky.model ? sky.model.batches.length : 0,
      skyUndrawn: sky && sky.model ? [...sky.model.undrawnBatches] : [],
      skyBoundsRadius: sky && sky.model ? sky.model.bounds.r : 0,
      // Whether the last frame drew the sky instance (false when culled).
      skyDrawn: Boolean(sky && sky.instance && app.skyScene.instances.includes(sky.instance)),
      skySequence: sky && sky.instance && sky.instance.sequence >= 0 ? sky.model.sequences[sky.instance.sequence].name : null,
      camera: {
        yaw: camera.yaw,
        pitch: camera.pitch,
        distance: camera.distance,
        target: [...camera.target],
        aspect: scene.camera.aspect,
        zoomGoal: app.zoomGoal(),
      },
    };
  }

  /** Render one frame without advancing time and read the framebuffer back. */
  function grab() {
    app.resize();
    app.draw(0);
    const gl = viewer.gl;
    const width = canvas.width;
    const height = canvas.height;
    const data = new Uint8Array(width * height * 4);
    gl.readPixels(0, 0, width, height, gl.RGBA, gl.UNSIGNED_BYTE, data);
    return { width, height, data };
  }

  /** The drawn colour where a world point lands on the canvas. */
  function groundPixel(x, y, z = 0) {
    const frameData = grab();
    const screen = new Float32Array(2);
    scene.camera.worldToScreen(screen, new Float32Array([x, y, z]), scene.viewport);
    const px = Math.min(frameData.width - 1, Math.max(0, screen[0]));
    const py = Math.min(frameData.height - 1, Math.max(0, screen[1]));
    const i = (py * frameData.width + px) * 4;
    return { px, py, rgb: [frameData.data[i], frameData.data[i + 1], frameData.data[i + 2]] };
  }

  /**
   * For each ground point [x, y], the greenest pixel within `reach` pixels
   * of where it lands, from one frame: a one-pixel line is found even when
   * the point maps beside it. Null for a point that lands off the canvas.
   */
  function groundPeaks(points, reach = 1) {
    const frameData = grab();
    const screen = new Float32Array(2);
    return points.map(([x, y]) => {
      scene.camera.worldToScreen(screen, new Float32Array([x, y, 0]), scene.viewport);
      const inside = screen[0] >= reach && screen[1] >= reach && screen[0] < frameData.width - reach && screen[1] < frameData.height - reach;
      if (!inside) return null;
      let best = null;
      for (let dy = -reach; dy <= reach; dy++) {
        for (let dx = -reach; dx <= reach; dx++) {
          const px = Math.min(frameData.width - 1, Math.max(0, Math.round(screen[0]) + dx));
          const py = Math.min(frameData.height - 1, Math.max(0, Math.round(screen[1]) + dy));
          const i = (py * frameData.width + px) * 4;
          const rgb = [frameData.data[i], frameData.data[i + 1], frameData.data[i + 2]];
          if (!best || rgb[1] > best.rgb[1]) best = { px, py, rgb };
        }
      }
      return best;
    });
  }

  /**
   * Where a world point lands on the canvas, in canvas pixels, as the
   * renderer's camera computes it: x from the left; y as the library gives
   * it (the framebuffer row).
   */
  function worldToCanvas(x, y, z = 0) {
    app.resize();
    const screen = new Float32Array(2);
    scene.camera.worldToScreen(screen, new Float32Array([x, y, z]), scene.viewport);
    return [screen[0], screen[1]];
  }

  let marked = null;

  /** Remember the current frame, to compare a later one against. */
  function mark() {
    marked = grab();
  }

  /**
   * How many pixels differ clearly from the marked frame.
   * Two renders of one still scene differ by a few low-amplitude pixels
   * (measured: 38 pixels, largest step 13 of 255), so small steps are ignored.
   */
  function changedSinceMark() {
    const now = grab();
    if (!marked || marked.width !== now.width || marked.height !== now.height) return null;
    let changed = 0;
    let largest = 0;
    for (let i = 0; i < now.data.length; i += 4) {
      const step = Math.max(Math.abs(now.data[i] - marked.data[i]), Math.abs(now.data[i + 1] - marked.data[i + 1]), Math.abs(now.data[i + 2] - marked.data[i + 2]));
      if (step > largest) largest = step;
      if (step > 40) changed++;
    }
    return { changed, largest };
  }

  const bg = BACKGROUND.map((c) => Math.round(c * 255));
  const isBackground = (r, g, b) => Math.abs(r - bg[0]) <= 1 && Math.abs(g - bg[1]) <= 1 && Math.abs(b - bg[2]) <= 1;

  /** Where the drawn pixels are. Rows count from the top, like the page. */
  function pixels() {
    const { width, height, data } = grab();
    const colors = new Set();
    let covered = 0;
    let sumX = 0;
    let minX = width;
    let maxX = -1;
    let minY = height;
    let maxY = -1;
    for (let i = 0, p = 0; i < data.length; i += 4, p++) {
      if (isBackground(data[i], data[i + 1], data[i + 2])) continue;
      const x = p % width;
      const y = height - 1 - Math.floor(p / width); // the framebuffer is read bottom row first
      covered++;
      sumX += x;
      if (x < minX) minX = x;
      if (x > maxX) maxX = x;
      if (y < minY) minY = y;
      if (y > maxY) maxY = y;
      colors.add(((data[i] >> 3) << 10) | ((data[i + 1] >> 3) << 5) | (data[i + 2] >> 3));
    }
    const box = covered ? { minX, maxX, minY, maxY } : { minX: null, maxX: null, minY: null, maxY: null };
    return { width, height, covered, colors: colors.size, centerX: covered ? sumX / covered : null, ...box };
  }

  /**
   * Colour statistics of the drawn (non-background) pixels: mean channel
   * values, mean brightness, the share of pixels that are clearly red
   * (red above 60 and over 1.6 times both green and blue), and the count
   * of clearly green pixels (the same rule for green).
   */
  function colorStats() {
    const { data } = grab();
    let n = 0;
    let red = 0;
    let green = 0;
    let dark = 0;
    const sum = [0, 0, 0];
    for (let i = 0; i < data.length; i += 4) {
      const r = data[i];
      const g = data[i + 1];
      const b = data[i + 2];
      if (isBackground(r, g, b)) continue;
      n++;
      sum[0] += r;
      sum[1] += g;
      sum[2] += b;
      if (r > 60 && r > 1.6 * g && r > 1.6 * b) red++;
      if (g > 60 && g > 1.6 * r && g > 1.6 * b) green++;
      if (r + g + b < 30) dark++;
    }
    const mean = sum.map((s) => (n ? s / n : 0));
    return { pixels: n, mean, brightness: (mean[0] + mean[1] + mean[2]) / 3, redShare: n ? red / n : 0, green, darkShare: n ? dark / n : 0 };
  }

  /** True when nothing is loading: no model being added, no texture in flight. */
  function idle() {
    return app.pending === 0 && viewer.promiseMap.size === 0;
  }

  Object.assign(app, { state, groundPixel, groundPeaks, worldToCanvas, mark, changedSinceMark, pixels, colorStats, idle });
})();
