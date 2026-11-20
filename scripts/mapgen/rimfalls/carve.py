"""The basin at the foot of a rim fall.

    wall \\__ notch __/ basin \\__ foot

The basin is a bowl at the level of the wall's foot. Its uphill side cuts a
notch into the wall: the rock waterfall stands in it, raised terrain behind.
The ground is only ever lowered, and only within BASIN_RADIUS +
BASIN_BLEND of the basin centre.
"""

from __future__ import annotations

import math

import numpy as np

from flora.terrain import bilinear

from . import config
from .sites import Point, Site


def basin_centre(site: Site) -> Point:
    return (site.x + site.dir[0] * config.BASIN_AHEAD, site.y + site.dir[1] * config.BASIN_AHEAD)


def basin_edge(vz: np.ndarray, site: Site) -> float:
    """Level of the basin edge: the ground at its downhill side, before the cut."""
    cx, cy = basin_centre(site)
    return bilinear(vz, cx + site.dir[0] * config.BASIN_RADIUS, cy + site.dir[1] * config.BASIN_RADIUS)


def cut(vz: np.ndarray, site: Site, edge: float) -> np.ndarray:
    """The ground with this site's basin and notch cut in."""
    out = vz.copy()
    cx, cy = basin_centre(site)
    reach = config.BASIN_RADIUS + config.BASIN_BLEND
    h, w = vz.shape
    for y in range(max(0, math.floor(cy - reach)), min(h - 1, math.ceil(cy + reach)) + 1):
        for x in range(max(0, math.floor(cx - reach)), min(w - 1, math.ceil(cx + reach)) + 1):
            r = math.hypot(x - cx, y - cy)
            if r > reach:
                continue
            old = float(vz[y, x])
            if r <= config.BASIN_RADIUS:
                target = edge - config.BASIN_DEPTH * (1.0 - (r / config.BASIN_RADIUS) ** 2)
            else:
                t = (r - config.BASIN_RADIUS) / config.BASIN_BLEND
                target = edge + (old - edge) * (t * t * (3.0 - 2.0 * t))
            out[y, x] = min(old, target)
    return out
