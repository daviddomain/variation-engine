import unittest

from variation_engine.analysis.models import (
    AmplitudeMetrics,
    FileMetadata,
    PitchMetrics,
    TimbreMetrics,
    TransientMetrics,
)
from variation_engine.analysis.profile import suggest_profile


class ProfileHeuristicTest(unittest.TestCase):
    def test_suggests_percussive_for_short_transient_unpitched_sample(self) -> None:
        profile = suggest_profile(
            file=_file(duration_seconds=0.25),
            amplitude=_amplitude(),
            transient=_transient(transient_strength=0.82, attack_duration_ms=4.0),
            pitch=_pitch(pitch_confidence=0.12, is_probably_pitched=False),
            timbre=_timbre(spectral_flatness=0.03),
        )

        self.assertEqual(profile.suggested_profile, "percussive")
        self.assertGreater(profile.confidence, 0.0)
        self.assertIn("strong transient", profile.reasons)
        self.assertIn("short duration", profile.reasons)
        self.assertIn("low pitch confidence", profile.reasons)

    def test_suggests_tonal_percussive_for_transient_pitched_sample(self) -> None:
        profile = suggest_profile(
            file=_file(duration_seconds=0.6),
            amplitude=_amplitude(),
            transient=_transient(transient_strength=0.8, attack_duration_ms=7.0),
            pitch=_pitch(pitch_confidence=0.78, is_probably_pitched=True),
            timbre=_timbre(spectral_flatness=0.01),
        )

        self.assertEqual(profile.suggested_profile, "tonal_percussive")
        self.assertIn("stable pitch estimate", profile.reasons)

    def test_suggests_sustained_tonal_for_long_soft_pitched_sample(self) -> None:
        profile = suggest_profile(
            file=_file(duration_seconds=2.0),
            amplitude=_amplitude(),
            transient=_transient(transient_strength=0.25, attack_duration_ms=120.0),
            pitch=_pitch(pitch_confidence=0.84, is_probably_pitched=True),
            timbre=_timbre(spectral_flatness=0.01),
        )

        self.assertEqual(profile.suggested_profile, "sustained_tonal")
        self.assertIn("soft attack", profile.reasons)
        self.assertIn("longer duration", profile.reasons)

    def test_suggests_sfx_texture_for_flat_unpitched_sample(self) -> None:
        profile = suggest_profile(
            file=_file(duration_seconds=1.5),
            amplitude=_amplitude(),
            transient=_transient(transient_strength=0.2, attack_duration_ms=20.0),
            pitch=_pitch(pitch_confidence=0.2, is_probably_pitched=False),
            timbre=_timbre(spectral_flatness=0.2),
        )

        self.assertEqual(profile.suggested_profile, "sfx_texture")
        self.assertIn("high spectral flatness", profile.reasons)

    def test_allows_unknown_when_rules_do_not_match(self) -> None:
        profile = suggest_profile(
            file=_file(duration_seconds=0.9),
            amplitude=_amplitude(),
            transient=_transient(transient_strength=0.4, attack_duration_ms=30.0),
            pitch=_pitch(pitch_confidence=0.42, is_probably_pitched=False),
            timbre=_timbre(spectral_flatness=0.02),
        )

        self.assertEqual(profile.suggested_profile, "unknown")
        self.assertGreaterEqual(profile.confidence, 0.0)
        self.assertLessEqual(profile.confidence, 1.0)
        self.assertTrue(profile.reasons)


def _file(duration_seconds: float) -> FileMetadata:
    return FileMetadata(
        path="sample.wav",
        sample_rate=44100,
        channels=1,
        duration_seconds=duration_seconds,
        sample_count=int(44100 * duration_seconds),
    )


def _amplitude() -> AmplitudeMetrics:
    return AmplitudeMetrics(
        peak_amplitude=0.8,
        rms=0.2,
        crest_factor=4.0,
        leading_silence_ms=0.0,
        trailing_silence_ms=0.0,
    )


def _transient(transient_strength: float, attack_duration_ms: float) -> TransientMetrics:
    return TransientMetrics(
        onset_time_ms=0.0,
        attack_duration_ms=attack_duration_ms,
        transient_strength=transient_strength,
        transient_confidence=0.8,
    )


def _pitch(pitch_confidence: float, is_probably_pitched: bool) -> PitchMetrics:
    return PitchMetrics(
        estimated_f0_hz=220.0 if is_probably_pitched else None,
        estimated_midi_note=57 if is_probably_pitched else None,
        estimated_note_name="A3" if is_probably_pitched else None,
        pitch_confidence=pitch_confidence,
        is_probably_pitched=is_probably_pitched,
        pitch_stability=0.8 if is_probably_pitched else 0.1,
    )


def _timbre(spectral_flatness: float) -> TimbreMetrics:
    return TimbreMetrics(
        spectral_centroid=1200.0,
        spectral_bandwidth=900.0,
        spectral_rolloff=3000.0,
        spectral_flatness=spectral_flatness,
        spectral_contrast_mean=12.0,
    )


if __name__ == "__main__":
    unittest.main()
