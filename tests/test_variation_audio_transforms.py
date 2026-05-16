import unittest
from dataclasses import replace

import numpy as np

from variation_engine.analysis.models import (
    AmplitudeMetrics,
    AnalysisResult,
    FileMetadata,
    PitchMetrics,
    ProfileMetrics,
    TimbreMetrics,
    TransientMetrics,
)
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
            analysis=_analysis(),
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

        brighter = apply_brightness(audio, sample_rate=8000, amount=0.2)
        darker = apply_brightness(audio, sample_rate=8000, amount=-0.2)

        self.assertEqual(brighter.shape, audio.shape)
        self.assertEqual(darker.shape, audio.shape)

    def test_brightness_zero_amount_returns_unchanged_copy(self) -> None:
        audio = _plucked_like_audio(sample_rate=8000)

        transformed = apply_brightness(
            audio,
            sample_rate=8000,
            amount=0.0,
            spectral_centroid=900.0,
            spectral_bandwidth=1100.0,
            spectral_rolloff=1900.0,
        )

        self.assertEqual(transformed.shape, audio.shape)
        np.testing.assert_array_equal(transformed, audio)
        self.assertFalse(np.shares_memory(transformed, audio))

    def test_brightness_positive_and_negative_change_audio_differently(self) -> None:
        audio = _plucked_like_audio(sample_rate=8000)
        presence_band = _analysis_presence_band(
            spectral_centroid=938.0,
            spectral_bandwidth=1304.0,
        )

        brighter = apply_brightness(
            audio,
            sample_rate=8000,
            amount=0.5,
            estimated_f0_hz=124.0,
            spectral_centroid=938.0,
            spectral_bandwidth=1304.0,
            spectral_rolloff=1851.0,
        )
        darker = apply_brightness(
            audio,
            sample_rate=8000,
            amount=-0.5,
            estimated_f0_hz=124.0,
            spectral_centroid=938.0,
            spectral_bandwidth=1304.0,
            spectral_rolloff=1851.0,
        )

        original_presence_energy = _band_energy(
            audio,
            sample_rate=8000,
            frequency_range=presence_band,
        )
        brighter_presence_energy = _band_energy(
            brighter,
            sample_rate=8000,
            frequency_range=presence_band,
        )
        darker_presence_energy = _band_energy(
            darker,
            sample_rate=8000,
            frequency_range=presence_band,
        )

        self.assertGreater(brighter_presence_energy, original_presence_energy * 1.2)
        self.assertLess(darker_presence_energy, original_presence_energy * 0.8)
        self.assertFalse(np.allclose(brighter, darker))

    def test_brightness_uses_analysis_aware_parameters(self) -> None:
        audio = _plucked_like_audio(sample_rate=8000)

        low_presence = apply_brightness(
            audio,
            sample_rate=8000,
            amount=0.5,
            estimated_f0_hz=110.0,
            spectral_centroid=500.0,
            spectral_bandwidth=300.0,
            spectral_rolloff=900.0,
        )
        high_presence = apply_brightness(
            audio,
            sample_rate=8000,
            amount=0.5,
            estimated_f0_hz=330.0,
            spectral_centroid=1800.0,
            spectral_bandwidth=900.0,
            spectral_rolloff=3200.0,
        )

        self.assertFalse(np.allclose(low_presence, high_presence))

    def test_brightness_falls_back_for_missing_or_invalid_analysis_values(self) -> None:
        audio = _plucked_like_audio(sample_rate=8000)

        transformed = apply_brightness(
            audio,
            sample_rate=8000,
            amount=0.5,
            estimated_f0_hz=None,
            spectral_centroid=float("nan"),
            spectral_bandwidth=-1.0,
            spectral_rolloff=float("inf"),
        )

        self.assertEqual(transformed.shape, audio.shape)
        self.assertTrue(np.all(np.isfinite(transformed)))
        self.assertFalse(np.allclose(transformed, audio))

    def test_brightness_preserves_leading_silence_and_transient_position(self) -> None:
        audio = _plucked_like_transient_with_leading_silence(sample_rate=8000)
        input_first_active = _first_active_index(audio)
        input_peak_index = _peak_index(audio)

        for amount in (0.5, -0.5):
            with self.subTest(amount=amount):
                transformed = apply_brightness(
                    audio,
                    sample_rate=8000,
                    amount=amount,
                    estimated_f0_hz=124.0,
                    spectral_centroid=938.0,
                    spectral_bandwidth=1304.0,
                    spectral_rolloff=1851.0,
                )

                self.assertEqual(transformed.shape, audio.shape)
                self.assertLessEqual(float(np.max(np.abs(transformed[:256]))), 1e-7)
                self.assertLessEqual(float(np.max(np.abs(transformed[352:]))), 1e-7)
                self.assertEqual(_first_active_index(transformed), input_first_active)
                self.assertEqual(_peak_index(transformed), input_peak_index)
                self.assertGreater(
                    _window_energy(transformed, input_first_active, length=32),
                    _window_energy(audio, input_first_active, length=32) * 0.5,
                )

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


def _plucked_like_audio(sample_rate: int) -> np.ndarray:
    time = np.arange(sample_rate // 10, dtype=np.float64) / sample_rate
    envelope = np.exp(-time * 12.0)
    left = envelope * (
        0.35 * np.sin(2 * np.pi * 124.0 * time)
        + 0.2 * np.sin(2 * np.pi * 930.0 * time)
        + 0.08 * np.sin(2 * np.pi * 1850.0 * time)
    )
    right = envelope * (
        0.3 * np.sin(2 * np.pi * 124.0 * time)
        + 0.18 * np.sin(2 * np.pi * 1260.0 * time)
        + 0.06 * np.sin(2 * np.pi * 2300.0 * time)
    )
    return np.column_stack([left, right]).astype(np.float32)


def _plucked_like_transient_with_leading_silence(sample_rate: int) -> np.ndarray:
    audio = np.zeros((1024, 1), dtype=np.float32)
    transient_start = 256
    time = np.arange(96, dtype=np.float64) / sample_rate
    envelope = np.exp(-time * 80.0)
    transient = envelope * (
        0.8 * np.sin(2 * np.pi * 124.0 * time)
        + 0.4 * np.sin(2 * np.pi * 1500.0 * time)
    )
    audio[transient_start : transient_start + transient.shape[0], 0] = transient
    return audio


def _analysis_presence_band(
    *,
    spectral_centroid: float,
    spectral_bandwidth: float,
) -> tuple[float, float]:
    presence_center = spectral_centroid * 1.6
    presence_width = spectral_bandwidth * 0.75
    return (
        max(1.0, presence_center - presence_width),
        presence_center + presence_width,
    )


def _band_energy(
    audio: np.ndarray,
    *,
    sample_rate: int,
    frequency_range: tuple[float, float],
) -> float:
    frequencies = np.fft.rfftfreq(audio.shape[0], d=1.0 / sample_rate)
    spectrum = np.fft.rfft(audio.astype(np.float64, copy=False), axis=0)
    power = np.mean(np.abs(spectrum) ** 2, axis=1)
    low_frequency, high_frequency = frequency_range
    band_mask = (frequencies >= low_frequency) & (frequencies <= high_frequency)
    return float(np.sum(power[band_mask]))


def _first_active_index(audio: np.ndarray) -> int:
    envelope = np.max(np.abs(audio), axis=1)
    peak = float(np.max(envelope))
    active_indices = np.flatnonzero(envelope >= peak * 1e-4)
    return int(active_indices[0])


def _peak_index(audio: np.ndarray) -> int:
    return int(np.argmax(np.max(np.abs(audio), axis=1)))


def _window_energy(audio: np.ndarray, start: int, *, length: int) -> float:
    window = audio[start : start + length]
    return float(np.sum(window.astype(np.float64) ** 2))


def _analysis() -> AnalysisResult:
    return AnalysisResult(
        file=FileMetadata(
            path="samples/test.wav",
            sample_rate=44100,
            channels=2,
            duration_seconds=1.0,
            sample_count=44100,
        ),
        amplitude=AmplitudeMetrics(
            peak_amplitude=0.8,
            rms=0.2,
            crest_factor=4.0,
            leading_silence_ms=0.0,
            trailing_silence_ms=0.0,
        ),
        transient=TransientMetrics(
            onset_time_ms=5.0,
            attack_duration_ms=12.0,
            transient_strength=0.6,
            transient_confidence=0.7,
        ),
        pitch=PitchMetrics(
            estimated_f0_hz=124.0,
            estimated_midi_note=47,
            estimated_note_name="B2",
            pitch_confidence=0.6,
            is_probably_pitched=True,
            pitch_stability=0.9,
        ),
        timbre=TimbreMetrics(
            spectral_centroid=938.0,
            spectral_bandwidth=1304.0,
            spectral_rolloff=1851.0,
            spectral_flatness=0.34,
            spectral_contrast_mean=13.0,
        ),
        profile=ProfileMetrics(
            suggested_profile="tonal_percussive",
            confidence=0.75,
            reasons=[],
        ),
    )


if __name__ == "__main__":
    unittest.main()
