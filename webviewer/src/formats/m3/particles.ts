// Particle emitters (M3 PAR_): the switch, and inspection for the tests.
// The renderer runs and draws them (ref handlers/m3/particlesystem.ts).
// Also the M3 handler's other switches: ground lights and the fresnel term.

import type M3ParticleSystem from '@renderer/viewer/handlers/m3/particlesystem';
import type { AnimationReference } from '@renderer/parsers/m3/animationreference';
import { app, type Item } from '../../page/core/app';
import { m3Shared } from '../../page/core/library';
import { emitterState } from './emitters';

const find = (id: number): Item => {
  const item = app().items.find((i) => i.id === id);
  if (!item) throw new Error(`no item ${id}`);
  return item;
};
const m3 = () => m3Shared(app().viewer);
const quad = new Float32Array(12);

/** Run and draw particles, or not. Off, the emitters hold no particles and do not run. */
function setParticles(on: boolean): void {
  m3().particlesEnabled = Boolean(on);
}

/**
 * The emitters of one item as the renderer runs them. With `withParticles`,
 * each live particle too (emitters.ts).
 */
function particles(id: number, withParticles = false): { enabled: boolean; emitters: Record<string, unknown>[]; quads: number } {
  const item = find(id);
  const systems = item.instance.particleSystems;
  return { enabled: m3().particlesEnabled, emitters: systems.map((s) => emitterState(item, s, withParticles)), quads: systems.reduce((n, s) => n + s.quads, 0) };
}

/**
 * Run one item's emitters for `seconds` of game time in steps of `step`
 * seconds, with the frame loop's clock stopped for it (time scale 0), so
 * its particles move only here and stay put while a test measures them.
 */
function advanceParticles(id: number, seconds: number, step = 1 / 60): number {
  const item = find(id);
  item.instance.timeScale = 0;
  const steps = Math.round(seconds / step);
  for (let i = 0; i < steps; i++) item.instance.updateParticles(step);
  return steps;
}

/** Move an item to ground point (x, y), as the scene list does. */
function setItemPosition(id: number, x: number, y: number): void {
  app().setPosition(find(id), x, y);
}

/**
 * Play an item's sequence `name` from its start for `seconds`, in `step`
 * steps, with the frame loop's clock stopped for it (time scale 0), so
 * the animation and its particles move only here. `loopMode` 1 holds the
 * last frame. Returns the frame reached, in ms.
 */
function playParticles(id: number, name: string, seconds: number, step = 1 / 60, loopMode = 1): number {
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
function animKeys(id: number, name: string, ref: AnimationReference): [number, number][] {
  const item = find(id);
  const pose = item.instance.skeleton;
  const stg = pose ? pose.stg[item.model.sequences.findIndex((s) => s.name === name)] : undefined;
  if (!stg) throw new Error(`no sequence ${name}`);
  const out: [number, number][] = [];
  for (const i of stg.stcIndices) {
    const stc = stg.stc[i];
    const where = stc ? stc.animRefs[ref.animId] : undefined;
    const sts = stc ? stg.sts[stc.stsIndex] : undefined;
    if (!stc || !where || !sts || !sts.hasData(ref)) continue;
    const [container, track] = where;
    if (container === undefined || track === undefined) continue;
    const sd = stc.sd[container]?.sd[track];
    if (!sd) continue;
    sd.keys.forEach((t: number, k: number) => out.push([t, Number(sd.values[k])]));
  }
  return out;
}

/** The particle system of emitter `index` of an item. */
function systemOf(item: Item, index: number): M3ParticleSystem | undefined {
  return item.instance.particleSystems.find((x) => x.index === index);
}

/**
 * Draw particle `k` of emitter `index` alone (the item's clock stopped,
 * its mesh and other particles left out) and measure it: for each [u, v]
 * on its quad (0 to 1, u along the width, v along the length), how much
 * the drawn colour there differs from the frame without the particle
 * (sum of |r|, |g|, |b|, 0 to 765). Destroys the item's other particles;
 * the measured one is particle 0 afterwards.
 */
function particleSamples(id: number, index: number, k: number, uvs: readonly (readonly number[])[]): (number | null)[] {
  const item = find(id);
  const instance = item.instance;
  const scene = instance.scene;
  const s = systemOf(item, index);
  if (!s || !scene || k >= s.live) throw new Error(`no particle ${k} of emitter ${index}`);
  const camera = scene.camera;
  const gl = app().viewer.gl;
  instance.timeScale = 0;
  for (const other of instance.particleSystems) if (other !== s) other.live = 0;
  if (k !== 0) s.move(k, 0);
  s.live = 1;
  const batches = item.model.batches.slice();
  item.model.batches.length = 0;
  const read = (): { w: number; h: number; data: Uint8Array } => {
    app().resize();
    app().draw(0);
    const w = gl.drawingBufferWidth;
    const h = gl.drawingBufferHeight;
    const data = new Uint8Array(w * h * 4);
    gl.readPixels(0, 0, w, h, gl.RGBA, gl.UNSIGNED_BYTE, data);
    return { w, h, data };
  };
  const q = (i: number): number => quad[i] ?? 0;
  try {
    m3().particleQuad(s, 0, camera, quad);
    const screen = new Float32Array(2);
    const points = uvs.map(([u = 0, v = 0]) => {
      const p = new Float32Array(3);
      for (let j = 0; j < 3; j++) p[j] = q(j) + (q(9 + j) - q(j)) * u + (q(3 + j) - q(j)) * v;
      camera.worldToScreen(screen, p, scene.viewport);
      return [screen[0] ?? 0, screen[1] ?? 0] as const;
    });
    const withIt = read();
    s.live = 0;
    const without = read();
    return points.map(([x, y]) => {
      if (x < 0 || y < 0 || x >= withIt.w || y >= withIt.h) return null;
      const i = (Math.floor(y) * withIt.w + Math.floor(x)) * 4;
      const d = (c: number): number => Math.abs((withIt.data[i + c] ?? 0) - (without.data[i + c] ?? 0));
      return d(0) + d(1) + d(2);
    });
  } finally {
    // The particle stays, for another measurement.
    s.live = 1;
    item.model.batches.push(...batches);
  }
}

/** Draw spot lights on the ground plane, or not; `only`: one light index (into model.lights), -1 all. */
function setGroundLights(on: boolean, only = -1): void {
  m3().groundLightsEnabled = Boolean(on);
  m3().groundLightOnly = only;
}

/** The spot lights of one item now: type, bone, world position, axis, colour, ranges, cone angles, ground hit. */
function groundLights(id: number): Record<string, unknown>[] {
  const item = find(id);
  return item.model.lights.map((l) => {
    const s = m3().groundLight(item.instance, l);
    return { type: l.lightType, bone: l.boneIndex, position: Array.from(s.position), direction: Array.from(s.direction), color: Array.from(s.color), near: s.near, far: s.far, hotSpot: s.hotSpot, falloff: s.falloff, hit: s.hit && Array.from(s.hit) };
  });
}

/** Apply the layers' fresnel term, or not (every model). */
function setFresnel(on: boolean): void {
  m3().layerOptions.fresnel = Boolean(on);
}

export const particlesApi = { setParticles, particles, advanceParticles, playParticles, animKeys, particleSamples, setGroundLights, groundLights, setFresnel, setItemPosition };
