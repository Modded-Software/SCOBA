// The original textures a model file names, decoded for the texture window.
// The model's layers name them, the dataset serves them, and core's DDS
// decode (page/core/ddsdecode.ts) reads them.

import type { GameContext } from '../../../../page/core/context';
import { decodeDds, type DecodedTexture } from '../../../../page/core/ddsdecode';
import { messageOf } from '../../../../page/core/dom';
import { SC2 } from '../game';

/** What reading the originals needs: the model loader and the dataset routes. */
export type OriginalsDeps = Pick<GameContext, 'render' | 'api'>;

/** One decoded texture, as the texture viewer page takes it. */
export type Original = DecodedTexture;

/** One texture file, decoded: its colour, and its alpha when that is not one value all over. */
function decode({ api }: OriginalsDeps, source: string, dataset: string, urls: string[]): Promise<Original> {
  if (!source.endsWith('.dds')) return Promise.reject(new Error('not a DDS file'));
  return decodeDds(String(api.pathSolver(dataset, SC2)(source)), source.split('\\').pop() ?? source, urls);
}

/** Every texture a model file names, decoded; and the ones that failed, with why. */
export async function originals(deps: OriginalsDeps, file: string, dataset: string, urls: string[]): Promise<{ textures: Original[]; failed: string[] }> {
  const model = await deps.render.loadModel(deps.api.modelUrl(file, dataset, SC2), deps.api.pathSolver(dataset, SC2));
  if (!model) throw new Error(`cannot load ${file}`);
  const sources = new Set(model.textures.map((source) => source.replaceAll('/', '\\')));
  const textures: Original[] = [];
  const failed: string[] = [];
  for (const source of [...sources].sort()) {
    await decode(deps, source, dataset, urls).then(
      (texture) => textures.push(texture),
      (error: unknown) => failed.push(`${source.split('\\').pop() ?? source} (${messageOf(error)})`),
    );
  }
  return { textures, failed };
}
