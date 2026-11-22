// The HD texture viewer (scripts/hdtex/compare.py builds it) served below
// /textures/, so the model viewer can show it in a window. The folder is
// WEBVIEWER_HDTEX, or build/hdtex/compare of the project. Also the upscaled
// model textures themselves, for the view (serveHd).
import { readFile, stat } from 'node:fs/promises';
import { join, resolve, sep } from 'node:path';

const PREFIX = '/textures/';
const TYPES = new Map([
  ['html', 'text/html; charset=utf-8'],
  ['png', 'image/png'],
]);
const BUILD = 'uv run python scripts/hd_textures.py compare';

/** The folder the texture viewer is served from. */
export function texturesRoot(projectRoot) {
  return resolve(process.env.WEBVIEWER_HDTEX || join(projectRoot, 'build', 'hdtex', 'compare'));
}

/**
 * The cache folder of the upscaled model textures (scripts/hdtex): its
 * manifest.json names each texture a model uses ("asset") and the upscaled
 * DDS file ("file"). WEBVIEWER_HDTEX_MODELS, or build/hdtex/upscale/models.
 */
export function hdModelsRoot(projectRoot) {
  return resolve(process.env.WEBVIEWER_HDTEX_MODELS || join(projectRoot, 'build', 'hdtex', 'upscale', 'models'));
}

const assetKey = (path) => path.toLowerCase().replaceAll('/', '\\');

/** In-model texture path -> the upscaled file. Empty when nothing is cached. */
async function hdFiles(root) {
  let text;
  try {
    text = await readFile(join(root, 'manifest.json'), 'utf8');
  } catch (error) {
    if (error.code === 'ENOENT') return new Map();
    throw error;
  }
  return new Map(JSON.parse(text).textures.map((texture) => [assetKey(texture.asset), resolve(root, texture.file)]));
}

/** Answer /api/hd-textures and /hd-asset. Returns false for any other route. */
export async function serveHd(root, route, params, res, reply) {
  if (route === '/api/hd-textures') {
    reply.json(res, 200, { assets: [...(await hdFiles(root)).keys()] });
    return true;
  }
  if (route !== '/hd-asset') return false;
  const path = params.get('path');
  if (!path) {
    reply.json(res, 400, { error: 'path is required' });
    return true;
  }
  const full = (await hdFiles(root)).get(assetKey(path));
  if (!full || !full.startsWith(root + sep) || !(await isFile(full))) {
    reply.json(res, 404, { error: 'no HD texture', path });
    return true;
  }
  reply.sendFile(res, full, 'application/octet-stream', 'no-store');
  return true;
}

const isFile = (path) =>
  stat(path).then(
    (found) => found.isFile(),
    (error) => {
      if (error.code === 'ENOENT' || error.code === 'ENOTDIR') return false;
      throw error;
    },
  );

/**
 * Answer a route below /textures/. Returns false when the route is not one.
 * `reply`: { json(res, code, body), sendFile(res, full, type, cache) }.
 */
export async function serveTextures(root, route, res, reply) {
  if (route === '/api/textures') {
    reply.json(res, 200, { built: await isFile(join(root, 'index.html')), build: BUILD });
    return true;
  }
  if (!route.startsWith(PREFIX)) return false;
  let rel;
  try {
    rel = decodeURIComponent(route.slice(PREFIX.length)) || 'index.html';
  } catch (error) {
    reply.json(res, 400, { error: `bad path: ${error.message}` });
    return true;
  }
  const full = resolve(root, rel);
  const type = TYPES.get(rel.slice(rel.lastIndexOf('.') + 1).toLowerCase());
  // Only pages and images, and only inside the folder.
  if (!type || !full.startsWith(root + sep)) {
    reply.json(res, 404, { error: 'not found' });
    return true;
  }
  if (!(await isFile(full))) {
    const missing = rel === 'index.html' ? { error: 'the texture viewer is not built', build: BUILD } : { error: 'not found' };
    reply.json(res, 404, missing);
    return true;
  }
  // A new build rewrites the page and its images in place: never cached.
  reply.sendFile(res, full, type, 'no-store');
  return true;
}
