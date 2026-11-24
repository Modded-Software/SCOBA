// The nod model and instance as the page's (SPEC-VIEWER 6.1). `nod` is the
// library object: format code and the probes reach it through this.

import type { Vec3 } from '../../shared/records';
import type { Quat, RenderScene, SequenceInfo, ViewerInstance, ViewerModel } from '../../page/core/plugin';
import NodInstance from './instance';
import NodModel from './model';

export const NOD_FORMAT = 'nod';

export class NodView implements ViewerModel {
  readonly format = NOD_FORMAT;
  constructor(readonly nod: NodModel) {}
  get bounds(): { readonly r: number } {
    return this.nod.bounds;
  }
  get vertexMin(): ArrayLike<number> {
    return this.nod.vertexMin;
  }
  get vertexMax(): ArrayLike<number> {
    return this.nod.vertexMax;
  }
  get loaded(): boolean {
    return this.nod.groups.some((g) => g.look.kind !== null && g.indexCount > 0);
  }
  get undrawn(): readonly string[] {
    return this.nod.undrawn;
  }
  get textures(): readonly string[] {
    return this.nod.textureFiles;
  }
  addInstance(): NodInstanceView {
    return new NodInstanceView(this, this.nod.addInstance());
  }
}

export class NodInstanceView implements ViewerInstance {
  constructor(
    readonly model: NodView,
    readonly nod: NodInstance,
  ) {}
  get sequences(): readonly SequenceInfo[] {
    return this.nod.clips.map((clip) => ({ name: clip.name, length: NodInstance.lengthMs(clip) }));
  }
  setLocation(at: Vec3): void {
    this.nod.setLocation(at);
  }
  setRotation(turn: Quat): void {
    this.nod.setRotation(turn);
  }
  setScale(by: Vec3): void {
    this.nod.setScale(by);
  }
  setSequence(index: number): void {
    this.nod.setSequence(index);
  }
  setLoop(loop: boolean): void {
    this.nod.loop = loop;
  }
  get timeScale(): number {
    return this.nod.timeScale;
  }
  set timeScale(value: number) {
    this.nod.timeScale = value;
  }
  get sequenceEnded(): boolean {
    return this.nod.sequenceEnded;
  }
  get sequence(): number {
    return this.nod.sequence;
  }
  get frame(): number {
    return this.nod.frame;
  }
  get location(): ArrayLike<number> {
    return this.nod.localLocation;
  }
  get rotation(): ArrayLike<number> {
    return this.nod.localRotation;
  }
  get scaling(): ArrayLike<number> {
    return this.nod.localScale;
  }
  show(): void {
    this.nod.show();
  }
  hide(): void {
    this.nod.hide();
  }
  get shown(): boolean {
    return this.nod.rendered;
  }
  attach(scene: RenderScene): void {
    scene.addInstance(this.nod);
  }
  detach(): void {
    this.nod.detach();
  }
  get attached(): boolean {
    return Boolean(this.nod.scene);
  }
  get drawn(): boolean {
    const scene = this.nod.scene;
    return Boolean(scene && scene.instances.includes(this.nod));
  }
  get highlight(): number {
    return this.nod.highlight;
  }
  set highlight(value: number) {
    this.nod.highlight = value;
  }
  get solidOnly(): boolean {
    return this.nod.solidOnly;
  }
  set solidOnly(value: boolean) {
    this.nod.solidOnly = value;
  }
  renderOpaque(): void {
    this.nod.renderOpaque();
  }
  renderPick(r: number, g: number, b: number): void {
    this.nod.renderPick(r, g, b);
  }
}

/** An instance's library object; an error when it is not a nod one. */
export function nodInstance(instance: ViewerInstance): NodInstance {
  if (!(instance instanceof NodInstanceView)) throw new Error(`not a nod instance: ${instance.model.format}`);
  return instance.nod;
}

const views = new WeakMap<NodModel, NodView>();

/** The one view of a loaded library resource, or null when it is no nod model. */
export function adoptNod(resource: unknown): NodView | null {
  if (!(resource instanceof NodModel)) return null;
  const known = views.get(resource);
  if (known) return known;
  const view = new NodView(resource);
  views.set(resource, view);
  return view;
}
