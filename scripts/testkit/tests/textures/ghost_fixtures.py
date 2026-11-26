"""A made-up StarCraft: Ghost build and a stand-in NODExport, for the Ghost adapter's host tests.

The stand-in answers the four modes the adapter calls (catalog, nod,
materials) from `exporter.json` beside it, in the shapes of
nodexport_catalog.cpp, nodexport_nod.cpp and nodexport_materials.cpp.
Each call is appended to `calls.log`.
"""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

import numpy as np
from hdtex.core import dds
from hdtex.ghost import codecs  # its formats name the fence and raw crate files below
from hdtex.ghost.build import Build

from testkit.tests.textures.fixtures import colour_rgba, texture_file

STAND_IN = r'''
import json, sys
from pathlib import Path
here = Path(__file__).parent
spec = json.loads((here / "exporter.json").read_text())
with open(here / "calls.log", "a") as log:
    log.write(" ".join(sys.argv[1:2]) + "\n")
mode = sys.argv[1]
if mode == "catalog":
    models = sorted(p.name for p in (Path(sys.argv[2]) / "3D" / "Models").glob("*.nod"))
    out = {"format": "catalog", "templates": spec["templates"], "refusedTemplates": [], "motionSets": [], "refusedMotionSets": [],
           "models": [{"file": m, "materials": 1, "bones": 1, "groups": 1, "vertexTypes": [0]} for m in models if m not in spec["catalogRefused"]],
           "refusedModels": [{"name": m, "error": e} for m, e in spec["catalogRefused"].items()]}
    Path(sys.argv[3]).write_text(json.dumps(out))
    sys.exit(0)
if mode == "nod":
    name = Path(sys.argv[2]).name
    if name in spec["nodRefused"]:
        Path(sys.argv[3]).write_text(json.dumps({"format": "nod", "error": spec["nodRefused"][name]}))
        sys.exit(1)
    import struct
    materials = spec["models"][name]
    # One triangle per material, at the texture coordinates spec["uvs"] names for it (default: inside 0..1).
    vertices, groups = b"", []
    for at, material in enumerate(materials):
        corners = spec["uvs"].get(name, {}).get(material, [[0.1, 0.1], [0.9, 0.1], [0.1, 1.004]])
        for u, v in corners:
            vertices += struct.pack("<3f3f2f4B4f", 0, 0, 0, 0, 0, 1, u, v, 0, 0, 0, 0, 1, 0, 0, 0)
        groups.append({"material": at, "vertexType": 0, "firstVertex": 3 * at, "vertexCount": 3, "firstIndex": 3 * at, "indexCount": 3, "droppedTriangles": 0, "bones": [0]})
    indices = struct.pack(f"<{3 * len(materials)}I", *range(3 * len(materials)))
    Path(sys.argv[3]).write_text(json.dumps({"format": "nod", "materials": materials, "vertexStride": 52, "vertexCount": 3 * len(materials),
                                             "indexOffset": len(vertices), "indexCount": 3 * len(materials), "groups": groups}))
    Path(sys.argv[4]).write_bytes(vertices + indices)
    sys.exit(0)
if mode == "materials":
    names = [line.strip() for line in Path(sys.argv[3]).read_text().splitlines() if line.strip()]
    none = {"step": "none", "source": None, "line": 0, "properties": [], "textures": {}}
    out = [{"name": n, **spec["materials"].get(n, none)} for n in names]
    Path(sys.argv[4]).write_text(json.dumps({"format": "materials", "materials": out}))
    sys.exit(0)
sys.exit(2)
'''

CRATE = "3d\\materials\\chestcrate2.dds"
GLOW = "materials\\colors\\glowred.dds"
ENV = "3d\\materials\\chrome_env.dds"
SKY = "3d\\materials\\sky_top.dds"
CLEAR = "3d\\materials\\leaves.dds"
CUBE = "3d\\materials\\cube_env.dds"
TINY = "3d\\materials\\dot.dds"
DXT2 = "3d\\materials\\premul.dds"
DXT3 = "3d\\materials\\fence.dds"
RAW = "3d\\materials\\crate_raw.dds"
VOLUME = "3d\\materials\\fog.dds"
MISSING = "3d\\materials\\gone.dds"
SPARE = "materials\\colors\\spare.dds"  # a file no material names


def _opaque(seed: int, size: int = 64) -> np.ndarray:
    rgba = colour_rgba(seed, size, size)
    rgba[:, :, 3] = 255
    return rgba


def _header_only(fourcc: bytes, cube: bool = False, volume: bool = False) -> bytes:
    """A DDS whose header is all a test reads: the format, cube or volume flags."""
    data = texture_file("diffuse", _opaque(9), "DXT5")
    head = bytearray(data)
    struct.pack_into("<4s", head, 84, fourcc)
    if cube:
        struct.pack_into("<I", head, 112, 0x200 | 0xFC00)
    if volume:
        struct.pack_into("<I", head, 112, 0x200000)
    return bytes(head)


def make_build(root: Path) -> Build:
    """The build folder, its texture files, and the stand-in NODExport."""
    files = {
        "3D/Materials/chestCrate2.dds": texture_file("diffuse", _opaque(1), "DXT1"),
        "Materials/Colors/glowRed.dds": texture_file("diffuse", colour_rgba(2), "DXT5"),
        "3D/Materials/chrome_env.dds": texture_file("data", colour_rgba(3), "DXT5"),
        "3D/Materials/sky_top.dds": texture_file("diffuse", _opaque(4), "DXT1"),
        # Colours equal, every index 3: each pixel is DXT1's transparent black.
        "3D/Materials/leaves.dds": dds.build(64, 64, [bytes([0, 0, 0, 0, 255, 255, 255, 255]) * 256], b"", "DXT1"),
        "3D/Materials/cube_env.dds": _header_only(b"DXT5", cube=True),
        "3D/Materials/dot.dds": texture_file("diffuse", _opaque(5, 16), "DXT1"),
        "3D/Materials/premul.dds": _header_only(b"DXT2"),
        "3D/Materials/fence.dds": texture_file("diffuse", colour_rgba(6), codecs.DXT3.id),
        "3D/Materials/crate_raw.dds": texture_file("diffuse", colour_rgba(7), codecs.RGBA32.id),
        "3D/Materials/fog.dds": _header_only(b"DXT5", volume=True),
        "Materials/Colors/spare.dds": texture_file("diffuse", _opaque(8), "DXT1"),
        "3D/Materials/vine.tga": b"TGA",
        "3D/Models/crate.nod": b"\x0a",
        "3D/Models/props.nod": b"\x0a",
        "3D/Models/broken.nod": b"\x09",
        "3D/Models/old.nod": b"\x08",
        "Misc/Templates/Global.not": b"NOT",
        "MaterialDirs.txt": b"Materials\\Colors\n",
    }
    for rel, data in files.items():
        (root / "game" / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / "game" / rel).write_bytes(data)

    def tex(rel: str, key: str = "texture") -> dict:
        return {"step": "archive", "source": "Materials/common.nsa", "line": 1, "properties": [["shader", "Normal"]], "textures": {key: rel}}

    spec = {
        "templates": [
            {"name": "crate_actor", "model": "Crate", "motionSet": None, "script": None, "type": 1, "scale": None},
            {"name": "ghost_of_nothing", "model": "nothing.nod", "motionSet": None, "script": None, "type": 1, "scale": None},
            {"name": "no_model", "model": None, "motionSet": None, "script": None, "type": 1, "scale": None},
        ],
        "catalogRefused": {"old.nod": "version 8, not 10"},
        "nodRefused": {"broken.nod": "version 9, not 10"},
        # The crate's own triangle spans u 0.2 to 1.6: chestCrate2 repeats there, so it tiles (props.nod does not repeat it).
        # The fence's triangle is moved whole to u 2.1 .. 2.9: that is no repeat.
        "uvs": {
            "crate.nod": {"chestCrate2": [[0.2, 0.2], [1.6, 0.2], [0.2, 0.8]]},
            "props.nod": {"fence": [[2.1, 0.1], [2.9, 0.1], [2.1, 0.9]]},
        },
        "models": {
            "crate.nod": ["chestCrate2", "glowRed", "chrome"],
            "props.nod": ["chestCrate2", "skyMat", "leaves", "cubeMat", "dotMat", "premul", "fence", "raw", "fogMat", "goneMat", "vine", "collide"],
        },
        "materials": {
            "chestCrate2": {"step": "texture", "source": "3D/Materials/chestCrate2.dds", "line": 0, "properties": [], "textures": {"texture": "3D/Materials/chestCrate2.dds"}},
            "glowRed": tex("Materials/Colors/glowRed.dds", "glow"),
            "chrome": tex("3D/Materials/chrome_env.dds", "envmap"),
            "skyMat": {**tex("3D/Materials/sky_top.dds"), "properties": [["shader", "sky"]]},
            "leaves": tex("3D/Materials/leaves.dds"),
            "cubeMat": tex("3D/Materials/cube_env.dds"),
            "dotMat": tex("3D/Materials/dot.dds"),
            "premul": tex("3D/Materials/premul.dds"),
            "fence": tex("3D/Materials/fence.dds"),
            "raw": tex("3D/Materials/crate_raw.dds"),
            "fogMat": tex("3D/Materials/fog.dds"),
            "goneMat": tex(None),
            "vine": tex("3D/Materials/vine.tga"),
        },
    }
    tool = root / "nodexport"
    tool.mkdir()
    (tool / "exporter.json").write_text(json.dumps(spec))
    script = tool / "NODExport"
    script.write_text(f"#!{sys.executable}\n{STAND_IN}")
    script.chmod(0o755)
    return Build(root / "game", script)


def calls(build: Build) -> list[str]:
    """The modes the stand-in was called with, in order."""
    log = build.exporter.parent / "calls.log"
    return log.read_text().split() if log.is_file() else []
