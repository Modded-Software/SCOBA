// What the nod format tells the tests (SPEC-VIEWER-GHOST 7, 9): the
// layout, the groups as drawn, the bone matrices now, the skinned
// positions now (computed here from the same matrices the shader gets),
// the axes check, and the library's edge list. Reached as sc2viewer.probe('nod', name, itemId, ...).

import { mat4, vec3 } from 'gl-matrix';
import { edgePairs } from '@renderer/viewer/edges';
import type { FeatureContext } from '../../page/core/context';
import type { Item } from '../../page/core/types';
import { nodInstance } from './adapter';
import { curveAt } from './clips';
import { STRIDE } from './container';
import { MIRROR } from './instance';
import type NodInstance from './instance';

const skin = mat4.create();
const part = mat4.create();
const point = vec3.create();

/** The vertex `v` of the instance's model, skinned by the pose now, in model space of the viewer (Y mirrored). */
function skinned(instance: NodInstance, v: number, out: vec3, normal = false): vec3 {
  const model = instance.model;
  const view = new DataView(model.data.vertices);
  const at = v * STRIDE;
  vec3.set(point, view.getFloat32(at + (normal ? 12 : 0), true), view.getFloat32(at + (normal ? 16 : 4), true), view.getFloat32(at + (normal ? 20 : 8), true));
  if (model.skinned) {
    mat4.multiplyScalar(skin, skin, 0);
    for (let k = 0; k < 4; k++) {
      const weight = view.getFloat32(at + 36 + k * 4, true);
      if (!weight) continue;
      const bone = view.getUint8(at + 32 + k);
      mat4.multiplyScalar(part, instance.matrices.subarray(bone * 16, bone * 16 + 16), weight);
      mat4.add(skin, skin, part);
    }
    if (normal) {
      skin[12] = 0;
      skin[13] = 0;
      skin[14] = 0;
    }
    vec3.transformMat4(point, point, skin);
  }
  return vec3.transformMat4(out, point, MIRROR);
}

export function createNodProbes({ scene }: Pick<FeatureContext, 'scene'>): Readonly<Record<string, unknown>> {
  function find(itemId: number): NodInstance {
    const item: Item | undefined = scene.items.find((i) => i.id === itemId);
    if (!item) throw new Error(`no item ${itemId}`);
    return nodInstance(item.instance);
  }

  /** Counts, the stride, and the group table as the export gives it. */
  function layout(itemId: number): Record<string, unknown> {
    const { data } = find(itemId).model;
    return { vertexCount: data.vertexCount, indexCount: data.indices.length, stride: STRIDE, bones: data.bones.length, materials: data.materialNames, groups: data.groups };
  }

  /** Per group: material, drawn kind (null: not drawn), triangles, texture, why it is not drawn. */
  function groups(itemId: number): Record<string, unknown>[] {
    const instance = find(itemId);
    return instance.model.groups.map((g) => ({ index: g.index, material: g.material, kind: g.look.kind, shader: g.look.shader, triangles: g.indexCount / 3, texture: g.look.texture, textureLoaded: g.texture !== null, undrawn: g.look.undrawn, why: g.look.why, drawnLast: instance.lastDrawn.includes(g.index) }));
  }

  /** The bone matrices now (global x move(offset)), 16 numbers each; the clip and the playhead. */
  function bones(itemId: number): Record<string, unknown> {
    const instance = find(itemId);
    instance.updatePose();
    return { clip: instance.clip?.name ?? null, frame: instance.frame, matrices: [...instance.matrices], globals: [...instance.globals] };
  }

  /** Skinned positions now, every `step`th vertex, Y mirrored; and the file's own positions of the same vertices. */
  function positions(itemId: number, step = 1): { skinned: number[][]; file: number[][] } {
    const instance = find(itemId);
    instance.updatePose();
    const view = new DataView(instance.model.data.vertices);
    const out = { skinned: [] as number[][], file: [] as number[][] };
    for (let v = 0; v < instance.model.data.vertexCount; v += Math.max(1, step)) {
      out.skinned.push([...skinned(instance, v, vec3.create())]);
      out.file.push([view.getFloat32(v * STRIDE, true), view.getFloat32(v * STRIDE + 4, true), view.getFloat32(v * STRIDE + 8, true)]);
    }
    return out;
  }

  /**
   * The axes check: for each triangle with an area, whether the normal
   * from its corners (right-handed, counter-clockwise) points the way of
   * its vertex normals. `drawn`: as the viewer draws it (Y mirrored,
   * corners turned round). `unmirrored`: the corners turned, the values not
   * mirrored. Counts of triangles that agree and that do not.
   */
  function axes(itemId: number): Record<string, { agree: number; disagree: number }> {
    const instance = find(itemId);
    const { data } = instance.model;
    const view = new DataView(data.vertices);
    const read = (v: number, offset: number, mirror: boolean): vec3 => vec3.fromValues(view.getFloat32(v * STRIDE + offset, true), view.getFloat32(v * STRIDE + offset + 4, true) * (mirror ? -1 : 1), view.getFloat32(v * STRIDE + offset + 8, true));
    const count = (mirror: boolean): { agree: number; disagree: number } => {
      const result = { agree: 0, disagree: 0 };
      const face = vec3.create();
      const e1 = vec3.create();
      const e2 = vec3.create();
      for (let i = 0; i + 2 < data.indices.length; i += 3) {
        // As drawn: a, c, b (model.ts turns each triangle round).
        const [a, b, c] = [data.indices[i] ?? 0, data.indices[i + 2] ?? 0, data.indices[i + 1] ?? 0];
        const pa = read(a, 0, mirror);
        vec3.cross(face, vec3.sub(e1, read(b, 0, mirror), pa), vec3.sub(e2, read(c, 0, mirror), pa));
        if (vec3.length(face) < 1e-12) continue;
        const n = vec3.add(vec3.create(), vec3.add(vec3.create(), read(a, 12, mirror), read(b, 12, mirror)), read(c, 12, mirror));
        if (vec3.dot(face, n) > 0) result.agree++;
        else result.disagree++;
      }
      return result;
    };
    return { drawn: count(true), unmirrored: count(false) };
  }

  /** Play clip `index` and hold the playhead at `ms`, for the animation tests. */
  function holdAt(itemId: number, index: number, ms: number): Record<string, unknown> {
    const instance = find(itemId);
    instance.setSequence(index);
    instance.frame = ms;
    instance.timeScale = 0;
    instance.updatePose();
    return { sequence: instance.sequence, frame: instance.frame };
  }

  /**
   * The key joins of every clip of the instance (SPEC-VIEWER-GHOST 4.2): for
   * each key but the last of a track, the curve at the key's end against
   * the next key's value. `frames`: t in frames since the key (the
   * viewer's reading). `unit`: t from 0 to 1 over the key. A join holds
   * when the error is below 0.001, relative to the value (at least 1).
   */
  function joins(itemId: number): Record<string, { hold: number; miss: number }> {
    const instance = find(itemId);
    const out = { frames: { hold: 0, miss: 0 }, unit: { hold: 0, miss: 0 } };
    const end = new Float64Array(3);
    const next = new Float64Array(3);
    for (const clip of instance.clips) {
      for (const track of clip.tracks) {
        for (let k = 0; k + 1 < track.frames.length; k++) {
          const span = (track.frames[k + 1] ?? 0) - (track.frames[k] ?? 0);
          curveAt(track, k + 1, 0, next);
          for (const [reading, t] of [['frames', span], ['unit', 1]] as const) {
            curveAt(track, k, t, end);
            const error = Math.max(...[0, 1, 2].map((a) => Math.abs((end[a] ?? 0) - (next[a] ?? 0)) / Math.max(1, Math.abs(next[a] ?? 0))));
            if (error < 0.001) out[reading].hold++;
            else out[reading].miss++;
          }
        }
      }
    }
    return out;
  }

  /**
   * The palette check: the mean distance of each skinned vertex from the
   * rest place of the bone that carries most of its weight, with each
   * vertex's bone numbers as exported, and shifted by `shift` (a palette
   * read off by that much). Rest places from the offsets (clips.ts).
   */
  function boneSpread(itemId: number, shift: number): { vertices: number; mean: number } {
    const instance = find(itemId);
    const { data } = instance.model;
    const view = new DataView(data.vertices);
    let sum = 0;
    let vertices = 0;
    for (let v = 0; v < data.vertexCount; v++) {
      let best = 0;
      let weight = -1;
      for (let k = 0; k < 4; k++) {
        const w = view.getFloat32(v * STRIDE + 36 + k * 4, true);
        if (w > weight) [weight, best] = [w, view.getUint8(v * STRIDE + 32 + k)];
      }
      const bone = data.bones[(best + shift) % data.bones.length];
      if (!bone) continue;
      const at = [0, 1, 2].map((a) => view.getFloat32(v * STRIDE + a * 4, true) + (bone.offset[a] ?? 0));
      sum += Math.hypot(at[0] ?? 0, at[1] ?? 0, at[2] ?? 0);
      vertices++;
    }
    return { vertices, mean: vertices ? sum / vertices : 0 };
  }

  /** The triangles of group `group` as drawn (corners a, c, b of the export's a, b, c), as vertex numbers. */
  function triangles(itemId: number, group: number): number[][] {
    const { data, groups: drawn } = find(itemId).model;
    const g = drawn[group];
    if (!g) throw new Error(`no group ${group} of ${drawn.length}`);
    const out: number[][] = [];
    for (let i = g.firstIndex; i + 2 < g.firstIndex + g.indexCount; i += 3) out.push([data.indices[i] ?? 0, data.indices[i + 2] ?? 0, data.indices[i + 1] ?? 0]);
    return out;
  }

  /** Whether any bone matrix now holds a number that is not finite. */
  function poseFinite(itemId: number): boolean {
    const instance = find(itemId);
    instance.updatePose();
    return instance.matrices.every(Number.isFinite);
  }

  /** The library's edge list of a triangle list (the edge draw of both formats), for a unit test. */
  const edges = (elements: readonly number[], start = 0, count = elements.length - start): number[] => edgePairs(elements, start, count);

  return { layout, groups, bones, positions, axes, holdAt, joins, poseFinite, boneSpread, triangles, edges };
}
