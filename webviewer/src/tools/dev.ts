// The dev server with hot reload. Runs build/server.js as a child and
// keeps it current:
//   - a change under src/ or the renderer source (ref/mdx-m3-viewer/src)
//     rebuilds (scripts/build.sh). patches/ is not watched: the build
//     writes it, so watching it would rebuild for ever;
//   - a build/server.js with new content, from that rebuild or from any
//     other build (a test run rebuilds the same folder), restarts the
//     child. A build that changes only the page does not restart it.
// A failed build keeps the running server and logs the error. The page
// files are read from disk on each browser load, so a reload of the page
// shows a new page build.
//
// Started by scripts/start.sh (the service and make viewer-serve).

import { spawn, type ChildProcess } from 'node:child_process';
import { createHash } from 'node:crypto';
import { readFileSync, watch, watchFile } from 'node:fs';
import { join } from 'node:path';

/** The viewer folder. scripts/paths.sh exports it. */
function viewerDir(): string {
  const dir = process.env.WEBVIEWER_DIR;
  if (dir === undefined || dir === '') {
    throw new Error('WEBVIEWER_DIR is not set; start this tool with scripts/start.sh');
  }
  return dir;
}

const HERE = viewerDir();
const SERVER = join(HERE, 'build', 'server.js');
const WATCHED = ['src', join('ref', 'mdx-m3-viewer', 'src')];
/** Edits come in bursts (a save, a git checkout): wait this long after the last one. */
const SETTLE_MS = 400;

const log = (text: string): void => console.log(`dev: ${text}`);

let server: ChildProcess | null = null;
let stopping = false;

/** Start build/server.js. Its exit on its own ends this process, so systemd restarts all. */
function startServer(): void {
  // Its own process group: a stop ends the jobs it started too (index runs, stormex).
  const child = spawn('node', [SERVER], { cwd: HERE, stdio: 'inherit', detached: true });
  server = child;
  log(`server started, pid ${child.pid}`);
  child.on('exit', (code, signal) => {
    if (server !== child) return;
    server = null;
    if (stopping) return;
    log(`server exited on its own (code ${code}, signal ${signal}); stopping`);
    process.exit(code === 0 ? 1 : (code ?? 1));
  });
}

/** Stop the running server; resolves when it has exited. */
function stopServer(): Promise<void> {
  const child = server;
  if (child === null) return Promise.resolve();
  server = null;
  return new Promise((done) => {
    child.once('exit', () => done());
    if (child.pid === undefined) child.kill('SIGTERM');
    else process.kill(-child.pid, 'SIGTERM');
  });
}

let restarting = Promise.resolve();
function restartServer(): void {
  restarting = restarting.then(async () => {
    log('build/server.js changed; restarting the server');
    await stopServer();
    if (!stopping) startServer();
  });
}

let building = false;
let again = false;
/** Rebuild; a change during a build runs one more build after it. */
function rebuild(): void {
  if (building) {
    again = true;
    return;
  }
  building = true;
  log('source changed; building');
  const child = spawn('bash', ['scripts/build.sh'], { cwd: HERE, stdio: 'inherit' });
  child.on('exit', (code) => {
    building = false;
    if (code === 0) log('build done');
    else log(`build failed (code ${code}); the running server stays`);
    if (again) {
      again = false;
      rebuild();
    }
  });
}

/** Call `act` once, SETTLE_MS after the last of a burst of calls. */
function settled(act: () => void): () => void {
  let timer: NodeJS.Timeout | null = null;
  return () => {
    if (timer !== null) clearTimeout(timer);
    timer = setTimeout(() => {
      timer = null;
      act();
    }, SETTLE_MS);
  };
}

const onSource = settled(rebuild);
for (const folder of WATCHED) {
  watch(join(HERE, folder), { recursive: true }, onSource);
}

// build/ is a link into the work folder and esbuild replaces the file:
// poll it, and compare its content, not its time.
const digest = (): string => createHash('sha256').update(readFileSync(SERVER)).digest('hex');
let built = digest();
const onServer = settled(() => {
  const now = digest();
  if (now === built) return;
  built = now;
  restartServer();
});
watchFile(SERVER, { interval: 500 }, onServer);

for (const signal of ['SIGTERM', 'SIGINT'] as const) {
  process.on(signal, () => {
    stopping = true;
    stopServer().then(
      () => process.exit(0),
      (error: unknown) => {
        log(`the server did not stop: ${error instanceof Error ? error.message : String(error)}`);
        process.exit(1);
      },
    );
  });
}

log(`watching ${WATCHED.join(', ')} and build/server.js`);
startServer();
