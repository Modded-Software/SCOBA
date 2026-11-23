// One particle emitter as the renderer runs it, for the tests.

import type M3ParticleSystem from '@renderer/viewer/handlers/m3/particlesystem';
import type M3Layer from '@renderer/viewer/handlers/m3/layer';
import { app, type Item } from '../../page/core/app';
import { m3Shared } from '../../page/core/library';

const position = new Float32Array(3);
const quad = new Float32Array(12);
const start = new Float32Array(3);

const originOf = (m: ArrayLike<number>): number[] => [m[12] ?? 0, m[13] ?? 0, m[14] ?? 0];

/** The layers a particle draws with, and the one that gives its texture. */
function layersOf(item: Item, s: M3ParticleSystem): { materialType: number; blendMode: number | null; layers: M3Layer[]; layer: M3Layer | undefined } {
  const e = s.emitter;
  const map = item.model.materialMaps[e.materialReferenceIndex];
  if (!map) throw new Error(`emitter ${s.index}: no material reference ${e.materialReferenceIndex}`);
  // Type 2: a displacement material (normal and strength layers); otherwise standard.
  const displacement = map.materialType === 2 ? item.model.displacementMaterials[map.materialIndex] : undefined;
  if (displacement) {
    return { materialType: map.materialType, blendMode: null, layers: [displacement.normalLayer, displacement.strengthLayer].filter((l) => l.active), layer: undefined };
  }
  const material = item.model.materials[1][map.materialIndex];
  if (!material) throw new Error(`emitter ${s.index}: no material ${map.materialIndex}`);
  const pick = (n: number): M3Layer | undefined => material.layers[n];
  const layer = [pick(0), pick(4)].find((l) => l && l.active && !l.constant && l.texture);
  // Diffuse, emissive 1 and 2, alpha masks 1 and 2.
  const layers = [0, 4, 5, 8, 9].map(pick).filter((l): l is M3Layer => Boolean(l && l.active));
  return { materialType: map.materialType, blendMode: material.blendMode, layers, layer };
}

/**
 * One emitter. `reach`: the farthest a particle can be from its emitter
 * (emission area, top start speed and the vertical acceleration over the
 * longest life, times the emitter scale). With `withParticles`, each live
 * particle: serial, age and life in seconds, world position, start colour
 * (rgba 0 to 255).
 */
export function emitterState(item: Item, s: M3ParticleSystem, withParticles: boolean): Record<string, unknown> {
  const e = s.emitter;
  const origin = originOf(s.matrix);
  // PARC copies emit from their own bones: every slot's origin, the emitter first.
  const copies = s.copies.map((c, k) => ({ bone: c.copy.boneIndex, rateInit: c.copy.emissionRate.initValue, origin: originOf(c.matrix), spawned: s.slotSpawned[k + 1] }));
  const origins = [origin, ...copies.map((c) => c.origin)];
  const scale = Math.max(s.scale(), ...s.copies.map((c) => Math.hypot(c.matrix[0] ?? 0, c.matrix[1] ?? 0, c.matrix[2] ?? 0)));
  const life = s.lifeMax;
  const reach = scale * (s.areaReach() + s.topSpeed() * life + 0.5 * Math.abs(e.zAcceleration) * life * life) + 1e-3;
  const { materialType, blendMode, layers, layer } = layersOf(item, s);
  const out: Record<string, unknown> = {
    materialType,
    blendMode,
    layers: layers.map((l) => ({ type: l.type, channels: l.colorChannels, constant: Boolean(l.constant), binds: l.binds })),
    map: layer ? layer.type : null,
    mapLoaded: Boolean(layer && layer.texture && layer.texture.texture),
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
    const scene = item.instance.scene;
    if (!scene) throw new Error(`item ${item.id} is in no scene`);
    const m3 = m3Shared(app().viewer);
    const particles = [];
    for (let i = 0; i < s.live; i++) {
      s.position(position, i);
      m3.particleQuad(s, i, scene.camera, quad);
      const speed = m3.particleMotion(s, i, start);
      particles.push({
        bounces: s.bounces[i],
        rest: s.rest[i],
        born: Array.from(s.born.subarray(i * 3, i * 3 + 3)),
        serial: s.serial[i],
        age: s.time - (s.birth[i] ?? 0),
        life: s.life[i],
        position: Array.from(position),
        quad: Array.from(quad),
        start: Array.from(start),
        speed,
        startColor: Array.from(s.colors.subarray(i * 12, i * 12 + 4)),
      });
    }
    out['particles'] = particles;
  }
  return out;
}
