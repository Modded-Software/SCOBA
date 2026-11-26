// Scene items (records of the game's categories, bare model files): add,
// remove, clear, swap. An item's `source` is its record and category, or
// null for a bare model file. Core applies the game's placement (SPEC-VIEWER
// 6.4); it does not read the record's data. An item's `dataset` is where
// that record and the model's textures come from (core/datasets.ts).
// The scene list is page/ui/instances.ts; it follows the scene's events.

import type { AddOptions, Item, ItemSource } from './types';
import type { ApiClient, GameRegistry, SceneService, StatusService } from './context';
import type { EventBus, ViewerEvents } from './bus';
import type { Host } from './host';
import type { SkyPart } from './sky';
import type { Placement, PlacementWish, ViewerModel } from './plugin';
import { ORIGINAL_SKIN } from '../../shared/textures';
import type { Skins } from './skins';

const REACH = 1.25; // half the room a model with no footprint takes in a row

/** What swapModel may change. */
interface Swap {
  source?: ItemSource | null;
  dataset?: string;
  placement?: Placement;
}

export interface SceneDeps {
  readonly host: Host;
  readonly games: GameRegistry;
  readonly api: ApiClient;
  readonly status: StatusService;
  readonly events: EventBus<ViewerEvents>;
  readonly sky: SkyPart;
  readonly skins: Pick<Skins, 'apply'>;
}

export function createScene({ host, games, api, status, events, sky, skins }: SceneDeps): SceneService {
  const { scene } = host;
  const { pluginOf, partsOf } = games;
  const items: Item[] = [];
  let nextId = 1;

  function applyTransform(item: Item): void {
    const half = (item.rot * Math.PI) / 360;
    item.instance.setLocation([item.x, item.y, item.placement.height]);
    item.instance.setRotation([0, 0, Math.sin(half), Math.cos(half)]);
    const [sx, sy, sz] = item.placement.scale;
    item.instance.setScale([sx * item.scale, sy * item.scale, sz * item.scale]);
  }

  /** The speed of one animation of an item, as its game says. */
  const rateOf = (item: Item, sequence: number): number => pluginOf(item.game).playRate(item.source ? item.source.record : null, item.instance.sequences[sequence]);

  /** Play the item's own (idle) animation, looping. Ends a one-shot. */
  function applySequence(item: Item): void {
    item.oneShot = null;
    item.instance.setSequence(item.sequence);
    item.instance.setLoop(true);
    item.instance.timeScale = rateOf(item, item.sequence);
  }

  /** Play one animation once; then the item goes back to its own (see endOneShots). */
  function playOnce(item: Item, sequence: number): void {
    item.oneShot = sequence;
    item.instance.setSequence(sequence);
    item.instance.setLoop(false);
    item.instance.timeScale = rateOf(item, sequence);
  }

  /** Make an animation the item's own: it loops; the list row and the scene show it. */
  function loopSequence(item: Item, sequence: number): void {
    item.sequence = sequence;
    applySequence(item);
    events.emit('item-changed', { item, field: 'sequence' });
    events.emit('scene-edited', { what: 'sequence' });
  }

  /** After each update: items whose one-shot has ended go back to their own animation. */
  function endOneShots(): void {
    for (const item of items) if (item.oneShot !== null && item.instance.sequenceEnded) applySequence(item);
  }

  function applyLook(item: Item): void {
    const { teamColor, tint } = item.capabilities;
    if (teamColor) teamColor.set(item.team);
    if (tint) tint.set(item.placement.tint);
  }

  const reach = (placement: Placement): number => (placement.radius === null ? REACH : Math.max(REACH, placement.radius + 0.5));

  /** Where the next one goes: in a row, clear of the rightmost one. */
  function nextX(placement: Placement): number {
    return items.length ? Math.max(...items.map((item) => item.x + reach(item.placement))) + reach(placement) : 0;
  }

  /** The model of a file in a dataset of a game; an error when it does not load. */
  async function loadModel(path: string, dataset: string, game: string): Promise<ViewerModel> {
    const model = await host.loadModel(api.modelUrl(path, dataset, game), api.pathSolver(dataset, game));
    if (!model) throw new Error('cannot load ' + path);
    return model;
  }

  /**
   * A new instance of a model, with what its format lets it do, and the
   * placement's clips handed to the format (SPEC-VIEWER 6.4): before the
   * game picks the rest animation out of the instance's sequences.
   */
  async function instanceOf(model: ViewerModel, placement: Placement, from: { game: string; dataset: string }): Promise<Pick<Item, 'model' | 'instance' | 'capabilities'>> {
    const format = host.formatOf(model);
    const instance = model.addInstance();
    if (placement.clips.length) {
      if (!format.attachClips) throw new Error(`${placement.file}: format ${format.id} cannot take ${placement.clips.length} clip(s)`);
      const refused = await format.attachClips(instance, placement.clips, (reference) => api.assetUrl('animation', reference, from.dataset, from.game));
      if (refused.length) {
        console.warn(`scobaeditor: ${placement.file}: clips left out: ${refused.join('; ')}`);
        status.setStatus(`${placement.file}: ${refused.length} clip(s) left out (${refused[0] ?? ''})`, { failure: true });
      }
    }
    return { model, instance, capabilities: format.capabilities(instance) };
  }

  /** The wish of add options: the scale pick (random when not given), the angle, the variant. */
  function wishOf(options: AddOptions): PlacementWish {
    const wish: PlacementWish = { pick: options.pick ?? Math.random() };
    if (options.rot !== undefined) wish.rot = options.rot;
    if (options.variant !== undefined) wish.variant = options.variant;
    return wish;
  }

  /** Place one item: load its model, apply the placement, add it to the scene and the list. */
  function place(source: ItemSource | null, placement: Placement, from: { game: string; dataset: string }, options: AddOptions): Promise<number> {
    const { game, dataset } = from;
    const name = source ? source.record.name : placement.file;
    status.setStatus('loading ' + name);
    return status.busy(async () => {
      const model = await loadModel(placement.file, dataset, game);
      const made = await instanceOf(model, placement, from);
      const item: Item = {
        id: nextId++,
        game,
        path: placement.file,
        dataset,
        source,
        placement,
        ...made,
        x: options.x ?? nextX(placement),
        y: options.y ?? 0,
        rot: placement.rot,
        scale: options.scale ?? 1,
        sequence: options.sequence ?? pluginOf(game).restSequence(made.instance.sequences),
        team: options.team ?? 0,
        skin: options.skin ?? ORIGINAL_SKIN,
        largestTexture: 0,
        unshown: [],
        missingSkin: false,
        oneShot: null,
        options: partsOf(game).itemOptions(options.options ?? {}),
      };
      // An animation or a team the model does not have is refused, not replaced.
      if (!Number.isInteger(item.sequence) || item.sequence < -1 || item.sequence >= item.instance.sequences.length) throw new Error(`${name}: no animation ${item.sequence}; it has ${item.instance.sequences.length}`);
      const teams = item.capabilities.teamColor ? item.capabilities.teamColor.colors.length : 1;
      if (!(Number.isInteger(item.team) && item.team >= 0 && item.team < teams)) throw new Error(`${name}: no team ${item.team}; it has ${teams}`);
      applyTransform(item);
      applySequence(item);
      applyLook(item);
      item.instance.attach(scene);
      items.push(item);
      events.emit('item-added', { item });
      events.emit('scene-edited', { what: 'add' });
      status.setStatus('');
      host.reportUndrawn(name, model);
      // Its skin after it shows, and not waited for: the add does not depend on the texture service (R-VIEW-110); idle() waits for it.
      skins.apply(item).catch(status.reportFailure);
      return item.id;
    });
  }

  /** Run a load with the pending count up and its failure on the status line. */
  const loading = <T>(work: () => Promise<T>): Promise<T> => status.busy(work);

  /** The game and dataset an add names: the gallery's game and that game's current dataset when not given. */
  async function fromOf(options: AddOptions): Promise<{ game: string; dataset: string }> {
    const game = options.game ?? games.game();
    pluginOf(game);
    await games.loadGame(game);
    return { game, dataset: api.requireDataset(options.dataset ?? api.currentDataset(game), game) };
  }

  /**
   * Add a model file. `options.game` and `options.dataset`: where its
   * textures come from; the gallery's game and its current dataset when not given.
   */
  function add(path: string, options: AddOptions = {}): Promise<number> {
    return loading(async () => {
      const from = await fromOf(options);
      return await place(null, pluginOf(from.game).placeFile(path, wishOf(options)), from, options);
    });
  }

  /**
   * Add a record by category and id, placed as its game says. A record the
   * game makes a backdrop (an SC2 skybox unit) becomes the sky instead, and
   * a record of a ground category becomes the ground; neither is placed,
   * and the result is null.
   */
  function addRecord(category: string, id: string, options: AddOptions = {}): Promise<number | null> {
    return loading(async () => {
      const from = await fromOf(options);
      const game = pluginOf(from.game);
      const record = await api.record(category, id, from.dataset, from.game);
      if (game.categories.some((one) => one.id === category && one.ground)) {
        await sky.setGround({ ...from, category, id: record.id, name: record.name, texture: record.file });
        status.setStatus(`${record.name} is a ground texture: set as the ground`);
        return null;
      }
      const placement = game.place(category, record, wishOf(options));
      if (placement.asBackdrop) {
        await sky.setSky({ id: record.id, name: record.name, file: placement.file, ...from });
        status.setStatus(`${record.name} is a ${game.backdrop}: set as the sky`);
        return null;
      }
      return await place({ category, record }, placement, from, options);
    });
  }

  /**
   * Give a placed item another source, dataset or placement. Its id, place,
   * angle, own scale, team and game options stay; the placement follows the record. It
   * keeps playing its animation when the new model has one of that name.
   */
  function swapModel(item: Item, next: Swap): Promise<void> {
    return loading(async () => {
      const { source = item.source, dataset = item.dataset, placement = item.placement } = next;
      const model = await loadModel(placement.file, dataset, item.game);
      const made = await instanceOf(model, placement, { game: item.game, dataset });
      // Removed while the model loaded: nothing to swap.
      if (!items.includes(item)) return;
      const playing = item.sequence >= 0 ? (item.instance.sequences[item.sequence]?.name ?? null) : null;
      const same = playing === null ? -1 : made.instance.sequences.findIndex((s) => s.name === playing);
      item.instance.detach();
      Object.assign(item, { path: placement.file, source, dataset, placement, ...made, largestTexture: 0, unshown: [], missingSkin: false, sequence: same >= 0 ? same : pluginOf(item.game).restSequence(made.instance.sequences) });
      applyTransform(item);
      applySequence(item);
      applyLook(item);
      item.instance.attach(scene);
      events.emit('item-swapped', { item });
      events.emit('scene-edited', { what: 'swap' });
      host.reportUndrawn(source ? source.record.name : placement.file, model);
      skins.apply(item).catch(status.reportFailure);
    });
  }

  /** The wish that keeps an item as it is: its scale pick and angle. */
  const keep = (item: Item, variant: number | null): PlacementWish => ({ pick: item.placement.pick, rot: item.rot, variant });

  /** Swap a placed item to another of its record's variants; place, angle and scale stay. */
  async function setVariation(item: Item, variant: number): Promise<void> {
    const source = item.source;
    if (!source || item.placement.variants < 1) throw new Error(`item ${item.id} has no variants`);
    const placement = pluginOf(item.game).place(source.category, source.record, keep(item, variant));
    return swapModel(item, { placement });
  }

  /**
   * Take a placed item's record, model and textures from another dataset.
   * It keeps its variant; a record there without that variant is refused,
   * and so is a record the other dataset does not have. The item stays as it is.
   */
  function setItemDataset(item: Item, dataset: string): Promise<void> {
    return loading(async () => {
      api.requireDataset(dataset, item.game);
      // A bare model file: the same file, its textures from the other dataset.
      const own = item.source;
      if (!own) return await swapModel(item, { dataset });
      const record = await api.record(own.category, own.record.id, dataset, item.game);
      const placement = pluginOf(item.game).place(own.category, record, keep(item, item.placement.variant));
      return await swapModel(item, { source: { category: own.category, record }, dataset, placement });
    });
  }

  function remove(id: number): void {
    const at = items.findIndex((item) => item.id === id);
    const item = items[at];
    if (!item) return;
    item.instance.detach();
    items.splice(at, 1);
    events.emit('items-removed', { ids: [id], all: false });
    events.emit('scene-edited', { what: 'remove' });
  }

  /** Remove the items `ids` in one go: one list rebuild, one scene write. */
  function removeMany(ids: readonly number[]): number {
    const gone = items.filter((item) => ids.includes(item.id));
    if (!gone.length) return 0;
    for (const item of gone) {
      item.instance.detach();
      items.splice(items.indexOf(item), 1);
    }
    events.emit('items-removed', { ids: gone.map((item) => item.id), all: false });
    events.emit('scene-edited', { what: 'remove' });
    return gone.length;
  }

  function clear(): void {
    for (const item of items) item.instance.detach();
    items.length = 0;
    events.emit('items-removed', { ids: [], all: true });
    events.emit('scene-edited', { what: 'clear' });
  }

  /** Start every animation again from its first frame. */
  function restart(): void {
    for (const item of items) applySequence(item);
  }

  /** Turn an item to `rot` degrees and show it in its list row. */
  function setRotation(item: Item, rot: number): void {
    item.rot = rot;
    applyTransform(item);
    events.emit('item-changed', { item, field: 'rot' });
  }

  /** Move an item to ground point (x, y) and show it in its list row. */
  function setPosition(item: Item, x: number, y: number): void {
    item.x = x;
    item.y = y;
    applyTransform(item);
    events.emit('item-changed', { item, field: 'x' });
    events.emit('item-changed', { item, field: 'y' });
  }

  return {
    items,
    ...sky,
    add,
    addRecord,
    setVariation,
    setItemDataset,
    remove,
    removeMany,
    clear,
    restart,
    playOnce,
    loopSequence,
    endOneShots,
    setRotation,
    setPosition,
    applyTransform,
    applySequence,
    applyLook,
  };
}
