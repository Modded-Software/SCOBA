// The layout of "add all": by size, smallest first, in small, medium and
// large clusters, each with its own cell size; on a map with units
// already, the block goes next to them.

import type { SceneService } from '../../core/context';
import type { GroundBox, Item, LayoutEntry } from '../../core/types';

const GAP = 0.5; // world units between neighbours
const CLUSTERS = 3; // small, medium, large

/** Bounding size on the ground: the diameter of the model's bounds, scaled as drawn. */
const size = (item: Item): number => 2 * item.model.bounds.r * Math.max(item.placement.scale[0], item.placement.scale[1]) * item.scale;

/** Ground box of items, each a square of its size around its centre; null for none. */
function footprint(list: readonly Item[]): GroundBox | null {
  if (!list.length) return null;
  const box = { x0: Infinity, x1: -Infinity, y0: Infinity, y1: -Infinity };
  for (const item of list) {
    const h = size(item) / 2;
    box.x0 = Math.min(box.x0, item.x - h);
    box.x1 = Math.max(box.x1, item.x + h);
    box.y0 = Math.min(box.y0, item.y - h);
    box.y1 = Math.max(box.y1, item.y + h);
  }
  return box;
}

/**
 * Split sizes (ascending) into up to CLUSTERS runs of the sorted list, so
 * smallest first still holds across clusters. The splits are the ones
 * with the least ground area: sum over clusters of count x cell squared,
 * the cell being the cluster's largest size plus GAP. An outlier then
 * gets a cluster of its own instead of setting everyone's cell.
 * Returns the index where each cluster starts.
 */
function clusterStarts(sizes: readonly number[]): number[] {
  const n = sizes.length;
  if (!n) return [];
  // Area of the cluster holding sizes[i .. j-1].
  const area = (i: number, j: number): number => (j - i) * ((sizes[j - 1] ?? 0) + GAP) ** 2;
  let best = { cost: area(0, n), starts: [0] };
  for (let a = 1; a < n; a++) {
    const two = area(0, a) + area(a, n);
    if (two < best.cost) best = { cost: two, starts: [0, a] };
    if (CLUSTERS < 3) continue;
    for (let b = a + 1; b < n; b++) {
      const three = area(0, a) + area(a, b) + area(b, n);
      if (three < best.cost) best = { cost: three, starts: [0, a, b] };
    }
  }
  return best.starts;
}

/**
 * Smallest first, in size clusters (small, medium, large). Each cluster is
 * a near-square grid of equal cells, the cell its largest size plus GAP,
 * so an outlier sets the cells of its own cluster only. The clusters stand
 * side by side, small to large, top edges aligned. On an empty scene the
 * block is centred on the origin. With units already there (`others`) it
 * goes next to them, GAP away: below them when their footprint is wider
 * than deep, else to the right, so repeated runs stay together.
 */
export function arrange(scene: Pick<SceneService, 'setPosition'>, list: readonly Item[], others: readonly Item[] = []): LayoutEntry[] {
  const sorted = [...list].sort((a, b) => size(a) - size(b));
  const starts = clusterStarts(sorted.map(size));
  const clusters = starts.map((start, k) => {
    const members = sorted.slice(start, starts[k + 1] ?? sorted.length);
    const largest = members[members.length - 1];
    const cell = (largest ? size(largest) : 0) + GAP;
    const cols = Math.ceil(Math.sqrt(members.length));
    return { members, cell, cols, width: cols * cell, depth: Math.ceil(members.length / cols) * cell };
  });
  const depth = Math.max(0, ...clusters.map((c) => c.depth));
  const blockWidth = clusters.reduce((sum, c) => sum + c.width, 0);
  // Where the block's centre goes.
  let cx = 0;
  let cy = 0;
  const near = footprint(others);
  if (near) {
    if (near.x1 - near.x0 >= near.y1 - near.y0) {
      cx = (near.x0 + near.x1) / 2;
      cy = near.y0 - GAP - depth / 2;
    } else {
      cx = near.x1 + GAP + blockWidth / 2;
      cy = (near.y0 + near.y1) / 2;
    }
  }
  const top = cy + depth / 2;
  let left = cx - blockWidth / 2;
  const layout: LayoutEntry[] = [];
  clusters.forEach((c, k) => {
    c.members.forEach((item, i) => {
      const col = i % c.cols;
      const row = Math.floor(i / c.cols);
      scene.setPosition(item, left + (col + 0.5) * c.cell, top - (row + 0.5) * c.cell);
      layout.push({ id: item.id, size: size(item), x: item.x, y: item.y, cluster: k, cell: c.cell });
    });
    left += c.width;
  });
  return layout;
}
