"""A small map, game storage, and upscaler for the hdtex host tests.

Nothing here touches the game or the GPU. The storage is a dict, and the
upscaler enlarges with nearest-neighbour.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from hdtex import bc3, dds, roles
from hdtex.casc import CascError

SIZE = 64
CATALOG_PATH = "mods\\swarm.sc2mod\\base.sc2data\\gamedata\\terraintexdata.xml"
TEXTURE_FOLDER = "mods\\liberty.sc2mod\\base.sc2assets\\assets\\textures\\"
NORMAL_TRAILER = b"_NXD"

DOCUMENT_INFO = """<?xml version="1.0" encoding="utf-8"?>
<DocInfo>
    <Dependencies>
        <Value>bnet:Void Story (Campaign)/0.0/999,file:{dependency}</Value>
    </Dependencies>
</DocInfo>
"""


def diffuse_rgba(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    angle = np.arange(SIZE) * (2 * np.pi / SIZE)
    wave = np.sin(angle)[:, None] * np.cos(angle * 2)[None, :]
    planes = [128 + 60 * np.roll(wave, shift, axis=1) for shift in (0, 16, 32, 8)]
    image = np.stack(planes, axis=2) + rng.normal(0, 2, (SIZE, SIZE, 4))
    return np.clip(np.rint(image), 0, 255).astype(np.uint8)


def normal_rgba() -> np.ndarray:
    angle = np.arange(SIZE) * (2 * np.pi / SIZE)
    rgba = np.zeros((SIZE, SIZE, 4), dtype=np.uint8)
    rgba[:, :, 0] = roles.NORMAL_RED
    rgba[:, :, 1] = np.rint((0.3 * np.cos(angle)[:, None] * 0.5 + 0.5) * 255)
    rgba[:, :, 3] = np.rint((0.4 * np.sin(angle)[None, :] * 0.5 + 0.5) * 255)
    return rgba


def dds_file(role: str, rgba: np.ndarray, trailer: bytes = b"") -> bytes:
    """A game texture: the picture with a full mip chain, as the role packs it."""
    levels = roles.ROLES[role].join(roles.ROLES[role].split(rgba), None, True)
    return dds.build(SIZE, SIZE, [bc3.encode(level) for level in levels], trailer)


def game_catalog(numbers: tuple[int, ...]) -> str:
    entries = "".join(
        f'<CTerrainTex id="Zerus{n}">'
        f'<Texture value="Assets\\Textures\\Zerus_{n}.dds"/>'
        f'<Normalmap value="Assets\\Textures\\Zerus_{n}Normal.dds"/>'
        "</CTerrainTex>"
        for n in numbers
    )
    template = '<CTerrainTex default="1"><Texture value="Assets\\Textures\\##id##.dds"/></CTerrainTex>'
    return f"<Catalog>{template}{entries}</Catalog>"


class FakeCasc:
    """The game storage as a dict of path to bytes."""

    def __init__(self, numbers: tuple[int, ...] = (1, 2)) -> None:
        self.files: dict[str, bytes] = {CATALOG_PATH: game_catalog(numbers).encode()}
        for n in numbers:
            self.files[f"{TEXTURE_FOLDER}zerus_{n}.dds"] = dds_file("diffuse", diffuse_rgba(n))
            self.files[f"{TEXTURE_FOLDER}zerus_{n}normal.dds"] = dds_file("normal", normal_rgba(), NORMAL_TRAILER)

    def find(self, suffixes: list[str]) -> list[str]:
        wanted = tuple(suffix.lower() for suffix in suffixes)
        return sorted(path for path in self.files if path.endswith(wanted)) if wanted else []

    def extract(self, paths: list[str], out_dir: Path) -> dict[str, Path]:
        found = {}
        for path in paths:
            if path not in self.files:
                raise CascError(f"not in the storage: {path}")
            target = out_dir / Path(*path.split("\\"))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(self.files[path])
            found[path] = target
        return found


class FakeUpscaler:
    """Stands in for `upscaler.run`. Enlarges 4x and records each run.

    The model `seedvr2` adds a fine pattern, so its files differ from the
    files of the other models, as the real ones do.
    """

    def __init__(self) -> None:
        self.runs: list[tuple[str, list[str]]] = []

    def __call__(self, input_dir: Path, output_dir: Path, model: str, wrap, gpu=None, tile=None):
        output_dir.mkdir(parents=True, exist_ok=True)
        outputs = {}
        names = []
        for source in sorted(input_dir.glob("*.png")):
            image = Image.open(source)
            target = output_dir / f"{source.stem}_4x.png"
            image = image.resize((image.width * 4, image.height * 4), Image.NEAREST)
            if model == "seedvr2":
                # 4 px blocks, so the pattern survives the 2x shrink of the generative variant.
                pixels = np.asarray(image).astype(np.int16)
                rows, cols = np.indices(pixels.shape[:2])
                step = np.where(((rows // 4) + (cols // 4)) % 2 == 0, 6, -6)
                pixels = pixels + (step[:, :, None] if pixels.ndim == 3 else step)
                image = Image.fromarray(np.clip(pixels, 0, 255).astype(np.uint8))
            image.save(target)
            outputs[source.stem] = target
            names.append(source.name)
        self.runs.append((model, names))
        return outputs


def write_map(map_dir: Path, textures: tuple[str, ...] = ("Zerus2", "Zerus1")) -> Path:
    """The files of a map that the texture tools read."""
    map_dir.mkdir(parents=True, exist_ok=True)
    (map_dir / "DocumentInfo").write_text(DOCUMENT_INFO.format(dependency="Campaigns/VoidStory.SC2Campaign"))
    rows = "".join(f'<texture i="{index}" name="{name}"/>' for index, name in enumerate(textures))
    (map_dir / "t3Terrain.xml").write_text(
        f'<terrain><textureList num="64">{rows}<texture i="63" name=""/></textureList></terrain>'
    )
    return map_dir
