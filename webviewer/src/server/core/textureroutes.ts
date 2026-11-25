// The texture routes of SPEC-VIEWER section 8, over a game's texture
// service. A game without one answers 404 on each (R-VIEW-100).

import type { BakeAsk, SkinAsk, TextureRequestAsk, UnbakeAsk } from '../../shared/textures';
import { HttpError, type GameBackend } from './backend';
import { BodyError, json, sendFile, type Request } from './http';

/** The body of a POST, as an object. */
async function body(request: Request): Promise<Record<string, unknown>> {
  if (request.method !== 'POST') throw new HttpError(405, { error: 'method not allowed' });
  let value: unknown;
  try {
    value = await request.json();
  } catch (error) {
    if (error instanceof BodyError) throw new HttpError(400, { error: error.message });
    throw error;
  }
  if (typeof value !== 'object' || value === null || Array.isArray(value)) throw new HttpError(400, { error: 'the body is a JSON object' });
  return value as Record<string, unknown>;
}

const get = (request: Request): void => {
  if (request.method !== 'GET') throw new HttpError(405, { error: 'method not allowed' });
};

/** A bake or unbake body names an owner, or an asset; not both. */
function ownerOrAsset(ask: Record<string, unknown>, what: string): void {
  if (('owner' in ask) === ('asset' in ask)) throw new HttpError(400, { error: `a ${what} body names an owner or an asset` });
}

/**
 * `/api/<game>/textures[/<part>]`. `part` is undefined for the states.
 * `datasetOf` checks the dataset of the query; it is asked only for a game with the service.
 */
export async function textureRoute(game: GameBackend, part: string | undefined, datasetOf: () => string, request: Request): Promise<void> {
  const service = game.textures;
  if (!service) throw new HttpError(404, { error: `${game.id} has no texture service` });
  const dataset = datasetOf();
  const { params, res } = request;
  if (part === undefined) {
    get(request);
    json(res, 200, service.states(dataset, params.getAll('asset')));
  } else if (part === 'owner') {
    get(request);
    json(res, 200, service.lookup(dataset, params.get('owner') ?? ''));
  } else if (part === 'judge') {
    const assets = (await body(request))['assets'];
    if (!Array.isArray(assets) || !assets.every((asset): asset is string => typeof asset === 'string')) throw new HttpError(400, { error: 'a judge body has "assets": a list of texture names' });
    json(res, 200, await service.judge(dataset, assets));
  } else if (part === 'request') {
    json(res, 200, await service.request(dataset, (await body(request)) as unknown as TextureRequestAsk));
  } else if (part === 'skin') {
    json(res, 200, await service.skin(dataset, (await body(request)) as unknown as SkinAsk));
  } else if (part === 'bake') {
    const ask = await body(request);
    ownerOrAsset(ask, 'bake');
    json(res, 200, await service.bake(dataset, ask as unknown as BakeAsk));
  } else if (part === 'unbake') {
    const ask = await body(request);
    ownerOrAsset(ask, 'unbake');
    json(res, 200, await service.unbake(dataset, ask as unknown as UnbakeAsk));
  } else if (part === 'file') {
    get(request);
    const asset = params.get('asset');
    const variant = params.get('variant');
    if (!asset || !variant) throw new HttpError(400, { error: 'asset and variant are required' });
    const full = service.file(dataset, asset, variant);
    if (!full) throw new HttpError(404, { error: 'no such variant file', asset, variant });
    // The URL carries the file's hash (v), so a new variant file has a new URL.
    sendFile(res, full, 'application/octet-stream', 'max-age=3600');
  } else {
    throw new HttpError(404, { error: 'not found' });
  }
}
