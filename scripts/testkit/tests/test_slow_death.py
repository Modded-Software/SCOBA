from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace

from project_root import project_root
from slow_death_assets import (
    BLOCK_KINDS,
    FAST_CLIPS,
    PARTICLE_ANIMATED,
    PARTICLE_PLAIN,
    RIBBON_ANIMATED,
    RIBBON_PLAIN,
    SDR3_KIND,
    SLOW_DEATHS,
    SLOW_SIMULATIONS,
    keyframe_blocks,
    retime_model,
    scaled,
    speed_up_clips,
)

MAP = project_root() / "out" / "SCOBA256.SC2Map"
GOLIATH_SLOW = Path("Assets") / "Units" / "Terran" / "GoliathDeath" / "GoliathDeathSlow.m3"
RATE_ID = 0x1111


def block(frames, keys, fend):
    return SimpleNamespace(frames=list(frames), keys=list(keys), fend=fend)


def reference(value, anim_id=0):
    return SimpleNamespace(initValue=value, nullValue=value, header=SimpleNamespace(animId=anim_id))


def emitter(animated, plain):
    fields = {name: reference(2.0) for name in animated}
    fields.update({name: 2.0 for name in plain})
    return SimpleNamespace(**fields)


def fake_model():
    stc = SimpleNamespace(**{kind: [] for kind in BLOCK_KINDS})
    stc.sd3v = [block([0, 100, 200], ["a", "b", "c"], 200)]
    stc.sdr3 = [block([0, 400], [10.0, 20.0], 400)]
    stc.animIds = [RATE_ID]
    stc.animRefs = [(SDR3_KIND << 16) | 0]
    particle = emitter(PARTICLE_ANIMATED, PARTICLE_PLAIN)
    particle.emissionRate = reference(2.0, RATE_ID)
    return SimpleNamespace(
        sequences=[SimpleNamespace(animStartInMS=0, animEndInMS=1000)],
        sequenceTransformationCollections=[stc],
        particles=[particle],
        ribbons=[emitter(RIBBON_ANIMATED, RIBBON_PLAIN)],
        lights=[],
        forces=[],
        bones=[],
    )


class RetimeTest(unittest.TestCase):
    def test_powers(self) -> None:
        self.assertEqual(scaled(2.0, 1, 4), 8.0)
        self.assertEqual(scaled(2.0, -1, 4), 0.5)
        self.assertEqual(scaled(2.0, -2, 4), 0.125)

    def test_every_block_kind_is_stretched(self) -> None:
        # One block per kind: each must be found and stretched exactly once.
        model = fake_model()
        stc = SimpleNamespace(
            **{kind: [block([index + 1], ["k"], index + 1)] for index, kind in enumerate(BLOCK_KINDS)}
        )
        stc.animIds = []
        stc.animRefs = []
        model.sequenceTransformationCollections = [stc]
        self.assertEqual(len(keyframe_blocks(stc)), len(BLOCK_KINDS))
        counts = retime_model(model, 4)
        self.assertEqual(counts["blocks"], len(BLOCK_KINDS))
        for index, blocks in enumerate(keyframe_blocks(stc)):
            self.assertEqual(blocks[0].frames, [(index + 1) * 4])
            self.assertEqual(blocks[0].fend, (index + 1) * 4)

    def test_every_emitter_field_is_scaled(self) -> None:
        # Every field in the power tables moves by its power, none is skipped.
        model = fake_model()
        retime_model(model, 4)
        emitter_fields = model.particles[0]
        ribbon_fields = model.ribbons[0]
        particle_animated = {
            "emissionSpeed1": emitter_fields.emissionSpeed1,
            "emissionSpeed2": emitter_fields.emissionSpeed2,
            "lifespan1": emitter_fields.lifespan1,
            "lifespan2": emitter_fields.lifespan2,
            "emissionRate": emitter_fields.emissionRate,
            "trailingParticlesRate": emitter_fields.trailingParticlesRate,
        }
        particle_plain = {
            "zAcceleration": emitter_fields.zAcceleration,
            "drag": emitter_fields.drag,
            "noiseFrequency": emitter_fields.noiseFrequency,
        }
        ribbon_animated = {"speed": ribbon_fields.speed, "lifespan": ribbon_fields.lifespan}
        ribbon_plain = {
            "gravity": ribbon_fields.gravity,
            "drag": ribbon_fields.drag,
            "surfaceNoiseFrequency": ribbon_fields.surfaceNoiseFrequency,
        }
        # A field added to a power table must be added here too.
        self.assertEqual(set(particle_animated), set(PARTICLE_ANIMATED))
        self.assertEqual(set(particle_plain), set(PARTICLE_PLAIN))
        self.assertEqual(set(ribbon_animated), set(RIBBON_ANIMATED))
        self.assertEqual(set(ribbon_plain), set(RIBBON_PLAIN))
        for name, power in PARTICLE_ANIMATED.items():
            self.assertEqual(particle_animated[name].initValue, scaled(2.0, power, 4), name)
            self.assertEqual(particle_animated[name].nullValue, scaled(2.0, power, 4), name)
        for name, power in PARTICLE_PLAIN.items():
            self.assertEqual(particle_plain[name], scaled(2.0, power, 4), name)
        for name, power in RIBBON_ANIMATED.items():
            self.assertEqual(ribbon_animated[name].initValue, scaled(2.0, power, 4), name)
        for name, power in RIBBON_PLAIN.items():
            self.assertEqual(ribbon_plain[name], scaled(2.0, power, 4), name)

    def test_sequence_and_keyframes_stretch(self) -> None:
        model = fake_model()
        retime_model(model, 4)
        stc = model.sequenceTransformationCollections[0]
        self.assertEqual(model.sequences[0].animEndInMS, 4000)
        self.assertEqual(stc.sd3v[0].frames, [0, 400, 800])
        self.assertEqual(stc.sd3v[0].fend, 800)
        self.assertEqual(stc.sd3v[0].keys, ["a", "b", "c"])

    def test_emitters_match_the_stretch(self) -> None:
        model = fake_model()
        retime_model(model, 4)
        particle = model.particles[0]
        ribbon = model.ribbons[0]
        self.assertEqual(particle.lifespan1.initValue, 8.0)
        self.assertEqual(particle.emissionSpeed1.initValue, 0.5)
        self.assertEqual(particle.emissionRate.nullValue, 0.5)
        self.assertEqual(particle.zAcceleration, 0.125)
        self.assertEqual(ribbon.lifespan.initValue, 8.0)
        self.assertEqual(ribbon.speed.initValue, 0.5)
        self.assertEqual(ribbon.gravity, 0.125)

    def test_keyed_rate_scales_once(self) -> None:
        model = fake_model()
        retime_model(model, 4)
        self.assertEqual(model.sequenceTransformationCollections[0].sdr3[0].keys, [2.5, 5.0])

    def test_particle_count_is_kept(self) -> None:
        # rate x lifespan is the live particle count; the stretch must not change it.
        model = fake_model()
        before = model.particles[0].emissionRate.initValue * model.particles[0].lifespan1.initValue
        retime_model(model, 4)
        after = model.particles[0].emissionRate.initValue * model.particles[0].lifespan1.initValue
        self.assertEqual(before, after)

    def test_child_stretch_is_separate(self) -> None:
        # Keyframes follow the stretch; the emitter simulation follows the child stretch.
        model = fake_model()
        retime_model(model, 4, 2)
        stc = model.sequenceTransformationCollections[0]
        particle = model.particles[0]
        self.assertEqual(model.sequences[0].animEndInMS, 4000)
        self.assertEqual(stc.sd3v[0].frames, [0, 400, 800])
        self.assertEqual(stc.sdr3[0].frames, [0, 1600])
        self.assertEqual(stc.sdr3[0].keys, [5.0, 10.0])
        self.assertEqual(particle.lifespan1.initValue, 4.0)
        self.assertEqual(particle.emissionSpeed1.initValue, 1.0)
        self.assertEqual(particle.zAcceleration, 0.5)
        self.assertEqual(model.ribbons[0].lifespan.initValue, 4.0)

    def test_fractional_child_stretch(self) -> None:
        # 12.5 is half of 25: the children run 2x faster; the keyframes keep the stretch.
        model = fake_model()
        retime_model(model, 100, 12.5)
        stc = model.sequenceTransformationCollections[0]
        particle = model.particles[0]
        self.assertEqual(model.sequences[0].animEndInMS, 100000)
        self.assertEqual(stc.sd3v[0].frames, [0, 10000, 20000])
        self.assertEqual(stc.sdr3[0].keys, [0.8, 1.6])
        self.assertEqual(particle.lifespan1.initValue, 25.0)
        self.assertEqual(particle.emissionSpeed1.initValue, 0.16)
        self.assertEqual(particle.zAcceleration, 2.0 / 156.25)
        self.assertEqual(model.ribbons[0].lifespan.initValue, 25.0)

    def test_configured_children_are_twice_as_fast(self) -> None:
        # Negative: the hull stretch must stay 100; only the child stretch halves.
        bc = [(stretch, child) for _, target, stretch, child in SLOW_DEATHS if target.name == "BattlecruiserLokiDeathSlow.m3"]
        self.assertEqual(bc, [(100, 12.5)])

    def test_tentacle_simulation_matches_anim_speed(self) -> None:
        # 40 = 1 / AnimSpeed 0.025; negative: no keyframe stretch (stretch 1 in generate).
        self.assertEqual([(target.name, sim) for _, target, sim in SLOW_SIMULATIONS], [("LeviathanTentacleSlow.m3", 40)])
        model = fake_model()
        retime_model(model, 1, 40)
        self.assertEqual(model.sequences[0].animEndInMS, 1000)
        self.assertEqual(model.ribbons[0].speed.initValue, 2.0 / 40)
        self.assertEqual(model.ribbons[0].gravity, 2.0 / 1600)

    def test_speed_up_named_clip_only(self) -> None:
        # Stand shrinks 3x; negative: the Walk clip and sequence keep their times.
        stand = SimpleNamespace(name="Stand_full", **{kind: [] for kind in BLOCK_KINDS})
        stand.sd3v = [block([0, 33, 3000], ["a", "b", "c"], 3000)]
        walk = SimpleNamespace(name="Walk_full", **{kind: [] for kind in BLOCK_KINDS})
        walk.sd3v = [block([0, 3000], ["a", "b"], 3000)]
        model = SimpleNamespace(
            sequences=[
                SimpleNamespace(name="Stand", animStartInMS=0, animEndInMS=3000),
                SimpleNamespace(name="Walk", animStartInMS=0, animEndInMS=3000),
            ],
            sequenceTransformationCollections=[stand, walk],
        )
        self.assertEqual(speed_up_clips(model, ("Stand",), 3), 1)
        self.assertEqual(model.sequences[0].animEndInMS, 1000)
        self.assertEqual(stand.sd3v[0].frames, [0, 11, 1000])
        self.assertEqual(stand.sd3v[0].fend, 1000)
        self.assertEqual(model.sequences[1].animEndInMS, 3000)
        self.assertEqual(walk.sd3v[0].frames, [0, 3000])

    def test_speed_up_missing_clip_fails(self) -> None:
        model = SimpleNamespace(sequences=[], sequenceTransformationCollections=[])
        with self.assertRaises(ValueError):
            speed_up_clips(model, ("Stand",), 3)

    def test_leviathan_stand_is_three_times_faster(self) -> None:
        self.assertEqual([(t.name, n, f) for _, t, n, f in FAST_CLIPS], [("LeviathanSCOBA.m3", ("Stand",), 3)])

    @unittest.skipUnless(MAP.is_dir(), "built map is absent")
    def test_built_leviathan_stand_length(self) -> None:
        # Stock leviathan.m3: Stand 3000 ms, Walk 3000 ms, Spell 1833 ms.
        from dump_m3_clip_metrics import frame_rows

        rows = frame_rows(MAP / FAST_CLIPS[0][1])
        self.assertEqual(rows["Stand"]["dur"], 1000)
        self.assertEqual(rows["Walk"]["dur"], 3000)
        self.assertEqual(rows["Spell"]["dur"], 1833)

    def test_goliath_death_is_two_times_slower(self) -> None:
        # Hull and children both 2x; negative: no other stretch for the Goliath.
        goliath = [(stretch, child) for _, target, stretch, child in SLOW_DEATHS if target == GOLIATH_SLOW]
        self.assertEqual(goliath, [(2, 2)])

    def test_child_stretch_below_one_fails(self) -> None:
        with self.assertRaises(ValueError):
            retime_model(fake_model(), 4, 0)

    def test_missing_field_fails(self) -> None:
        model = fake_model()
        del model.ribbons[0].gravity
        with self.assertRaises(ValueError):
            retime_model(model, 4)

    def test_stretch_below_one_fails(self) -> None:
        with self.assertRaises(ValueError):
            retime_model(fake_model(), 0)


class BuiltModelTest(unittest.TestCase):
    @unittest.skipUnless(MAP.is_dir(), "built map is absent")
    def test_built_death_is_stretched(self) -> None:
        from dump_m3_clip_metrics import frame_rows

        for _, relative, stretch, _ in SLOW_DEATHS:
            rows = frame_rows(MAP / relative)
            self.assertTrue(rows)
            for name, row in rows.items():
                self.assertTrue(name.startswith("Death"), name)
                self.assertEqual(row["dur"] % stretch, 0, name)
                self.assertGreaterEqual(row["dur"], 1000 * stretch, name)

    @unittest.skipUnless(MAP.is_dir(), "built map is absent")
    def test_built_goliath_death_is_two_times_stock(self) -> None:
        # Stock GoliathDeath.m3: Death 6667 ms, Death 01 5000 ms, Death 02 5000 ms.
        from dump_m3_clip_metrics import frame_rows

        rows = frame_rows(MAP / GOLIATH_SLOW)
        self.assertEqual({name: row["dur"] for name, row in rows.items()},
                         {"Death": 13334, "Death 01": 10000, "Death 02": 10000})


if __name__ == "__main__":
    unittest.main()
