"""Plan every water feature of a map: the new ground and the doodads. No file access.

Order, per site set:
1. falls from the pipe mouths (they fix where water lands);
2. ground: a basin under every landing point; then the pool is found and
   everything else gets its rim;
3. every change fades into the old ground; then the rim is restored and
   the ground under every pipe mouth is freed;
4. rocks in the pool, on that ground.
`problems` then measures the result. The build fails on any problem.
"""

from __future__ import annotations

import math
import random
from typing import NamedTuple

import numpy as np

from flora.terrain import bilinear

from . import carve, compose, config
from .compose import Placement
from .models import Models, overlap_share
from .sites import Site, levels


class Plan(NamedTuple):
    ground: np.ndarray  # new vertex z
    placements: list[Placement]
    pools: list[np.ndarray]  # wet vertices per site
    levels: dict[str, float]
    sites: list[Site]
    rocks: tuple[compose.RockPlacement, ...] = ()  # standing in the pools


def make(old: np.ndarray, sites: list[Site], models: Models, seed: int = config.SEED) -> Plan:
    rng = random.Random(seed)
    level = levels(sites)
    vz = old.copy()
    common = compose.common_facing(sites)
    falls = [compose.pipe_falls(i, site, level[site.water], models, rng, common) for i, site in enumerate(sites)]
    pools = []
    keep = np.zeros(old.shape, dtype=bool)
    for i, site in enumerate(sites):
        seeds = [compose.landing(models, p) for p in falls[i]]
        vz = carve.basin(vz, site.rect, seeds, level[site.water])
        wet = carve.pool(vz, site.rect, seeds, level[site.water])
        vz = carve.rim(vz, site.rect, wet, level[site.water])
        pools.append(wet)
        keep |= wet
    vz = carve.feather(old, vz, keep)
    # The fade must not undo a rim or a freed mouth.
    for i, site in enumerate(sites):
        vz = carve.rim(vz, site.rect, pools[i], level[site.water])
        vz = carve.free_mouths(vz, site.mouths)
    # Rocks last, on the final ground. Their own chance: the falls do not change with them.
    rock_rng = random.Random(f"{seed}:rocks")
    rocks = []
    for i, site in enumerate(sites):
        landings = [compose.landing(models, p) for p in falls[i]]
        rocks += compose.pool_rocks(i, vz, pools[i], level[site.water], landings, models, rock_rng)
    return Plan(vz, [p for group in falls for p in group], pools, level, sites, tuple(rocks))


def problems(old: np.ndarray, plan: Plan, models: Models) -> list[str]:
    """Everything that would make a feature look wrong, measured on the plan."""
    out: list[str] = []
    vz = plan.ground
    moved = float(np.abs(vz - old).max())
    if moved > config.MAX_CHANGE:
        out.append(f"ground moved {moved:.2f}, limit {config.MAX_CHANGE}")
    for i, site in enumerate(plan.sites):
        level = plan.levels[site.water]
        mine = [p for p in plan.placements if p.site == i]
        tag = f"site {i} {site.rect}"
        if not mine:
            out.append(f"{tag}: no fall")
        widths = {}
        for m_index, mouth in enumerate(site.mouths):
            fed = [p for p in mine if p.mouth == m_index]
            if not fed:
                out.append(f"{tag}: pipe mouth {m_index} has no fall")
            else:
                # Operator 2026-11-20: not a thin thread, not copies.
                each = [compose.model_of(models, p).width * p.flat for p in fed]
                widths[m_index] = max(each)
                if len(fed) < 2 or sum(each) < 2 * mouth.radius:
                    out.append(f"{tag}: pipe mouth {m_index} has a thin stream ({len(fed)} falls, {sum(each):.2f} wide, opening {2 * mouth.radius:.2f})")
                if len({(round(p.scale, 3), round(p.flat, 3)) for p in fed}) != len(fed):
                    out.append(f"{tag}: pipe mouth {m_index} has two falls of one size")
                # Operator 2026-11-20: no fall reaches past the side of its pipe.
                for p in fed:
                    reach = compose.side_reach(models, p, site)
                    if reach > mouth.radius + config.SIDE_TOLERANCE:
                        out.append(f"{tag}: a fall of pipe mouth {m_index} reaches {reach:.2f} to the side, pipe radius {mouth.radius:.2f}")
            under = vz[carve.mouth_mask(vz.shape, mouth)]
            if under.size and float(under.max()) > mouth.lip_z - config.PIPE_CLEAR + 1e-6:
                out.append(f"{tag}: ground reaches pipe mouth {m_index} ({under.max():.2f} against lip {mouth.lip_z:.2f})")
        # Operator 2026-11-20: the bigger pipe has the bigger fall.
        for a in widths:
            for b in widths:
                if site.mouths[a].radius > site.mouths[b].radius and widths[a] <= widths[b]:
                    out.append(f"{tag}: pipe mouth {a} is bigger than {b} but its falls are not ({widths[a]:.2f} against {widths[b]:.2f})")
        for p in mine:
            name = f"{tag}: {p.kind} {p.variation} at {p.x:.1f},{p.y:.1f}"
            # The fall's water line stands FALL_RAISE over the pool.
            over = compose.surface_z(models, p) - level
            if abs(over - config.FALL_RAISE) > 1e-6:
                out.append(f"{name}: base at {compose.surface_z(models, p):.2f}, water at {level:.2f}, wanted {config.FALL_RAISE} over it")
            q = compose.landing(models, p)
            wet = level - bilinear(vz, q[0], q[1])
            if wet < config.WET_MIN:
                out.append(f"{name}: water lands on dry ground at {q[0]:.1f},{q[1]:.1f} (depth {wet:.2f})")
            if not plan.pools[i][int(round(q[1])), int(round(q[0]))]:
                out.append(f"{name}: water lands outside the pool at {q[0]:.1f},{q[1]:.1f}")
            # The top is near the bottom of the opening: FALL_TOP +- its jitter up from the lip, plus the raise.
            mouth = site.mouths[p.mouth]
            top = compose.top_z(models, p)
            low = mouth.lip_z + (config.FALL_TOP - config.FALL_TOP_JITTER) * 2 * mouth.radius + config.FALL_RAISE - config.TOP_TOLERANCE
            high = mouth.lip_z + (config.FALL_TOP + config.FALL_TOP_JITTER) * 2 * mouth.radius + config.FALL_RAISE + config.TOP_TOLERANCE
            if not low <= top <= high:
                out.append(f"{name}: top at {top:.2f}, wanted {low:.2f} to {high:.2f} (pipe lip {mouth.lip_z:.2f})")
        for a_index, a in enumerate(mine):
            for b in mine[a_index + 1 :]:
                share = overlap_share(compose.outline(models, a), compose.outline(models, b))
                if share > config.FALL_OVERLAP_LIMIT:
                    out.append(f"{tag}: {a.kind} {a.variation} and {b.kind} {b.variation} overlap {share:.0%}")
        # The water sheet ends on a shore: nothing wet but the pool.
        zone = carve.inside(vz.shape, site.rect, config.SHORE_MARGIN)
        stray = zone & ~plan.pools[i] & (vz < level + config.RIM - 1e-6)
        if stray.any():
            out.append(f"{tag}: {int(stray.sum())} vertices outside the pool are below the rim")
        if not plan.pools[i].any():
            out.append(f"{tag}: no pool")
        out += rock_problems(plan, models, i, tag)
    return out


def rock_problems(plan: Plan, models: Models, i: int, tag: str) -> list[str]:
    """Rocks of one pool: in the water, on the floor, clear of the falls, apart, not alike."""
    out: list[str] = []
    if not models.rocks.get(config.ROCK_TYPE):
        return out  # no rock model measured: no rocks are planned
    vz, level = plan.ground, plan.levels[plan.sites[i].water]
    rocks = [r for r in plan.rocks if r.site == i]
    if not rocks:
        out.append(f"{tag}: no rock in the pool")
    landings = [compose.landing(models, p) for p in plan.placements if p.site == i]
    for k, r in enumerate(rocks):
        name = f"{tag}: rock {r.variation} at {r.x:.1f},{r.y:.1f}"
        floor = bilinear(vz, r.x, r.y)
        if not plan.pools[i][int(round(r.y)), int(round(r.x))]:
            out.append(f"{name}: outside the pool")
        elif level - floor < config.ROCK_MIN_DEPTH - 1e-6:
            out.append(f"{name}: in water {level - floor:.2f} deep, wanted {config.ROCK_MIN_DEPTH}")
        shape = models.rocks[r.kind][r.variation]
        if not -0.01 <= r.z - floor <= config.ROCK_LIFT * -shape.lo[2] * r.scale + 0.01:
            out.append(f"{name}: origin at {r.z:.2f}, pool floor at {floor:.2f}: buried or floating")
        top = r.z + shape.hi[2] * r.scale
        if top < level + config.ROCK_ABOVE[0] - 1e-6:
            out.append(f"{name}: top at {top:.2f}, under the water at {level:.2f} + {config.ROCK_ABOVE[0]}")
        if not config.ROCK_SCALE[0] <= r.scale <= config.ROCK_SCALE[1]:
            out.append(f"{name}: scale {r.scale:.2f} outside {config.ROCK_SCALE}")
        near = min((math.hypot(r.x - q[0], r.y - q[1]) for q in landings), default=math.inf)
        if near < config.ROCK_FALL_CLEAR - 1e-6:
            out.append(f"{name}: {near:.2f} from where a fall lands, wanted {config.ROCK_FALL_CLEAR}")
        for other in rocks[k + 1 :]:
            gap = math.hypot(r.x - other.x, r.y - other.y)
            if gap < config.ROCK_SPACING - 1e-6:
                out.append(f"{name}: {gap:.2f} from the rock at {other.x:.1f},{other.y:.1f}, wanted {config.ROCK_SPACING}")
            if other.variation == r.variation:
                out.append(f"{name}: the rock at {other.x:.1f},{other.y:.1f} is the same variation")
    return out
