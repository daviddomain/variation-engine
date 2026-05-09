import unittest

import numpy as np

from variation_engine.analysis.pitch import calculate_pitch_metrics


class PitchMetricsTest(unittest.TestCase):
    def test_tonal_sample_estimates_pitch(self) -> None:
        sample_rate = 22050
        time = np.arange(sample_rate, dtype=np.float64) / sample_rate
        audio = 0.5 * np.sin(2.0 * np.pi * 110.0 * time)

        metrics = calculate_pitch_metrics(audio, sample_rate)

        self.assertTrue(metrics.is_probably_pitched)
        self.assertIsNotNone(metrics.estimated_f0_hz)
        self.assertAlmostEqual(metrics.estimated_f0_hz, 110.0, delta=2.0)
        self.assertEqual(metrics.estimated_midi_note, 45)
        self.assertEqual(metrics.estimated_note_name, "A2")
        self.assertGreaterEqual(metrics.pitch_confidence, 0.45)
        self.assertGreaterEqual(metrics.pitch_stability, 0.35)

    def test_noise_sample_does_not_force_pitch(self) -> None:
        rng = np.random.default_rng(1)
        audio = rng.normal(0.0, 0.2, 22050)

        metrics = calculate_pitch_metrics(audio, sample_rate=22050)

        self.assertFalse(metrics.is_probably_pitched)
        self.assertIsNone(metrics.estimated_f0_hz)
        self.assertIsNone(metrics.estimated_midi_note)
        self.assertIsNone(metrics.estimated_note_name)
        self.assertGreaterEqual(metrics.pitch_confidence, 0.0)
        self.assertLessEqual(metrics.pitch_confidence, 1.0)
        self.assertGreaterEqual(metrics.pitch_stability, 0.0)
        self.assertLessEqual(metrics.pitch_stability, 1.0)


if __name__ == "__main__":
    unittest.main()
