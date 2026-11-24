// The M3 format module (SPEC-VIEWER 6.3): its readers, its models and
// instances (adapter.ts), what its instances can do, its post pass and
// what it tells the tests.

import m3 from '@renderer/viewer/handlers/m3/handler';
import dds from '@renderer/viewer/handlers/dds/handler';
import tga from '@renderer/viewer/handlers/tga/handler';
import type M3Layer from '@renderer/viewer/handlers/m3/layer';
import type { Capabilities, FormatModule, TextureSlot, ViewerInstance } from '../../page/core/plugin';
import { adoptM3, eachLayer, M3_FORMAT, m3Instance, m3Model } from './adapter';
import { createDisplacement } from './displacement';
import { createLayersApi, m3Facts } from './layers';
import { createParticlesApi } from './particles';
import { createBillboardsApi } from './billboards';

/** Team colours the M3 shaders know. */
const TEAM_COLORS = 14;

/** One layer that names a texture file. */
class M3Slot implements TextureSlot {
  constructor(readonly layer: M3Layer) {}
  get source(): string {
    return String(this.layer.source);
  }
  ownSize(): number {
    const own = this.layer.active && this.layer.texture ? this.layer.texture.texture : null;
    return own ? Math.max(own.width, own.height) : 0;
  }
}

function capabilities(view: ViewerInstance): Capabilities {
  const instance = m3Instance(view);
  const model = m3Model(view.model);
  return {
    teamColor: { count: TEAM_COLORS, set: (index) => instance.setTeamColor(index) },
    tint: { set: (color) => instance.setVertexColor(color ? [color[0], color[1], color[2], 1] : [1, 1, 1, 1]) },
    textureOverride: {
      slots: () => eachLayer(model).flatMap(({ layer }) => (layer.active && !layer.constant && layer.source ? [new M3Slot(layer)] : [])),
      set(slot, texture) {
        if (!(slot instanceof M3Slot)) throw new Error('not an M3 texture slot');
        instance.setTexture(slot.layer.material.index, slot.layer.index, texture ?? undefined);
      },
      applied: () => instance.textureOverrides.size,
    },
    edges: { draw: (r, g, b) => instance.renderEdges(r, g, b) },
  };
}

export const m3Format: FormatModule = {
  id: M3_FORMAT,
  extensions: ['.m3'],
  handlers: [m3, dds, tga],
  adopt: adoptM3,
  capabilities,
  postPasses: (viewer) => [createDisplacement(viewer)],
  inspect: m3Facts,
  probes: (context) => ({ ...createParticlesApi(context), ...createBillboardsApi(context), ...createLayersApi(context) }),
};
