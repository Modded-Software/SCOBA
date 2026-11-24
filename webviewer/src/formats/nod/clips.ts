// NAD clips as `NODExport nad` writes them (SPEC-VIEWER-GHOST 4.2, 7), and
// the bone pose at a frame.
//
// A key is 13 numbers: frame, value (3), b (3), c (3), d (3). Between key k
// and key k+1, at t frames after key k: value + t b + t^2 c + t^3 d, per
// axis. The last key of a track ends the curve: its value holds after it.
// Kind 0 turns the bone by three angles in degrees; kind 1 moves it, added
// to its rest position.
//
// Bone pose, parents first:
//   local  = move(rest place + track move) x turn(angles)
//   global = parent's global x local
//   matrix = global x move(offset)
// `offset` is minus the bone's rest place in model space, the inverse bind
// the vertices are stored against. The rest place of a bone in its parent
// is therefore taken from the offsets: parent's offset minus its own (a
// root: minus its own). It equals the file's `position` in every bone of
// 1383 models; in some bones of the 18 models whose bones have a turned
// `orientation` it does not (O-GHOST-14). `orientation` is not part of the
// pose: with either it or `position`, the rest pose of such a model moves
// its vertices off the file's positions (rest-pose test, lurker_alt).
// The angle order (X, then Y, then Z) is not tested (O-GHOST-9).

import { mat4 } from 'gl-matrix';
import type { NodBone } from './container';

export interface Track {
  bone: number;
  kind: 0 | 1;
  /** Frame of each key, rising. */
  frames: Float64Array;
  /** 12 numbers a key: value, b, c, d. */
  curves: Float64Array;
}

export interface NodClip {
  name: string;
  /** In frames. */
  length: number;
  framesPerSecond: number;
  tracks: Track[];
}

type Json = Record<string, unknown>;
const isObject = (v: unknown): v is Json => typeof v === 'object' && v !== null && !Array.isArray(v);

/** A clip export, checked; `bones` is the model's bone count. */
export function readClip(body: unknown, name: string, bones: number): NodClip {
  const fail = (why: string): never => {
    throw new Error(`clip ${name}: ${why}`);
  };
  if (!isObject(body)) return fail('not an object');
  if (typeof body['error'] === 'string') return fail(`refused: ${body['error']}`);
  const length = body['length'];
  const fps = body['framesPerSecond'];
  if (typeof length !== 'number' || !(length >= 0)) return fail('length is not a number of frames');
  if (typeof fps !== 'number' || !(fps > 0)) return fail('framesPerSecond is not a number');
  const raw = body['tracks'];
  if (!Array.isArray(raw)) return fail('tracks is not a list');
  const tracks = raw.map((t: unknown, i): Track => {
    if (!isObject(t)) return fail(`track ${i} is not an object`);
    const bone = t['bone'];
    const kind = t['kind'];
    const keys = t['keys'];
    if (typeof bone !== 'number' || !Number.isInteger(bone) || bone < 0 || bone >= bones) return fail(`track ${i} names bone ${String(bone)}; the model has ${bones}`);
    if (kind !== 0 && kind !== 1) return fail(`track ${i} has kind ${String(kind)}, not 0 or 1`);
    if (!Array.isArray(keys) || !keys.length) return fail(`track ${i} has no keys`);
    const frames = new Float64Array(keys.length);
    const curves = new Float64Array(keys.length * 12);
    keys.forEach((key: unknown, k) => {
      if (!Array.isArray(key) || key.length !== 13) return fail(`track ${i} key ${k} is not 13 numbers`);
      const last = k === keys.length - 1;
      key.forEach((v: unknown, n) => {
        // The last key's curve is not evaluated: its b, c and d may be null (not-a-number).
        const used = n < 4 || !last;
        if (typeof v !== 'number' && !(v === null && !used)) fail(`track ${i} key ${k} number ${n} is ${String(v)}`);
        const value = typeof v === 'number' ? v : 0;
        if (n === 0) frames[k] = value;
        else curves[k * 12 + n - 1] = value;
      });
      if (k > 0 && (frames[k] ?? 0) < (frames[k - 1] ?? 0)) fail(`track ${i} key ${k} is before the key ahead of it`);
      return undefined;
    });
    return { bone, kind, frames, curves };
  });
  return { name, length, framesPerSecond: fps, tracks };
}

/** The curve of key `k` at `t` frames after it. */
export function curveAt(track: Track, k: number, t: number, out: Float64Array): Float64Array {
  const base = k * 12;
  const c = track.curves;
  for (let a = 0; a < 3; a++) out[a] = (c[base + a] ?? 0) + t * (c[base + 3 + a] ?? 0) + t * t * (c[base + 6 + a] ?? 0) + t * t * t * (c[base + 9 + a] ?? 0);
  return out;
}

/** A track's three numbers at `frame`. Before the first key: its value; from the last key on: the last value. */
export function sample(track: Track, frame: number, out: Float64Array): Float64Array {
  const { frames } = track;
  const n = frames.length;
  let k = 0;
  while (k + 1 < n && (frames[k + 1] ?? 0) <= frame) k++;
  if (k === n - 1 || frame <= (frames[0] ?? 0)) return curveAt(track, k, 0, out);
  return curveAt(track, k, frame - (frames[k] ?? 0), out);
}

const DEG = Math.PI / 180;
const scratch = new Float64Array(3);
const turn = mat4.create();
const local = mat4.create();

/**
 * The bone matrices at `frame` of `clip` (null: the rest pose), each
 * global x move(offset), into `out` (16 numbers a bone). `globals` gets
 * each bone's global matrix.
 */
export function pose(bones: readonly NodBone[], clip: NodClip | null, frame: number, out: Float32Array, globals: Float32Array): void {
  const angles = new Float64Array(bones.length * 3);
  const moves = new Float64Array(bones.length * 3);
  if (clip) {
    for (const track of clip.tracks) {
      sample(track, frame, scratch);
      (track.kind === 0 ? angles : moves).set(scratch, track.bone * 3);
    }
  }
  bones.forEach((bone, b) => {
    mat4.identity(turn);
    mat4.rotateZ(turn, turn, (angles[b * 3 + 2] ?? 0) * DEG);
    mat4.rotateY(turn, turn, (angles[b * 3 + 1] ?? 0) * DEG);
    mat4.rotateX(turn, turn, (angles[b * 3] ?? 0) * DEG);
    const parent = bone.parent >= 0 ? bones[bone.parent] : undefined;
    const rest = [0, 1, 2].map((a) => (parent ? parent.offset[a] ?? 0 : 0) - (bone.offset[a] ?? 0));
    mat4.fromTranslation(local, [(rest[0] ?? 0) + (moves[b * 3] ?? 0), (rest[1] ?? 0) + (moves[b * 3 + 1] ?? 0), (rest[2] ?? 0) + (moves[b * 3 + 2] ?? 0)]);
    mat4.mul(local, local, turn);
    const global = globals.subarray(b * 16, b * 16 + 16);
    if (bone.parent >= 0) mat4.mul(global, globals.subarray(bone.parent * 16, bone.parent * 16 + 16), local);
    else mat4.copy(global, local);
    const matrix = out.subarray(b * 16, b * 16 + 16);
    mat4.translate(matrix, global, bone.offset);
  });
}
