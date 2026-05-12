from dataclasses import asdict, dataclass
from pathlib import Path
from random import Random

import numpy as np
import soundfile as sf

from variation_engine.analysis.models import AnalysisResult
from variation_engine.variation.planner import VariationPlanResult, create_variation_plan


DEFAULT_RENDER_SEED = 0
SOURCE_ROUND_ROBIN_COUNT = 8


@dataclass(frozen=True)
class RoundRobinRenderInstruction:
    index: int
    gain_db: float
    timing_shift_ms: float
    output_filename: str


@dataclass(frozen=True)
class RenderedFileSummary:
    path: str
    sample_rate: int
    channels: int
    sample_count: int
    gain_db: float
    timing_shift_ms: float


@dataclass(frozen=True)
class RenderResult:
    output_dir: str
    seed: int
    selected_preset_id: str
    round_robin_count: int
    files: tuple[RenderedFileSummary, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def build_source_round_robin_instructions(
    seed: int = DEFAULT_RENDER_SEED,
) -> tuple[RoundRobinRenderInstruction, ...]:
    """Build deterministic source-only round-robin instructions."""
    variable_variations = [
        (0.3, 1.0),
        (-0.3, -1.0),
        (0.5, 2.0),
        (-0.5, -2.0),
        (0.2, 0.0),
        (-0.2, 1.0),
        (0.1, -1.0),
    ]
    Random(seed).shuffle(variable_variations)
    variation_values = [(0.0, 0.0), *variable_variations]

    return tuple(
        RoundRobinRenderInstruction(
            index=index,
            gain_db=gain_db,
            timing_shift_ms=timing_shift_ms,
            output_filename=f"rr_{index:02d}.wav",
        )
        for index, (gain_db, timing_shift_ms) in enumerate(variation_values, start=1)
    )


def render_audio_variant(
    audio: np.ndarray,
    sample_rate: int,
    instruction: RoundRobinRenderInstruction,
) -> np.ndarray:
    """Apply safe deterministic gain and timing offsets to an audio buffer."""
    shifted_audio = _shift_audio(audio, sample_rate, instruction.timing_shift_ms)
    gain_factor = 10 ** (instruction.gain_db / 20.0)
    gained_audio = shifted_audio * gain_factor
    peak = float(np.max(np.abs(gained_audio))) if gained_audio.size else 0.0
    if peak > 1.0:
        return gained_audio / peak

    return gained_audio


def render_source_round_robins(
    input_path: str | Path,
    output_dir: str | Path,
    analysis: AnalysisResult,
    category_id: str | None = None,
    source_note: str | None = None,
    seed: int = DEFAULT_RENDER_SEED,
) -> RenderResult:
    """Render exactly eight source-note round-robin WAV files."""
    plan = create_variation_plan(
        analysis,
        category_id=category_id,
        source_note=source_note,
    )
    audio, sample_rate = sf.read(input_path, always_2d=True)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    input_info = sf.info(input_path)
    instructions = build_source_round_robin_instructions(seed)
    output_subtype = _wav_output_subtype(input_info.subtype)
    rendered_files = tuple(
        _write_round_robin_file(
            output_path=output_path,
            audio=audio,
            sample_rate=sample_rate,
            channels=input_info.channels,
            subtype=output_subtype,
            instruction=instruction,
        )
        for instruction in instructions
    )

    return RenderResult(
        output_dir=str(output_path),
        seed=seed,
        selected_preset_id=plan.selected_preset.id,
        round_robin_count=SOURCE_ROUND_ROBIN_COUNT,
        files=rendered_files,
        warnings=_render_warnings(plan),
    )


def _shift_audio(audio: np.ndarray, sample_rate: int, timing_shift_ms: float) -> np.ndarray:
    shift_samples = int(round(timing_shift_ms * sample_rate / 1000.0))
    if shift_samples == 0 or audio.shape[0] == 0:
        return audio.copy()

    shift_samples = max(-audio.shape[0], min(audio.shape[0], shift_samples))
    shifted_audio = np.zeros_like(audio)
    if shift_samples > 0:
        shifted_audio[shift_samples:] = audio[:-shift_samples]
    else:
        source_start = abs(shift_samples)
        shifted_audio[: audio.shape[0] - source_start] = audio[source_start:]

    return shifted_audio


def _write_round_robin_file(
    output_path: Path,
    audio: np.ndarray,
    sample_rate: int,
    channels: int,
    subtype: str,
    instruction: RoundRobinRenderInstruction,
) -> RenderedFileSummary:
    rendered_audio = render_audio_variant(audio, sample_rate, instruction)
    file_path = output_path / instruction.output_filename
    sf.write(file_path, rendered_audio, sample_rate, subtype=subtype)

    return RenderedFileSummary(
        path=str(file_path),
        sample_rate=sample_rate,
        channels=channels,
        sample_count=rendered_audio.shape[0],
        gain_db=instruction.gain_db,
        timing_shift_ms=instruction.timing_shift_ms,
    )


def _wav_output_subtype(input_subtype: str) -> str:
    return input_subtype if input_subtype in sf.available_subtypes("WAV") else "FLOAT"


def _render_warnings(plan: VariationPlanResult) -> tuple[str, ...]:
    warnings = list(plan.warnings)
    if plan.plan.velocity_layer_count > 1:
        warnings.append(
            "Render command intentionally writes source-only round-robins; velocity layers are skipped."
        )
    if len(plan.plan.target_notes) > 1:
        warnings.append(
            "Render command intentionally writes source-only round-robins; pitch-mapped target notes are skipped."
        )
    return tuple(warnings)
