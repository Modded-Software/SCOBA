// Inspection used by the tests: scene state, framebuffer reads and pixel
// statistics, on window.sc2viewer. A format's own switches are its module's (formats/<id>).

import type { Feature } from '../../core/context';
import { createInspectFrame } from './frame';
import { createState } from './state';

export const inspectFeature: Feature = {
  id: 'inspect',
  install(context) {
    const frame = createInspectFrame(context);
    context.testApi.viewer({ state: createState(context), ...frame });
    context.testApi.app({ gridLines: frame.gridLines });
  },
};
