// The library's M3 classes as the page's model and instance (SPEC-VIEWER
// 6.1). The library is not changed for them. `m3` is the library object:
// format code and the tests reach the M3 members through it.

import type ModelViewer from '@renderer/viewer/viewer';
import type { M3HandlerObject } from '@renderer/viewer/handlers/m3/handler';
import M3Model from '@renderer/viewer/handlers/m3/model';
import type M3ModelInstance from '@renderer/viewer/handlers/m3/modelinstance';
import type M3Layer from '@renderer/viewer/handlers/m3/layer';
import type { M3StandardMaterial } from '@renderer/viewer/handlers/m3/standardmaterial';
import type { Vec3 } from '../../shared/records';
import type { Quat, RenderScene, SequenceInfo, ViewerInstance, ViewerModel } from '../../page/core/plugin';

export const M3_FORMAT = 'm3';

/** Every layer of a model's standard materials, with its material. */
export function eachLayer(model: M3Model): { material: M3StandardMaterial; layer: M3Layer }[] {
  return model.materials[1].flatMap((material) => material.layers.map((layer) => ({ material, layer })));
}

export class M3View implements ViewerModel {
  readonly format = M3_FORMAT;
  constructor(readonly m3: M3Model) {}
  get bounds(): { readonly r: number } {
    return this.m3.bounds;
  }
  get vertexMin(): ArrayLike<number> {
    return this.m3.vertexMin;
  }
  get vertexMax(): ArrayLike<number> {
    return this.m3.vertexMax;
  }
  get loaded(): boolean {
    return this.m3.batches.length > 0;
  }
  get undrawn(): readonly string[] {
    return this.m3.undrawnBatches;
  }
  get textures(): readonly string[] {
    return eachLayer(this.m3).flatMap(({ layer }) => (layer.active && !layer.constant && layer.source ? [String(layer.source)] : []));
  }
  addInstance(): M3InstanceView {
    return new M3InstanceView(this, this.m3.addInstance());
  }
}

export class M3InstanceView implements ViewerInstance {
  constructor(
    readonly model: M3View,
    readonly m3: M3ModelInstance,
  ) {}
  get sequences(): readonly SequenceInfo[] {
    return this.model.m3.sequences.map((s) => ({ name: s.name, length: (s.interval[1] ?? 0) - (s.interval[0] ?? 0) }));
  }
  setLocation(at: Vec3): void {
    this.m3.setLocation(at);
  }
  setRotation(turn: Quat): void {
    this.m3.setRotation(turn);
  }
  setScale(by: Vec3): void {
    this.m3.setScale(by);
  }
  setSequence(index: number): void {
    this.m3.setSequence(index);
  }
  /** Loop mode 2 repeats; mode 1 plays once and holds. Mode 0, "as the file says", is not used. */
  setLoop(loop: boolean): void {
    this.m3.setSequenceLoopMode(loop ? 2 : 1);
  }
  get timeScale(): number {
    return this.m3.timeScale;
  }
  set timeScale(value: number) {
    this.m3.timeScale = value;
  }
  get sequenceEnded(): boolean {
    return this.m3.sequenceEnded;
  }
  get sequence(): number {
    return this.m3.sequence;
  }
  get frame(): number {
    return this.m3.frame;
  }
  get location(): ArrayLike<number> {
    return this.m3.localLocation;
  }
  get rotation(): ArrayLike<number> {
    return this.m3.localRotation;
  }
  get scaling(): ArrayLike<number> {
    return this.m3.localScale;
  }
  show(): void {
    this.m3.show();
  }
  hide(): void {
    this.m3.hide();
  }
  get shown(): boolean {
    return this.m3.rendered;
  }
  attach(scene: RenderScene): void {
    scene.addInstance(this.m3);
  }
  detach(): void {
    this.m3.detach();
  }
  get attached(): boolean {
    return Boolean(this.m3.scene);
  }
  get drawn(): boolean {
    const scene = this.m3.scene;
    return Boolean(scene && scene.instances.includes(this.m3));
  }
  get highlight(): number {
    return this.m3.highlight;
  }
  set highlight(value: number) {
    this.m3.highlight = value;
  }
  get solidOnly(): boolean {
    return this.m3.solidOnly;
  }
  set solidOnly(value: boolean) {
    this.m3.solidOnly = value;
  }
  renderOpaque(): void {
    this.m3.renderOpaque();
  }
  renderPick(r: number, g: number, b: number): void {
    this.m3.renderPick(r, g, b);
  }
}

/** An instance's library object; an error when it is not an M3 one. */
export function m3Instance(instance: ViewerInstance): M3ModelInstance {
  if (!(instance instanceof M3InstanceView)) throw new Error(`not an M3 instance: ${instance.model.format}`);
  return instance.m3;
}

/** A model's library object; an error when it is not an M3 one. */
export function m3Model(model: ViewerModel): M3Model {
  if (!(model instanceof M3View)) throw new Error(`not an M3 model: ${model.format}`);
  return model.m3;
}

/** The M3 handler's shared object: its shaders and the switches the tests turn. */
export function m3Shared(viewer: ModelViewer): M3HandlerObject {
  const shared = viewer.sharedCache.get('m3');
  if (!isM3Shared(shared)) throw new Error('the M3 handler is not loaded');
  return shared;
}

function isM3Shared(value: unknown): value is M3HandlerObject {
  return typeof value === 'object' && value !== null && 'particlesEnabled' in value && 'layerOptions' in value;
}

const views = new WeakMap<M3Model, M3View>();

/** The one view of a loaded library resource, or null when it is no M3 model. */
export function adoptM3(resource: unknown): M3View | null {
  if (!(resource instanceof M3Model)) return null;
  const known = views.get(resource);
  if (known) return known;
  const view = new M3View(resource);
  views.set(resource, view);
  return view;
}
