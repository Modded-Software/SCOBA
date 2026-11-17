from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET

from project_root import project_root
from hitvolumes.validate_pod_actor import check_pod_actor, pod_actor_problems

GOOD = """<Catalog>
<CActorUnit id="SCOBADropPodArt" parent="GenericUnitStandardNoAutoSoundLinks" default="1"><Model value="DropPodFalling"/></CActorUnit>
<CActorUnit id="TerranDropPod" parent="SCOBADropPodArt" unitName="TerranDropPod"/>
<CActorUnit id="SCOBAHeroPod" parent="SCOBADropPodArt" unitName="SCOBAHeroPod"/>
</Catalog>"""

# The hero pod on the concrete actor: not created in game (podbirth/20261117-105245).
CHAINED = GOOD.replace('id="SCOBAHeroPod" parent="SCOBADropPodArt"', 'id="SCOBAHeroPod" parent="TerranDropPod"')

# The actor as extracted from the original map: no parent, no model.
OLD = """<Catalog>
<CActorUnit id="TerranDropPod"><Scale value="4.5"/></CActorUnit>
<CActorUnit id="SCOBAHeroPod" parent="TerranDropPod" unitName="SCOBAHeroPod"/>
</Catalog>"""


class PodActorTest(unittest.TestCase):
    def test_good_actor_passes(self) -> None:
        self.assertEqual(pod_actor_problems(ET.fromstring(GOOD)), [])

    def test_old_actor_fails(self) -> None:
        problems = pod_actor_problems(ET.fromstring(OLD))
        self.assertEqual(problems, ["ActorData: missing CActorUnit SCOBADropPodArt"])

    def test_hero_pod_on_concrete_actor_fails(self) -> None:
        self.assertEqual(len(pod_actor_problems(ET.fromstring(CHAINED))), 1)

    def test_art_not_default_fails(self) -> None:
        bad = GOOD.replace(' default="1"', "")
        self.assertEqual(len(pod_actor_problems(ET.fromstring(bad))), 1)

    def test_hero_pod_with_own_wrong_model_fails(self) -> None:
        bad = GOOD.replace('unitName="SCOBAHeroPod"/>', 'unitName="SCOBAHeroPod"><Model value="SCOBAHeroPod"/></CActorUnit>')
        self.assertEqual(len(pod_actor_problems(ET.fromstring(bad))), 1)

    def test_src_map_passes(self) -> None:
        self.assertEqual(check_pod_actor(project_root() / "src" / "SCOBA.SC2Map"), [])


if __name__ == "__main__":
    unittest.main()
