import json
import unittest

import numpy as np

from variation_engine.analysis.timbre import calculate_timbre_metrics


class TimbreMetricsTest(unittest.TestCase):
    def test_bright_sample_has_higher_centroid_than_dark_sample(self) -> None:
        sample_rate = 22050
        time = np.arange(sample_rate, dtype=np.float64) / sample_rate
        dark = 0.5 * np.sin(2.0 * np.pi * 220.0 * time)
        bright = 0.5 * np.sin(2.0 * np.pi * 4000.0 * time)

        dark_metrics = calculate_timbre_metrics(dark, sample_rate)
        bright_metrics = calculate_timbre_metrics(bright, sample_rate)

        self.assertGreater(bright_metrics.spectral_centroid, dark_metrics.spectral_centroid)

    def test_metrics_are_plain_json_numbers(self) -> None:
        sample_rate = 22050
        time = np.arange(sample_rate, dtype=np.float64) / sample_rate
        audio = 0.5 * np.sin(2.0 * np.pi * 440.0 * time)

        metrics = calculate_timbre_metrics(audio, sample_rate)
        payload = {
            "spectral_centroid": metrics.spectral_centroid,
            "spectral_bandwidth": metrics.spectral_bandwidth,
            "spectral_rolloff": metrics.spectral_rolloff,
            "spectral_flatness": metrics.spectral_flatness,
            "spectral_contrast_mean": metrics.spectral_contrast_mean,
        }

        json.dumps(payload)
        for value in payload.values():
            self.assertIsInstance(value, float)

    def test_silent_sample_returns_zero_metrics(self) -> None:
        metrics = calculate_timbre_metrics(np.zeros(1024, dtype=np.float32), sample_rate=22050)

        self.assertEqual(metrics.spectral_centroid, 0.0)
        self.assertEqual(metrics.spectral_bandwidth, 0.0)
        self.assertEqual(metrics.spectral_rolloff, 0.0)
        self.assertEqual(metrics.spectral_flatness, 0.0)
        self.assertEqual(metrics.spectral_contrast_mean, 0.0)


if __name__ == "__main__":
    unittest.main()
