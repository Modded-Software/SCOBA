// Billboard behaviours (M3 BBSC): inspection for the tests. The renderer
// turns the bones to the camera (ref handlers/m3/billboard.ts).

import { app } from '../../page/core/app';

/** Column `c` of a 4x4 matrix, unit length. */
function unit(m: ArrayLike<number>, c: number): number[] {
  const v = [m[c * 4] ?? 0, m[c * 4 + 1] ?? 0, m[c * 4 + 2] ?? 0];
  const l = Math.hypot(...v) || 1;
  return v.map((x) => x / l);
}

/**
 * One item's BBSC records and, per record, its bone's world axes now
 * (x, y, z, each unit length) and position, and the camera eye and
 * forward. `billboarded`: bones turned so far, over all updates.
 */
function billboards(id: number): Record<string, unknown> {
  const item = app().items.find((i) => i.id === id);
  if (!item) throw new Error(`no item ${id}`);
  const { instance, model } = item;
  const scene = instance.scene;
  if (!scene) throw new Error(`item ${id} is in no scene`);
  const camera = scene.camera;
  const nodes = instance.skeleton ? instance.skeleton.nodes : [];
  const records = [...model.billboards.values()].map((r) => {
    const node = nodes[r.boneIndex];
    const m = node ? node.worldMatrix : null;
    const bone = model.bones[r.boneIndex];
    return {
      bone: r.boneIndex,
      name: bone ? bone.name : null,
      type: r.billboardType,
      lookAt: r.cameraLookAt,
      axes: m ? [unit(m, 0), unit(m, 1), unit(m, 2)] : null,
      position: m ? [m[12], m[13], m[14]] : null,
    };
  });
  const back = camera.directionZ;
  return {
    sequence: instance.sequence,
    billboarded: instance.skeleton ? instance.skeleton.billboarded : 0,
    eye: Array.from(camera.location),
    forward: [-(back[0] ?? 0), -(back[1] ?? 0), -(back[2] ?? 0)],
    up: Array.from(camera.directionY),
    records,
  };
}

export const billboardsApi = { billboards };
