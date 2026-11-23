import { test, expect } from '@playwright/test';

// M3 particle emitters (PAR_), step 1: emission by rate, lifespans, the
// closed-form motion, size, colour and rotation over the life, drawn as
// camera-facing quads in the material's blend mode. Rules: WhiteoutFlakes
// renderer/particle/sc2 (sc2_kernels_spawn, sc2_kernels_build) and
// renderer/sc2/sc2_element_math.h. Field layout: m3addon structures.xml,
// checked field by field against its m3.py on one file per version.
// Truth: the emitter state the renderer keeps (sc2viewer.particles), and the
// drawn frame with particles on and off (sc2viewer.setParticles).

const VIEW = { yaw: -Math.PI / 2, pitch: 0.3, distance: 6, target: [0, 0, 1] };

async function open(page) {
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => {
    if (m.text().startsWith('viewer:') || m.type() === 'error') errors.push(m.text());
  });
  await page.goto('/');
  await expect.poll(() => errors.join(' | ') || page.evaluate(() => Boolean(window.sc2viewer && window.sc2viewer.ready)), { timeout: 10_000 }).toBe(true);
  await page.evaluate((v) => {
    window.sc2viewer.view(v);
    window.sc2viewer.setGrid(false);
  }, VIEW);
  return errors;
}

const idle = (page) => page.waitForFunction(() => window.sc2viewer.idle(), null, { timeout: 20_000 });
/** Add a unit; `sequence` -1 plays no animation (every track at its rest value). */
const unit = async (page, id, sequence) => {
  const item = await page.evaluate(([u, q]) => window.sc2viewer.addUnit(u, { x: 0, y: 0, rot: 0, pick: 0.5, dataset: 'stock', ...(q === null ? {} : { sequence: q }) }), [id, sequence ?? null]);
  await idle(page);
  return item;
};
const state = (page, id, positions = false) => page.evaluate(([i, p]) => window.sc2viewer.particles(i, p), [id, positions]);
/** Run an item's emitters for `seconds` of game time in 1/60 s steps (the frame loop keeps running too). */
const advance = (page, id, seconds) => page.evaluate(([i, s]) => window.sc2viewer.advanceParticles(i, s, 1 / 60), [id, seconds]);
const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);

/** Everything a live particle must satisfy, as a list of what failed (empty when all is well). */
function particleFaults(emitter) {
  const faults = [];
  for (const p of emitter.particles) {
    if (!(p.age >= 0 && p.age <= p.life + 1e-6)) faults.push(`age ${p.age} outside life ${p.life}`);
    if (!(p.life >= emitter.lifeMin - 1e-6 && p.life <= emitter.lifeMax + 1e-6)) faults.push(`life ${p.life} outside [${emitter.lifeMin}, ${emitter.lifeMax}]`);
    // The nearest slot: the emitter or one of its PARC copies.
    const d = Math.min(...emitter.origins.map((o) => dist(p.position, o)));
    if (!(d <= emitter.reach)) faults.push(`at ${d.toFixed(3)} from the emitter, reach ${emitter.reach.toFixed(3)}`);
  }
  return faults;
}

test('Probe: both emitters are read from PAR_ version 24 as m3addon reads them', async ({ page }) => {
  const errors = await open(page);
  const id = await unit(page, 'Probe');
  const s = await state(page, id);
  console.log('Probe emitters', JSON.stringify(s.emitters.map(({ particles, ...e }) => e)));
  expect(s.emitters.map((e) => [e.version, e.read, e.bone, e.max])).toEqual([[24, true, 20, 28], [24, true, 21, 36]]);
  // m3addon values (tools: m3.py on probe.m3).
  expect(s.emitters[0].rateInit).toBeCloseTo(25, 5);
  expect(s.emitters[0].lifeInit).toEqual([expect.closeTo(0.3, 5), expect.closeTo(0.48, 5)]);
  expect(s.emitters[0].worldSpace).toBe(true);
  expect(s.emitters[1].rateInit).toBe(0);
  expect(errors).toEqual([]);
});

test('Probe at rest: emission follows the rate, every particle dies at its lifespan and stays in reach of its emitter', async ({ page }) => {
  const errors = await open(page);
  const id = await unit(page, 'Probe', -1);
  await advance(page, id, 2);
  const s = await state(page, id, true);
  const [e0, e1] = s.emitters;
  console.log('emitter 0', JSON.stringify({ ...e0, particles: e0.particles.length }));
  console.log('emitter 1', JSON.stringify({ ...e1, particles: e1.particles.length }));
  // A constant rate, so spawned / time is the rate (windows wider than one frame of births).
  expect(e0.rateMin).toBe(e0.rateMax);
  expect(e0.spawned).toBeGreaterThanOrEqual(Math.floor(0.85 * e0.rateMax * e0.time));
  expect(e0.spawned).toBeLessThanOrEqual(Math.ceil(1.15 * e0.rateMax * e0.time) + 1);
  // Steady state: about rate x mean life alive, never more than the emitter holds.
  const meanLife = (e0.lifeMin + e0.lifeMax) / 2;
  expect(e0.live).toBeGreaterThanOrEqual(Math.floor(0.5 * e0.rateMax * meanLife));
  expect(e0.live).toBeLessThanOrEqual(Math.min(e0.max, Math.ceil(1.5 * e0.rateMax * meanLife) + 1));
  expect(e0.particles.length).toBe(e0.live);
  // The older ones are gone: births minus the living are the dead.
  expect(e0.spawned - e0.live).toBeGreaterThan(0);
  expect(particleFaults(e0)).toEqual([]);
  // The rest value of the rate track (m3addon: 25).
  expect(e0.rateMax).toBeCloseTo(25, 5);
  // Negative: an emitter whose rate is 0 all along emits nothing.
  expect(e1.rateMax).toBe(0);
  expect(e1.spawned).toBe(0);
  expect(e1.live).toBe(0);
  expect(errors).toEqual([]);
});

test('Probe at rest: the particles draw; switched off, nothing is drawn and nothing is born', async ({ page }) => {
  const errors = await open(page);
  const id = await unit(page, 'Probe', -1);
  // From behind: from the front the body hides the thruster glow.
  await page.evaluate(() => window.sc2viewer.view({ yaw: Math.PI / 2, pitch: 0.3, distance: 3, target: [0, 0, 0.4] }));
  await advance(page, id, 1);
  // Switching off clears the particles, so the frame with them is marked first.
  const change = await page.evaluate((i) => {
    const v = window.sc2viewer;
    v.mark();
    const quadsOn = v.particles(i).quads;
    v.setParticles(false);
    const off = v.changedSinceMark();
    v.mark();
    const offAgain = v.changedSinceMark();
    v.setParticles(true);
    return { off, offAgain, quadsOn };
  }, id);
  console.log('Probe change', JSON.stringify(change), JSON.stringify((await state(page, id)).emitters.map((e) => [e.blendMode, e.map, e.mapLoaded, e.mapPath])));
  expect((await state(page, id)).emitters[0].mapLoaded).toBe(true);
  expect(change.quadsOn).toBeGreaterThan(0);
  expect(change.off.changed).toBeGreaterThan(200);
  // Negative: two frames without particles are the same picture.
  expect(change.offAgain.changed).toBeLessThan(50);
  // Negative: while off, no quads, and the emitters do not run.
  await page.evaluate(() => window.sc2viewer.setParticles(false));
  const before = await state(page, id);
  await advance(page, id, 0.5);
  // `quads` is what the last drawn frame drew: draw one.
  const after = await page.evaluate((i) => {
    window.sc2viewer.mark();
    return window.sc2viewer.particles(i);
  }, id);
  await page.evaluate(() => window.sc2viewer.setParticles(true));
  expect(after.quads).toBe(0);
  expect(after.emitters[0].spawned).toBe(before.emitters[0].spawned);
  expect(after.emitters[0].live).toBe(0);
  expect(errors).toEqual([]);
});

test('negative: Probe standing: its Stand animation keys the emission rate to 0, so it emits nothing', async ({ page }) => {
  const errors = await open(page);
  const id = await unit(page, 'Probe');
  const item = (await page.evaluate(() => window.sc2viewer.state())).items[0];
  console.log('Probe sequence', item.sequenceName);
  expect(item.sequenceName).toMatch(/^Stand/);
  await advance(page, id, 1);
  const s = await state(page, id);
  console.log('Probe standing', JSON.stringify(s.emitters.map((e) => [e.rateInit, e.rateMin, e.rateMax, e.spawned])));
  for (const e of s.emitters) {
    expect(e.rateMax).toBe(0);
    expect(e.spawned).toBe(0);
  }
  expect(s.quads).toBe(0);
  expect(errors).toEqual([]);
});

test('Zerus Tree: world-space spores stay where they were born when the tree moves, and new ones are born at its new place', async ({ page }) => {
  test.setTimeout(60_000);
  const errors = await open(page);
  const id = await page.evaluate(() => window.sc2viewer.addDoodad('ZerusTree', { x: 0, y: 0, rot: 0, variation: 9, pick: 0.5, dataset: 'stock' }));
  await idle(page);
  const path = (await page.evaluate(() => window.sc2viewer.state())).items[0].path;
  expect(path.toLowerCase()).toMatch(/zerustree_09\.m3$/);
  await advance(page, id, 6);
  const s = await state(page, id, true);
  console.log('Zerus Tree', JSON.stringify(s.emitters.map(({ particles, ...e }) => ({ ...e, particles: particles.length }))));
  expect(s.emitters.map((e) => [e.version, e.worldSpace])).toEqual([[21, true], [21, true]]);
  for (const e of s.emitters) {
    const meanLife = (e.lifeMin + e.lifeMax) / 2;
    expect(e.live).toBeGreaterThanOrEqual(Math.floor(0.5 * e.rateMax * meanLife));
    expect(e.live).toBeLessThanOrEqual(e.max);
    expect(particleFaults(e)).toEqual([]);
  }
  // Move the tree 5 to the side, without advancing time: both snapshots in
  // one call, so no frame of the page runs between them.
  const { first, moved } = await page.evaluate((i) => {
    const v = window.sc2viewer;
    const first = v.particles(i, true);
    v.setItemPosition(i, 5, 0);
    v.mark();
    return { first, moved: v.particles(i, true) };
  }, id);
  const before = new Map(first.emitters[0].particles.map((p) => [p.serial, p.position]));
  const stayed = moved.emitters[0].particles.filter((p) => before.has(p.serial));
  expect(first.emitters[0].live).toBeGreaterThan(0);
  expect(stayed.length).toBe(first.emitters[0].particles.length);
  expect(stayed.filter((p) => dist(p.position, before.get(p.serial)) > 1e-4)).toEqual([]);
  // The emitter itself went along.
  expect(moved.emitters[0].origin[0] - first.emitters[0].origin[0]).toBeCloseTo(5, 3);
  // New births are at the new place: after a full lifespan, all are in reach of it.
  await advance(page, id, s.emitters[0].lifeMax + 0.5);
  const later = await state(page, id, true);
  expect(later.emitters[0].live).toBeGreaterThan(0);
  expect(particleFaults(later.emitters[0])).toEqual([]);
  expect(errors).toEqual([]);
});

test('animated colour keys (SDCC tracks, COL entries) are read: Nova Defensive Drone emits without a page error', async ({ page }) => {
  const errors = await open(page);
  const id = await unit(page, 'NovaDefensiveDrone');
  await advance(page, id, 2);
  const s = await state(page, id, true);
  console.log('Nova Defensive Drone', JSON.stringify(s.emitters.map(({ particles, ...e }) => ({ rate: [e.rateMin, e.rateMax], live: e.live, spawned: e.spawned, colors: [...new Set(particles.map((p) => p.startColor.join(',')))].slice(0, 4) }))));
  expect(s.emitters.length).toBeGreaterThan(0);
  const all = s.emitters.flatMap((e) => e.particles);
  expect(all.length).toBeGreaterThan(0);
  expect(all.filter((p) => !p.startColor.every((c) => Number.isFinite(c) && c >= 0 && c <= 255))).toEqual([]);
  for (const e of s.emitters) expect(particleFaults(e)).toEqual([]);
  expect(errors).toEqual([]);
});

/** Quad corners 0 and 1 differ along the length axis, 0 and 3 along the width (particlerender CORNERS). */
const sub = (q, a, b) => [q[a * 3] - q[b * 3], q[a * 3 + 1] - q[b * 3 + 1], q[a * 3 + 2] - q[b * 3 + 2]];
const len = (v) => Math.hypot(...v);
const cosine = (a, b) => Math.abs(a[0] * b[0] + a[1] * b[1] + a[2] * b[2]) / (len(a) * len(b));

test('Battlecruiser at rest: tail particles are stretched along their travel; billboards stay square', async ({ page }) => {
  const errors = await open(page);
  const id = await unit(page, 'Battlecruiser', -1);
  await advance(page, id, 1);
  // Two snapshots 0.05 s apart in one call: the travel of each particle between them.
  const { first, second } = await page.evaluate((i) => {
    const v = window.sc2viewer;
    const first = v.particles(i, true);
    v.advanceParticles(i, 0.05, 1 / 60);
    return { first, second: v.particles(i, true) };
  }, id);
  const tails = second.emitters.filter((e) => e.particleType === 1 && e.live > 0);
  console.log('Battlecruiser tail emitters', JSON.stringify(tails.map((e) => [e.index, e.live, e.tail])));
  expect(tails.length).toBeGreaterThan(0);
  let checked = 0;
  const off = [];
  for (const e of tails) {
    const before = new Map(first.emitters[e.index].particles.map((p) => [p.serial, p.position]));
    for (const p of e.particles) {
      const was = before.get(p.serial);
      if (!was) continue;
      const travel = [p.position[0] - was[0], p.position[1] - was[1], p.position[2] - was[2]];
      if (len(travel) < 1e-4) continue;
      checked++;
      const c = cosine(sub(p.quad, 1, 0), travel);
      if (c < 0.95) off.push(c.toFixed(3));
      // At least the tail length times the width (unless clampTailParts cuts it).
      const ratio = len(sub(p.quad, 1, 0)) / len(sub(p.quad, 3, 0));
      if (!(e.flags & CLAMP_TAIL) && ratio < e.tail - 1e-3) off.push(`ratio ${ratio.toFixed(3)} < tail ${e.tail}`);
    }
  }
  console.log('Battlecruiser tails checked', checked, 'off', JSON.stringify(off.slice(0, 10)));
  expect(checked).toBeGreaterThan(5);
  expect(off).toEqual([]);
  // Negative: a billboard (type 0) is square whatever its travel.
  const bills = second.emitters.filter((e) => e.particleType === 0).flatMap((e) => e.particles);
  expect(bills.length).toBeGreaterThan(0);
  expect(bills.filter((p) => Math.abs(len(sub(p.quad, 1, 0)) - len(sub(p.quad, 3, 0))) > 1e-4 * len(sub(p.quad, 3, 0)) + 1e-6)).toEqual([]);
  expect(errors).toEqual([]);
});

test('Helios (PARC copies): the jet fire emits from all four engines, the end exhaust and fire from their copies only', async ({ page }) => {
  const errors = await open(page);
  const id = await unit(page, 'BattlecruiserHelios', -1);
  await advance(page, id, 2);
  const s = await state(page, id, true);
  const byBone = (b) => s.emitters.find((e) => e.bone === b);
  const slotOf = (e, p) => {
    const d = e.origins.map((o) => dist(p.position, o));
    return d.indexOf(Math.min(...d));
  };
  console.log('Helios copies', JSON.stringify(s.emitters.filter((e) => e.copies.length).map((e) => [e.bone, e.rateInit, e.copies.map((c) => [c.bone, c.rateInit]), e.slotSpawned, e.live])));
  // battlecruiserwarfield.m3 (m3addon): jetfire02 on bone 25 with copies on 26, 27, 28, rate 35 each.
  const jet = byBone(25);
  expect(jet.copies.map((c) => c.bone)).toEqual([26, 27, 28]);
  // Four separate places, each emitting at the same rate (2 s x 35 = 70; wide window).
  expect(new Set(jet.origins.map((o) => o.map((v) => v.toFixed(3)).join())).size).toBe(4);
  for (const n of jet.slotSpawned) expect(n).toBeGreaterThan(40);
  // Each engine holds live particles of its own.
  const held = [0, 0, 0, 0];
  for (const p of jet.particles) held[slotOf(jet, p)]++;
  for (const n of held) expect(n).toBeGreaterThan(0);
  // End exhaust (bone 19): the emitter's own rate is 0; copies on 34 and 37 at 15, on 44 at 0.
  const exhaust = byBone(19);
  expect(exhaust.copies.map((c) => [c.bone, c.rateInit])).toEqual([[34, 15], [37, 15], [44, 0]]);
  expect(exhaust.slotSpawned[0]).toBe(0);
  expect(exhaust.slotSpawned[1]).toBeGreaterThan(10);
  expect(exhaust.slotSpawned[2]).toBeGreaterThan(10);
  expect(exhaust.slotSpawned[3]).toBe(0);
  for (const e of s.emitters) expect(particleFaults(e)).toEqual([]);
  expect(errors).toEqual([]);
});

test('Stalker Attack (partEmit): each key the playhead steps over bursts its value once; none at rest, none after the end', async ({ page }) => {
  const errors = await open(page);
  // At rest: no playhead, no burst.
  const rest = await unit(page, 'Stalker', -1);
  await advance(page, rest, 2);
  const still = await state(page, rest);
  expect(still.emitters.flatMap((e) => e.bursts).every((n) => n === 0)).toBe(true);
  const id = await unit(page, 'Stalker');
  const before = await state(page, id);
  const e0 = before.emitters[0];
  expect(e0.partEmit.animFlags & 2).toBe(2);
  // The oracle: the positive keys of Attack, read from the model data.
  const { keys, end } = await page.evaluate(([i, ref]) => {
    const item = window.SC2App.items.find((x) => x.id === i);
    const seq = item.model.sequences.find((s) => s.name === 'Attack');
    return { keys: window.sc2viewer.animKeys(i, 'Attack', ref), end: seq.interval[1] };
  }, [id, e0.partEmit]);
  const want = keys.filter(([t, v]) => t >= 0 && t <= end && v > 0).reduce((n, [, v]) => n + v, 0);
  console.log('Stalker Attack partEmit keys', JSON.stringify(keys), 'end', end, 'want', want);
  expect(want).toBeGreaterThan(0);
  // Once through Attack, held at its last frame.
  const reached = await page.evaluate((i) => window.sc2viewer.playParticles(i, 'Attack', 3), id);
  const after = await state(page, id);
  console.log('Stalker Attack bursts', JSON.stringify(after.emitters.map((e) => [e.bursts, e.spawned])), 'frame', reached);
  expect(reached).toBe(end);
  expect(after.emitters[0].bursts[0]).toBe(want);
  expect(after.emitters[0].spawned).toBeGreaterThanOrEqual(want);
  // Held at the end: more time owes nothing more.
  await page.evaluate((i) => {
    const item = window.SC2App.items.find((x) => x.id === i);
    for (let k = 0; k < 60; k++) item.instance.updateAnimations(1 / 60);
  }, id);
  expect((await state(page, id)).emitters[0].bursts[0]).toBe(want);
  expect(errors).toEqual([]);
});

/** PAR_ flags bit clampTailParts (m3addon structures.xml). */
const CLAMP_TAIL = 0x40000;

test('Searchlight beam (clampTailParts): no tail reaches farther than its particle travelled; unclamped it would', async ({ page }) => {
  const errors = await open(page);
  const id = await unit(page, 'DestructibleSearchlight', -1);
  await advance(page, id, 2);
  const s = await state(page, id, true);
  const beams = s.emitters.filter((e) => e.particleType === 1 && (e.flags & CLAMP_TAIL) && e.live > 0);
  expect(beams.length).toBeGreaterThan(0);
  const rows = [];
  for (const e of beams) {
    for (const p of e.particles) {
      const half = len(sub(p.quad, 1, 0)) / 2;
      const width = len(sub(p.quad, 3, 0)) / 2;
      const travelled = len([p.position[0] - p.start[0], p.position[1] - p.start[1], p.position[2] - p.start[2]]);
      // Unclamped half length, and the clamped one (WhiteoutFlakes StepAnalytic):
      // the tail ratio cut to travelled / (speed x width), then max(ratio, speed x ratio).
      const full = width * Math.max(e.tail, e.tail * p.speed);
      const cut = Math.max(travelled, travelled / p.speed);
      rows.push({ half, full, cut, want: Math.min(full, cut), age: p.age });
    }
  }
  console.log('Searchlight beams', JSON.stringify(rows.slice(0, 8)));
  expect(rows.length).toBeGreaterThan(3);
  expect(rows.filter((r) => Math.abs(r.half - r.want) > 1e-3 * r.full + 1e-4)).toEqual([]);
  // Negative: young particles are shorter than the unclamped rule would draw.
  expect(rows.filter((r) => r.half < 0.9 * r.full).length).toBeGreaterThan(0);
  expect(errors).toEqual([]);
});

test('particle materials draw with their alpha-mask layers bound, and only layers the particle shader reads', async ({ page }) => {
  const errors = await open(page);
  // Zerus Tree spores: smokelit.dds with an alpha mask on its alpha channel.
  const id = await page.evaluate(() => window.sc2viewer.addDoodad('ZerusTree', { x: 0, y: 0, rot: 0, variation: 9, pick: 0.5, dataset: 'stock' }));
  await idle(page);
  await advance(page, id, 3);
  // Draw one frame, then read the layer bind counters.
  const binds = (x) => x.emitters.map((e) => e.layers.map((l) => l.binds));
  const before = binds(await state(page, id));
  await page.evaluate(() => window.sc2viewer.mark());
  const s = await state(page, id);
  const drawn = s.emitters.filter((e) => e.quads > 0);
  expect(binds(s)).not.toEqual(before);
  console.log('Zerus Tree particle layers', JSON.stringify(drawn.map((e) => [e.index, e.blendMode, e.layers])));
  const masked = drawn.filter((e) => e.layers.some((l) => l.type === 'alphaMask'));
  expect(masked.length).toBe(2);
  for (const e of masked) {
    const mask = e.layers.find((l) => l.type === 'alphaMask');
    // Channel 2: the alpha channel (layers.glsl CHANNELSELECT_A).
    expect(mask.channels).toBe(2);
    expect(mask.binds).toBeGreaterThan(before[e.index][e.layers.indexOf(mask)]);
  }
  // Negative: no particle layer list names a layer the particle shader does not read.
  const known = new Set(['diffuse', 'emissive', 'emissive2', 'alphaMask', 'alphaMask2']);
  expect(drawn.flatMap((e) => e.layers.map((l) => l.type)).filter((t) => !known.has(t))).toEqual([]);
  expect(errors).toEqual([]);
});

test('Xel Naga Shrine: emitters with a displacement material run and draw over the frame copy; with displacement off they draw nothing', async ({ page }) => {
  const errors = await open(page);
  const warnings = [];
  page.on('console', (m) => warnings.push(m.text()));
  const id = await unit(page, 'XelNagaShrine', -1);
  await advance(page, id, 2);
  await page.evaluate(() => window.sc2viewer.mark());
  const s = await state(page, id);
  const shimmer = s.emitters.filter((e) => e.materialType === 2);
  console.log('XelNagaShrine displacement emitters', JSON.stringify(shimmer.map((e) => [e.index, e.live, e.quads, e.layers])));
  expect(shimmer.length).toBeGreaterThan(0);
  expect(shimmer.filter((e) => e.live > 0 && e.quads === e.live).length).toBeGreaterThan(0);
  // No longer listed as not drawn.
  expect(warnings.filter((w) => w.includes('material type 2 (displacement)'))).toEqual([]);
  const undrawn = (await page.evaluate(() => window.sc2viewer.state())).items[0].undrawn || [];
  expect(undrawn.filter((u) => /particle emitter \d+: displacement/.test(u))).toEqual([]);
  // Negative: with displacement off, the emitters draw nothing.
  const off = await page.evaluate((i) => {
    const v = window.sc2viewer;
    v.setDisplacement(false);
    v.mark();
    const r = v.particles(i).emitters.filter((e) => e.materialType === 2).map((e) => e.quads);
    v.setDisplacement(true);
    return r;
  }, id);
  expect(off.every((q) => q === 0)).toBe(true);
  expect(errors).toEqual([]);
});

test('negative: a video texture (.ogv) is not fetched; the model lists it as not drawn', async ({ page }) => {
  const errors = await open(page);
  const asked = [];
  page.on('request', (r) => {
    if (r.url().toLowerCase().includes('.ogv')) asked.push(r.url());
  });
  await unit(page, 'BlimpAds');
  const item = (await page.evaluate(() => window.sc2viewer.state())).items[0];
  console.log('BlimpAds undrawn', JSON.stringify(item.undrawn));
  expect(asked).toEqual([]);
  expect((item.undrawn || []).filter((u) => u.includes('video texture') && u.endsWith('.ogv')).length).toBeGreaterThan(0);
  expect(errors).toEqual([]);
});

test('negative: a model without emitters has none, and the particle switch changes nothing in its frame', async ({ page }) => {
  const errors = await open(page);
  const id = await unit(page, 'Marine');
  const s = await state(page, id);
  expect(s.emitters).toEqual([]);
  expect(s.quads).toBe(0);
  const change = await page.evaluate(() => {
    const v = window.sc2viewer;
    v.setParticles(false);
    v.mark();
    v.setParticles(true);
    return v.changedSinceMark();
  });
  expect(change.changed).toBeLessThan(50);
  expect(errors).toEqual([]);
});
