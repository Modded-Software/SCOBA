// The state index is worked out again when the pipeline's code changed
// (SPEC-VIEWER 17.1). The head names the hash of the code that wrote it
// (scripts/hdtex/core/view.py `code`); the server makes the same hash
// (core/textures.ts `pipelineCode`) and, at its start, indexes a dataset
// whose head names another. A server of its own: it is stopped, its head is
// given another code, and it is started again on the same store.
import { readFileSync } from 'node:fs';
import { DatabaseSync } from 'node:sqlite';
import { join, resolve } from 'node:path';
import { test, expect, ownServer, startServer, INDEX_FILE } from '../fixtures.mjs';
import { source } from '../unit/source.mjs';

test.describe.configure({ mode: 'serial', timeout: 400_000 });

const GAME = 'ghost';
const DATASET = 'build';
const REPO = resolve('..');
/** A statement of the repository's SQL tree, as the pipeline and the server's reader run it. */
const statement = (name) => readFileSync(join(REPO, 'sql', 'texture-index', `${name}.sql`), 'utf8');

/** The head of the Ghost dataset in a store's state index, as JSON. */
function headIn(store) {
  const db = new DatabaseSync(join(store, INDEX_FILE), { readOnly: true });
  try {
    return JSON.parse(String(db.prepare(statement('dataset_head')).get(GAME, DATASET).head));
  } finally {
    db.close();
  }
}

/** Write a head into a stopped server's state index. */
function putHead(store, head) {
  const db = new DatabaseSync(join(store, INDEX_FILE));
  try {
    db.prepare(statement('dataset_put_head')).run(GAME, DATASET, JSON.stringify(head));
  } finally {
    db.close();
  }
}

test('the head names the code that wrote it; a head of other code is indexed again at the start, one of this code is not', async ({ worker }, testInfo) => {
  const { pipelineCode } = await source('src/server/core/textures.ts');
  const code = pipelineCode(REPO);
  expect(code).toMatch(/^[0-9a-f]{64}$/);
  let server = await ownServer(worker, testInfo.parallelIndex, 'index-code');
  const { store, datasets, root, port } = server;
  // Python and the server hash the same files the same way: the head the pipeline wrote names the server's hash.
  expect(headIn(store).code).toBe(code);
  await server.stop();

  // A field no pipeline writes marks the head: a start that indexes the dataset writes the head anew, without it.
  // Negative: a head of this code is not indexed again; the mark stays.
  putHead(store, { ...headIn(store), mark: 'kept' });
  server = await startServer({ port, store, datasets, log: join(root, 'same.log') });
  await server.stop();
  expect(headIn(store).mark, 'negative: no index at a start with the head of this code').toBe('kept');

  // A head of other code: the start indexes it, and the head names this code again.
  putHead(store, { ...headIn(store), code: 'other', mark: 'kept' });
  server = await startServer({ port, store, datasets, log: join(root, 'other.log') });
  await server.stop();
  const after = headIn(store);
  expect({ code: after.code, mark: after.mark }).toEqual({ code, mark: undefined });
});
