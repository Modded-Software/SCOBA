// What the page needs from mdx-m3-viewer, in the shape of its UMD build:
// ModelViewer.viewer.ModelViewer and ModelViewer.viewer.handlers.
// Built from the source of the ref repo (ref/mdx-m3-viewer), where every
// change of ours is a commit; patches/ holds the same commits as files.
// The paths are literal on purpose: the bundler only follows static requires.
'use strict';

module.exports = {
  viewer: {
    ModelViewer: require('../ref/mdx-m3-viewer/src/viewer/viewer').default,
    handlers: {
      m3: require('../ref/mdx-m3-viewer/src/viewer/handlers/m3/handler').default,
      dds: require('../ref/mdx-m3-viewer/src/viewer/handlers/dds/handler').default,
      tga: require('../ref/mdx-m3-viewer/src/viewer/handlers/tga/handler').default,
    },
  },
  // The DDS parser alone, so tests can decode a texture file in the page.
  parsers: {
    dds: { Image: require('../ref/mdx-m3-viewer/src/parsers/dds/image').DdsImage },
  },
};
