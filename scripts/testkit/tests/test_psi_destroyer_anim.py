from __future__ import annotations

import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from project_root import project_root
from spore_scale import (
    DEFAULT_ANIM_SPEED,
    PSI_DESTROYER_ANIM_MARKER,
    PSI_DESTROYER_ANIM_SLOWDOWN,
    PSI_DESTROYER_MODELS,
    slow_model_animations,
    slow_psi_destroyer_animations,
)

ROOT = project_root()
MODEL_DATA = Path("Base.SC2Data") / "GameData" / "ModelData.xml"
SRC_MODELS = ROOT / "src" / "SCOBA.SC2Map" / MODEL_DATA
BUILT_MODELS = ROOT / "out" / "SCOBA256.SC2Map" / MODEL_DATA

MODELS = """<?xml version="1.0" encoding="us-ascii"?>
<Catalog>
    <CModel id="Mothership">
        <AnimSpeed value="0.250000"/>
        <Occlusion value="None"/>
    </CModel>
    <CModel id="PsiDecimator">
        <ScaleMax value="3.500000,3.500000,3.500000"/>
        <ScaleMin value="3.500000,3.500000,3.500000"/>
    </CModel>
    <CModel id="PsiDecimatorWave">
        <ScaleMax value="2.000000,2.000000,2.000000"/>
    </CModel>
</Catalog>
"""


def anim_speeds(text: str) -> dict[str, float | None]:
    speeds: dict[str, float | None] = {}
    for node in ET.fromstring(text.encode("ascii")).findall("CModel"):
        speed = node.find("AnimSpeed")
        speeds[node.get("id", "")] = None if speed is None else float(speed.get("value", ""))
    return speeds


def children(text: str, model_id: str) -> list[tuple[str, str]]:
    node = ET.fromstring(text.encode("ascii")).find(f"./CModel[@id='{model_id}']")
    assert node is not None, model_id
    return [(child.tag, child.get("value", "")) for child in node]


class SlowModelAnimationsTest(unittest.TestCase):
    def test_model_without_speed_gets_the_slowed_default(self) -> None:
        text, changed = slow_model_animations(MODELS, ("PsiDecimator",), 2.0)
        self.assertEqual(changed, 1)
        self.assertEqual(anim_speeds(text)["PsiDecimator"], 0.5)

    def test_existing_speed_is_divided(self) -> None:
        text, _ = slow_model_animations(MODELS, ("Mothership",), 2.0)
        self.assertEqual(anim_speeds(text)["Mothership"], 0.125)

    def test_missing_model_is_added(self) -> None:
        text, changed = slow_model_animations(MODELS, ("PsiDecimatorDeath",), 2.0)
        self.assertEqual(changed, 1)
        self.assertEqual(anim_speeds(text)["PsiDecimatorDeath"], 0.5)
        self.assertEqual(children(text, "PsiDecimatorDeath"), [("AnimSpeed", "0.500000")])

    def test_other_fields_of_the_model_are_kept(self) -> None:
        text, _ = slow_model_animations(MODELS, ("PsiDecimator",), 2.0)
        self.assertEqual(
            children(text, "PsiDecimator"),
            [
                ("ScaleMax", "3.500000,3.500000,3.500000"),
                ("ScaleMin", "3.500000,3.500000,3.500000"),
                ("AnimSpeed", "0.500000"),
            ],
        )

    def test_other_models_are_untouched(self) -> None:
        text, _ = slow_model_animations(MODELS, ("PsiDecimator", "PsiDecimatorDeath"), 2.0)
        speeds = anim_speeds(text)
        self.assertEqual(speeds["Mothership"], 0.25)
        # The id is a prefix of the target id; it must not be matched.
        self.assertIsNone(speeds["PsiDecimatorWave"])
        self.assertEqual(children(text, "PsiDecimatorWave"), children(MODELS, "PsiDecimatorWave"))

    def test_each_model_appears_once(self) -> None:
        text, _ = slow_model_animations(MODELS, ("PsiDecimator", "PsiDecimatorDeath"), 2.0)
        ids = [node.get("id") for node in ET.fromstring(text.encode("ascii")).findall("CModel")]
        self.assertEqual(sorted(ids), sorted(set(ids)))
        self.assertEqual(text.count("<AnimSpeed"), 3)

    def test_no_models_changes_nothing(self) -> None:
        text, changed = slow_model_animations(MODELS, (), 2.0)
        self.assertEqual(changed, 0)
        self.assertEqual(text, MODELS)

    def test_slowdown_must_be_positive(self) -> None:
        for slowdown in (0.0, -2.0):
            with self.assertRaises(ValueError):
                slow_model_animations(MODELS, ("PsiDecimator",), slowdown)

    def test_self_closing_model_fails(self) -> None:
        source = MODELS.replace("</Catalog>", '    <CModel id="Bare"/>\n</Catalog>')
        with self.assertRaises(ValueError):
            slow_model_animations(source, ("Bare",), 2.0)

    def test_missing_catalog_fails(self) -> None:
        with self.assertRaises(ValueError):
            slow_model_animations("<Other/>", ("PsiDecimatorDeath",), 2.0)


class SlowPsiDestroyerTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.map_dir = Path(self._tmp.name)
        self.models = self.map_dir / MODEL_DATA
        self.models.parent.mkdir(parents=True)
        self.models.write_text(MODELS, encoding="utf-8")

    def test_slowdown_is_two_for_unit_and_death_models(self) -> None:
        self.assertEqual(PSI_DESTROYER_ANIM_SLOWDOWN, 2.0)
        self.assertEqual(PSI_DESTROYER_MODELS, ("PsiDecimator", "PsiDecimatorDeath"))

    def test_models_are_slowed_and_marked(self) -> None:
        self.assertEqual(slow_psi_destroyer_animations(self.map_dir), 2)
        speeds = anim_speeds(self.models.read_text(encoding="utf-8"))
        for model_id in PSI_DESTROYER_MODELS:
            self.assertEqual(speeds[model_id], DEFAULT_ANIM_SPEED / PSI_DESTROYER_ANIM_SLOWDOWN, model_id)
        self.assertEqual(speeds["Mothership"], 0.25)
        self.assertTrue((self.map_dir / PSI_DESTROYER_ANIM_MARKER).is_file())

    def test_second_run_does_not_slow_again(self) -> None:
        slow_psi_destroyer_animations(self.map_dir)
        once = self.models.read_text(encoding="utf-8")
        self.assertEqual(slow_psi_destroyer_animations(self.map_dir), 0)
        self.assertEqual(self.models.read_text(encoding="utf-8"), once)


class BuiltMapTest(unittest.TestCase):
    @unittest.skipUnless(BUILT_MODELS.is_file(), "built map is absent")
    def test_built_speed_is_source_speed_over_slowdown(self) -> None:
        source = anim_speeds(SRC_MODELS.read_text(encoding="ascii"))
        built = anim_speeds(BUILT_MODELS.read_text(encoding="ascii"))
        for model_id in PSI_DESTROYER_MODELS:
            before = source.get(model_id)
            if before is None:
                before = DEFAULT_ANIM_SPEED
            self.assertEqual(built[model_id], before / PSI_DESTROYER_ANIM_SLOWDOWN, model_id)

    @unittest.skipUnless(BUILT_MODELS.is_file(), "built map is absent")
    def test_built_models_outside_the_step_keep_source_speed(self) -> None:
        source = anim_speeds(SRC_MODELS.read_text(encoding="ascii"))
        built = anim_speeds(BUILT_MODELS.read_text(encoding="ascii"))
        checked = 0
        for model_id, speed in source.items():
            if model_id in PSI_DESTROYER_MODELS:
                continue
            self.assertEqual(built[model_id], speed, model_id)
            checked += 1
        self.assertGreater(checked, 0)


if __name__ == "__main__":
    unittest.main()
