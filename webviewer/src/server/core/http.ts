// The HTTP side of the server: the request a route sees, JSON and file
// replies, query numbers, and the listening server. A route never writes
// headers itself.

import { createReadStream, createWriteStream } from 'node:fs';
import { rename, rm, stat } from 'node:fs/promises';
import { createServer, type IncomingMessage, type ServerResponse } from 'node:http';

/** One request, as the routes see it. */
export interface Request {
  readonly method: string;
  /** The raw path, before any decoding: "/../x" and "/%2e%2e/x" never normalise onto a real route. */
  readonly route: string;
  readonly params: URLSearchParams;
  readonly res: ServerResponse;
  /** The body as JSON. A body that is not JSON, or larger than BODY_LIMIT, is an error. */
  json(): Promise<unknown>;
  /** The body into a file, never held whole in memory (`receive`). */
  save(target: string, limit: number): Promise<number>;
}

/** The largest body a request may send. A texture call sends a few names. */
export const BODY_LIMIT = 64 * 1024;

/** A route answers a request it knows and returns true; false: not mine. */
export type Route = (request: Request) => Promise<boolean>;

/** The code of a Node system error (ENOENT, ...), or undefined. */
export function errorCode(error: unknown): string | undefined {
  const code: unknown = typeof error === 'object' && error !== null ? Reflect.get(error, 'code') : undefined;
  return typeof code === 'string' ? code : undefined;
}

/** The message of an error, or the value as text. */
export function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export function json(res: ServerResponse, code: number, body: unknown): void {
  res.writeHead(code, { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' });
  res.end(JSON.stringify(body));
}

/** `more`: headers beside the type and the cache rule. */
export function sendFile(res: ServerResponse, full: string, type: string, cache: string, more: Readonly<Record<string, string>> = {}): void {
  res.writeHead(200, { ...more, 'content-type': type, 'cache-control': cache });
  createReadStream(full)
    .on('error', (error) => res.destroy(error))
    .pipe(res);
}

/** True when `path` is a file; false when nothing (or a non-folder parent) is there. */
export async function isFile(path: string): Promise<boolean> {
  try {
    return (await stat(path)).isFile();
  } catch (error) {
    const code = errorCode(error);
    if (code === 'ENOENT' || code === 'ENOTDIR') return false;
    throw error;
  }
}

/** A whole-number query value, clamped to [low, high]; a missing or bad value gives `standard`. */
export function intParam(params: URLSearchParams, name: string, standard: number, low: number, high: number): number {
  const value = Number.parseInt(params.get(name) ?? '', 10);
  return Number.isFinite(value) ? Math.min(Math.max(value, low), high) : standard;
}

/** Every request that is not a GET ends here, with 405. Routes for another method go before it. */
export const onlyGet: Route = async ({ method, res }) => {
  if (method === 'GET') return false;
  json(res, 405, { error: 'method not allowed' });
  return true;
};

/** Thrown for a body that cannot be read: the routes answer 400 with the message. */
export class BodyError extends Error {}

function readJson(req: IncomingMessage): Promise<unknown> {
  return new Promise((resolve, reject) => {
    const parts: Buffer[] = [];
    let size = 0;
    req.on('data', (part: Buffer) => {
      size += part.length;
      if (size > BODY_LIMIT) {
        reject(new BodyError(`the body is larger than ${BODY_LIMIT} bytes`));
        req.destroy();
        return;
      }
      parts.push(part);
    });
    req.on('error', reject);
    req.on('end', () => {
      try {
        resolve(JSON.parse(Buffer.concat(parts).toString('utf8')));
      } catch (error) {
        reject(new BodyError(`the body is not JSON: ${messageOf(error)}`));
      }
    });
  });
}

/** Thrown for a body past the bound of `receive`: the routes answer 413 with the message. */
export class TooLarge extends Error {}

let parts = 0;

/**
 * Write a body to `target`: streamed to a file of another name beside it,
 * then renamed, so a reader never sees half a file. Returns its size. A body
 * past `limit` bytes, or one that stops before its end, leaves `target` as
 * it was. The request is not destroyed: the reply can still be sent.
 */
async function receive(req: IncomingMessage, target: string, limit: number): Promise<number> {
  const large = (): TooLarge => new TooLarge(`the body is larger than ${limit} bytes`);
  const declared = Number(req.headers['content-length'] ?? Number.NaN);
  if (declared > limit) throw large();
  const part = `${target}.${process.pid}.${++parts}.part`;
  const out = createWriteStream(part);
  let size = 0;
  try {
    await new Promise<void>((resolve, reject) => {
      const data = (chunk: Buffer): void => {
        size += chunk.length;
        if (size > limit) {
          req.off('data', data);
          reject(large());
        } else if (!out.write(chunk)) {
          req.pause();
          out.once('drain', () => req.resume());
        }
      };
      req.on('data', data);
      req.once('end', () => out.end());
      req.once('error', reject);
      req.once('close', () => {
        if (!req.complete) reject(new Error('the body stopped before its end'));
      });
      out.once('error', reject);
      out.once('finish', resolve);
    });
    await rename(part, target);
  } catch (error) {
    out.destroy();
    await rm(part, { force: true });
    throw error;
  }
  return size;
}

function requestOf(req: IncomingMessage, res: ServerResponse): Request {
  const raw = req.url ?? '/';
  const cut = raw.indexOf('?');
  return {
    method: req.method ?? 'GET',
    route: cut < 0 ? raw : raw.slice(0, cut),
    params: new URLSearchParams(cut < 0 ? '' : raw.slice(cut + 1)),
    res,
    json: () => readJson(req),
    save: (target, limit) => receive(req, target, limit),
  };
}

/**
 * Listen on `host:port`. Each request goes to the routes in order; the
 * first that answers ends it. None: 404. A route that throws: 500 with
 * the message, or the connection closed when the reply had started.
 */
export function serve(routes: readonly Route[], port: number, host: string, ready: () => void): void {
  async function handle(request: Request): Promise<void> {
    for (const route of routes) if (await route(request)) return;
    json(request.res, 404, { error: 'not found' });
  }
  createServer((req, res) => {
    handle(requestOf(req, res)).catch((error: unknown) => {
      console.error(error);
      if (!res.headersSent) json(res, 500, { error: messageOf(error) });
      else res.destroy();
    });
  }).listen(port, host, ready);
}
