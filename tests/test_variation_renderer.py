import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

import numpy as np
import soundfile as sf

from variation_engine.cli import main
from variation_engine.variation.renderer import (
    build_source_round_robin_instructions,
    render_audio_variant,
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
        delayed_instruction = type(instruction)(
            index=1,
            gain_db=0.0,
            timing_shift_ms=2.0,
            output_filename="rr_01.wav",
        )

        rendered = render_audio_variant(audio, sample_rate=1000, instruction=delayed_instruction)

        self.assertEqual(rendered.shape, audio.shape)
        np.testing.assert_allclose(rendered[:, 0], [0.0, 0.0, 1.0, 0.5])

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
        self.assertEqual(len(output["files"]), 8)

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


if __name__ == "__main__":
    unittest.main()
