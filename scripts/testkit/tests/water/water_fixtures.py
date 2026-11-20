"""Fixtures of the water feature host tests: the synthetic map, its objects and helpers."""

from __future__ import annotations
import math
import struct
import xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
from flora.dirt import DIRT_NAME
from flora.hazard_paint import write_layer
from flora.terrain import bilinear
from mapgen.waterfeatures import ground, models as models_mod, plan as planner, sites as site_finder
from mapgen.waterfeatures.sites import Mouth

MODELS = models_mod.load()
N = 129  # vertices per side of the synthetic map
SCALE = 0.001  # quantizeScale of the synthetic map
UNIT_AT = (100.0, 100.0)
RECTS = [("Albion", (48.0, 64.0, 64.0, 80.0)), ("Albion", (72.0, 40.0, 88.0, 56.0)), ("BelShir", (8.0, 8.0, 24.0, 16.0)), ("Albion", (8.0, 100.0, 16.0, 108.0))]


def hills() -> np.ndarray:
    """Ground of the synthetic map: z 10 with low hills, so banks and shores exist."""
    ys, xs = np.mgrid[0:N, 0:N]
    return 10.0 + 0.8 * np.sin(xs / 9.0) * np.cos(ys / 7.0)


def unit_xml(kind: str = "PsiDecimator", scale: str = "1,1,1", rotation: str = "") -> str:
    return f'    <ObjectUnit Id="5" Position="{UNIT_AT[0]},{UNIT_AT[1]},0"{rotation} Scale="{scale}" UnitType="{kind}" Player="7"/>\r\n'


def mouths_of(vz: np.ndarray, xml: str | None = None, pending: dict | None = None) -> list[Mouth]:
    pending = {"PsiDecimator": 2.0} if pending is None else pending
    return site_finder.pipe_mouths(xml or unit_xml(), MODELS, lambda x, y: bilinear(vz, x, y), pending)


def planned(vz: np.ndarray | None = None) -> tuple[np.ndarray, planner.Plan]:
    vz = hills() if vz is None else vz
    return vz, planner.make(vz, site_finder.find(RECTS, mouths_of(vz)), MODELS)


def cylinder(start: tuple[float, float, float], end: tuple[float, float, float], radius: float, rings: int = 30) -> np.ndarray:
    """Points on a tube from start to end."""
    a, b = np.array(start), np.array(end)
    axis = (b - a) / np.linalg.norm(b - a)
    side = np.cross(axis, (0.0, 0.0, 1.0)) if abs(axis[2]) < 0.9 else np.cross(axis, (1.0, 0.0, 0.0))
    side /= np.linalg.norm(side)
    up = np.cross(side, axis)
    out = []
    for k in range(rings + 1):
        centre = a + (b - a) * k / rings
        out += [centre + radius * (math.cos(t) * side + math.sin(t) * up) for t in np.linspace(0, math.tau, 12, endpoint=False)]
    return np.array(out)


OBJECTS_HEAD = '<?xml version="1.0" encoding="utf-8"?>\r\n<PlacedObjects Version="27">\r\n'
OBJECTS_TAIL = "</PlacedObjects>\r\n"
ABSOLUTE = '        <Flag Index="HeightAbsolute" Value="1"/>\r\n'


def doodad(oid: int, kind: str, x: float, y: float, z: float, flags: str = ABSOLUTE) -> str:
    return f'    <ObjectDoodad Id="{oid}" Position="{x},{y},{z}" Rotation="1" Scale="2,2,2" Type="{kind}">\r\n{flags}    </ObjectDoodad>\r\n'


# The water catalog of the synthetic map; WaterHeightTest adds entries at {more}.
WATER_BASE = '<Catalog>\r\n    <CWater id="BelShir">\r\n        <State index="0" Height="7.150000" Specularity="56.5"/>\r\n    </CWater>\r\n{more}</Catalog>\r\n'


def water_heights(text: str) -> dict[str, float]:
    """Water type -> height of its first state, from a water catalog text."""
    out = {}
    for el in ET.fromstring(text):
        state = el.find("State")
        if state is not None:
            out[el.get("id")] = float(state.get("Height") or state.find("Height").get("value"))
    return out


MASK = 256  # texture mask cells per side of the synthetic map: 2 per map cell
GRASS_SLOT, DIRT_SLOT = 4, 5
LANE = 6  # dirt weight the synthetic map holds everywhere before the step
PALETTE = {GRASS_SLOT: "Zerus3", DIRT_SLOT: DIRT_NAME}


def write_map(folder: Path, vz: np.ndarray, unit: str) -> Path:
    """A synthetic built map: what apply_water_features reads and writes."""
    folder.mkdir(parents=True)
    records = np.zeros((N, N, 3), dtype="<u2")
    records[..., 0] = np.rint(vz / SCALE).astype("<u2")
    (folder / "t3HeightMap").write_bytes(struct.pack("<4sIII", b"HMAP", 101, N, N) + bytes(16) + records.tobytes())
    palette = "".join(f'<texture i="{i}" name="{name}"/>' for i, name in PALETTE.items())
    (folder / "t3Terrain.xml").write_text(
        f'<terrain><textureList num="8">{palette}</textureList><vertData quantizeBias="1" quantizeScale="{SCALE}" standardHeight="8" name="t3HeightMap"/></terrain>\n',
        encoding="utf-8",
    )
    # Texture masks: grass everywhere, weak lane dirt everywhere, nothing else.
    (folder / "t3TextureMasks").write_bytes(struct.pack("<4sIIII", b"MASK", 102, 0, MASK, MASK) + bytes(44) + bytes(8 * MASK * MASK // 2))
    write_layer(folder / "t3TextureMasks", GRASS_SLOT, np.full((MASK, MASK), 15, dtype=np.uint8))
    dirt = np.zeros((MASK, MASK), dtype=np.uint8)
    dirt[:, :] = LANE
    write_layer(folder / "t3TextureMasks", DIRT_SLOT, dirt)
    water = bytearray(b"WATR" + struct.pack("<II", 110, len(RECTS)) + bytes(20))
    for name, rect in RECTS:
        water += name.encode().ljust(8, b"\0") + bytes(32) + struct.pack("<4f", *rect)
    (folder / "t3Water").write_bytes(bytes(water))
    game = folder / "Base.SC2Data" / "GameData"
    game.mkdir(parents=True)
    (game / "WaterData.xml").write_bytes(WATER_BASE.format(more="").encode("utf-8"))
    (folder / "CellAttribute_Pnp").write_bytes(struct.pack("<I", (N - 1) * (N - 1) * 8) + bytes((N - 1) * (N - 1)))
    (folder / "Preload.xml").write_bytes(b"<Preload>\r\n</Preload>\r\n")
    (folder / "t3CellFlags").write_bytes(bytes(32) + bytes([1]) * ((N - 1) * (N - 1)))  # flora reads it
    # Trees on the ground calibrate the height offset (flora/terrain.py); one stands at a site.
    trees = "".join(doodad(10 + k, "ZerusTree", x, y, round(float(vz[y, x]), 4)) for k, (x, y) in enumerate([(5, 5), (20, 90), (110, 30), (120, 120), (60, 30), (56, 78)]))
    placed = doodad(30, "RockWaterfall", 58, 70, 9) + doodad(31, "Waterfall", 4, 120, 9)
    (folder / "Objects").write_bytes((OBJECTS_HEAD + unit + trees + placed + OBJECTS_TAIL).encode("utf-8"))
    return folder
