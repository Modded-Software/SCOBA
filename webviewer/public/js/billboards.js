// Billboard behaviours (M3 BBSC): inspection for the tests. The renderer
// turns the bones to the camera (ref handlers/m3/billboard.ts).
'use strict';

(() => {
  const app = window.SC2App;
  const { items } = app;

  /**
   * One item's BBSC records and, per record, its bone's world axes now
   * (x, y, z, each unit length) and position, and the camera eye and
   * forward. `billboarded`: bones turned so far, over all updates.
   */
  function billboards(id) {
    const item = items.find((i) => i.id === id);
    if (!item) throw new Error(`no item ${id}`);
    const { instance, model } = item;
    const camera = instance.scene.camera;
    const nodes = instance.skeleton ? instance.skeleton.nodes : [];
    const unit = (m, c) => {
      const v = [m[c * 4], m[c * 4 + 1], m[c * 4 + 2]];
      const l = Math.hypot(...v) || 1;
      return v.map((x) => x / l);
    };
    const records = [...model.billboards.values()].map((r) => {
      const m = nodes[r.boneIndex] ? nodes[r.boneIndex].worldMatrix : null;
      return {
        bone: r.boneIndex,
        name: model.bones[r.boneIndex] ? model.bones[r.boneIndex].name : null,
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
      forward: [-back[0], -back[1], -back[2]],
      up: Array.from(camera.directionY),
      records,
    };
  }

  Object.assign(app, { billboards });
})();
