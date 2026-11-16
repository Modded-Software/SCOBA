from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET

from footfall.fx import (
    FOOTFALL_UNITS,
    NO_ADDON,
    Foot,
    add_points,
    event_name,
    filters_xml,
    fx_actors_xml,
    fx_models_xml,
    merge_block,
    model_events_xml,
    sound_xml,
    unit_on_xml,
)


class Desc:
    def createInstance(self):
        return Node()


class Node:
    def __init__(self, **fields):
        self.structureDescription = DESC
        self.fields = dict(fields)
        for k, v in fields.items():
            setattr(self, k, v)


DESC = Desc()
_ids = iter(range(1, 10000))


def track(init):
    return Node(header=Node(animId=next(_ids)), initValue=init, nullValue=Node(**init.fields))


def bone(name, parent):
    return Node(
        name=name,
        parent=parent,
        location=track(Node(x=1.0, y=2.0, z=3.0)),
        rotation=track(Node(x=0.5, y=0.5, z=0.5, w=0.5)),
        scale=track(Node(x=1.0, y=1.0, z=1.0)),
        ar1=Node(header=Node(animId=next(_ids)), initValue=1, nullValue=1),
    )


FEET = (Foot("Bone Foot L", "Left"), Foot("Bone Foot R", "Right"), Foot("Bone Leg", "03"))


def fake_model():
    bones = [bone("Bone Root", -1), bone("Bone Foot L", 0), bone("Bone Foot R", 0), bone("Bone Leg", 0), bone("Ref_Center", 0)]
    return Node(
        bones=bones,
        absoluteInverseBoneRestPositions=[Node(matrix=i) for i in range(5)],
        attachmentPoints=[Node(name="Ref_Center", boneIndex=4, unknown=-1)],
        attachmentPointAddons=[NO_ADDON],
    )


def parse(entries: str) -> ET.Element:
    return ET.fromstring("<Catalog>" + entries + "</Catalog>")


class AddPointsTest(unittest.TestCase):
    def test_each_point_has_own_bone_under_foot(self):
        model = fake_model()
        add_points(model, FEET)
        names = [b.name for b in model.bones]
        for foot in FEET:
            point = next(p for p in model.attachmentPoints if p.name == foot.point)
            self.assertEqual(names[point.boneIndex], foot.point)
            self.assertEqual(model.bones[point.boneIndex].parent, names.index(foot.bone))

    def test_new_bone_is_zero_offset_identity(self):
        model = fake_model()
        add_points(model, FEET)
        new = model.bones[-1]
        loc, rot = new.location.initValue, new.rotation.initValue
        self.assertEqual((loc.x, loc.y, loc.z), (0.0, 0.0, 0.0))
        self.assertEqual((rot.x, rot.y, rot.z, rot.w), (0.0, 0.0, 0.0, 1.0))

    def test_template_bone_unchanged(self):
        model = fake_model()
        add_points(model, FEET)
        self.assertEqual(model.bones[4].location.initValue.x, 1.0)
        self.assertEqual(model.bones[4].name, "Ref_Center")

    def test_new_anim_ids_unique(self):
        model = fake_model()
        add_points(model, FEET)
        ids = [t.header.animId for b in model.bones for t in (b.location, b.rotation, b.scale, b.ar1)]
        self.assertEqual(len(ids), len(set(ids)))

    def test_counts_stay_parallel(self):
        model = fake_model()
        add_points(model, FEET)
        self.assertEqual(len(model.absoluteInverseBoneRestPositions), len(model.bones))
        self.assertEqual(len(model.attachmentPointAddons), len(model.attachmentPoints))

    def test_second_run_rejected(self):
        model = fake_model()
        add_points(model, FEET)
        with self.assertRaises(ValueError):
            add_points(model, FEET)


class TableTest(unittest.TestCase):
    def test_goliath_two_feet_queen_six(self):
        feet = {spec.unit: len(spec.feet) for spec in FOOTFALL_UNITS}
        self.assertEqual(feet, {"Goliath": 2, "Queen": 6})

    def test_queen_lighter_and_smaller_than_goliath(self):
        goliath, queen = (next(s for s in FOOTFALL_UNITS if s.unit == u) for u in ("Goliath", "Queen"))
        self.assertLess(queen.dust[1], goliath.dust[0])
        self.assertLess(queen.splash[1], goliath.splash[0])
        self.assertLess(queen.sound.volume[1], goliath.sound.volume[0])
        self.assertNotEqual(queen.sound.files, goliath.sound.files)

    def test_attach_points_unique_per_unit(self):
        for spec in FOOTFALL_UNITS:
            points = [f.point for f in spec.feet]
            self.assertEqual(len(points), len(set(points)), spec.unit)

    def test_left_right_use_stock_filters_index_gets_own(self):
        self.assertEqual(Foot("b", "Left").filter_id("Goliath"), "AMFilterHardpointLeft")
        self.assertEqual(Foot("b", "04").filter_id("Queen"), "ScobaAMFilterQueenFoot04")


class XmlTest(unittest.TestCase):
    spec = next(s for s in FOOTFALL_UNITS if s.unit == "Queen")

    def test_events_one_per_contact(self):
        times = [[0.1, 0.5], [0.2], [0.3], [0.4], [0.6], [0.7]]
        events = parse(model_events_xml(self.spec, times)).findall("Events")
        self.assertEqual(len(events), 7)
        self.assertEqual([e.find("Name").get("value") for e in events][:2], [event_name(0)] * 2)
        self.assertTrue(all(e.find("Type").get("value") == "Custom" for e in events))

    def test_index_filter_selects_hardpoint_index(self):
        filters = parse(filters_xml(self.spec)).findall("CAttachMethodFilter")
        self.assertEqual(len(filters), 6)
        keys = filters[2].findall("Keys")
        self.assertEqual([(k.get("Keyword"), k.get("Index")) for k in keys], [("Hardpoint", "3")])
        goliath = next(s for s in FOOTFALL_UNITS if s.unit == "Goliath")
        self.assertEqual(filters_xml(goliath), "")  # negative: stock filters, none added

    def test_every_created_actor_is_defined(self):
        defined = {e.get("id") for e in parse(fx_actors_xml(self.spec))}
        ons = parse('<CActorUnit id="Queen">' + unit_on_xml(self.spec) + "</CActorUnit>").find("CActorUnit").findall("On")
        created = {o.get("Send").split(" ", 1)[1] for o in ons if o.get("Send").startswith("Create ")}
        self.assertTrue(created)
        self.assertLessEqual(created, defined)

    def test_splash_only_in_water_dust_only_dry_sound_always(self):
        ons = parse('<CActorUnit id="Queen">' + unit_on_xml(self.spec) + "</CActorUnit>").find("CActorUnit").findall("On")
        first = [o for o in ons if f"ModelEventName {event_name(0)}" in o.get("Terms")]
        by_send = {o.get("Send"): o.get("Terms") for o in first}
        self.assertIn("IsStatus ScobaInWater 1", by_send["Create QueenFootSplash1"])
        self.assertIn("IsStatus ScobaInWater 0", by_send["Create QueenFootDust1"])
        self.assertNotIn("IsStatus", by_send["Create QueenFootSound1"])
        # Negative: no engine water-material gate (it stopped all splashes).
        self.assertFalse([o for o in ons if "TerrainPhysicsMaterial" in o.get("Terms")])

    def test_engine_ripples_switched_off(self):
        ons = parse('<CActorUnit id="Queen">' + unit_on_xml(self.spec) + "</CActorUnit>").find("CActorUnit").findall("On")
        off = {o.get("Terms") for o in ons if o.get("Send") == "TerrainSquibDeactivate"}
        self.assertEqual(off, {"ActorCreation", "UnitBirth.Queen"})

    def test_effect_models_and_sound(self):
        models = parse(fx_models_xml(self.spec))
        dust = models.find("CModel[@id='QueenFootDust']")
        self.assertEqual(dust.find("ScaleMin").get("value").split(",")[0], f"{self.spec.dust[0]:.6f}")
        sound = parse(sound_xml(self.spec)).find("CSound[@id='QueenFootstep']")
        self.assertEqual(len(sound.findall("AssetArray")), len(self.spec.sound.files))


class MergeTest(unittest.TestCase):
    def test_existing_block_keeps_fields_and_gains_inner(self):
        text = '<Catalog>\n    <CModel id="Goliath">\n        <ScaleMax value="1"/>\n    </CModel>\n</Catalog>\n'
        out = merge_block(text, "CModel", "Goliath", "        <Events/>\n")
        node = ET.fromstring(out).find("CModel[@id='Goliath']")
        self.assertIsNotNone(node.find("ScaleMax"))
        self.assertIsNotNone(node.find("Events"))
        self.assertEqual(len(ET.fromstring(out).findall("CModel")), 1)

    def test_missing_block_appended(self):
        out = merge_block("<Catalog>\n</Catalog>\n", "CModel", "Queen", "        <Events/>\n")
        self.assertIsNotNone(ET.fromstring(out).find("CModel[@id='Queen']/Events"))

    def test_other_ids_untouched(self):
        text = '<Catalog>\n    <CModel id="GoliathDeath">\n    </CModel>\n</Catalog>\n'
        out = merge_block(text, "CModel", "Goliath", "        <Events/>\n")
        root = ET.fromstring(out)
        self.assertIsNone(root.find("CModel[@id='GoliathDeath']/Events"))
        self.assertIsNotNone(root.find("CModel[@id='Goliath']/Events"))


if __name__ == "__main__":
    unittest.main()
