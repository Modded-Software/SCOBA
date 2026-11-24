// A DDS texture file, decoded in the page with the renderer's DDS reader,
// as PNG object URLs: its colour, and its alpha when that is not one value
// all over. The texture windows of the games use it.

import { make } from './dom';
import { DdsImage } from './library';

const DDS_FOURCC = 84; // byte offset of the pixel format's FourCC in a DDS file

/** One decoded texture. `planes` are object URLs the caller revokes (they are also in `urls`). */
export interface DecodedTexture {
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

/** Fetch a DDS file and decode its first level; `name` is how the texture is listed. */
export async function decodeDds(url: string, name: string, urls: string[]): Promise<DecodedTexture> {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${response.status}`);
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
  const planes: DecodedTexture['planes'] = [{ plane: 'color', image: await pngUrl(width, height, color, urls) }];
  if (!flat) planes.push({ plane: 'alpha', image: await pngUrl(width, height, alpha, urls) });
  return { texture: name, format: fourCC || 'uncompressed', size: [width, height], planes };
}
