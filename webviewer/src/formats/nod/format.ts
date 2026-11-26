// The nod format module (SPEC-VIEWER-GHOST 7): StarCraft: Ghost models
// through the container the server exports with NODExport. Its handler
// takes only that container (it starts with "NODX"); its textures are DDS
// files, read by the m3 format's DDS handler. Clips come through
// attachClips. Capabilities: the edge draw and the texture override of
// each drawn group, per instance; no team colour or tint.

import type ModelViewer from '@renderer/viewer/viewer';
import type { Clip, FormatModule, RendererHandler, TextureSlot, ViewerInstance } from '../../page/core/plugin';
import { adoptNod, NOD_FORMAT, nodInstance } from './adapter';
import { readClip } from './clips';
import { isContainer } from './container';
import NodModel, { type DrawGroup } from './model';
import { createNodProbes } from './probes';
import { loadShader } from '../../page/core/render/gl';
import { SHADER_LOADING } from './instance';

const handler: RendererHandler = {
  load(viewer: ModelViewer): void {
    // Bone matrices are float texels.
    if (!viewer.webgl.ensureExtension('OES_texture_float')) throw new Error('nod: no float texture support');
    // The shader files are fetched once; every model waits for them (model.ts, its blockers).
    const loading = loadShader(viewer, 'nod', '/shaders/nod.vert', '/shaders/nod.frag').then((shader) => {
      viewer.sharedCache.set('nod', shader);
    });
    viewer.sharedCache.set(SHADER_LOADING, loading);
    // Each model that waits reports a failed load as its own. The load itself is reported
    // here once, so it is seen with no model waiting too.
    loading.catch((error: unknown) => {
      console.error(`viewer: the nod shaders did not load: ${error instanceof Error ? error.message : String(error)}`);
    });
  },
  isValidSource: isContainer,
  resource: NodModel,
};

/** One drawn group with a texture file (SPEC-VIEWER-GHOST 7): its source is that file, relative to the build. */
class NodSlot implements TextureSlot {
  constructor(readonly group: DrawGroup) {}
  get source(): string {
    return this.group.look.texture ?? '';
  }
  ownSize(): number {
    const own = this.group.texture;
    return own ? Math.max(own.width, own.height) : 0;
  }
}

/** Fetch and read each clip; a clip that cannot be read is left out and named. */
async function attachClips(view: ViewerInstance, clips: readonly Clip[], url: (reference: string) => string): Promise<readonly string[]> {
  const instance = nodInstance(view);
  const bones = instance.model.bones.length;
  const refused: string[] = [];
  const read = await Promise.all(
    clips.map(async (clip) => {
      const res = await fetch(url(clip.reference));
      if (!res.ok) {
        refused.push(`${clip.name} (${clip.reference}): HTTP ${res.status}`);
        return null;
      }
      try {
        return readClip(await res.json(), clip.name, bones);
      } catch (error) {
        if (!(error instanceof Error)) throw error;
        refused.push(`${clip.name} (${clip.reference}): ${error.message}`);
        return null;
      }
    }),
  );
  instance.clips = read.filter((clip) => clip !== null);
  instance.setSequence(-1);
  return refused;
}

export const nodFormat: FormatModule = {
  id: NOD_FORMAT,
  extensions: ['.nod'],
  handlers: [handler],
  adopt: adoptNod,
  attachClips,
  capabilities: (view) => {
    const instance = nodInstance(view);
    return {
      textureOverride: {
        slots: () => instance.model.groups.flatMap((group) => (group.look.kind && group.look.texture && group.indexCount ? [new NodSlot(group)] : [])),
        set(slot, texture) {
          if (!(slot instanceof NodSlot)) throw new Error('not a nod texture slot');
          if (texture) instance.textureOverrides.set(slot.group.index, texture);
          else instance.textureOverrides.delete(slot.group.index);
        },
        applied: () => instance.textureOverrides.size,
      },
      edges: { draw: (r, g, b) => instance.renderEdges(r, g, b), triangles: () => instance.triangleCount, drawTriangles: (runs) => instance.renderTriangles(runs) },
    };
  },
  inspect(view) {
    const instance = nodInstance(view);
    return { bones: instance.model.bones.length, skinned: instance.model.skinned, clips: instance.clips.map((c) => c.name), groupsDrawnLast: instance.lastDrawn.length };
  },
  probes: (context) => createNodProbes(context),
};
