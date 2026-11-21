import math
import re
import unittest

from flora.treevary import T, conflicts, neighbours, repair, too_similar, vary_objects
from project_root import project_root


def clone_grid(n: int, gap: float) -> list[T]:
    """n x n identical trees: every neighbour pair is a look-alike."""
    return [T(10 + i * gap, 10 + j * gap, 4.0, 1.0, 3) for i in range(n) for j in range(n)]


class TreeVaryTest(unittest.TestCase):
    def test_one_difference_is_enough(self) -> None:
        a = T(0, 0, 4.0, 0.0, 3)
        self.assertTrue(too_similar(a, a._replace(x=1)))
        self.assertFalse(too_similar(a, a._replace(variation=4)))
        self.assertFalse(too_similar(a, a._replace(scale=4.0 * 1.6)))
        self.assertFalse(too_similar(a, a._replace(rotation=math.radians(50))))
        # Rotation wraps: 350 deg and 10 deg are 20 deg apart.
        self.assertTrue(too_similar(a._replace(rotation=math.radians(350)), a._replace(rotation=math.radians(10))))

    def test_neighbour_radius_is_relative_to_scale(self) -> None:
        small = [T(0, 0, 2.0, 0, 0), T(4, 0, 2.0, 0, 0)]  # reach 1.5 * (1 + 1) = 3
        large = [T(0, 0, 6.0, 0, 0), T(4, 0, 6.0, 0, 0)]  # reach 1.5 * (3 + 3) = 9
        self.assertEqual(neighbours(small), [[], []])
        self.assertEqual(neighbours(large), [[1], [0]])

    def test_dense_clones_are_repaired(self) -> None:
        trees = clone_grid(6, 2.0)
        self.assertGreater(len(conflicts(trees)), 0)
        fixed, changed = repair(trees)
        self.assertEqual(conflicts(fixed), [])
        self.assertGreater(changed, 0)
        self.assertEqual([(t.x, t.y) for t in fixed], [(t.x, t.y) for t in trees])  # never moves

    def test_varied_set_is_untouched(self) -> None:
        trees = [T(10 + i * 2.0, 10, 4.0, i * math.radians(60), i % 12) for i in range(6)]
        self.assertEqual(conflicts(trees), [])
        fixed, changed = repair(trees)
        self.assertEqual(changed, 0)
        self.assertEqual(fixed, trees)

    def test_deterministic(self) -> None:
        trees = clone_grid(5, 2.0)
        self.assertEqual(repair(trees, 7), repair(trees, 7))

    def test_objects_rewrite(self) -> None:
        tags = "".join(
            f'<ObjectDoodad Id="{i}" Position="{10 + i},10,5" Rotation="1" Scale="4,4,4" Type="ZerusTree">'
            '<Flag Index="HeightAbsolute" Value="1"/></ObjectDoodad>\n'
            for i in range(4)
        )
        text, before, changed, after = vary_objects(f"<PlacedObjects>\n{tags}</PlacedObjects>")
        self.assertGreater(before, 0)
        self.assertEqual(after, 0)
        self.assertGreater(changed, 0)
        self.assertEqual(text.count("HeightAbsolute"), 4)
        self.assertEqual(text.count('Position="'), 4)


if __name__ == "__main__":
    unittest.main()


class TreeSwayTest(unittest.TestCase):
    """Operator 2026-11-21: every tree doodad animates at 0.25."""

    def test_doodad_and_intro_trees_share_the_speed(self) -> None:
        src = project_root() / "src" / "SCOBA.SC2Map"
        actors = (src / "Base.SC2Data" / "GameData" / "ActorData.xml").read_text(encoding="utf-8")
        block = re.search(r'<CActorDoodad id="ZerusTree">(.*?)</CActorDoodad>', actors, re.S)
        self.assertIsNotNone(block)
        self.assertIn('<On Terms="ActorCreation" Send="AnimSetTimeScaleGlobal 0.250000"/>', block.group(1))
        # Negative: no other tree doodad actor in the source sets its own speed.
        others = re.findall(r'<CActorDoodad id="(ZerusTree\w+)"', actors)
        self.assertEqual(others, [])
        tuning = (src / "scripts" / "app" / "systems" / "visual_tuning.galaxy").read_text(encoding="utf-8")
        self.assertIn("const fixed c_TREE_ANIM_SPEED = 0.25;", tuning)
        for actor in ("gv_introTree", "gv_introTree2"):
            self.assertIn(f'ActorSend({actor}, "AnimSetTimeScaleGlobal " + FixedToString(c_TREE_ANIM_SPEED, 2));', tuning)
