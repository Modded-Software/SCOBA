// The scene state the tests read: sc2viewer.state().

import { app, type Item } from '../../core/app';
import { constantLayers, drawOrder, texturesLoaded, texturesWanted, uvLayers } from './layers';

const sequenceName = (item: Item, index: number): string | null => (index >= 0 ? (item.model.sequences[index]?.name ?? null) : null);

function itemState(item: Item): Record<string, unknown> {
  const unit = item.unit;
  const playing = item.instance.sequence >= 0 ? item.model.sequences[item.instance.sequence] : undefined;
  return {
    id: item.id,
    path: item.path,
    // Where its data and textures come from.
    dataset: item.dataset,
    // A unit or a doodad, never both; a bare model file is neither.
    unit: unit && !unit.doodad ? unit.id : null,
    doodad: unit && unit.doodad ? unit.id : null,
    variation: item.variation,
    name: unit ? unit.name : null,
    // Loaded means the model has geometry to draw.
    loaded: item.model.batches.length > 0,
    x: item.x,
    y: item.y,
    rot: item.rot,
    scale: item.scale,
    team: item.team,
    dataScale: [...item.dataScale],
    sequence: item.instance.sequence,
    sequenceName: sequenceName(item, item.instance.sequence),
    sequences: item.model.sequences.map((s) => s.name),
    // What the renderer holds.
    frame: item.instance.frame,
    rate: item.instance.timeScale,
    highlight: item.instance.highlight,
    // The animation from the menu while it plays once, by name; else null.
    oneShot: item.oneShot !== null ? sequenceName(item, item.oneShot) : null,
    // The playing sequence's length in ms.
    sequenceLength: playing ? (playing.interval[1] ?? 0) - (playing.interval[0] ?? 0) : 0,
    location: Array.from(item.instance.localLocation),
    rotation: Array.from(item.instance.localRotation),
    engineScale: Array.from(item.instance.localScale),
    engineTeam: item.instance.teamColor,
    tint: Array.from(item.instance.vertexColor),
    texturesLoaded: texturesLoaded(item.model),
    // HD textures (features/hd): the choice, the layers that have both sets, and
    // the texture overrides the renderer's instance holds.
    hd: item.hd,
    hdLayers: item.hdLayers,
    hdApplied: item.instance.textureOverrides.size,
    // The longest side of any texture the model has, and whether that makes its grid glow blue.
    largestTexture: item.largestTexture,
    blueGlow: app().isHd(item),
    // Geometry layout as the renderer reads it.
    vertexStride: item.model.vertexSize,
    vertexCount: item.model.vertexCount,
    vertexBytes: item.model.vertexBytes,
    // Element indices: bytes each, and the largest stored (vertexCount - 1 unless they wrapped).
    elementBytes: item.model.elementBytes,
    elementMax: item.model.elementMax,
    // Culling: the model's bounding sphere radius, and whether the last
    // frame drew the instance (false when it was culled).
    boundsRadius: item.model.bounds.r,
    // The rest-pose vertex box (model space, before the data and instance scale).
    vertexBox: [[...item.model.vertexMin], [...item.model.vertexMax]],
    undrawn: [...item.model.undrawnBatches],
    displacementBatches: item.model.displacementBatches.length,
    // Per region: the UV transform the renderer applies (scale, offset),
    // the stored range of the first UV set, and that range decoded.
    regionUv: item.model.regions.map((r) => ({
      scale: r.uvScale,
      offset: r.uvOffset,
      raw: [...r.rawUvRange],
      range: r.rawUvRange.map((c) => c * r.uvScale + r.uvOffset),
    })),
    uvLayers: uvLayers(item.model),
    constantLayers: constantLayers(item.model),
    drawOrder: drawOrder(item),
    drawn: app().scene.instances.includes(item.instance),
  };
}

export function state(): Record<string, unknown> {
  const a = app();
  const sky = a.sky;
  const skyModel = sky ? sky.model : null;
  const camera = a.camera;
  return {
    items: a.items.map(itemState),
    sceneInstances: a.scene.grid.cells.reduce((n, cell) => n + cell.instances.length, 0),
    grid: a.ground.enabled,
    pointer: a.pointer ? [...a.pointer] : null,
    ghost: a.ghostState(),
    pick: a.pickState(),
    // Displacement batches the last frame drew (sky and units).
    displacedBatches: a.displacedBatches,
    rings: a.ground.rings.map((r) => (r ? { x: r.x, y: r.y, radius: r.radius, width: r.width } : null)),
    sky: sky ? { id: sky.id, name: sky.name, file: sky.file } : null,
    // Loaded: the sky model has geometry to draw.
    skyLoaded: Boolean(skyModel && skyModel.batches.length > 0),
    skyTextures: skyModel ? texturesLoaded(skyModel) : 0,
    skyTexturesWanted: skyModel ? texturesWanted(skyModel) : 0,
    // What the sky file holds: vertices, batches drawn, batches not drawn.
    skyVertices: skyModel ? skyModel.vertexCount : 0,
    skyBatches: skyModel ? skyModel.batches.length : 0,
    skyUndrawn: skyModel ? [...skyModel.undrawnBatches] : [],
    skyBoundsRadius: skyModel ? skyModel.bounds.r : 0,
    // Whether the last frame drew the sky instance (false when culled).
    skyDrawn: Boolean(sky && sky.instance && a.skyScene.instances.includes(sky.instance)),
    skySequence: sky && sky.instance && skyModel && sky.instance.sequence >= 0 ? (skyModel.sequences[sky.instance.sequence]?.name ?? null) : null,
    camera: {
      yaw: camera.yaw,
      pitch: camera.pitch,
      distance: camera.distance,
      target: [...camera.target],
      aspect: a.scene.camera.aspect,
      zoomGoal: a.zoomGoal(),
    },
  };
}
