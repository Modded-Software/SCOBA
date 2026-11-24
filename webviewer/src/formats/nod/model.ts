// A Ghost model on the renderer library's model base class
// (SPEC-VIEWER-GHOST 7, scope G1). The bytes are the container the server
// exports (container.ts); nothing here reads a NOD file. The vertex data
// stays in the file's axes; the instance mirrors Y, so the triangles are
// turned round here (4.8).

import Model from '@renderer/viewer/model';
import type { HandlerResourceData } from '@renderer/viewer/handlerresource';
import Texture from '@renderer/viewer/texture';
import { edgePairs } from '@renderer/viewer/edges';
import { readContainer, STRIDE, type NodBone, type NodData } from './container';
import { lookOf, type DrawKind, type GroupLook } from './materials';
// The instance class is made here (addInstance); instance.ts names this class as a type only.
import NodInstance, { SHADER_LOADING } from './instance';

/** One mesh group as it is drawn. */
export interface DrawGroup {
  index: number;
  material: string;
  look: GroupLook;
  /** Into the element buffer, in indices. */
  firstIndex: number;
  indexCount: number;
  texture: Texture | null;
}

/** A group's edges in the model's edge buffer: the first edge and how many. */
export interface EdgeRange {
  first: number;
  count: number;
}

export default class NodModel extends Model {
  readonly data: NodData;
  readonly groups: DrawGroup[];
  readonly bones: readonly NodBone[];
  readonly vertexBuffer: WebGLBuffer;
  readonly elementBuffer: WebGLBuffer;
  /** Rest box, in the viewer's axes (Y mirrored). */
  readonly vertexMin: Float32Array;
  readonly vertexMax: Float32Array;
  /** The vertices with any bone weight on a skinned vertex set. */
  readonly skinned: boolean;
  readonly undrawn: string[];
  readonly textureFiles: string[];
  /** The element indices as drawn, kept to make the edge buffer from (edges()). */
  private readonly indices: Uint32Array;
  /** Every group's edges, each once, made on the first edges() call; null before. */
  private edgeBuffer: WebGLBuffer | null = null;
  /** Each group's place in the edge buffer, in edges, by group index. */
  private readonly edgeRanges = new Map<number, EdgeRange>();

  constructor(bytes: Uint8Array, resourceData: HandlerResourceData) {
    super(resourceData);
    const name = String(resourceData.fetchUrl ?? 'nod model');
    // The library waits for the blockers before it hands the model out: the shader files first.
    const loading: unknown = this.viewer.sharedCache.get(SHADER_LOADING);
    if (!(loading instanceof Promise)) throw new Error(`${name}: the nod handler is not loaded`);
    this.blockers.push(loading);
    this.data = readContainer(bytes, name);
    const { data } = this;
    const gl = this.viewer.gl;
    this.bones = data.bones;
    this.skinned = data.bones.length > 0 && data.groups.some((g) => g.vertexType % 3 !== 0);

    const vertexBuffer = gl.createBuffer();
    const elementBuffer = gl.createBuffer();
    if (!vertexBuffer || !elementBuffer) throw new Error(`${name}: no WebGL buffer`);
    this.vertexBuffer = vertexBuffer;
    this.elementBuffer = elementBuffer;
    gl.bindBuffer(gl.ARRAY_BUFFER, vertexBuffer);
    gl.bufferData(gl.ARRAY_BUFFER, data.vertices, gl.STATIC_DRAW);
    // The Y mirror turns the winding: a, b, c becomes a, c, b.
    const turned = new Uint32Array(data.indices.length);
    for (let i = 0; i + 2 < data.indices.length; i += 3) {
      turned[i] = data.indices[i] ?? 0;
      turned[i + 1] = data.indices[i + 2] ?? 0;
      turned[i + 2] = data.indices[i + 1] ?? 0;
    }
    if (!this.viewer.webgl.ensureExtension('OES_element_index_uint')) throw new Error(`${name}: no 32-bit index support`);
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, elementBuffer);
    gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, turned, gl.STATIC_DRAW);
    this.indices = turned;

    const byName = new Map(data.materials.map((m) => [m.name, m]));
    this.undrawn = [];
    this.textureFiles = [];
    this.groups = data.groups.map((group, index) => {
      const material = data.materialNames[group.material] ?? '';
      const look = lookOf(material, byName.get(material));
      if (look.undrawn) this.undrawn.push(`group ${index} ${look.undrawn}`);
      const drawn: DrawGroup = { index, material, look, firstIndex: group.firstIndex, indexCount: group.indexCount, texture: null };
      if (look.kind && look.texture && group.indexCount) {
        if (!this.textureFiles.includes(look.texture)) this.textureFiles.push(look.texture);
        const loading = this.viewer.load(look.texture, this.pathSolver).then((texture) => {
          // The library reports a texture that fails as an error event; the group then draws nothing.
          if (texture instanceof Texture) drawn.texture = texture;
          return texture;
        });
        this.blockers.push(loading);
      }
      return drawn;
    });

    // The rest box of the vertices, Y mirrored; the culling sphere around it.
    const min = [Infinity, Infinity, Infinity];
    const max = [-Infinity, -Infinity, -Infinity];
    const view = new DataView(data.vertices);
    for (let v = 0; v < data.vertexCount; v++) {
      for (let a = 0; a < 3; a++) {
        const value = view.getFloat32(v * STRIDE + a * 4, true) * (a === 1 ? -1 : 1);
        min[a] = Math.min(min[a] ?? 0, value);
        max[a] = Math.max(max[a] ?? 0, value);
      }
    }
    if (!data.vertexCount) {
      min.fill(0);
      max.fill(0);
    }
    this.vertexMin = Float32Array.from(min);
    this.vertexMax = Float32Array.from(max);
    const [x0, y0, z0] = this.vertexMin;
    const [x1, y1, z1] = this.vertexMax;
    const cx = ((x0 ?? 0) + (x1 ?? 0)) / 2;
    const cy = ((y0 ?? 0) + (y1 ?? 0)) / 2;
    const cz = ((z0 ?? 0) + (z1 ?? 0)) / 2;
    // A skinned model moves past its rest box: twice its radius covers a pose.
    const r = Math.hypot((x1 ?? 0) - cx, (y1 ?? 0) - cy, (z1 ?? 0) - cz) * (this.skinned ? 2 : 1);
    this.bounds.x = cx;
    this.bounds.y = cy;
    this.bounds.z = cz;
    this.bounds.r = r;
  }

  /** The groups drawn as one of `kinds`, with geometry. */
  drawn(kinds: readonly DrawKind[]): DrawGroup[] {
    return this.groups.filter((g) => g.look.kind !== null && kinds.includes(g.look.kind) && g.indexCount > 0);
  }

  /**
   * The edge buffer: every group's triangle edges, each once, as line
   * element pairs, and each group's range in it. Made on the first call,
   * so a model never drawn with edges never pays for them.
   */
  edges(): { buffer: WebGLBuffer; ranges: ReadonlyMap<number, EdgeRange> } | null {
    if (!this.edgeBuffer) {
      const lists = this.groups.map((g) => edgePairs(this.indices, g.firstIndex, g.indexCount));
      const array = new Uint32Array(lists.reduce((n, list) => n + list.length, 0));
      let at = 0;
      lists.forEach((list, index) => {
        this.edgeRanges.set(index, { first: at / 2, count: list.length / 2 });
        array.set(list, at);
        at += list.length;
      });
      if (!array.length) return null;
      const gl = this.viewer.gl;
      const buffer = gl.createBuffer();
      if (!buffer) throw new Error('nod: no WebGL buffer for the edges');
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, buffer);
      gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, array, gl.STATIC_DRAW);
      this.edgeBuffer = buffer;
    }
    return { buffer: this.edgeBuffer, ranges: this.edgeRanges };
  }

  addInstance(): NodInstance {
    return new NodInstance(this);
  }
}
