// PhotoCraft as the server sees it (SPEC-PHOTOCRAFT section 7): the install
// below PHOTOCRAFT_HOME, its state for the health answer, and the route that
// serves the editor site below /photocraft/. Read from disk on each request,
// so a new install needs no restart.

import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import type { PhotocraftHealth } from '../../shared/protocol';
import { errorCode, isFile, json, sendFile, type Route } from './http';

/** The route prefix of the editor site. */
export const SITE_ROUTE = '/photocraft/';

/** One path part of a site file: no separator, and never "." or "..". */
const PART = /^[A-Za-z0-9_-][A-Za-z0-9._-]*$/;

/** The content type by file ending. A `.wasm` must be `application/wasm` to compile while it loads. */
const TYPES: Readonly<Record<string, string>> = {
  html: 'text/html; charset=utf-8',
  js: 'text/javascript; charset=utf-8',
  wasm: 'application/wasm',
  css: 'text/css; charset=utf-8',
  json: 'application/json; charset=utf-8',
  svg: 'image/svg+xml',
  png: 'image/png',
  ico: 'image/x-icon',
  md: 'text/plain; charset=utf-8',
  txt: 'text/plain; charset=utf-8',
};

/** The folders and files of an install. */
export function photocraftPlaces(home: string): { site: string; renderer: string; pins: string } {
  return { site: join(home, 'site'), renderer: join(home, 'bin', 'photocraft-cli'), pins: join(home, 'photocraft.pins') };
}

/** The text of a file, or undefined when it is not there. */
function textOf(path: string): string | undefined {
  try {
    return readFileSync(path, 'utf8');
  } catch (error) {
    const code = errorCode(error);
    if (code === 'ENOENT' || code === 'ENOTDIR') return undefined;
    throw error;
  }
}

/** The install's state: its recorded pins, or why there is none. A site without a renderer is no install. */
export async function photocraftHealth(home: string): Promise<PhotocraftHealth> {
  const places = photocraftPlaces(home);
  const missing = (what: string): PhotocraftHealth => ({ installed: false, pins: [], reason: `${what}; run: make install-photocraft` });
  const pins = textOf(places.pins);
  if (pins === undefined) return missing(`PhotoCraft is not installed: no pin record at ${places.pins}`);
  if (!(await isFile(join(places.site, 'index.html')))) return missing(`the PhotoCraft install has no editor site at ${places.site}`);
  if (!(await isFile(places.renderer))) return missing(`the PhotoCraft install has no renderer at ${places.renderer}`);
  return { installed: true, pins: pins.split('\n').filter((line) => line !== ''), reason: null };
}

/**
 * `GET /photocraft/<file>`: a file of the editor site. `/photocraft/` is its
 * page. A file that is not there is a 404, never the page. The route is the
 * raw path, so an encoded ".." is no path part and never leaves the site.
 */
export function photocraftSite(home: string): Route {
  const { site } = photocraftPlaces(home);
  return async ({ method, route, res }) => {
    if (!route.startsWith(SITE_ROUTE)) return false;
    if (method !== 'GET') {
      json(res, 405, { error: 'method not allowed' });
      return true;
    }
    const rest = route.slice(SITE_ROUTE.length);
    const parts = rest === '' ? ['index.html'] : rest.split('/');
    if (!parts.every((part) => PART.test(part))) {
      json(res, 404, { error: 'not found' });
      return true;
    }
    const full = join(site, ...parts);
    if (!(await isFile(full))) {
      json(res, 404, { error: 'not found' });
      return true;
    }
    const name = parts[parts.length - 1] ?? '';
    const dot = name.lastIndexOf('.');
    const type = (dot > 0 ? TYPES[name.slice(dot + 1).toLowerCase()] : undefined) ?? (dot > 0 ? 'application/octet-stream' : 'text/plain; charset=utf-8');
    sendFile(res, full, type, 'no-store');
    return true;
  };
}
