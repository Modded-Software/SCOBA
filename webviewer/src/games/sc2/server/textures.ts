// The HD texture viewer (scripts/hdtex/compare.py builds it) served below
// /api/sc2/x/textures/, so the model viewer can show it in a window. The
// folder is WEBVIEWER_HDTEX, or build/hdtex/compare of the project. Also
// the upscaled model textures themselves, for the view (hdRoute).

import { readFile } from 'node:fs/promises';
import { join, resolve, sep } from 'node:path';
import { errorCode, isFile, json, messageOf, sendFile, type Route } from '../../../server/core/http';

/** The extension route below x/textures. */
const PREFIX = '/';
const TYPES = new Map([
  ['html', 'text/html; charset=utf-8'],
  ['png', 'image/png'],
]);
const BUILD = 'uv run python scripts/hd_textures.py compare';

/** The folder the texture viewer is served from. */
export function texturesRoot(projectRoot: string, env: NodeJS.ProcessEnv = process.env): string {
  return resolve(env['WEBVIEWER_HDTEX'] || join(projectRoot, 'build', 'hdtex', 'compare'));
}

/**
 * The cache folder of the upscaled model textures (scripts/hdtex): its
 * manifest.json names each texture a model uses ("asset") and the upscaled
 * DDS file ("file"). WEBVIEWER_HDTEX_MODELS, or build/hdtex/upscale/models.
 */
export function hdModelsRoot(projectRoot: string, env: NodeJS.ProcessEnv = process.env): string {
  return resolve(env['WEBVIEWER_HDTEX_MODELS'] || join(projectRoot, 'build', 'hdtex', 'upscale', 'models'));
}

const assetKey = (path: string): string => path.toLowerCase().replaceAll('/', '\\');

/** In-model texture path -> the upscaled file. Empty when nothing is cached. */
async function hdFiles(root: string): Promise<Map<string, string>> {
  let body: string;
  try {
    body = await readFile(join(root, 'manifest.json'), 'utf8');
  } catch (error) {
    if (errorCode(error) === 'ENOENT') return new Map();
    throw error;
  }
  const data: unknown = JSON.parse(body);
  const list: unknown = typeof data === 'object' && data !== null ? Reflect.get(data, 'textures') : undefined;
  if (!Array.isArray(list)) throw new Error(`${join(root, 'manifest.json')}: no "textures" list`);
  const out = new Map<string, string>();
  for (const entry of list) {
    const asset: unknown = typeof entry === 'object' && entry !== null ? Reflect.get(entry, 'asset') : undefined;
    const file: unknown = typeof entry === 'object' && entry !== null ? Reflect.get(entry, 'file') : undefined;
    if (typeof asset !== 'string' || typeof file !== 'string') throw new Error(`${join(root, 'manifest.json')}: a texture without "asset" and "file"`);
    out.set(assetKey(asset), resolve(root, file));
  }
  return out;
}

/** x/hd-textures ('list': the in-model paths) and x/hd-asset?path= ('file': one upscaled file). */
export function hdRoute(root: string, part: 'list' | 'file'): Route {
  return async ({ route, method, params, res }) => {
    if (route !== '') return false;
    if (method !== 'GET') {
      json(res, 405, { error: 'method not allowed' });
      return true;
    }
    if (part === 'list') {
      json(res, 200, { assets: [...(await hdFiles(root)).keys()] });
      return true;
    }
    const path = params.get('path');
    if (!path) {
      json(res, 400, { error: 'path is required' });
      return true;
    }
    const full = (await hdFiles(root)).get(assetKey(path));
    if (!full || !full.startsWith(root + sep) || !(await isFile(full))) {
      json(res, 404, { error: 'no HD texture', path });
      return true;
    }
    sendFile(res, full, 'application/octet-stream', 'no-store');
    return true;
  };
}

/** x/textures (whether the viewer is built) and every route below x/textures/ (its page and images). */
export function texturesRoute(root: string): Route {
  return async ({ route, method, res }) => {
    if (method !== 'GET') {
      json(res, 405, { error: 'method not allowed' });
      return true;
    }
    if (route === '') {
      json(res, 200, { built: await isFile(join(root, 'index.html')), build: BUILD });
      return true;
    }
    if (!route.startsWith(PREFIX)) return false;
    let rel: string;
    try {
      rel = decodeURIComponent(route.slice(PREFIX.length)) || 'index.html';
    } catch (error) {
      json(res, 400, { error: `bad path: ${messageOf(error)}` });
      return true;
    }
    const full = resolve(root, rel);
    const type = TYPES.get(rel.slice(rel.lastIndexOf('.') + 1).toLowerCase());
    // Only pages and images, and only inside the folder.
    if (!type || !full.startsWith(root + sep)) {
      json(res, 404, { error: 'not found' });
      return true;
    }
    if (!(await isFile(full))) {
      json(res, 404, rel === 'index.html' ? { error: 'the texture viewer is not built', build: BUILD } : { error: 'not found' });
      return true;
    }
    // A new build rewrites the page and its images in place: never cached.
    sendFile(res, full, type, 'no-store');
    return true;
  };
}
