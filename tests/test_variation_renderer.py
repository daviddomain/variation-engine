import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from io import StringIO
from pathlib import Path

import numpy as np
import soundfile as sf

from variation_engine.cli import main
from variation_engine.analysis.models import (
    AmplitudeMetrics,
    AnalysisResult,
    FileMetadata,
    PitchMetrics,
    ProfileMetrics,
    TimbreMetrics,
    TransientMetrics,
)
from variation_engine.variation.render_recipes import ROUND_ROBIN_RENDER_RECIPE_BY_ID
from variation_engine.variation.renderer import (
    build_source_round_robin_instructions,
    render_audio_variant,
    render_source_round_robins,
)


class VariationRendererTest(unittest.TestCase):
    def test_instruction_order_is_deterministic_for_seed(self) -> None:
        first = build_source_round_robin_instructions(seed=7)
        second = build_source_round_robin_instructions(seed=7)

        self.assertEqual(first, second)
        self.assertEqual(first[0].gain_db, 0.0)
        self.assertEqual(first[0].timing_shift_ms, 0.0)

    def test_render_audio_variant_keeps_length_and_delays_positive_timing_shift(self) -> None:
        audio = np.array([[1.0], [0.5], [0.25], [0.0]], dtype=np.float32)
        instruction = build_source_round_robin_instructions(seed=0)[0]
        delayed_instruction = replace(
            instruction,
            gain_db=0.0,
            timing_shift_ms=2.0,
        )

        rendered = render_audio_variant(audio, sample_rate=1000, instruction=delayed_instruction)

        self.assertEqual(rendered.shape, audio.shape)
        np.testing.assert_allclose(rendered[:, 0], [0.0, 0.0, 1.0, 0.5])

    def test_render_audio_variant_advances_negative_timing_shift(self) -> None:
        audio = np.array([[1.0], [0.5], [0.25], [0.125]], dtype=np.float32)
        instruction = build_source_round_robin_instructions(seed=0)[0]
        advanced_instruction = replace(
            instruction,
            gain_db=0.0,
            timing_shift_ms=-2.0,
        )

        rendered = render_audio_variant(audio, sample_rate=1000, instruction=advanced_instruction)

        self.assertEqual(rendered.shape, audio.shape)
        np.testing.assert_allclose(rendered[:, 0], [0.25, 0.125, 0.0, 0.0])

    def test_render_audio_variant_scales_positive_gain_to_prevent_clipping(self) -> None:
        audio = np.array([[1.0], [-1.0], [0.5]], dtype=np.float32)
        instruction = build_source_round_robin_instructions(seed=0)[0]
        boosted_instruction = replace(
            instruction,
            gain_db=0.5,
            timing_shift_ms=0.0,
        )

        rendered = render_audio_variant(audio, sample_rate=1000, instruction=boosted_instruction)

        self.assertLessEqual(float(np.max(np.abs(rendered))), 1.0)
        np.testing.assert_allclose(rendered[:, 0], [1.0, -1.0, 0.5], atol=1e-7)

    def test_render_audio_variant_uses_plucked_string_transform_path(self) -> None:
        audio = np.column_stack(
            [
                np.linspace(0.0, 0.5, 32, dtype=np.float32),
                np.linspace(0.5, 0.0, 32, dtype=np.float32),
            ]
        )
        instruction = build_source_round_robin_instructions(seed=0)[0]
        plucked_instruction = replace(
            instruction,
            recipe_id="plucked_string",
            micropitch_cents=4.0,
            attack_amount=-0.15,
            brightness_amount=0.2,
            decay_amount=-0.08,
            stereo_balance_amount=0.08,
        )

        rendered = render_audio_variant(audio, sample_rate=1000, instruction=plucked_instruction)

        self.assertEqual(rendered.shape, audio.shape)
        self.assertFalse(np.array_equal(rendered, audio))
        self.assertLessEqual(float(np.max(np.abs(rendered))), 1.0)

    def test_render_audio_variant_keeps_non_plucked_safe_behavior(self) -> None:
        audio = np.array([[0.2, 0.1], [0.4, -0.3], [0.6, 0.5]], dtype=np.float32)
        instruction = build_source_round_robin_instructions(seed=0)[0]
        non_plucked_instruction = replace(
            instruction,
            recipe_id="unknown_conservative",
            micropitch_cents=4.0,
            attack_amount=-0.15,
            brightness_amount=0.2,
            decay_amount=-0.08,
            stereo_balance_amount=0.08,
            gain_db=0.0,
            timing_shift_ms=0.0,
        )

        rendered = render_audio_variant(
            audio,
            sample_rate=1000,
            instruction=non_plucked_instruction,
        )

        np.testing.assert_array_equal(rendered, audio)

    def test_render_command_writes_exactly_eight_stereo_wavs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            input_path = Path(tmp_dir) / "sample.wav"
            output_dir = Path(tmp_dir) / "generated"
            audio = _stereo_sample(sample_rate=8000)
            sf.write(input_path, audio, 8000, subtype="FLOAT")
            stdout = StringIO()

            with redirect_stdout(stdout):
                exit_code = main(
                    ["render", str(input_path), "--output", str(output_dir), "--seed", "11"]
                )

            rendered_paths = sorted(output_dir.glob("*.wav"))
            original, original_rate = sf.read(input_path, always_2d=True)
            first_rendered, first_rate = sf.read(output_dir / "rr_01.wav", always_2d=True)
            rendered_audio = [
                sf.read(path, always_2d=True)
                for path in rendered_paths
            ]

        output = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(
            [path.name for path in rendered_paths],
            [f"rr_{index:02d}.wav" for index in range(1, 9)],
        )
        self.assertEqual(output["round_robin_count"], 8)
        self.assertEqual(output["selected_render_recipe_id"], "unknown_conservative")
        self.assertEqual(len(output["files"]), 8)
        for file_summary in output["files"]:
            self.assertEqual(
                set(file_summary),
                {
                    "path",
                    "sample_rate",
                    "channels",
                    "sample_count",
                    "recipe_id",
                    "micropitch_cents",
                    "timing_shift_ms",
                    "gain_db",
                    "attack_amount",
                    "brightness_amount",
                    "decay_amount",
                    "saturation_amount",
                    "stereo_balance_amount",
                },
            )
            self.assertEqual(file_summary["recipe_id"], "unknown_conservative")

        self.assertEqual(first_rate, original_rate)
        self.assertEqual(first_rendered.shape, original.shape)
        np.testing.assert_allclose(first_rendered, original, atol=1e-7)

        for rendered, sample_rate in rendered_audio:
            self.assertEqual(sample_rate, 8000)
            self.assertEqual(rendered.shape, audio.shape)

    def test_render_command_is_deterministic_with_same_seed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            input_path = Path(tmp_dir) / "sample.wav"
            first_dir = Path(tmp_dir) / "first"
            second_dir = Path(tmp_dir) / "second"
            sf.write(input_path, _stereo_sample(sample_rate=8000), 8000, subtype="FLOAT")

            first_stdout = StringIO()
            second_stdout = StringIO()
            with redirect_stdout(first_stdout):
                first_exit = main(
                    ["render", str(input_path), "--output", str(first_dir), "--seed", "5"]
                )
            with redirect_stdout(second_stdout):
                second_exit = main(
                    ["render", str(input_path), "--output", str(second_dir), "--seed", "5"]
                )

            self.assertEqual(first_exit, 0)
            self.assertEqual(second_exit, 0)
            for index in range(1, 9):
                first_audio, first_rate = sf.read(first_dir / f"rr_{index:02d}.wav", always_2d=True)
                second_audio, second_rate = sf.read(second_dir / f"rr_{index:02d}.wav", always_2d=True)
                self.assertEqual(first_rate, second_rate)
                np.testing.assert_array_equal(first_audio, second_audio)

    def test_plucked_string_render_command_is_deterministic_with_same_seed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            input_path = Path(tmp_dir) / "sample.wav"
            first_dir = Path(tmp_dir) / "first"
            second_dir = Path(tmp_dir) / "second"
            sf.write(input_path, _stereo_sample(sample_rate=8000), 8000, subtype="FLOAT")

            first_stdout = StringIO()
            second_stdout = StringIO()
            with redirect_stdout(first_stdout):
                first_exit = main(
                    [
                        "render",
                        str(input_path),
                        "--output",
                        str(first_dir),
                        "--category",
                        "plucked_string",
                        "--seed",
                        "5",
                    ]
                )
            with redirect_stdout(second_stdout):
                second_exit = main(
                    [
                        "render",
                        str(input_path),
                        "--output",
                        str(second_dir),
                        "--category",
                        "plucked_string",
                        "--seed",
                        "5",
                    ]
                )

            self.assertEqual(first_exit, 0)
            self.assertEqual(second_exit, 0)
            for index in range(1, 9):
                first_audio, first_rate = sf.read(first_dir / f"rr_{index:02d}.wav", always_2d=True)
                second_audio, second_rate = sf.read(second_dir / f"rr_{index:02d}.wav", always_2d=True)
                self.assertEqual(first_rate, second_rate)
                np.testing.assert_array_equal(first_audio, second_audio)

    def test_render_command_selects_category_recipe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            input_path = Path(tmp_dir) / "sample.wav"
            output_dir = Path(tmp_dir) / "generated"
            sf.write(input_path, _stereo_sample(sample_rate=8000), 8000, subtype="FLOAT")
            stdout = StringIO()

            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "render",
                        str(input_path),
                        "--output",
                        str(output_dir),
                        "--category",
                        "plucked_string",
                        "--seed",
                        "11",
                    ]
                )

        output = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(output["selected_render_recipe_id"], "plucked_string")
        for file_summary in output["files"]:
            self.assertEqual(file_summary["recipe_id"], "plucked_string")
            self.assertIn("micropitch_cents", file_summary)
            self.assertIn("attack_amount", file_summary)
            self.assertIn("brightness_amount", file_summary)
            self.assertIn("decay_amount", file_summary)
            self.assertIn("saturation_amount", file_summary)
            self.assertIn("stereo_balance_amount", file_summary)

    def test_render_source_round_robins_uses_temporary_recipe_range_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            input_path = Path(tmp_dir) / "sample.wav"
            output_dir = Path(tmp_dir) / "generated"
            sf.write(input_path, _stereo_sample(sample_rate=8000), 8000, subtype="FLOAT")

            result = render_source_round_robins(
                input_path,
                output_dir,
                _analysis(profile="tonal_percussive"),
                category_id="plucked_string",
                seed=11,
                render_recipe_range_overrides={
                    "micropitch_cents": (-1.0, 1.0),
                    "timing_shift_ms": (-0.5, 0.5),
                    "gain_db": (-0.1, 0.1),
                },
            )

        self.assertEqual(result.selected_render_recipe_id, "plucked_string")
        for file_summary in result.files:
            self.assertGreaterEqual(file_summary.micropitch_cents, -1.0)
            self.assertLessEqual(file_summary.micropitch_cents, 1.0)
            self.assertGreaterEqual(file_summary.timing_shift_ms, -0.5)
            self.assertLessEqual(file_summary.timing_shift_ms, 0.5)
            self.assertGreaterEqual(file_summary.gain_db, -0.1)
            self.assertLessEqual(file_summary.gain_db, 0.1)

        self.assertEqual(
            ROUND_ROBIN_RENDER_RECIPE_BY_ID["plucked_string"].micropitch_cents.min_value,
            -4.0,
        )
        self.assertEqual(
            ROUND_ROBIN_RENDER_RECIPE_BY_ID["plucked_string"].micropitch_cents.max_value,
            4.0,
        )

    def test_render_command_rejects_invalid_source_note(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            input_path = Path(tmp_dir) / "sample.wav"
            sf.write(input_path, _stereo_sample(sample_rate=8000), 8000, subtype="FLOAT")
            stdout = StringIO()
            stderr = StringIO()

            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = main(
                    [
                        "render",
                        str(input_path),
                        "--output",
                        str(Path(tmp_dir) / "generated"),
                        "--source-note",
                        "H3",
                    ]
                )

        self.assertNotEqual(exit_code, 0)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("error: Invalid note name", stderr.getvalue())


def _stereo_sample(sample_rate: int) -> np.ndarray:
    time = np.arange(sample_rate // 20, dtype=np.float32) / sample_rate
    left = 0.2 * np.sin(2 * np.pi * 220.0 * time)
    right = 0.15 * np.sin(2 * np.pi * 330.0 * time)
    return np.column_stack([left, right]).astype(np.float32)


def _analysis(profile: str) -> AnalysisResult:
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
            estimated_midi_note=None,
            estimated_note_name=None,
            pitch_confidence=0.0,
            is_probably_pitched=False,
            pitch_stability=0.0,
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
