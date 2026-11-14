from __future__ import annotations

import unittest
from types import SimpleNamespace

from project_root import project_root
from slow_death_assets import (
    BLOCK_KINDS,
    PARTICLE_ANIMATED,
    PARTICLE_PLAIN,
    RIBBON_ANIMATED,
    RIBBON_PLAIN,
    SDR3_KIND,
    SLOW_DEATHS,
    keyframe_blocks,
    retime_model,
    scaled,
)

MAP = project_root() / "out" / "SCOBA256.SC2Map"
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
            self.assertEqual(list(rows), ["Death"])
            self.assertEqual(rows["Death"]["dur"] % stretch, 0)
            self.assertGreaterEqual(rows["Death"]["dur"], 1000 * stretch)


if __name__ == "__main__":
    unittest.main()
