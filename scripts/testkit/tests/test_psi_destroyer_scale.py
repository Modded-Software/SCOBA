from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from project_root import project_root
from spore_scale import (
    PSI_DESTROYER_MARKER,
    PSI_DESTROYER_SCALE,
    PSI_DESTROYER_UNITS,
    scale_psi_destroyer,
    scale_unit_instances,
)

ROOT = project_root()
SRC_OBJECTS = ROOT / "src" / "SCOBA.SC2Map" / "Objects"
BUILT_OBJECTS = ROOT / "out" / "SCOBA256.SC2Map" / "Objects"

OBJECTS = """<?xml version="1.0" encoding="utf-8"?>
<PlacedObjects Version="27">
    <ObjectUnit Id="1" Position="10,10,0" Rotation="0.302" Scale="1,1,1" UnitType="Predator" Player="7"/>
    <ObjectUnit Id="2" Position="120,124,0" Scale="1,1,1" UnitType="PsiDecimator" Player="7">
        <Flag Index="ForcePlacement" Value="1"/>
    </ObjectUnit>
    <ObjectUnit Id="3" Position="5.5,52.5,0" Scale="1.5,1.5,1.5" UnitType="SporeCannon" Player="8"/>
    <ObjectDoodad Id="4" Position="1,1,0" Scale="2,2,2" Type="PsiDecimator"/>
</PlacedObjects>
"""


def unit_scales(text: str) -> dict[str, list[list[float]]]:
    scales: dict[str, list[list[float]]] = {}
    for block in re.findall(r"<ObjectUnit\b[^>]*>", text, re.S):
        unit_type = re.search(r'\bUnitType="([^"]+)"', block)
        scale = re.search(r'\bScale="([^"]+)"', block)
        if unit_type is None or scale is None:
            continue
        scales.setdefault(unit_type.group(1), []).append([float(v) for v in scale.group(1).split(",")])
    return scales


class ScaleUnitInstancesTest(unittest.TestCase):
    def test_target_scale_is_multiplied(self) -> None:
        text, changed = scale_unit_instances(OBJECTS, {"PsiDecimator"}, 2.0)
        self.assertEqual(changed, 1)
        self.assertEqual(unit_scales(text)["PsiDecimator"], [[2.0, 2.0, 2.0]])

    def test_other_units_are_untouched(self) -> None:
        text, _ = scale_unit_instances(OBJECTS, {"PsiDecimator"}, 2.0)
        scales = unit_scales(text)
        self.assertEqual(scales["Predator"], [[1.0, 1.0, 1.0]])
        self.assertEqual(scales["SporeCannon"], [[1.5, 1.5, 1.5]])

    def test_only_the_scale_attribute_changes(self) -> None:
        text, _ = scale_unit_instances(OBJECTS, {"PsiDecimator"}, 2.0)
        expected = OBJECTS.replace(
            'Position="120,124,0" Scale="1,1,1"', 'Position="120,124,0" Scale="2.0000,2.0000,2.0000"'
        )
        self.assertEqual(text, expected)

    def test_doodad_with_the_same_type_is_untouched(self) -> None:
        text, _ = scale_unit_instances(OBJECTS, {"PsiDecimator"}, 2.0)
        self.assertIn('<ObjectDoodad Id="4" Position="1,1,0" Scale="2,2,2" Type="PsiDecimator"/>', text)

    def test_non_uniform_scale_is_multiplied_per_axis(self) -> None:
        source = '<ObjectUnit Id="2" Scale="1,2,3" UnitType="PsiDecimator" Player="7"/>'
        text, _ = scale_unit_instances(source, {"PsiDecimator"}, 2.0)
        self.assertEqual(unit_scales(text)["PsiDecimator"], [[2.0, 4.0, 6.0]])

    def test_no_match_changes_nothing(self) -> None:
        text, changed = scale_unit_instances(OBJECTS, {"Missing"}, 2.0)
        self.assertEqual(changed, 0)
        self.assertEqual(text, OBJECTS)

    def test_missing_scale_attribute_fails(self) -> None:
        source = '<ObjectUnit Id="2" Position="1,1,0" UnitType="PsiDecimator" Player="7"/>'
        with self.assertRaises(ValueError):
            scale_unit_instances(source, {"PsiDecimator"}, 2.0)


class ScalePsiDestroyerTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.map_dir = Path(self._tmp.name)
        self.objects = self.map_dir / "Objects"

    def test_factor_is_two(self) -> None:
        self.assertEqual(PSI_DESTROYER_SCALE, 2.0)
        self.assertEqual(PSI_DESTROYER_UNITS, {"PsiDecimator"})

    def test_map_objects_are_scaled_and_marked(self) -> None:
        self.objects.write_text(OBJECTS, encoding="utf-8")
        self.assertEqual(scale_psi_destroyer(self.map_dir), 1)
        scales = unit_scales(self.objects.read_text(encoding="utf-8"))
        self.assertEqual(scales["PsiDecimator"], [[PSI_DESTROYER_SCALE] * 3])
        self.assertEqual(scales["Predator"], [[1.0, 1.0, 1.0]])
        self.assertTrue((self.map_dir / PSI_DESTROYER_MARKER).is_file())

    def test_second_run_does_not_scale_again(self) -> None:
        self.objects.write_text(OBJECTS, encoding="utf-8")
        scale_psi_destroyer(self.map_dir)
        once = self.objects.read_text(encoding="utf-8")
        self.assertEqual(scale_psi_destroyer(self.map_dir), 0)
        self.assertEqual(self.objects.read_text(encoding="utf-8"), once)

    def test_absent_unit_fails_and_writes_nothing(self) -> None:
        source = OBJECTS.replace('UnitType="PsiDecimator"', 'UnitType="Marine"')
        self.objects.write_text(source, encoding="utf-8")
        with self.assertRaises(ValueError):
            scale_psi_destroyer(self.map_dir)
        self.assertEqual(self.objects.read_text(encoding="utf-8"), source)
        self.assertFalse((self.map_dir / PSI_DESTROYER_MARKER).exists())


class BuiltMapTest(unittest.TestCase):
    @unittest.skipUnless(BUILT_OBJECTS.is_file(), "built map is absent")
    def test_built_scale_is_source_scale_times_factor(self) -> None:
        source = unit_scales(SRC_OBJECTS.read_text(encoding="utf-8"))
        built = unit_scales(BUILT_OBJECTS.read_text(encoding="utf-8"))
        for unit_type in PSI_DESTROYER_UNITS:
            self.assertEqual(len(source[unit_type]), 1, unit_type)
            expected = [[v * PSI_DESTROYER_SCALE for v in scale] for scale in source[unit_type]]
            self.assertEqual(built[unit_type], expected, unit_type)

    @unittest.skipUnless(BUILT_OBJECTS.is_file(), "built map is absent")
    def test_built_units_outside_the_step_keep_source_scale(self) -> None:
        # Spores have their own scale step, so they are excluded here.
        from spore_scale import SPORE_UNITS

        source = unit_scales(SRC_OBJECTS.read_text(encoding="utf-8"))
        built = unit_scales(BUILT_OBJECTS.read_text(encoding="utf-8"))
        skipped = PSI_DESTROYER_UNITS | SPORE_UNITS
        checked = 0
        for unit_type, scales in source.items():
            if unit_type in skipped:
                continue
            self.assertEqual(built[unit_type], scales, unit_type)
            checked += 1
        self.assertGreater(checked, 0)


if __name__ == "__main__":
    unittest.main()
