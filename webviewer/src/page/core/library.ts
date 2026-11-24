// The renderer library (ref/mdx-m3-viewer), as the page core uses it.
// Only page/core and the formats import the library (SPEC-VIEWER section 3).
// Format classes are not named here: they belong to their format module
// (src/formats/<id>), and core reaches them through core/plugin.ts.

import ModelViewer from '@renderer/viewer/viewer';
import Texture from '@renderer/viewer/texture';
import { DdsImage } from '@renderer/parsers/dds/image';

export { ModelViewer, DdsImage, Texture };
export type { default as Scene } from '@renderer/viewer/scene';
