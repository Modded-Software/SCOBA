// The edit routes of SPEC-PHOTOCRAFT section 7, over a game's texture
// service. A game without one answers 404 on each (R-PC-28); while
// PhotoCraft is not installed each answers 503 with the reason (R-PC-13).

import { SCRATCH_NAME, SCRATCH_NAME_HEADER, type EditBody, type EditOpenAsk, type EditsBody } from '../../shared/edits';
import type { PhotocraftHealth } from '../../shared/protocol';
import { HttpError, type GameBackend } from './backend';
import { BodyError, json, sendFile, type Request } from './http';

function method(request: Request, wanted: string): void {
  if (request.method !== wanted) throw new HttpError(405, { error: 'method not allowed' });
}

/** The body of a request, as a JSON object. */
async function body(request: Request): Promise<Record<string, unknown>> {
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

/**
 * `/api/<game>/textures/edit[/<part>...]`: `rest` is the path after `edit`.
 * `datasetOf` checks the dataset of the query. The scratch and the pictures
 * take none: the editor's bridge asks for them by the session alone.
 * `install` reads the state of the PhotoCraft install.
 */
export async function editRoute(game: GameBackend, rest: readonly string[], datasetOf: () => string, install: () => Promise<PhotocraftHealth>, request: Request): Promise<void> {
  const edits = game.textures?.edits;
  if (!edits) throw new HttpError(404, { error: `${game.id} has no texture service` });
  const health = await install();
  if (!health.installed) throw new HttpError(503, { error: 'PhotoCraft is not installed', reason: health.reason ?? '' });
  const { res } = request;
  const [first, second, third, ...more] = rest;
  if (more.length > 0) throw new HttpError(404, { error: 'not found' });
  if (first === undefined) {
    method(request, 'GET');
    json(res, 200, { sessions: await edits.list(datasetOf()) } satisfies EditsBody);
  } else if (first === 'open' && second === undefined) {
    method(request, 'POST');
    const dataset = datasetOf();
    json(res, 200, { session: await edits.open(dataset, (await body(request)) as unknown as EditOpenAsk) } satisfies EditBody);
  } else if (second === undefined) {
    method(request, 'GET');
    json(res, 200, { session: await edits.one(datasetOf(), first) } satisfies EditBody);
  } else if (second === 'scratch' && third === undefined) {
    if (request.method === 'PUT') {
      json(res, 200, await edits.write(first, request));
      return;
    }
    method(request, 'GET');
    sendFile(res, await edits.scratch(first), 'application/octet-stream', 'no-store', { [SCRATCH_NAME_HEADER]: SCRATCH_NAME });
  } else if ((second === 'base' || second === 'rendered') && third !== undefined) {
    method(request, 'GET');
    // The URL carries the plane's pixel hash (v): a new picture has a new URL.
    sendFile(res, await edits.picture(first, second, third), 'image/png', 'max-age=3600');
  } else if (second === 'transfer' && third === undefined) {
    method(request, 'POST');
    json(res, 200, await edits.transfer(datasetOf(), first));
  } else if (second === 'discard' && third === undefined) {
    method(request, 'POST');
    json(res, 200, await edits.discard(datasetOf(), first));
  } else {
    throw new HttpError(404, { error: 'not found' });
  }
}
