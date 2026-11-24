// A Ghost model instance on the renderer library's instance base class
// (SPEC-VIEWER-GHOST 7, scopes G1 and G2): its clips, one at a time; the
// bone matrices of the pose now; and the draws. Clips belong to the
// instance, not the model: two actors may share a model file.

import { mat4 } from 'gl-matrix';
import ModelInstance from '@renderer/viewer/modelinstance';
import DataTexture from '@renderer/viewer/gl/datatexture';
import Shader from '@renderer/viewer/gl/shader';
import { pose, type NodClip } from './clips';
import { STRIDE } from './container';
import { KIND_CODE, type DrawKind } from './materials';
import type NodModel from './model';
import type { DrawGroup } from './model';

/** The viewer's axes from the file's: Y mirrored (SPEC-VIEWER-GHOST 4.8). */
export const MIRROR = mat4.fromScaling(mat4.create(), [1, -1, 1]);

const world = mat4.create();
const OPAQUE: readonly DrawKind[] = ['solid', 'cutout'];
const TRANSLUCENT: readonly DrawKind[] = ['add', 'blend'];

/** The key of the handler's shader load in the viewer's shared cache: a Promise<void>. */
export const SHADER_LOADING = 'nod-loading';

/** The shader of the nod format, made by its handler (format.ts). */
export function nodShader(instance: NodInstance): Shader {
  const shader = instance.model.viewer.sharedCache.get('nod');
  if (!(shader instanceof Shader)) throw new Error('the nod handler is not loaded');
  return shader;
}

/** A uniform's place; null for one the compiler removed (WebGL takes null and sets nothing). */
const at = (shader: Shader, name: string): WebGLUniformLocation | null => shader.uniforms[name] ?? null;

export default class NodInstance extends ModelInstance {
  declare model: NodModel;
  clips: NodClip[] = [];
  sequence = -1;
  /** Playhead in ms. */
  frame = 0;
  loop = true;
  sequenceEnded = false;
  highlight = 0;
  solidOnly = false;
  /** 16 numbers a bone: global x move(offset), the pose now. */
  readonly matrices: Float32Array;
  readonly globals: Float32Array;
  private readonly boneTexture: DataTexture;
  private dirty = true;
  /** The groups the last draws drew, for the probes. */
  lastDrawn: number[] = [];

  constructor(model: NodModel) {
    super(model);
    const count = Math.max(model.bones.length, 1);
    this.matrices = new Float32Array(count * 16);
    this.globals = new Float32Array(count * 16);
    for (let b = 0; b < count; b++) mat4.identity(this.matrices.subarray(b * 16, b * 16 + 16));
    this.boneTexture = new DataTexture(model.viewer.gl, 4, count * 4, 1);
  }

  /** The clip playing; null for none. */
  get clip(): NodClip | null {
    return this.sequence >= 0 ? (this.clips[this.sequence] ?? null) : null;
  }

  /** Length of a clip in ms. */
  static lengthMs(clip: NodClip): number {
    return (clip.length / clip.framesPerSecond) * 1000;
  }

  setSequence(index: number): void {
    this.sequence = index >= 0 && index < this.clips.length ? index : -1;
    this.frame = 0;
    this.sequenceEnded = false;
    this.dirty = true;
  }

  /** The pose at the playhead, into the matrices and the bone texture. */
  updatePose(): void {
    const clip = this.clip;
    pose(this.model.bones, clip, clip ? (this.frame / 1000) * clip.framesPerSecond : 0, this.matrices, this.globals);
    this.boneTexture.bindAndUpdate(this.matrices, this.matrices.length / 4, 1);
    this.dirty = false;
  }

  override updateAnimations(dt: number): void {
    const clip = this.clip;
    if (clip) {
      const end = NodInstance.lengthMs(clip);
      this.frame += dt * 1000;
      if (this.frame > end) {
        this.frame = this.loop && end > 0 ? this.frame % end : end;
        this.sequenceEnded = true;
      } else {
        this.sequenceEnded = false;
      }
      this.dirty = true;
    }
    if (this.dirty) this.updatePose();
  }

  /** Set the camera, the matrices and the vertex layout for a draw. Only an instance in a scene is drawn. */
  private use(shader: Shader): void {
    const model = this.model;
    const gl = model.viewer.gl;
    const scene = this.scene;
    if (!scene) throw new Error('a nod instance is drawn outside a scene');
    const { attribs } = shader;
    if (this.dirty) this.updatePose();
    shader.use();
    gl.uniformMatrix4fv(at(shader, 'u_VP'), false, scene.camera.viewProjectionMatrix);
    gl.uniformMatrix4fv(at(shader, 'u_world'), false, mat4.mul(world, this.worldMatrix, MIRROR));
    gl.uniform3fv(at(shader, 'u_lightPos'), scene.lightPosition);
    gl.uniform1f(at(shader, 'u_highlight'), this.highlight);
    gl.uniform1f(at(shader, 'u_skinned'), model.skinned ? 1 : 0);
    this.boneTexture.bind(15);
    gl.uniform1i(at(shader, 'u_boneMap'), 15);
    gl.uniform1f(at(shader, 'u_texel'), 1 / this.boneTexture.width);
    gl.uniform1i(at(shader, 'u_texture'), 0);
    gl.bindBuffer(gl.ARRAY_BUFFER, model.vertexBuffer);
    gl.vertexAttribPointer(attribs['a_position'] ?? 0, 3, gl.FLOAT, false, STRIDE, 0);
    gl.vertexAttribPointer(attribs['a_normal'] ?? 0, 3, gl.FLOAT, false, STRIDE, 12);
    gl.vertexAttribPointer(attribs['a_uv'] ?? 0, 2, gl.FLOAT, false, STRIDE, 24);
    gl.vertexAttribPointer(attribs['a_bones'] ?? 0, 4, gl.UNSIGNED_BYTE, false, STRIDE, 32);
    gl.vertexAttribPointer(attribs['a_weights'] ?? 0, 4, gl.FLOAT, false, STRIDE, 36);
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, model.elementBuffer);
  }

  private draw(shader: Shader, group: DrawGroup, kind: DrawKind): void {
    const gl = this.model.viewer.gl;
    gl.uniform1f(at(shader, 'u_kind'), KIND_CODE[kind]);
    this.model.viewer.webgl.bindTexture(group.texture, 0);
    if (group.look.twoSided) gl.disable(gl.CULL_FACE);
    else {
      gl.enable(gl.CULL_FACE);
      gl.cullFace(gl.BACK);
      gl.frontFace(gl.CCW);
    }
    gl.drawElements(gl.TRIANGLES, group.indexCount, gl.UNSIGNED_INT, group.firstIndex * 4);
  }

  override renderOpaque(): void {
    const groups = this.model.drawn(OPAQUE);
    this.lastDrawn = groups.map((g) => g.index);
    if (!groups.length) return;
    const gl = this.model.viewer.gl;
    const shader = nodShader(this);
    this.use(shader);
    gl.uniform4f(at(shader, 'u_pick'), 0, 0, 0, 0);
    gl.disable(gl.BLEND);
    gl.depthMask(true);
    for (const group of groups) this.draw(shader, group, group.look.kind ?? 'solid');
  }

  override renderTranslucent(): void {
    if (this.solidOnly) return;
    const groups = this.model.drawn(TRANSLUCENT);
    if (!groups.length) return;
    this.lastDrawn = [...this.lastDrawn, ...groups.map((g) => g.index)];
    const gl = this.model.viewer.gl;
    const shader = nodShader(this);
    this.use(shader);
    gl.uniform4f(at(shader, 'u_pick'), 0, 0, 0, 0);
    gl.enable(gl.BLEND);
    gl.depthMask(false);
    for (const group of groups) {
      if (group.look.kind === 'add') gl.blendFunc(gl.ONE, gl.ONE);
      else gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
      this.draw(shader, group, group.look.kind ?? 'blend');
    }
    gl.depthMask(true);
    gl.disable(gl.BLEND);
  }

  /** One flat colour, for picking by pixel: the solid and cut-out groups; all drawn groups when it has none. */
  renderPick(r: number, g: number, b: number): void {
    const opaque = this.model.drawn(OPAQUE);
    const groups = opaque.length ? opaque : this.model.drawn(TRANSLUCENT);
    if (!groups.length) return;
    const gl = this.model.viewer.gl;
    const shader = nodShader(this);
    this.use(shader);
    gl.uniform4f(at(shader, 'u_pick'), r, g, b, 1);
    gl.disable(gl.BLEND);
    gl.depthMask(true);
    // A cut-out group keeps its cut: only its solid texels are picked.
    for (const group of groups) this.draw(shader, group, group.look.kind === 'cutout' ? 'cutout' : 'solid');
    gl.uniform4f(at(shader, 'u_pick'), 0, 0, 0, 0);
  }
}
