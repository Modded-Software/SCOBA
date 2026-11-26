// The scene state the tests read: scobaeditor.state(). What only a format
// knows of an instance comes from that format (FormatModule.inspect).

import type { FeatureContext } from '../../core/context';
import type { Item } from '../../core/types';
import type { ViewerInstance } from '../../core/plugin';

export function createState({ render, scene, camera: view, games, testApi }: Pick<FeatureContext, 'render' | 'scene' | 'camera' | 'games' | 'testApi'>): () => Record<string, unknown> {
  const sequenceName = (item: Item, index: number): string | null => (index >= 0 ? (item.instance.sequences[index]?.name ?? null) : null);

  /** The format's own facts of an instance; none when the format tells nothing. */
  function formatFacts(instance: ViewerInstance): Record<string, unknown> {
    const format = render.formatOf(instance.model);
    return format.inspect ? format.inspect(instance) : {};
  }

  /** One key per category noun of the game: the item's record id under its own noun, null under the others. */
  function recordKeys(item: Item): Record<string, string | null> {
    const noun = games.nounOf(item);
    const out: Record<string, string | null> = {};
    for (const category of games.pluginOf(item.game).categories) out[category.noun] = item.source && category.noun === noun ? item.source.record.id : null;
    return out;
  }

  /** The asset of each texture slot of the item, as the game names it for the texture service; one asset may fill several slots. Empty without slots. */
  function textureSlots(item: Item): string[] {
    const override = item.capabilities.textureOverride;
    const assetOf = games.partsOf(item.game).textureAsset;
    if (!override || !assetOf) return [];
    return override.slots().map((slot) => assetOf(slot.source)).sort();
  }

  function itemState(item: Item): Record<string, unknown> {
    const record = item.source ? item.source.record : null;
    const playing = item.instance.sequence >= 0 ? item.instance.sequences[item.instance.sequence] : undefined;
    const facts = formatFacts(item.instance);
    return {
      id: item.id,
      path: item.path,
      game: item.game,
      // Where its data and textures come from.
      dataset: item.dataset,
      // Its record under its category's noun (SC2: unit, doodad); a bare model file has none.
      ...recordKeys(item),
      // Which of the record's model files (an SC2 doodad's variation); null when it has one.
      variation: item.placement.variant,
      name: record ? record.name : null,
      // Loaded means the model has geometry to draw.
      loaded: item.model.loaded,
      x: item.x,
      y: item.y,
      rot: item.rot,
      scale: item.scale,
      team: item.team,
      dataScale: [...item.placement.scale],
      sequence: item.instance.sequence,
      sequenceName: sequenceName(item, item.instance.sequence),
      sequences: item.instance.sequences.map((s) => s.name),
      // What the renderer holds.
      frame: item.instance.frame,
      rate: item.instance.timeScale,
      highlight: item.instance.highlight,
      // The animation from the menu while it plays once, by name; else null.
      oneShot: item.oneShot !== null ? sequenceName(item, item.oneShot) : null,
      // The playing sequence's length in ms.
      sequenceLength: playing ? playing.length : 0,
      location: Array.from(item.instance.location),
      rotation: Array.from(item.instance.rotation),
      engineScale: Array.from(item.instance.scaling),
      engineTeam: facts['engineTeam'],
      tint: facts['tint'],
      texturesLoaded: facts['texturesLoaded'],
      // Its skin (SPEC-VIEWER 17.4), the textures the renderer's instance holds in place of its own, and the largest side it shows.
      skin: item.skin,
      overrides: item.capabilities.textureOverride ? item.capabilities.textureOverride.applied() : 0,
      // The textures a skin can replace: the asset of each override slot (`overrides` counts slots).
      textureSlots: textureSlots(item),
      largestTexture: item.largestTexture,
      unshown: [...item.unshown],
      missingSkin: item.missingSkin,
      // The game's facts (SC2: blueGlow).
      ...games.partsOf(item.game).itemFacts(item),
      // Geometry layout as the renderer reads it (the format's facts).
      vertexStride: facts['vertexStride'],
      vertexCount: facts['vertexCount'],
      vertexBytes: facts['vertexBytes'],
      elementBytes: facts['elementBytes'],
      elementMax: facts['elementMax'],
      // Edges the format's edge buffer holds (0 before the first edge draw).
      edgeCount: facts['edgeCount'],
      // Culling: the model's bounding sphere radius, and whether the last
      // frame drew the instance (false when it was culled).
      boundsRadius: item.model.bounds.r,
      // The rest-pose vertex box (model space, before the data and instance scale).
      vertexBox: [Array.from(item.model.vertexMin), Array.from(item.model.vertexMax)],
      undrawn: [...item.model.undrawn],
      displacementBatches: facts['displacementBatches'],
      regionUv: facts['regionUv'],
      uvLayers: facts['uvLayers'],
      constantLayers: facts['constantLayers'],
      drawOrder: facts['drawOrder'],
      drawn: item.instance.drawn,
    };
  }

  function state(): Record<string, unknown> {
    const sky = scene.sky();
    const skyModel = sky ? sky.model : null;
    const skyInstance = sky ? sky.instance : null;
    const skyFacts = skyInstance ? formatFacts(skyInstance) : {};
    const camera = view.camera;
    return {
      items: scene.items.map(itemState),
      sceneInstances: render.scene.grid.cells.reduce((n, cell) => n + cell.instances.length, 0),
      grid: render.ground.enabled,
      // The ground texture's record, and the texture the ground draws: its size, null while none (SPEC-VIEWER 17.5).
      ground: scene.ground(),
      groundTexture: render.ground.texture ? [render.ground.texture.width, render.ground.texture.height] : null,
      pointer: view.pointer()?.slice() ?? null,
      // What the features add (pick, dragPreview).
      ...testApi.stateParts(),
      // Displacement batches the last frame drew (sky and units).
      displacedBatches: render.displacedBatches(),
      rings: render.ground.rings.map((r) => (r ? { x: r.x, y: r.y, radius: r.radius, width: r.width } : null)),
      sky: sky ? { id: sky.id, name: sky.name, file: sky.file } : null,
      // Loaded: the sky model has geometry to draw.
      skyLoaded: Boolean(skyModel && skyModel.loaded),
      skyTextures: skyFacts['texturesLoaded'] ?? 0,
      skyTexturesWanted: skyFacts['texturesWanted'] ?? 0,
      // What the sky file holds: vertices, batches drawn, batches not drawn.
      skyVertices: skyFacts['vertexCount'] ?? 0,
      skyBatches: skyFacts['batches'] ?? 0,
      skyUndrawn: skyModel ? [...skyModel.undrawn] : [],
      skyBoundsRadius: skyModel ? skyModel.bounds.r : 0,
      // Whether the last frame drew the sky instance (false when culled).
      skyDrawn: Boolean(skyInstance && skyInstance.drawn),
      skySequence: skyInstance && skyInstance.sequence >= 0 ? (skyInstance.sequences[skyInstance.sequence]?.name ?? null) : null,
      camera: {
        yaw: camera.yaw,
        pitch: camera.pitch,
        distance: camera.distance,
        target: [...camera.target],
        aspect: render.scene.camera.aspect,
        zoomGoal: view.zoomGoal(),
      },
    };
  }

  return state;
}
