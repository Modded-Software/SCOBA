// Once per run, before any worker: start a server on the base texture store.
// The start builds the state index only when it is missing (the first run,
// or after the store was deleted); otherwise it syncs nothing. The server is
// stopped and the index's log folded into the file, so each worker copies
// one closed file (tests/fixtures.mjs).

import { existsSync } from 'node:fs';
import { mkdir } from 'node:fs/promises';
import { DatabaseSync } from 'node:sqlite';
import { join } from 'node:path';
import { BASE_PORT, INDEX_FILE, envPath, startServer } from './fixtures.mjs';

/** Fold the log of a WAL file into it; the log goes when the last connection closes. */
function closeIndex(file) {
  const db = new DatabaseSync(file);
  try {
    db.exec('PRAGMA wal_checkpoint(TRUNCATE)');
  } finally {
    db.close();
  }
}

export default async function globalSetup() {
  const store = envPath('TEXTURE_STORE');
  const root = join(envPath('WEBVIEWER_WORK'), 'test-workers');
  await mkdir(root, { recursive: true });
  const server = await startServer({ port: BASE_PORT, store, datasets: envPath('WEBVIEWER_DATASETS'), log: join(root, 'base-server.log') });
  try {
    const { games } = await (await fetch(`${server.url}/api/health`)).json();
    for (const { id, available } of games) {
      if (!available) continue;
      const answer = await fetch(`${server.url}/api/${id}/datasets`);
      if (!answer.ok) throw new Error(`the base server's ${id} datasets: ${answer.status} ${await answer.text()}`);
    }
  } finally {
    await server.stop();
  }
  const file = join(store, INDEX_FILE);
  if (!existsSync(file)) throw new Error(`the base server made no state index at ${file}`);
  closeIndex(file);
}
