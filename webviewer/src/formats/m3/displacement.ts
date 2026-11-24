// Displacement materials (heat haze, cloak shimmer, warp ripples): after a
// scene is drawn, the frame so far is copied to a texture and every drawn
// instance with displacement batches draws them over it, showing the copy
// shifted along their normal maps (M3ModelInstance.renderDisplacement).

// A post pass (SPEC-VIEWER 6.3): `enabled` off draws no displacement batch
// (for comparing frames). `draw` runs right after a scene and returns how
// many mesh batches it drew; particle quads are counted on each emitter
// (sc2viewer.particles).

import type ModelViewer from '@renderer/viewer/viewer';
import M3ModelInstance from '@renderer/viewer/handlers/m3/modelinstance';
import type { PostPass } from '../../page/core/plugin';

export const DISPLACEMENT = 'displacement';

export function createDisplacement(viewer: ModelViewer): PostPass {
  const gl = viewer.gl;
  const texture = gl.createTexture();
  let width = 0;
  let height = 0;

  gl.bindTexture(gl.TEXTURE_2D, texture);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);

  const displacement: PostPass = {
    id: DISPLACEMENT,
    enabled: true,
    draw(scene, w, h) {
      // Displacement meshes, or emitters with a displacement material.
      const instances = scene.instances.filter(
        (i): i is M3ModelInstance => i instanceof M3ModelInstance && (i.model.displacementBatches.length > 0 || i.model.displacementEmitters > 0),
      );
      if (!displacement.enabled || instances.length === 0) return 0;
      let drawn = 0;
      // The canvas has no alpha (alpha: false), so the copy is RGB.
      gl.bindTexture(gl.TEXTURE_2D, texture);
      if (w !== width || h !== height) {
        gl.copyTexImage2D(gl.TEXTURE_2D, 0, gl.RGB, 0, 0, w, h, 0);
        width = w;
        height = h;
      } else {
        gl.copyTexSubImage2D(gl.TEXTURE_2D, 0, 0, 0, 0, 0, w, h);
      }
      gl.viewport(0, 0, w, h);
      gl.scissor(0, 0, w, h);
      for (const instance of instances) {
        instance.renderDisplacement(texture, w, h);
        drawn += instance.model.displacementBatches.length;
      }
      gl.depthMask(true);
      return drawn;
    },
  };
  return displacement;
}
