// The scene store (SPEC-VIEWER section 10.2): IndexedDB database "viewer",
// object store "scenes", one record per scene, keyed by its id. This file
// moves records in and out; it does not check them. features/scenes checks
// every record it reads with parseSceneDocument.

import type { SceneDocument } from '../../../shared/scene';

const DATABASE = 'viewer';
const VERSION = 1;
const STORE = 'scenes';

/** A stored record as read: its key, and the value to check. */
export interface StoredScene {
  key: string;
  value: unknown;
}

export interface SceneStore {
  /** Every record, in key order. */
  all(): Promise<StoredScene[]>;
  put(scene: SceneDocument): Promise<void>;
  remove(id: string): Promise<void>;
}

/** A request as a promise. */
function settled<T>(request: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    request.addEventListener('success', () => resolve(request.result));
    request.addEventListener('error', () => reject(request.error ?? new Error('scene store: a request failed')));
  });
}

/** A transaction's end as a promise: it resolves once the write is on disk. */
function finished(transaction: IDBTransaction): Promise<void> {
  return new Promise((resolve, reject) => {
    transaction.addEventListener('complete', () => resolve());
    transaction.addEventListener('error', () => reject(transaction.error ?? new Error('scene store: a write failed')));
    transaction.addEventListener('abort', () => reject(transaction.error ?? new Error('scene store: a write was aborted')));
  });
}

function open(): Promise<IDBDatabase> {
  const request = indexedDB.open(DATABASE, VERSION);
  request.addEventListener('upgradeneeded', () => {
    const db = request.result;
    if (!db.objectStoreNames.contains(STORE)) db.createObjectStore(STORE, { keyPath: 'id' });
  });
  return new Promise((resolve, reject) => {
    request.addEventListener('success', () => resolve(request.result));
    request.addEventListener('error', () => reject(request.error ?? new Error('scene store: the database did not open')));
    request.addEventListener('blocked', () => reject(new Error('scene store: the database is open in an older page; close it')));
  });
}

export async function openSceneStore(): Promise<SceneStore> {
  const db = await open();
  return {
    async all() {
      const transaction = db.transaction(STORE, 'readonly');
      const store = transaction.objectStore(STORE);
      const [keys, values] = await Promise.all([settled(store.getAllKeys()), settled(store.getAll())]);
      if (keys.length !== values.length) throw new Error('scene store: keys and records differ in number');
      return keys.map((key, i) => ({ key: String(key), value: values[i] }));
    },
    async put(scene) {
      const transaction = db.transaction(STORE, 'readwrite');
      transaction.objectStore(STORE).put(scene);
      await finished(transaction);
    },
    async remove(id) {
      const transaction = db.transaction(STORE, 'readwrite');
      transaction.objectStore(STORE).delete(id);
      await finished(transaction);
    },
  };
}
