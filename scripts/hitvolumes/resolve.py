"""Unit type -> actor -> model -> m3 path and scale, from the game data stack.

The stack is the stock data the map depends on (Void Story), lowest first,
then the built map's own game data. A later entry with the same id wins over
an earlier one, field by field, and a field missing on an entry is read from
its parent.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import NamedTuple
from pathlib import Path

# Void Story data stack, lowest first. The map comes last.
STACK = (
    "mods/core.sc2mod",
    "mods/liberty.sc2mod",
    "mods/swarm.sc2mod",
    "mods/void.sc2mod",
    "campaigns/liberty.sc2campaign",
    "campaigns/libertystory.sc2campaign",
    "campaigns/swarm.sc2campaign",
    "campaigns/swarmstory.sc2campaign",
    "campaigns/void.sc2campaign",
    "campaigns/voidstory.sc2campaign",
)
CATALOGS = {"actor": "actordata.xml", "model": "modeldata.xml", "unit": "unitdata.xml"}
MAP_CATALOGS = {"actor": "ActorData.xml", "model": "ModelData.xml", "unit": "UnitData.xml"}
TOKEN_RE = re.compile(r'token id="([^"]+)" value="([^"]*)"')
SKIP_ATTRS = {"id", "parent", "default"}
# Actor classes that draw a unit: some heroes (Dehaka, KerriganVoid) use a
# CActorMissile as their unit actor.
ACTOR_TAGS = ("CActorUnit", "CActorMissile")
BIRTH_RE = re.compile(r"\s*UnitBirth\.([A-Za-z0-9_]+)\s*(?:;|$)")
MORPH_RE = re.compile(r"MorphTo ([A-Za-z0-9_]+)")
Vec3 = tuple[float, float, float]


class Resolution(NamedTuple):
    unit: str
    actor: str
    model: str
    m3: str
    scale: Vec3
    actor_scale: Vec3
    model_scale: Vec3
    # The ids the result was read from, nearest first (the stale check, fresh.py).
    actors: tuple[str, ...] = ()
    models: tuple[str, ...] = ()
    # VariationCount: the engine draws <name>_00.m3 .. _<n-1>.m3 at random.
    variations: int = 0

    def files(self) -> list[str]:
        """The m3 entries to look for, in order: the model path, then its
        first variation. The volume is the first that exists."""
        if self.variations > 0 and self.m3.lower().endswith(".m3"):
            return [self.m3, self.m3[:-3] + "_00.m3"]
        return [self.m3]


def stock_paths(stock_dir: Path, catalog: str) -> list[Path]:
    """The extracted stock catalog files, in stack order."""
    return [stock_dir / Path(*s.split("/")) / "base.sc2data" / "gamedata" / CATALOGS[catalog] for s in STACK]


def stock_entries() -> list[str]:
    """CASC paths of the stock catalogs, as stormex lists them."""
    return [f"{s}/base.sc2data/gamedata/{name}".replace("/", "\\") for s in STACK for name in CATALOGS.values()]


class Catalog:
    """Every entry of one catalog along the stack, by id."""

    def __init__(self, paths: list[Path], tags: tuple[str, ...]) -> None:
        self.entries: dict[str, list[ET.Element]] = {}
        for path in paths:
            if not path.is_file():
                continue
            parser = ET.XMLParser(target=ET.TreeBuilder(insert_pis=True))
            for el in ET.parse(path, parser).getroot():
                if el.tag in tags and el.get("id"):
                    self.entries.setdefault(el.get("id"), []).append(el)

    def parent(self, ident: str) -> str | None:
        for el in reversed(self.entries.get(ident, [])):
            if el.get("parent"):
                return el.get("parent")
        return None

    def chain(self, ident: str) -> list[str]:
        """The id and its parents, nearest first."""
        out: list[str] = []
        cur: str | None = ident
        while cur and cur in self.entries and cur not in out:
            out.append(cur)
            cur = self.parent(cur)
        return out

    def field(self, ident: str, name: str) -> str | None:
        for cur in self.chain(ident):
            for el in reversed(self.entries[cur]):
                f = el.find(name)
                if f is not None and f.get("value") is not None:
                    return f.get("value")
        return None

    def tokens(self, ident: str) -> dict[str, str]:
        """Token values along the parent chain: an attribute on a child wins
        over a token default declared in a parent."""
        found: dict[str, str] = {}
        chain = self.chain(ident)
        for cur in chain:
            for el in reversed(self.entries[cur]):
                for key, value in el.attrib.items():
                    if key not in SKIP_ATTRS:
                        found.setdefault(key, value)
        for cur in chain:
            for el in reversed(self.entries[cur]):
                for child in el:
                    if child.tag is ET.ProcessingInstruction:
                        match = TOKEN_RE.search(child.text or "")
                        if match:
                            found.setdefault(match.group(1), match.group(2))
        found["id"] = ident
        return found


def birth_units(el: ET.Element) -> list[str]:
    """Unit types whose birth creates this actor: On Terms="UnitBirth.X" Send="Create"."""
    out = []
    for on in el.findall("On"):
        if (on.get("Send") or "").strip() != "Create":
            continue
        match = BIRTH_RE.match(on.get("Terms") or "")
        if match:
            out.append(match.group(1))
    return out


def expand(text: str, values: dict[str, str]) -> str:
    return re.sub(r"##([A-Za-z]+)##", lambda m: values.get(m.group(1), m.group(0)), text)


def vec3(text: str | None) -> Vec3:
    """A data scale: one value for all axes, or x,y,z. Missing is 1."""
    if text is None:
        return (1.0, 1.0, 1.0)
    parts = [float(p) for p in text.split(",")]
    if len(parts) == 1:
        return (parts[0], parts[0], parts[0])
    if len(parts) != 3:
        raise ValueError(f"scale is not one or three values: {text!r}")
    return (parts[0], parts[1], parts[2])


class GameData:
    def __init__(self, stock_dir: Path, map_dir: Path) -> None:
        data = map_dir / "Base.SC2Data" / "GameData"
        self.actors = Catalog(stock_paths(stock_dir, "actor") + [data / MAP_CATALOGS["actor"]], ACTOR_TAGS)
        self.models = Catalog(stock_paths(stock_dir, "model") + [data / MAP_CATALOGS["model"]], ("CModel",))
        # unitName -> the first actor that lists it, in catalog order; and
        # unit -> the first actor its birth creates (a morph state such as
        # ArchiveSealed has no actor of its own).
        self.by_unit_name: dict[str, str] = {}
        self.by_birth: dict[str, str] = {}
        # A morph state (BanelingBurrowed, a lowered gate) keeps the actor
        # it morphed from and is drawn in another pose: no volume, only a reason.
        self.by_morph: dict[str, str] = {}
        for ident, els in self.actors.entries.items():
            for el in els:
                for name in (el.get("unitName") or "").split(","):
                    if name:
                        self.by_unit_name.setdefault(name, ident)
                for name in birth_units(el):
                    self.by_birth.setdefault(name, ident)
                for on in el.findall("On"):
                    for name in MORPH_RE.findall(on.get("Terms") or ""):
                        self.by_morph.setdefault(name, ident)

    def actor_for(self, unit: str) -> str | None:
        """The unit actor: the one named like the unit, else one listing it
        in unitName, else one that a UnitBirth of the unit creates."""
        if unit in self.actors.entries:
            return unit
        return self.by_unit_name.get(unit) or self.by_birth.get(unit)

    def unit_name(self, actor: str) -> str:
        for el in reversed(self.actors.entries[actor]):
            if el.get("unitName"):
                return el.get("unitName").split(",")[0]
        return actor

    def resolve(self, unit: str) -> Resolution | None:
        """None when the unit has no actor, or its actor no model file."""
        actor = self.actor_for(unit)
        if actor is None:
            return None
        model = self.actors.field(actor, "Model") or actor
        model = model.replace("##unitName##", self.unit_name(actor)).replace("##id##", actor)
        path = self.models.field(model, "Model")
        if path is None:
            return None
        path = expand(path, self.models.tokens(model))
        actor_scale = vec3(self.actors.field(actor, "Scale"))
        # The engine picks a model scale between ScaleMin and ScaleMax per
        # actor. A script cannot read which, so the volume uses the maximum.
        model_scale = vec3(self.models.field(model, "ScaleMax"))
        scale = (actor_scale[0] * model_scale[0], actor_scale[1] * model_scale[1], actor_scale[2] * model_scale[2])
        actors = tuple(self.actors.chain(actor))
        models = tuple(self.models.chain(model))
        variations = int(self.models.field(model, "VariationCount") or 0)
        return Resolution(unit, actor, model, path, scale, actor_scale, model_scale, actors, models, variations)
