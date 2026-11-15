"""pncprobe ray and look reports, and the point group checks (R-TPS-84)."""

from __future__ import annotations


def print_ray(data: dict) -> None:
    """Raw ray and look rows; see rayprobe.galaxy and lookprobe.galaxy."""
    raw = data.get("hover", {})
    print(f"ray: parkReady={raw.get('parkReady')} centred={raw.get('centred')} geom={raw.get('geom')} geom2={raw.get('geom2')}")
    for key in sorted(k for k in raw if k.startswith(("row", "far", "rest", "down", "after", "right", "end", "p0_", "p1_", "p2_", "p3_", "at"))):
        print(f"  {key}: {raw[key]}")


# Point probe (R-TPS-84): sweep tag -> the angle field of its rows. Rest (r)
# and aim (a); pitch sweeps at 3, 5, 8, 12 east, a yaw sweep at 5 east.
POINT_SWEEPS = tuple(f"{mode}{kind}_" for mode in ("r", "a") for kind in ("p0", "p1", "p2", "p3", "y"))
# Engine and script band centres agree within this, in degrees: about one
# sweep step plus the Zergling volume error (pncprobe 20261115-224549 fit).
POINT_CENTRE_TOLERANCE = 2.0
# Negative: no script pick this far outside the engine band, in degrees.
POINT_OUTSIDE = 4.0


def _point_rows(raw: dict, tag: str) -> list[tuple[float, int, int]]:
    rows = []
    for key in sorted(k for k in raw if k.startswith(tag) and k[len(tag):].isdigit()):
        f = str(raw[key]).split()
        angle = float(f[f.index("yaw" if tag.endswith("y_") else "pitch") + 1])
        if angle > 180.0:
            angle -= 360.0
        rows.append((angle, int(f[f.index("engine") + 1]), int(f[f.index("script") + 1])))
    return rows


def _band(rows, col: int):
    hit = [r[0] for r in rows if r[col]]
    return (min(hit), max(hit)) if hit else None


def check_point(raw: dict, checks) -> None:
    print(f"point: parkReady={raw.get('parkReady')} centred={raw.get('centred')} geom={raw.get('geom')} aimState={raw.get('aimState')}")
    checks.true("hover", "", "centred")
    # Nothing but the hero and the Zergling near the lane.
    print("point left: " + " ".join(str(raw.get(f"left{i}")) for i in range(1, 6)))
    checks.eq("hover", "", "leftCount", 0)
    # The start Medic (gt_MedicSpawn) exists and is parked far from the hero.
    print(f"point medic: seen={raw.get('medicSeen')} dist={raw.get('medicDist')}")
    checks.true("hover", "", "medicSeen")
    dist = raw.get("medicDist")
    verdict = "PASS" if dist is not None and dist >= 30 else "FAIL"
    print(f"point medicDist >= 30: got={dist} {verdict}")
    if verdict == "FAIL":
        checks.failures += 1
    for tag in POINT_SWEEPS:
        rows = _point_rows(raw, tag)
        engine, script = _band(rows, 1), _band(rows, 2)
        print(f"  {tag}: rows={len(rows)} engine={engine} script={script}")
        if engine is None or script is None:
            print(f"point {tag} both bands present: engine={engine} script={script} FAIL")
            checks.failures += 1
            continue
        gap = abs((engine[0] + engine[1]) / 2 - (script[0] + script[1]) / 2)
        verdict = "PASS" if gap <= POINT_CENTRE_TOLERANCE else "FAIL"
        print(f"point {tag} centre gap {gap:.1f} <= {POINT_CENTRE_TOLERANCE} {verdict}")
        if verdict == "FAIL":
            checks.failures += 1
        stray = [r[0] for r in rows if r[2] and (r[0] < engine[0] - POINT_OUTSIDE or r[0] > engine[1] + POINT_OUTSIDE)]
        verdict = "PASS" if not stray else "FAIL"
        print(f"point {tag} no script pick {POINT_OUTSIDE} outside the engine band: stray={stray} {verdict}")
        if stray:
            checks.failures += 1
