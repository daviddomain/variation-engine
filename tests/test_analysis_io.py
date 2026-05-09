import tempfile
import unittest
from pathlib import Path

import numpy as np
import soundfile as sf

from variation_engine.analysis.io import analyze_audio_file, calculate_amplitude_metrics


class AmplitudeMetricsTest(unittest.TestCase):
    def test_calculates_peak_rms_and_crest_factor(self) -> None:
        audio = np.array([[0.0], [0.5], [-1.0], [0.5]], dtype=np.float32)

        metrics = calculate_amplitude_metrics(audio, sample_rate=1000)

        self.assertEqual(metrics.peak_amplitude, 1.0)
        self.assertEqual(metrics.rms, round(float(np.sqrt(0.375)), 6))
        self.assertEqual(metrics.crest_factor, round(1.0 / float(np.sqrt(0.375)), 6))

    def test_detects_leading_and_trailing_silence(self) -> None:
        audio = np.array([[0.0], [0.0], [0.2], [0.0]], dtype=np.float32)

        metrics = calculate_amplitude_metrics(audio, sample_rate=1000)

        self.assertEqual(metrics.leading_silence_ms, 2.0)
        self.assertEqual(metrics.trailing_silence_ms, 1.0)

    def test_uses_any_audible_channel_for_stereo_silence_detection(self) -> None:
        audio = np.array(
            [
                [0.0, 0.0],
                [0.0, 0.2],
                [0.0, 0.0],
            ],
            dtype=np.float32,
        )

        metrics = calculate_amplitude_metrics(audio, sample_rate=1000)

        self.assertEqual(metrics.leading_silence_ms, 1.0)
        self.assertEqual(metrics.trailing_silence_ms, 1.0)


class AnalyzeAudioFileTest(unittest.TestCase):
    def test_result_keeps_file_section_and_adds_analysis_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "sample.wav"
            sf.write(path, np.array([0.0, 0.5, 0.0], dtype=np.float32), 1000)

            result = analyze_audio_file(path).to_dict()

        self.assertIn("file", result)
        self.assertIn("amplitude", result)
        self.assertIn("transient", result)
        self.assertIn("pitch", result)
        self.assertIn("sample_rate", result["file"])
        self.assertIn("peak_amplitude", result["amplitude"])
        self.assertIn("onset_time_ms", result["transient"])
        self.assertIn("pitch_confidence", result["pitch"])

    def test_file_with_leading_silence_reports_more_leading_silence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            no_silence_path = Path(tmp_dir) / "no-silence.wav"
            leading_silence_path = Path(tmp_dir) / "leading-silence.wav"
            sf.write(no_silence_path, np.array([0.5, 0.0], dtype=np.float32), 1000)
            sf.write(leading_silence_path, np.array([0.0, 0.0, 0.5], dtype=np.float32), 1000)

            no_silence = analyze_audio_file(no_silence_path).amplitude.leading_silence_ms
            leading_silence = analyze_audio_file(leading_silence_path).amplitude.leading_silence_ms

        self.assertGreater(leading_silence, no_silence)


if __name__ == "__main__":
    unittest.main()
