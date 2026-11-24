// The container a Ghost model is served as (SPEC-VIEWER-GHOST 7), which the
// nod format reads (src/formats/nod/container.ts):
//   "NODX", uint32 version 1, uint32 JSON length, the JSON (padded with
//   blanks to 4 bytes), then the model binary of `NODExport nod`.
// exporter.ts writes it. src/tools/build.ts also bundles this file alone as
// build/ghost-container.mjs, so the tests make a refused model with this
// code and not a copy of it.

import { NODX_MAGIC, NODX_VERSION } from '../../../shared/nodx';

/** The container of `body` ({ model, materials } or { error }) and the model binary. */
export function packContainer(body: Record<string, unknown>, binary: Uint8Array = new Uint8Array(0)): Buffer {
  const text = JSON.stringify(body);
  const padded = text + ' '.repeat((4 - (Buffer.byteLength(text) % 4)) % 4);
  const head = Buffer.alloc(12);
  head.write(NODX_MAGIC, 0, 'latin1');
  head.writeUInt32LE(NODX_VERSION, 4);
  head.writeUInt32LE(Buffer.byteLength(padded), 8);
  return Buffer.concat([head, Buffer.from(padded), binary]);
}
