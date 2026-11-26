"""The StarCraft: Ghost adapter on a made-up build and a stand-in NODExport (R-HD-150 to R-HD-155)."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from hdtex.core import registry
from hdtex.core.interfaces import GameError
from hdtex.ghost import export, game
from hdtex.ghost.build import BuildError, settings

from testkit.tests.textures import ghost_fixtures as gf


class GhostGameTest(unittest.TestCase):
    def setUp(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.root = Path(self._dir.name)
        self.build = gf.make_build(self.root)
        self.game = game.GhostGame(self.build, self.root / "index")

    def tearDown(self) -> None:
        self._dir.cleanup()

    def texture(self, asset: str):
        return {one.asset: one for one in self.game.textures("build")}[asset]

    def judged(self, asset: str):
        return self.game.judge("build", self.texture(asset))

    def test_registered(self) -> None:
        self.assertIs(registry.GAMES.get("ghost"), game.GAME)
        self.assertEqual(game.GAME.datasets(), ("build",))

    def test_textures_named_by_materials(self) -> None:
        assets = {one.asset for one in self.game.textures("build")}
        for asset in (gf.CRATE, gf.GLOW, gf.ENV, gf.SKY, gf.DXT3, gf.RAW):
            self.assertIn(asset, assets)
        # A file no material names is not a texture of the game.
        self.assertNotIn(gf.SPARE, assets)

    def test_users_and_entries(self) -> None:
        crate = self.texture(gf.CRATE)
        self.assertEqual(crate.origin, "3D/Materials/chestCrate2.dds")
        self.assertEqual(crate.users, ("3d\\models\\crate.nod", "3d\\models\\props.nod"))
        self.assertEqual(crate.entries, ("chestCrate2",))

    def test_tiles_where_a_triangle_spans_the_border(self) -> None:
        # crate.nod's triangle spans u 0.2 to 1.6; props.nod's does not: one model that repeats it is enough.
        self.assertTrue(self.texture(gf.CRATE).tiles)
        # Negative: inside 0..1, up to 1.004 (Nova's eyelashes): no repeat.
        self.assertFalse(self.texture(gf.GLOW).tiles)
        # Negative: a triangle moved whole to u 2.1 .. 2.9 samples no border.
        self.assertFalse(self.texture(gf.DXT3).tiles)

    def test_repeating_refuses_a_binary_of_another_size(self) -> None:
        answer = {"vertexStride": 52, "indexCount": 3, "indexOffset": 156, "groups": [], "materials": []}
        with self.assertRaisesRegex(BuildError, "binary is 10 bytes"):
            export.repeating(answer, b"\x00" * 10, "3D/Models/x.nod")

    def test_roles(self) -> None:
        self.assertEqual(self.judged(gf.CRATE).role, "diffuse")
        self.assertEqual(self.judged(gf.GLOW).role, "diffuse")
        self.assertEqual(self.judged(gf.ENV).role, "data")
        self.assertEqual(self.judged(gf.DXT3).role, "diffuse")
        self.assertEqual(self.judged(gf.RAW).role, "diffuse")

    def test_refusals(self) -> None:
        cases = {
            gf.CLEAR: "transparent",
            gf.CUBE: "cube",
            gf.TINY: "smaller than 32",
            gf.DXT2: "DXT2",
            gf.VOLUME: "volume",
        }
        for asset, words in cases.items():
            with self.subTest(asset=asset):
                one = self.judged(asset)
                self.assertIsNone(one.role)
                self.assertIn(words, one.reason)

    def test_refused_before_read(self) -> None:
        sky = self.texture(gf.SKY)
        self.assertTrue(sky.judged)
        self.assertIsNone(sky.role)
        self.assertIn("does not draw", sky.reason)
        vine = self.texture("3d\\materials\\vine.tga")
        self.assertIn("not a DDS", vine.reason)

    def test_owners(self) -> None:
        owners = {one.id: one for one in self.game.owners("build")}
        model = owners["model:3d\\models\\crate.nod"]
        self.assertEqual(set(model.textures), {gf.CRATE, gf.GLOW, gf.ENV})
        actor = owners["actor:crate_actor"]
        self.assertEqual(actor.below, ("model:3d\\models\\crate.nod",))
        self.assertEqual(actor.textures, model.textures)
        # A template whose model is not in the build, or that has none, owns nothing.
        self.assertNotIn("actor:ghost_of_nothing", owners)
        self.assertNotIn("actor:no_model", owners)
        self.assertFalse([one for one in owners if one.startswith("unit:")])

    def test_gaps(self) -> None:
        gaps = self.game.gaps("build")
        refused = " ".join(gaps["model files NODExport refused"])
        self.assertIn("old.nod", refused)
        self.assertIn("broken.nod", refused)
        self.assertIn("collide", gaps["materials found by no step"])
        self.assertIn("goneMat: texture", gaps["material texture files that are missing"])

    def test_listing_is_kept(self) -> None:
        self.game.textures("build")
        first = gf.calls(self.build)
        again = game.GhostGame(self.build, self.root / "index")
        again.textures("build")
        self.assertEqual(gf.calls(self.build), first)
        self.assertEqual(first.count("catalog"), 1)
        self.assertEqual(first.count("materials"), 1)

    def test_listing_made_again_on_change(self) -> None:
        self.game.textures("build")
        (self.build.root / "MaterialDirs.txt").write_text("Materials\\Colors\nMaterials\n")
        game.GhostGame(self.build, self.root / "index").textures("build")
        self.assertEqual(gf.calls(self.build).count("catalog"), 2)
        self.assertEqual(len(list((self.root / "index").glob("listing-*.json"))), 1)

    def test_build_is_not_written(self) -> None:
        """R-HD-150: listing, judging and reading originals change no file of the build and add none."""
        def snapshot() -> dict[str, tuple[int, int]]:
            return {str(p.relative_to(self.build.root)): (p.stat().st_size, p.stat().st_mtime_ns) for p in sorted(self.build.root.rglob("*"))}
        before = snapshot()
        for texture in self.game.textures("build"):
            if not texture.reason:
                self.game.judge("build", texture)
        self.game.owners("build")
        self.game.gaps("build")
        self.assertEqual(snapshot(), before)

    def test_no_bake(self) -> None:
        self.assertEqual(self.game.bakes, game.NO_BAKE)
        with self.assertRaisesRegex(GameError, "baking is not enabled"):
            self.game.package("build", [], [], {}, self.root / "out")
        with self.assertRaisesRegex(GameError, "baking is not enabled"):
            self.game.check(self.root / "out")

    def test_one_dataset_no_layer(self) -> None:
        with self.assertRaises(BuildError):
            self.game.textures("units")
        with self.assertRaises(BuildError):
            self.game.use("build", self.root)

    def test_settings_read_at_call(self) -> None:
        with mock.patch.dict(os.environ, {"GHOST_PATH": ""}):
            with self.assertRaisesRegex(BuildError, "GHOST_PATH is not set"):
                settings()
        env = {"GHOST_PATH": str(self.build.root), "NODSDK_EXPORT": str(self.build.exporter)}
        with mock.patch.dict(os.environ, env):
            self.assertEqual(settings(), self.build)
        with mock.patch.dict(os.environ, {**env, "NODSDK_EXPORT": str(self.root / "none")}):
            with self.assertRaisesRegex(BuildError, "not built"):
                settings()


if __name__ == "__main__":
    unittest.main()
