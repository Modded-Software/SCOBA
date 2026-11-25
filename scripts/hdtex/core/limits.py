"""The limits a variant must keep, judged on the numbers measured when it was made.

A variant that misses one has a problem: it is kept, shown, and may be
named by a skin. A bake of it is refused unless it is accepted (R-HD-90).
"""

from __future__ import annotations

from typing import NotRequired, TypedDict


class Missed(TypedDict):
    """One limit a variant's numbers miss. A bound of None: the original's own seam has none."""

    limit: str
    value: float | None
    bound: float | None


class Band(Missed):
    """One limit that applies, with its band and, in the state, its info text."""

    band: str
    info: NotRequired[str]

# Loss of the encoding on the largest level, in dB.
MIN_ENCODE_PSNR = 35.0
# The result shrunk to the original's size must be the same picture. An
# inverted channel correlates below zero, a swapped one near zero.
MIN_CORRELATION = 0.7
# A channel this close to the original (shrunk result, dB) is proven by its
# error. Its correlation is noise: a nearly flat channel correlates with nothing.
FLAT_PSNR = 50.0
# Far view: a small mip of the result against the same mip of the original, in levels.
MAX_COARSE_RMSE = 1.5
# The step across the wrap-around edge, relative to the original's. Some originals have a seam of their own.
MAX_SEAM_GROWTH = 1.5


def lowest_correlation(numbers: dict) -> float:
    """The lowest correlation over the channels that carry a picture. 1.0 when none does."""
    pairs = zip(numbers["fidelity_corr"], numbers["fidelity_psnr"])
    values = [corr for corr, psnr in pairs if corr is not None and psnr < FLAT_PSNR]
    return min(values) if values else 1.0


def seam_bound(numbers: dict) -> float | None:
    """The largest seam the result may have. None: the original's own seam has no bound."""
    source = numbers["seam_source"]
    return None if source is None else max(1.0, source) * MAX_SEAM_GROWTH


def missed(numbers: dict, tiles: bool) -> list[Missed]:
    """Each limit the numbers miss, with the measured value and the bound. Empty: the result is sound.

    The seam limit is for a texture that tiles. A seam of None is one with
    no finite ratio: the inside of the picture is flat and its edges differ.
    """
    found: list[Missed] = []
    if min(numbers["encode_psnr"]) < MIN_ENCODE_PSNR:
        found.append(
            {
                "limit": "encode_psnr",
                "value": min(numbers["encode_psnr"]),
                "bound": MIN_ENCODE_PSNR,
            }
        )
    if lowest_correlation(numbers) < MIN_CORRELATION:
        found.append(
            {
                "limit": "correlation",
                "value": lowest_correlation(numbers),
                "bound": MIN_CORRELATION,
            }
        )
    if numbers["coarse_rmse"] > MAX_COARSE_RMSE:
        found.append(
            {
                "limit": "coarse_rmse",
                "value": numbers["coarse_rmse"],
                "bound": MAX_COARSE_RMSE,
            }
        )
    bound = seam_bound(numbers)
    if (
        tiles
        and bound is not None
        and (numbers["seam"] is None or numbers["seam"] > bound)
    ):
        found.append({"limit": "seam", "value": numbers["seam"], "bound": bound})
    return found


OK, NEAR, PROBLEM = "ok", "near", "problem"
NONE = "none"  # the band of a number no limit binds: a user-made variant's (R-PC-80)
# The near bands are the agent's (O-VIEW-7): a number this close to its bound shows amber.
NEAR_ENCODE_PSNR = 38.0
NEAR_CORRELATION = 0.8
NEAR_COARSE_RMSE = 1.2
NEAR_SEAM_GROWTH = 1.3
INFO = {
    "encode_psnr": "Loss of the compression on the largest level, in dB. Low: blocks and banding the upscale did not have.",
    "correlation": "The variant shrunk to the original's size, against the original, lowest channel. Low: another picture, a swapped or inverted channel.",
    "coarse_rmse": "A small mip of the variant against the same mip of the original, in levels. High: from far away it is brighter, darker or of another colour.",
    "seam": "The step across the wrap-around edge, against the original's. High: the tiled texture shows its edges as lines.",
}


def _band(value: float | None, bound: float, near: float, low_is_bad: bool) -> str:
    if value is None:
        return PROBLEM
    if (value < bound) if low_is_bad else (value > bound):
        return PROBLEM
    return NEAR if ((value < near) if low_is_bad else (value > near)) else OK


def unbound(found: list[Band]) -> list[Band]:
    """The same numbers with no band: those of a user-made variant, which no limit binds."""
    return [{**item, "band": NONE} for item in found]


def bands(numbers: dict, tiles: bool) -> list[Band]:
    """Every limit that applies, with the number, the bound, its band and its info text (R-VIEW-120)."""
    found: list[Band] = [
        {
            "limit": "encode_psnr",
            "value": min(numbers["encode_psnr"]),
            "bound": MIN_ENCODE_PSNR,
            "band": _band(
                min(numbers["encode_psnr"]), MIN_ENCODE_PSNR, NEAR_ENCODE_PSNR, True
            ),
        },
        {
            "limit": "correlation",
            "value": lowest_correlation(numbers),
            "bound": MIN_CORRELATION,
            "band": _band(
                lowest_correlation(numbers), MIN_CORRELATION, NEAR_CORRELATION, True
            ),
        },
        {
            "limit": "coarse_rmse",
            "value": numbers["coarse_rmse"],
            "bound": MAX_COARSE_RMSE,
            "band": _band(
                numbers["coarse_rmse"], MAX_COARSE_RMSE, NEAR_COARSE_RMSE, False
            ),
        },
    ]
    bound = seam_bound(numbers)
    if tiles and bound is not None:
        near = max(1.0, numbers["seam_source"]) * NEAR_SEAM_GROWTH
        found.append(
            {
                "limit": "seam",
                "value": numbers["seam"],
                "bound": bound,
                "band": _band(numbers["seam"], bound, near, False),
            }
        )
    return [{**item, "info": INFO[item["limit"]]} for item in found]
