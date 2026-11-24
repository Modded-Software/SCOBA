// The original textures a model file names, decoded for the texture window.
// The model's layers name them, the dataset serves them, and the
// renderer's DDS reader decodes them.

import type { GameContext } from '../../../../page/core/context';

/** What reading the originals needs: the model loader and the dataset routes. */
export type OriginalsDeps = Pick<GameContext, 'render' | 'api'>;
import { make, messageOf } from '../../../../page/core/dom';
import { DdsImage } from '../../../../page/core/library';
import { SC2 } from '../game';

const DDS_FOURCC = 84; // byte offset of the pixel format's FourCC in a DDS file

/** One decoded texture, as the texture viewer page takes it. */
export interface Original {
  texture: string;
  format: string;
  size: [number, number];
  planes: { plane: 'color' | 'alpha'; image: string }[];
}

/** RGBA pixels as a PNG object URL, kept in `urls` so the caller can revoke it. */
function pngUrl(width: number, height: number, rgba: Uint8ClampedArray<ArrayBuffer>, urls: string[]): Promise<string> {
  const canvas = make('canvas', { width, height });
  const context = canvas.getContext('2d');
  if (!context) return Promise.reject(new Error('no 2d canvas'));
  context.putImageData(new ImageData(rgba, width, height), 0, 0);
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (!blob) {
        reject(new Error(`cannot encode ${width}x${height}`));
        return;
      }
      const url = URL.createObjectURL(blob);
      urls.push(url);
      resolve(url);
    }, 'image/png');
  });
}

/** One texture file, decoded: its colour, and its alpha when that is not one value all over. */
async function decode({ api }: OriginalsDeps, source: string, dataset: string, urls: string[]): Promise<Original> {
  const response = await fetch(String(api.pathSolver(dataset, SC2)(source)));
  if (!response.ok) throw new Error(`${response.status}`);
  if (!source.endsWith('.dds')) throw new Error('not a DDS file');
  const bytes = await response.arrayBuffer();
  const image = new DdsImage();
  image.load(bytes);
  const { width, height, data } = image.getMipmap(0);
  const fourCC = String.fromCharCode(...new Uint8Array(bytes, DDS_FOURCC, 4)).replace(/\0+$/, '');
  const color = new Uint8ClampedArray(data);
  const alpha = new Uint8ClampedArray(data.length);
  const first = data[3];
  let flat = true;
  for (let i = 0; i < data.length; i += 4) {
    const a = data[i + 3] ?? 0;
    if (a !== first) flat = false;
    alpha.set([a, a, a, 255], i);
    color[i + 3] = 255;
  }
  const planes: Original['planes'] = [{ plane: 'color', image: await pngUrl(width, height, color, urls) }];
  if (!flat) planes.push({ plane: 'alpha', image: await pngUrl(width, height, alpha, urls) });
  return { texture: source.split('\\').pop() ?? source, format: fourCC || 'uncompressed', size: [width, height], planes };
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
