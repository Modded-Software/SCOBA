// Particle emitters (M3 PAR_): the switch, and inspection for the tests.
// The renderer runs and draws them (ref handlers/m3/particlesystem.ts).
'use strict';

(() => {
  const app = window.SC2App;
  const { viewer, items } = app;

  const m3 = () => viewer.sharedCache.get('m3');
  const find = (id) => {
    const item = items.find((i) => i.id === id);
    if (!item) throw new Error(`no item ${id}`);
    return item;
  };
  const position = new Float32Array(3);
  const quad = new Float32Array(12);
  const start = new Float32Array(3);

  /** Run and draw particles, or not. Off, the emitters hold no particles and do not run. */
  function setParticles(on) {
    m3().particlesEnabled = Boolean(on);
  }

  /**
   * The emitters of one item as the renderer runs them. `reach`: the
   * farthest a particle can be from its emitter (emission area, top start
   * speed and the vertical acceleration over the longest life, times the
   * emitter scale). With `withParticles`, each live particle: serial,
   * age and life in seconds, world position, start colour (rgba 0 to 255).
   */
  function particles(id, withParticles = false) {
    const item = find(id);
    const systems = item.instance.particleSystems || [];
    const emitters = systems.map((s) => {
      const e = s.emitter;
      const origin = [s.matrix[12], s.matrix[13], s.matrix[14]];
      // PARC copies emit from their own bones: every slot's origin, the emitter first.
      const copies = s.copies.map((c, k) => ({ bone: c.copy.boneIndex, rateInit: c.copy.emissionRate.initValue, origin: [c.matrix[12], c.matrix[13], c.matrix[14]], spawned: s.slotSpawned[k + 1] }));
      const origins = [origin, ...copies.map((c) => c.origin)];
      const scale = Math.max(s.scale(), ...s.copies.map((c) => Math.hypot(c.matrix[0], c.matrix[1], c.matrix[2])));
      const life = s.lifeMax;
      const reach = scale * (s.areaReach() + s.topSpeed() * life + 0.5 * Math.abs(e.zAcceleration) * life * life) + 1e-3;
      const map = item.model.materialMaps[e.materialReferenceIndex];
      // Type 2: a displacement material (normal and strength layers); otherwise standard.
      const displacement = map.materialType === 2 ? item.model.displacementMaterials[map.materialIndex] : null;
      const material = displacement || item.model.materials[1][map.materialIndex];
      const layer = displacement ? null : [material.layers[0], material.layers[4]].find((l) => l.active && !l.constant && l.texture);
      // The layers a particle draws with: diffuse, emissive 1 and 2, alpha masks 1 and 2.
      const layers = displacement ? [displacement.normalLayer, displacement.strengthLayer].filter((l) => l.active) : [0, 4, 5, 8, 9].map((n) => material.layers[n]).filter((l) => l.active);
      const out = {
        materialType: map.materialType,
        blendMode: displacement ? null : material.blendMode,
        layers: layers.map((l) => ({ type: l.type, channels: l.colorChannels, constant: Boolean(l.constant), binds: l.binds })),
        map: layer ? layer.type : null,
        mapLoaded: Boolean(layer && layer.texture.texture),
        mapPath: layer ? layer.source : null,
        index: s.index,
        version: e.version,
        read: e.read,
        bone: e.boneIndex,
        material: e.materialReferenceIndex,
        shape: e.emissionAreaType,
        velocityType: e.emissionType,
        particleType: e.particleType,
        tail: e.lengthWidthRatio,
        bounce: e.bounce,
        friction: e.friction,
        flags: e.flags,
        additionalFlags: e.additionalFlags,
        worldSpace: s.worldSpace,
        // Motion: closed form, or per-step (euler: drag without its floor).
        euler: s.euler,
        drag: e.drag,
        mass: [e.mass, e.mass2],
        zAcceleration: e.zAcceleration,
        forces: e.forces,
        forcesFallback: e.forcesFallback,
        killSphere: e.killSphere,
        noiseAmplitude: e.noiseAmplitude,
        windMultiplier: e.windMultiplier,
        max: s.max,
        rateInit: e.emissionRate.initValue,
        lifeInit: [e.lifespan1.initValue, e.lifespan2.initValue],
        rate: s.rate,
        rateMin: s.rateMin,
        rateMax: s.rateMax,
        lifeMin: s.lifeMin,
        lifeMax: s.lifeMax,
        live: s.live,
        spawned: s.spawned,
        dropped: s.dropped,
        time: s.time,
        origin,
        origins,
        copies,
        slotSpawned: s.slotSpawned.slice(),
        bursts: s.bursts.slice(),
        partEmit: { animId: e.partEmit.animId, animFlags: e.partEmit.animFlags },
        reach,
        quads: s.quads,
      };
      if (withParticles) {
        out.particles = [];
        for (let i = 0; i < s.live; i++) {
          s.position(position, i);
          m3().particleQuad(s, i, item.instance.scene.camera, quad);
          const speed = m3().particleMotion(s, i, start);
          out.particles.push({ bounces: s.bounces[i], rest: s.rest[i], born: Array.from(s.born.subarray(i * 3, i * 3 + 3)), serial: s.serial[i], age: s.time - s.birth[i], life: s.life[i], position: Array.from(position), quad: Array.from(quad), start: Array.from(start), speed, startColor: Array.from(s.colors.subarray(i * 12, i * 12 + 4)) });
        }
      }
      return out;
    });
    return { enabled: m3().particlesEnabled, emitters, quads: systems.reduce((n, s) => n + s.quads, 0) };
  }

  /**
   * Run one item's emitters for `seconds` of game time in steps of `step`
   * seconds, with the frame loop's clock stopped for it (time scale 0), so
   * its particles move only here and stay put while a test measures them.
   */
  function advanceParticles(id, seconds, step = 1 / 60) {
    const item = find(id);
    item.instance.timeScale = 0;
    const steps = Math.round(seconds / step);
    for (let i = 0; i < steps; i++) item.instance.updateParticles(step);
    return steps;
  }

  /** Move an item to ground point (x, y), as the scene list does. */
  function setItemPosition(id, x, y) {
    app.setPosition(find(id), x, y);
  }

  /**
   * Play an item's sequence `name` from its start for `seconds`, in `step`
   * steps, with the frame loop's clock stopped for it (time scale 0), so
   * the animation and its particles move only here. `loopMode` 1 holds the
   * last frame. Returns the frame reached, in ms.
   */
  function playParticles(id, name, seconds, step = 1 / 60, loopMode = 1) {
    const item = find(id);
    const instance = item.instance;
    const index = item.model.sequences.findIndex((s) => s.name === name);
    if (index < 0) throw new Error(`no sequence ${name}`);
    instance.timeScale = 0;
    instance.setSequenceLoopMode(loopMode);
    instance.setSequence(index);
    const steps = Math.round(seconds / step);
    for (let i = 0; i < steps; i++) instance.updateAnimations(step);
    return instance.frame;
  }

  /** The keys of an animation reference in sequence `name`, read straight from the model data: [[ms, value], ...]. */
  function animKeys(id, name, ref) {
    const item = find(id);
    const pose = item.instance.skeleton;
    const stg = pose.stg[item.model.sequences.findIndex((s) => s.name === name)];
    const out = [];
    for (const i of stg.stcIndices) {
      const stc = stg.stc[i];
      const at = stc.animRefs[ref.animId];
      if (!at || !stg.sts[stc.stsIndex].hasData(ref)) continue;
      const sd = stc.sd[at[0]].sd[at[1]];
      sd.keys.forEach((t, k) => out.push([t, Number(sd.values[k])]));
    }
    return out;
  }

  /**
   * Draw particle `k` of emitter `index` alone (the item's clock stopped,
   * its mesh and other particles left out) and measure it: for each [u, v]
   * on its quad (0 to 1, u along the width, v along the length), how much
   * the drawn colour there differs from the frame without the particle
   * (sum of |r|, |g|, |b|, 0 to 765). Destroys the item's other particles;
   * the measured one is particle 0 afterwards.
   */
  function particleSamples(id, index, k, uvs) {
    const item = find(id);
    const instance = item.instance;
    const camera = item.instance.scene.camera;
    const gl = viewer.gl;
    const s = instance.particleSystems.find((x) => x.index === index);
    if (!s || k >= s.live) throw new Error(`no particle ${k} of emitter ${index}`);
    instance.timeScale = 0;
    for (const other of instance.particleSystems) if (other !== s) other.live = 0;
    if (k !== 0) s.move(k, 0);
    s.live = 1;
    const batches = item.model.batches.slice();
    item.model.batches.length = 0;
    const read = () => {
      app.resize();
      app.draw(0);
      const w = gl.drawingBufferWidth;
      const h = gl.drawingBufferHeight;
      const data = new Uint8Array(w * h * 4);
      gl.readPixels(0, 0, w, h, gl.RGBA, gl.UNSIGNED_BYTE, data);
      return { w, h, data };
    };
    try {
      m3().particleQuad(s, 0, camera, quad);
      const screen = new Float32Array(2);
      const points = uvs.map(([u, v]) => {
        const p = new Float32Array(3);
        for (let j = 0; j < 3; j++) p[j] = quad[j] + (quad[9 + j] - quad[j]) * u + (quad[3 + j] - quad[j]) * v;
        camera.worldToScreen(screen, p, instance.scene.viewport);
        return [screen[0], screen[1]];
      });
      const withIt = read();
      s.live = 0;
      const without = read();
      return points.map(([x, y]) => {
        if (x < 0 || y < 0 || x >= withIt.w || y >= withIt.h) return null;
        const i = (Math.floor(y) * withIt.w + Math.floor(x)) * 4;
        return Math.abs(withIt.data[i] - without.data[i]) + Math.abs(withIt.data[i + 1] - without.data[i + 1]) + Math.abs(withIt.data[i + 2] - without.data[i + 2]);
      });
    } finally {
      // The particle stays, for another measurement.
      s.live = 1;
      item.model.batches.push(...batches);
    }
  }

  /** Draw spot lights on the ground plane, or not; `only`: one light index (into model.lights), -1 all. */
  function setGroundLights(on, only = -1) {
    m3().groundLightsEnabled = Boolean(on);
    m3().groundLightOnly = only;
  }

  /** The spot lights of one item now: type, bone, world position, axis, colour, ranges, cone angles, ground hit. */
  function groundLights(id) {
    const item = find(id);
    return item.model.lights.map((l) => {
      const s = m3().groundLight(item.instance, l);
      return { type: l.lightType, bone: l.boneIndex, position: Array.from(s.position), direction: Array.from(s.direction), color: Array.from(s.color), near: s.near, far: s.far, hotSpot: s.hotSpot, falloff: s.falloff, hit: s.hit && Array.from(s.hit) };
    });
  }

  /** Apply the layers' fresnel term, or not (every model). */
  function setFresnel(on) {
    m3().layerOptions.fresnel = Boolean(on);
  }

  Object.assign(app, { setParticles, particles, advanceParticles, playParticles, animKeys, particleSamples, setGroundLights, groundLights, setFresnel, setItemPosition });
})();
