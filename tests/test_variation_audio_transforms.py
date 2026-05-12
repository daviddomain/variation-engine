import unittest
from dataclasses import replace

import numpy as np

from variation_engine.variation.audio_transforms import (
    apply_attack_envelope,
    apply_brightness,
    apply_decay_envelope,
    apply_micropitch,
    apply_plucked_string_transforms,
    apply_stereo_balance,
    limit_peak,
)
from variation_engine.variation.renderer import build_source_round_robin_instructions


class VariationAudioTransformsTest(unittest.TestCase):
    def test_transforms_preserve_length_and_channel_count(self) -> None:
        audio = _stereo_impulse()
        instruction = replace(
            build_source_round_robin_instructions(seed=0)[0],
            recipe_id="plucked_string",
            micropitch_cents=3.0,
            attack_amount=-0.1,
            brightness_amount=0.15,
            decay_amount=-0.05,
            stereo_balance_amount=0.04,
        )

        transformed = apply_plucked_string_transforms(
            audio,
            sample_rate=1000,
            instruction=instruction,
        )

        self.assertEqual(transformed.shape, audio.shape)

    def test_micropitch_preserves_shape_for_mono_input(self) -> None:
        audio = np.linspace(-0.5, 0.5, 32, dtype=np.float32).reshape(-1, 1)

        transformed = apply_micropitch(audio, cents=-4.0)

        self.assertEqual(transformed.shape, audio.shape)
        self.assertEqual(transformed.shape[1], 1)

    def test_attack_envelope_changes_only_start_area(self) -> None:
        audio = np.ones((12, 1), dtype=np.float32)

        transformed = apply_attack_envelope(audio, sample_rate=1000, amount=-0.1)

        self.assertEqual(transformed.shape, audio.shape)
        self.assertLess(transformed[0, 0], audio[0, 0])
        self.assertAlmostEqual(float(transformed[-1, 0]), 1.0)

    def test_brightness_preserves_shape_for_positive_and_negative_amounts(self) -> None:
        audio = _stereo_impulse()

        brighter = apply_brightness(audio, amount=0.2)
        darker = apply_brightness(audio, amount=-0.2)

        self.assertEqual(brighter.shape, audio.shape)
        self.assertEqual(darker.shape, audio.shape)

    def test_decay_envelope_preserves_length_and_changes_tail(self) -> None:
        audio = np.ones((24, 2), dtype=np.float32)

        transformed = apply_decay_envelope(audio, sample_rate=1000, amount=-0.08)

        self.assertEqual(transformed.shape, audio.shape)
        self.assertLess(transformed[-1, 0], audio[-1, 0])

    def test_stereo_balance_keeps_mono_unchanged(self) -> None:
        audio = np.array([[0.25], [0.5], [-0.25]], dtype=np.float32)

        transformed = apply_stereo_balance(audio, amount=0.08)

        self.assertEqual(transformed.shape, audio.shape)
        np.testing.assert_array_equal(transformed, audio)

    def test_stereo_balance_preserves_stereo_shape(self) -> None:
        audio = np.array([[0.5, 0.5], [0.25, -0.25]], dtype=np.float32)

        transformed = apply_stereo_balance(audio, amount=0.08)

        self.assertEqual(transformed.shape, audio.shape)
        self.assertGreater(transformed[0, 0], audio[0, 0])
        self.assertLess(transformed[0, 1], audio[0, 1])

    def test_limit_peak_prevents_clipping(self) -> None:
        audio = np.array([[1.5, -1.25], [0.5, -0.5]], dtype=np.float32)

        transformed = limit_peak(audio)

        self.assertLessEqual(float(np.max(np.abs(transformed))), 1.0)


def _stereo_impulse() -> np.ndarray:
    audio = np.zeros((32, 2), dtype=np.float32)
    audio[0, 0] = 0.5
    audio[1, 1] = -0.35
    audio[8:, 0] = 0.1
    audio[8:, 1] = -0.08
    return audio


if __name__ == "__main__":
    unittest.main()
