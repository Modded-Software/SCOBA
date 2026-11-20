"""Files of a built map the water features read and write.

Ground: t3HeightMap (HMAP, three u16 per vertex; z = (r0 + r1) x
quantizeScale + offset, flora/terrain.py). Only r0 is written.
Pathing paint: CellAttribute_Pnp, one byte per cell, 255 = no pathing.
"""

from __future__ import annotations

import re
import struct
from pathlib import Path

import numpy as np

from flora.terrain import _scale, bilinear
from terrain import sync_height

NO_PATH = 255


def vertex_z(map_dir: Path) -> np.ndarray:
    """Absolute ground z per heightmap vertex, [y, x]. Vertex (x, y) is world (x, y)."""
    return sync_height.vertex_z(Path(map_dir))


def ground_at(vz: np.ndarray, x: float, y: float) -> float:
    return bilinear(vz, x, y)


def write_vertex_z(map_dir: Path, old: np.ndarray, new: np.ndarray) -> int:
    """Write the changed vertices to t3HeightMap. Returns how many changed."""
    path = Path(map_dir) / "t3HeightMap"
    data = bytearray(path.read_bytes())
    magic, _version, sx, sy = struct.unpack_from("<4sIII", data, 0)
    if magic != b"HMAP" or (sy, sx) != new.shape or new.shape != old.shape:
        raise ValueError(f"{path} is not an HMAP of {new.shape}")
    records = np.frombuffer(data, dtype="<u2", offset=32, count=sx * sy * 3).reshape(sy, sx, 3).copy()
    steps = np.rint((new - old) / _scale(Path(map_dir))).astype(int)
    changed = steps != 0
    value = records[..., 0].astype(int) + steps
    if value[changed].size and (value[changed].min() < 0 or value[changed].max() > 65535):
        raise ValueError("carved ground does not fit the height map range")
    records[..., 0] = np.where(changed, value, records[..., 0]).astype("<u2")
    data[32 : 32 + sx * sy * 6] = records.tobytes()
    path.write_bytes(bytes(data))
    return int(changed.sum())


def paint_no_path(map_dir: Path, cells: np.ndarray) -> int:
    """Set the painted pathing of the True cells ([y, x]) to no pathing. Returns how many changed."""
    path = Path(map_dir) / "CellAttribute_Pnp"
    data = bytearray(path.read_bytes())
    n = cells.shape[0]
    if len(data) != 4 + n * n or cells.shape != (n, n):
        raise ValueError(f"{path} is not one byte per cell of {cells.shape}")
    grid = np.frombuffer(data, dtype=np.uint8, offset=4).reshape(n, n).copy()
    changed = cells & (grid != NO_PATH)
    grid[cells] = NO_PATH
    data[4:] = grid.tobytes()
    path.write_bytes(bytes(data))
    return int(changed.sum())


def set_water_height(text: str, name: str, height: float) -> str:
    """WaterData.xml with the first state of one water type at this height."""
    newline = "\r\n" if "\r\n" in text else "\n"
    state = f'<State index="0" Height="{height:.6f}"/>'
    entry = re.search(rf'<CWater id="{re.escape(name)}"\s*(/>|>(.*?)</CWater>)', text, re.S)
    if entry is None:
        close = text.rfind("</Catalog>")
        if close < 0:
            raise ValueError("WaterData.xml has no </Catalog>")
        block = f'    <CWater id="{name}">{newline}        {state}{newline}    </CWater>{newline}'
        return text[:close] + block + text[close:]
    body = entry.group(2)
    if body is None:
        block = f'<CWater id="{name}">{newline}        {state}{newline}    </CWater>'
        return text[: entry.start()] + block + text[entry.end() :]
    as_attr = re.search(r'(<State\b[^>]*\bHeight=")[^"]*(")', body)
    as_child = re.search(r'(<Height value=")[^"]*(")', body)
    if as_attr:
        body = body[: as_attr.start()] + as_attr.group(1) + f"{height:.6f}" + as_attr.group(2) + body[as_attr.end() :]
    elif as_child:
        body = body[: as_child.start()] + as_child.group(1) + f"{height:.6f}" + as_child.group(2) + body[as_child.end() :]
    elif re.search(r"<State\b", body):
        body = re.sub(r"<State\b", f'<State Height="{height:.6f}"', body, count=1)
    else:
        body = f"{newline}        {state}{body}"
    return text[: entry.start(2)] + body + text[entry.end(2) :]
