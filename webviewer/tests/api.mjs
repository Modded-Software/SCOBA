// The server's routes (SPEC-VIEWER section 8), for the tests. The game is
// SC2; a route that reads a dataset reads "scoba" unless told otherwise.

const GAME = 'sc2';
export const DATASET = 'scoba';

/** A query as URL parameters: an object, or a ready "a=1&b=2" text. */
const params = (base, query) => {
  const out = new URLSearchParams(base);
  for (const [key, value] of new URLSearchParams(typeof query === 'string' ? query : query ?? {})) out.append(key, value);
  return out;
};

export const api = {
  health: '/api/health',
  games: '/api/games',
  datasets: `/api/${GAME}/datasets`,
  reload: (id) => `/api/${GAME}/datasets/${id}/reload`,
  categories: (dataset = DATASET) => `/api/${GAME}/categories?${params({ dataset })}`,
  summary: (dataset = DATASET) => `/api/${GAME}/summary?${params({ dataset })}`,
  records: (category, query = {}, dataset = DATASET) => `/api/${GAME}/records/${category}?${params({ dataset }, query)}`,
  record: (category, id, dataset = DATASET) => `/api/${GAME}/record/${category}?${params({ dataset, id })}`,
  file: (path, dataset = DATASET) => `/api/${GAME}/file?${params({ dataset, path })}`,
  asset: (ref, dataset = DATASET, kind = 'texture') => `/api/${GAME}/asset?${params({ dataset, kind, ref })}`,
  icon: (name, dataset = DATASET) => `/api/${GAME}/icon/${name}?${params({ dataset })}`,
  backdrops: (query = {}) => `/api/${GAME}/backdrops?${params({}, query)}`,
  x: (name) => `/api/${GAME}/x/${name}`,
};

/** What the gallery filters offer, out of the categories: the shape /api/facets had. */
export async function facets(request, dataset = DATASET) {
  const categories = await (await request.get(api.categories(dataset))).json();
  const values = (category, filter) => categories.find((c) => c.id === category).filters.find((f) => f.id === filter).values.map((v) => v.value);
  return { races: values('units', 'race'), kinds: values('units', 'kind'), families: values('units', 'family'), doodadTypes: values('doodads', 'type'), tilesets: values('doodads', 'tileset') };
}
