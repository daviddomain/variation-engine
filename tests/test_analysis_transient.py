import unittest

import numpy as np

from variation_engine.analysis.transient import calculate_transient_metrics


class TransientMetricsTest(unittest.TestCase):
    def test_reports_valid_metrics_for_unclear_attack(self) -> None:
        audio = np.linspace(0.0, 0.4, num=100, dtype=np.float32).reshape(-1, 1)

        metrics = calculate_transient_metrics(audio, sample_rate=1000)

        self.assertGreaterEqual(metrics.onset_time_ms, 0.0)
        self.assertGreater(metrics.attack_duration_ms, 0.0)
        self.assertGreaterEqual(metrics.transient_strength, 0.0)
        self.assertLessEqual(metrics.transient_strength, 1.0)
        self.assertGreaterEqual(metrics.transient_confidence, 0.0)
        self.assertLessEqual(metrics.transient_confidence, 1.0)

    def test_percussive_sample_has_stronger_transient_than_soft_sample(self) -> None:
        percussive = np.concatenate(
            [
                np.zeros(4, dtype=np.float32),
                np.array([1.0], dtype=np.float32),
                np.linspace(0.7, 0.0, num=45, dtype=np.float32),
            ]
        ).reshape(-1, 1)
        soft = np.concatenate(
            [
                np.zeros(4, dtype=np.float32),
                np.linspace(0.0, 1.0, num=46, dtype=np.float32),
            ]
        ).reshape(-1, 1)

        percussive_metrics = calculate_transient_metrics(percussive, sample_rate=1000)
        soft_metrics = calculate_transient_metrics(soft, sample_rate=1000)

        self.assertLess(percussive_metrics.attack_duration_ms, soft_metrics.attack_duration_ms)
        self.assertGreater(percussive_metrics.transient_strength, soft_metrics.transient_strength)


if __name__ == "__main__":
    unittest.main()
