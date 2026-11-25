// The HTTP side of the server: the request a route sees, JSON and file
// replies, query numbers, and the listening server. A route never writes
// headers itself.

import { createReadStream } from 'node:fs';
import { stat } from 'node:fs/promises';
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

export function sendFile(res: ServerResponse, full: string, type: string, cache: string): void {
  res.writeHead(200, { 'content-type': type, 'cache-control': cache });
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

function requestOf(req: IncomingMessage, res: ServerResponse): Request {
  const raw = req.url ?? '/';
  const cut = raw.indexOf('?');
  return {
    method: req.method ?? 'GET',
    route: cut < 0 ? raw : raw.slice(0, cut),
    params: new URLSearchParams(cut < 0 ? '' : raw.slice(cut + 1)),
    res,
    json: () => readJson(req),
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
