// The routes of SPEC-VIEWER section 8, over the registered games. The
// route is read from the raw path, so an encoded ".." never reaches a
// real route.

import { ASSET_KINDS, ID_RULE, LIMIT, type AssetKind, type GamesBody, type HealthBody } from '../../shared/protocol';
import { HttpError, type GameBackend, type ListQuery } from './backend';
import { intParam, json, sendFile, type Request, type Route } from './http';

/** Query parameters that are not filters. */
const NOT_FILTERS = new Set(['dataset', 'q', 'offset', 'limit', 'v']);

function listQuery(params: URLSearchParams): ListQuery {
  const filters: Record<string, string> = {};
  for (const [key, value] of params) if (!NOT_FILTERS.has(key)) filters[key] = value;
  return {
    q: params.get('q') ?? '',
    offset: intParam(params, 'offset', 0, 0, Number.MAX_SAFE_INTEGER),
    limit: intParam(params, 'limit', LIMIT.standard, 1, LIMIT.max),
    filters,
  };
}

/** A required query parameter. */
function required(params: URLSearchParams, name: string): string {
  const value = params.get(name);
  if (!value) throw new HttpError(400, { error: `${name} is required` });
  return value;
}

/** The dataset a request names; required, and known to the game. */
function datasetOf(game: GameBackend, params: URLSearchParams): string {
  const dataset = required(params, 'dataset');
  if (!game.hasDataset(dataset)) throw new HttpError(404, { error: 'no such dataset', dataset });
  return dataset;
}

/** A category id out of the path, by the id rule. */
function categoryOf(part: string | undefined): string {
  if (part === undefined || !ID_RULE.test(part)) throw new HttpError(404, { error: 'no such category', category: part ?? '' });
  return part;
}

const isKind = (value: string): value is AssetKind => ASSET_KINDS.some((kind) => kind === value);

function method(request: Request, wanted: string): void {
  if (request.method !== wanted) throw new HttpError(405, { error: 'method not allowed' });
}

/** One game's routes: `rest` is the path after /api/<game>/, split at "/". */
async function gameRoute(game: GameBackend, rest: readonly string[], request: Request): Promise<void> {
  const { params, res } = request;
  const [first, second, third, ...more] = rest;
  if (first === 'x' && second !== undefined) {
    const extension = game.extensions[second];
    if (!extension) throw new HttpError(404, { error: 'not found' });
    // The extension sees the path after /x/<name>: '' for the name alone, '/...' below it.
    const tail = rest.length > 2 ? `/${rest.slice(2).join('/')}` : '';
    if (!(await extension({ ...request, route: tail }))) throw new HttpError(404, { error: 'not found' });
    return;
  }
  if (first === 'datasets' && second !== undefined && third === 'reload' && more.length === 0) {
    method(request, 'POST');
    if (!game.hasDataset(second)) throw new HttpError(404, { error: 'no such dataset', dataset: second });
    json(res, 200, await game.reload(second));
    return;
  }
  method(request, 'GET');
  const one = more.length === 0 && third === undefined;
  if (first === 'datasets' && second === undefined) {
    json(res, 200, await game.datasets());
  } else if (first === 'categories' && second === undefined) {
    json(res, 200, game.categories(datasetOf(game, params)));
  } else if (first === 'summary' && second === undefined) {
    json(res, 200, game.summary(datasetOf(game, params)));
  } else if (first === 'records' && one) {
    const category = categoryOf(second);
    json(res, 200, game.list(datasetOf(game, params), category, listQuery(params)));
  } else if (first === 'record' && one) {
    const category = categoryOf(second);
    const dataset = datasetOf(game, params);
    json(res, 200, game.record(dataset, category, required(params, 'id')));
  } else if (first === 'file' && second === undefined) {
    const dataset = datasetOf(game, params);
    const path = required(params, 'path');
    const full = await game.file(dataset, path);
    if (!full) throw new HttpError(404, { error: 'not found', path, dataset });
    sendFile(res, full, 'application/octet-stream', 'max-age=3600');
  } else if (first === 'asset' && second === undefined) {
    const dataset = datasetOf(game, params);
    const kind = required(params, 'kind');
    if (!isKind(kind)) throw new HttpError(400, { error: `kind is one of ${ASSET_KINDS.join(', ')}`, kind });
    const ref = required(params, 'ref');
    const full = await game.asset(dataset, kind, ref);
    if (!full) throw new HttpError(404, { error: 'not found', ref, dataset });
    sendFile(res, full, 'application/octet-stream', 'max-age=3600');
  } else if (first === 'icon' && one && second !== undefined) {
    const dataset = datasetOf(game, params);
    const full = game.icon(dataset, second);
    if (!full) throw new HttpError(404, { error: 'not found' });
    sendFile(res, full, 'image/png', 'max-age=3600');
  } else if (first === 'backdrops' && second === undefined) {
    json(res, 200, game.backdrops(listQuery(params)));
  } else {
    throw new HttpError(404, { error: 'not found' });
  }
}

/** The protocol's routes over `games`; the first game is the default one. */
export function protocol(games: readonly GameBackend[]): Route {
  const byId = new Map(games.map((game) => [game.id, game]));
  const first = games[0];
  if (!first) throw new Error('no game registered');
  return async (request) => {
    const { route, res } = request;
    if (route !== '/api' && !route.startsWith('/api/')) return false;
    try {
      const parts = route.split('/').slice(2);
      const [head, ...rest] = parts;
      if (head === 'health' && rest.length === 0) {
        method(request, 'GET');
        const body: HealthBody = { games: games.map((g) => ({ id: g.id, available: true })) };
        json(res, 200, body);
        return true;
      }
      if (head === 'games' && rest.length === 0) {
        method(request, 'GET');
        const body: GamesBody = { default: first.id, games: games.map((g) => ({ id: g.id, label: g.label, tab: g.tab, available: true, reason: null })) };
        json(res, 200, body);
        return true;
      }
      const game = head !== undefined && ID_RULE.test(head) ? byId.get(head) : undefined;
      if (!game) throw new HttpError(404, { error: 'no such game', game: head ?? '' });
      await gameRoute(game, rest, request);
    } catch (error) {
      if (!(error instanceof HttpError)) throw error;
      json(res, error.status, error.body);
    }
    return true;
  };
}
