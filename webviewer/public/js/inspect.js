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

  /** Layers that name a texture file: active and not a constant colour. */
  function texturesWanted(model) {
    let count = 0;
    for (const material of model.materials[1]) {
      for (const layer of material.layers) if (layer.active && !layer.constant) count++;
    }
    return count;
  }

  /**
   * Constant colour layers (flag 0x400, no texture): the colour uploaded,
   * rgba with the multiply applied, and how many draws bound the layer.
   */
  function constantLayers(model) {
    const out = [];
    for (const material of model.materials[1]) {
      for (const layer of material.layers) {
        if (!layer.active || !layer.constant) continue;
        out.push({ material: material.name, type: layer.type, color: Array.from(layer.constantColor), binds: layer.binds });
      }
    }
    return out;
  }

  /**
   * Turn one model's constant colour layers on or off, so a test can
   * measure what they draw. Returns how many layers changed.
   */
  function setConstantLayers(itemId, on) {
    const item = items.find((i) => i.id === itemId);
    if (!item) throw new Error(`no item ${itemId}`);
    let count = 0;
    for (const material of item.model.materials[1]) {
      for (const layer of material.layers) {
        if (!layer.constant) continue;
        layer.active = on ? 1 : 0;
        count++;
      }
    }
    return count;
  }

  /**
   * Each material of one model: its name and its alpha test (the material's
   * alphaTestThreshold / 255; 0 is no test), as the renderer draws it.
   */
  function alphaTests(itemId) {
    const item = items.find((i) => i.id === itemId);
    if (!item) throw new Error(`no item ${itemId}`);
    return item.model.materials[1].map((material) => ({ material: material.name, alphaTest: material.alphaTest }));
  }

  /** The alpha test each material was loaded with, kept while a test turns it off. */
  const ownAlphaTest = new WeakMap();

  /**
   * Turn one model's alpha tests off, or back to the model's own, so a test
   * can measure what the cut-out removes. Returns how many materials have a test.
   */
  function setAlphaTest(itemId, on) {
    const item = items.find((i) => i.id === itemId);
    if (!item) throw new Error(`no item ${itemId}`);
    let count = 0;
    for (const material of item.model.materials[1]) {
      if (typeof material.alphaTest !== 'number') continue;
      if (!ownAlphaTest.has(material)) ownAlphaTest.set(material, material.alphaTest);
      const own = ownAlphaTest.get(material);
      material.alphaTest = on ? own : 0;
      if (own > 0) count++;
    }
    return count;
  }

  function itemState(item) {
    return {
      id: item.id,
      path: item.path,
      // Where its data and textures come from.
      dataset: item.dataset,
      // A unit or a doodad, never both; a bare model file is neither.
      unit: item.unit && !item.unit.doodad ? item.unit.id : null,
      doodad: item.unit && item.unit.doodad ? item.unit.id : null,
      variation: item.variation,
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
      // HD textures (hd.js): the choice, the layers that have both sets, and
      // the texture overrides the renderer's instance holds.
      hd: item.hd,
      hdLayers: item.hdLayers,
      hdApplied: item.instance.textureOverrides.size,
      // The longest side of any texture the model has, and whether that makes its grid glow blue.
      largestTexture: item.largestTexture,
      blueGlow: app.isHd(item),
      // Geometry layout as the renderer reads it.
      vertexStride: item.model.vertexSize,
      vertexCount: item.model.vertexCount,
      vertexBytes: item.model.vertexBytes,
      // Element indices: bytes each, and the largest stored (vertexCount - 1 unless they wrapped).
      elementBytes: item.model.elementBytes,
      elementMax: item.model.elementMax,
      // Culling: the model's bounding sphere radius, and whether the last
      // frame drew the instance (false when it was culled).
      boundsRadius: item.model.bounds.r,
      // The rest-pose vertex box (model space, before the data and instance scale).
      vertexBox: [[...item.model.vertexMin], [...item.model.vertexMax]],
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
      constantLayers: constantLayers(item.model),
      drawOrder: drawOrder(item),
      drawn: scene.instances.includes(item.instance),
    };
  }

  /**
   * The standard batches the last frame drew for this instance, in the order
   * it drew them: file position, material, blend mode, priority.
   */
  function drawOrder(item) {
    const byFile = new Map(item.model.batches.map((b) => [b.fileOrder, b]));
    return item.instance.drawnOrder.map((fileOrder) => {
      const m = byFile.get(fileOrder).material;
      return { fileOrder, material: m.name, blendMode: m.blendMode, priority: m.priority };
    });
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

  /** The drawn colours where world points [x, y, z?] land on the canvas, from one frame. */
  function groundPixels(points) {
    const frameData = grab();
    const screen = new Float32Array(2);
    return points.map(([x, y, z = 0]) => {
      scene.camera.worldToScreen(screen, new Float32Array([x, y, z]), scene.viewport);
      const px = Math.min(frameData.width - 1, Math.max(0, screen[0]));
      const py = Math.min(frameData.height - 1, Math.max(0, screen[1]));
      const i = (py * frameData.width + px) * 4;
      return { px, py, rgb: [frameData.data[i], frameData.data[i + 1], frameData.data[i + 2]] };
    });
  }

  /** The drawn colour where a world point lands on the canvas. */
  function groundPixel(x, y, z = 0) {
    return groundPixels([[x, y, z]])[0];
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
    // Summed signed change (now minus marked) of r, g, b over the changed pixels.
    const delta = [0, 0, 0];
    for (let i = 0; i < now.data.length; i += 4) {
      const d = [now.data[i] - marked.data[i], now.data[i + 1] - marked.data[i + 1], now.data[i + 2] - marked.data[i + 2]];
      const step = Math.max(Math.abs(d[0]), Math.abs(d[1]), Math.abs(d[2]));
      if (step > largest) largest = step;
      if (step > 40) {
        changed++;
        for (let c = 0; c < 3; c++) delta[c] += d[c];
      }
    }
    return { changed, largest, delta };
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

  /** The share of drawn (non-background) pixels that are near white: every channel above 235. */
  function whiteShare() {
    const { data } = grab();
    let n = 0;
    let white = 0;
    for (let i = 0; i < data.length; i += 4) {
      if (isBackground(data[i], data[i + 1], data[i + 2])) continue;
      n++;
      if (data[i] > 235 && data[i + 1] > 235 && data[i + 2] > 235) white++;
    }
    return n ? white / n : 0;
  }

  /**
   * Grid lines along one canvas row (from the top): the centres, in pixels
   * from the left, of the runs of grid-line pixels. A grid-line pixel is
   * greener than the background: green at least 6 over it and 4 over red
   * (the faint grid away from units is about 14 and 10). Also the ground
   * quad's half size as last drawn.
   */
  function gridLines(row) {
    const { width, height, data } = grab();
    const y = height - 1 - row; // the framebuffer is read bottom row first
    const centres = [];
    let start = -1;
    for (let x = 0; x <= width; x++) {
      let on = false;
      if (x < width) {
        const i = (y * width + x) * 4;
        on = data[i + 1] - bg[1] >= 6 && data[i + 1] - data[i] >= 4;
      }
      if (on && start < 0) start = x;
      if (!on && start >= 0) {
        centres.push((start + x - 1) / 2);
        start = -1;
      }
    }
    return { width, centres, radius: app.ground.drawnRadius };
  }

  /** True when nothing is loading: no model being added, no texture in flight. */
  function idle() {
    return app.pending === 0 && viewer.promiseMap.size === 0;
  }

  /**
   * For each page pixel [clientX, clientY]: is something drawn there (not
   * the background colour)? From one frame. Read with the grid and the sky
   * off and the mouse away, it is the units' silhouette.
   */
  function drawnAt(points) {
    const { width, height, data } = grab();
    const box = canvas.getBoundingClientRect();
    const k = width / canvas.clientWidth;
    return points.map(([cx, cy]) => {
      const x = Math.floor((cx - box.left) * k);
      const y = height - 1 - Math.floor((cy - box.top) * k);
      if (x < 0 || y < 0 || x >= width || y >= height) return null;
      const i = (y * width + x) * 4;
      return !isBackground(data[i], data[i + 1], data[i + 2]);
    });
  }

  /** Draw only the solid (unblended) parts of every unit, or all parts again (tests compare the two). */
  function setSolidOnly(on) {
    for (const item of app.items) item.instance.solidOnly = Boolean(on);
  }

  Object.assign(app, { state, setConstantLayers, alphaTests, setAlphaTest, whiteShare, drawnAt, setSolidOnly, groundPixel, groundPixels, groundPeaks, worldToCanvas, mark, changedSinceMark, pixels, colorStats, gridLines, idle });
})();
