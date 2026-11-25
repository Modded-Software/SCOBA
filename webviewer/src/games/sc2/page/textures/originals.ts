// The original textures a model file names, decoded for the texture window.
// The model's layers name them, the dataset serves them, and core's DDS
// decode (page/core/ddsdecode.ts) reads them. Each carries the pipeline's
// name of it, its asset: the path as the storage spells it, lower case with
// backslashes (scripts/hdtex/sc2/sources.py stored_name).

import type { GameContext } from '../../../../page/core/context';
import { decodeDdsBytes, fetchTexture } from '../../../../page/core/ddsdecode';
import { messageOf } from '../../../../page/core/dom';
import type { ShownTexture } from '../../../../page/core/texturewindow';
import { SC2 } from '../game';

/** What reading the originals needs: the model loader and the dataset routes. */
export type OriginalsDeps = Pick<GameContext, 'render' | 'api'>;

/** The pipeline's name of a texture path. */
export const assetOf = (source: string): string => source.replaceAll('/', '\\').toLowerCase();

/**
 * One texture file, decoded: its colour, and its alpha when that is not one
 * value all over. Fetched first, so a missing file says its status; then a
 * name that is not a ".dds" file is refused (a layer may name other files).
 */
async function decode({ api }: OriginalsDeps, source: string, dataset: string, urls: string[]): Promise<ShownTexture> {
  const response = await fetchTexture(String(api.pathSolver(dataset, SC2)(source)));
  if (!source.endsWith('.dds')) throw new Error('not a DDS file');
  const decoded = await decodeDdsBytes(await response.arrayBuffer(), source.split('\\').pop() ?? source, urls);
  return { ...decoded, asset: assetOf(source) };
}

/** Every texture a model file names, decoded; and the ones that failed, with why. */
export async function originals(deps: OriginalsDeps, file: string, dataset: string, urls: string[]): Promise<{ textures: ShownTexture[]; failed: string[] }> {
  const model = await deps.render.loadModel(deps.api.modelUrl(file, dataset, SC2), deps.api.pathSolver(dataset, SC2));
  if (!model) throw new Error(`cannot load ${file}`);
  return decodeAll(deps, model.textures, dataset, urls);
}

/** These texture files, decoded, in name order; and the ones that failed, with why. */
export async function decodeAll(deps: OriginalsDeps, named: readonly string[], dataset: string, urls: string[]): Promise<{ textures: ShownTexture[]; failed: string[] }> {
  const sources = new Set(named.map((source) => source.replaceAll('/', '\\')));
  const textures: ShownTexture[] = [];
  const failed: string[] = [];
  for (const source of [...sources].sort()) {
    await decode(deps, source, dataset, urls).then(
      (texture) => textures.push(texture),
      (error: unknown) => failed.push(`${source.split('\\').pop() ?? source} (${messageOf(error)})`),
    );
  }
  return { textures, failed };
}
