import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

import numpy as np
import soundfile as sf

from variation_engine.analysis.models import (
    AmplitudeMetrics,
    AnalysisResult,
    FileMetadata,
    PitchMetrics,
    ProfileMetrics,
    TimbreMetrics,
    TransientMetrics,
)
from variation_engine.cli import main
from variation_engine.variation.planner import (
    InvalidNoteNameError,
    build_target_notes,
    create_variation_plan,
    midi_note_to_name,
    parse_note_name,
)
from variation_engine.variation.presets import get_variation_rule_preset


class VariationPlannerTest(unittest.TestCase):
    def test_source_only_produces_one_target_note(self) -> None:
        preset = get_variation_rule_preset("percussive")

        target_notes = build_target_notes(None, preset)

        self.assertEqual(len(target_notes), 1)
        self.assertIsNone(target_notes[0].note_name)
        self.assertIsNone(target_notes[0].midi_note)
        self.assertEqual(target_notes[0].semitone_offset, 0)
        self.assertEqual(target_notes[0].role, "source")

    def test_source_only_estimates_32_samples(self) -> None:
        result = create_variation_plan(_analysis(profile="percussive"))

        self.assertEqual(result.plan.round_robin_count, 8)
        self.assertEqual(result.plan.velocity_layer_count, 4)
        self.assertEqual(result.plan.estimated_output_sample_count, 32)

    def test_major_thirds_around_source_from_c3_produces_expected_notes(self) -> None:
        result = create_variation_plan(
            _analysis(profile="tonal_percussive"),
            source_note="C3",
        )

        self.assertEqual(len(result.plan.target_notes), 13)
        self.assertEqual(
            [target.note_name for target in result.plan.target_notes],
            [
                "C1",
                "E1",
                "G#1",
                "C2",
                "E2",
                "G#2",
                "C3",
                "E3",
                "G#3",
                "C4",
                "E4",
                "G#4",
                "C5",
            ],
        )
        self.assertEqual(result.plan.estimated_output_sample_count, 416)

    def test_explicit_source_note_overrides_detected_pitch(self) -> None:
        result = create_variation_plan(
            _analysis(
                profile="tonal_percussive",
                midi_note=57,
                note_name="A3",
                is_probably_pitched=True,
            ),
            source_note="C3",
        )

        self.assertIsNotNone(result.plan.source_note)
        self.assertEqual(result.plan.source_note.note_name, "C3")
        self.assertEqual(result.plan.source_note.midi_note, 48)
        self.assertEqual(result.plan.source_note.source, "override")

    def test_detected_pitch_is_used_without_source_note_override(self) -> None:
        result = create_variation_plan(
            _analysis(
                profile="tonal_percussive",
                midi_note=57,
                note_name="A3",
                is_probably_pitched=True,
            )
        )

        self.assertIsNotNone(result.plan.source_note)
        self.assertEqual(result.plan.source_note.note_name, "A3")
        self.assertEqual(result.plan.source_note.midi_note, 57)
        self.assertEqual(result.plan.source_note.source, "detected")

    def test_missing_pitch_with_tonal_mapping_falls_back_and_warns(self) -> None:
        result = create_variation_plan(_analysis(profile="tonal_percussive"))

        self.assertIsNone(result.plan.source_note)
        self.assertEqual(len(result.plan.target_notes), 1)
        self.assertEqual(result.plan.estimated_output_sample_count, 32)
        self.assertTrue(
            any("requires a source note" in warning for warning in result.warnings)
        )

    def test_category_override_selects_category_default_profile(self) -> None:
        result = create_variation_plan(
            _analysis(profile="percussive"),
            category_id="piano_keys",
            source_note="C3",
        )

        self.assertIsNotNone(result.selected_category)
        self.assertEqual(result.selected_category.id, "piano_keys")
        self.assertEqual(result.selected_preset.id, "tonal_percussive")
        self.assertEqual(result.plan.estimated_output_sample_count, 416)

    def test_unsupported_profile_falls_back_to_unknown_preset(self) -> None:
        result = create_variation_plan(_analysis(profile="unsupported_profile"))

        self.assertEqual(result.selected_preset.id, "unknown")
        self.assertTrue(
            any("Unsupported profile" in warning for warning in result.warnings)
        )

    def test_invalid_source_note_raises_clear_error(self) -> None:
        with self.assertRaisesRegex(InvalidNoteNameError, "Invalid note name"):
            create_variation_plan(_analysis(profile="tonal_percussive"), source_note="H3")

    def test_note_parsing_supports_sharps_and_flats(self) -> None:
        self.assertEqual(parse_note_name("C#3"), 49)
        self.assertEqual(parse_note_name("Db3"), 49)
        self.assertEqual(parse_note_name("Bb3"), 58)

    def test_midi_note_conversion_follows_c4_60(self) -> None:
        self.assertEqual(parse_note_name("C4"), 60)
        self.assertEqual(parse_note_name("C3"), 48)
        self.assertEqual(parse_note_name("A4"), 69)
        self.assertEqual(midi_note_to_name(60), "C4")

    def test_valid_source_note_outside_sensible_range_warns(self) -> None:
        result = create_variation_plan(
            _analysis(profile="tonal_percussive"),
            source_note="C10",
        )

        self.assertTrue(
            any("outside the sensible MIDI range" in warning for warning in result.warnings)
        )


class VariationPlannerCliTest(unittest.TestCase):
    def test_plan_command_prints_valid_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "sample.wav"
            sf.write(path, np.array([0.0, 0.5, 0.0], dtype=np.float32), 1000)
            stdout = StringIO()

            with redirect_stdout(stdout):
                exit_code = main(["plan", str(path), "--category", "piano_keys", "--source-note", "C3"])

        output = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertFalse(output["status"]["rendering_enabled"])
        self.assertEqual(output["plan"]["estimated_output_sample_count"], 416)

    def test_plan_command_with_invalid_source_note_prints_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "sample.wav"
            sf.write(path, np.array([0.0, 0.5, 0.0], dtype=np.float32), 1000)
            stdout = StringIO()
            stderr = StringIO()

            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = main(["plan", str(path), "--source-note", "H3"])

        self.assertNotEqual(exit_code, 0)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("error: Invalid note name", stderr.getvalue())
        self.assertIn("H3", stderr.getvalue())


def _analysis(
    profile: str,
    midi_note: int | None = None,
    note_name: str | None = None,
    is_probably_pitched: bool = False,
) -> AnalysisResult:
    return AnalysisResult(
        file=FileMetadata(
            path="samples/test.wav",
            sample_rate=44100,
            channels=1,
            duration_seconds=1.25,
            sample_count=55125,
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
            estimated_f0_hz=None,
            estimated_midi_note=midi_note,
            estimated_note_name=note_name,
            pitch_confidence=0.8 if is_probably_pitched else 0.0,
            is_probably_pitched=is_probably_pitched,
            pitch_stability=0.8 if is_probably_pitched else 0.0,
        ),
        timbre=TimbreMetrics(
            spectral_centroid=1000.0,
            spectral_bandwidth=500.0,
            spectral_rolloff=2000.0,
            spectral_flatness=0.1,
            spectral_contrast_mean=12.0,
        ),
        profile=ProfileMetrics(
            suggested_profile=profile,
            confidence=0.75,
            reasons=[],
        ),
    )


if __name__ == "__main__":
    unittest.main()
