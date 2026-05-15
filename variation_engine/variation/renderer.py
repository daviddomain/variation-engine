from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

from variation_engine.analysis.models import AnalysisResult
from variation_engine.variation.audio_transforms import (
    PLUCKED_STRING_RECIPE_ID,
    apply_plucked_string_transforms,
    limit_peak,
)
from variation_engine.variation.render_recipes import (
    ROUND_ROBIN_RENDER_RECIPE_BY_ID,
    UNKNOWN_CONSERVATIVE_RENDER_RECIPE_ID,
    RenderRecipeRangeOverrides,
    RoundRobinRenderInstruction,
    RoundRobinRenderRecipe,
    apply_render_recipe_range_overrides,
    generate_round_robin_render_instructions,
    select_round_robin_render_recipe,
)
from variation_engine.variation.planner import VariationPlanResult, create_variation_plan


DEFAULT_RENDER_SEED = 0
SOURCE_ROUND_ROBIN_COUNT = 8


@dataclass(frozen=True)
class RenderedFileSummary:
    path: str
    sample_rate: int
    channels: int
    sample_count: int
    recipe_id: str
    micropitch_cents: float
    timing_shift_ms: float
    gain_db: float
    attack_amount: float
    brightness_amount: float
    decay_amount: float
    saturation_amount: float
    stereo_balance_amount: float


@dataclass(frozen=True)
class RenderResult:
    output_dir: str
    seed: int
    selected_preset_id: str
    selected_render_recipe_id: str
    round_robin_count: int
    files: tuple[RenderedFileSummary, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def build_source_round_robin_instructions(
    seed: int = DEFAULT_RENDER_SEED,
    recipe: RoundRobinRenderRecipe | None = None,
) -> tuple[RoundRobinRenderInstruction, ...]:
    """Build deterministic source-only round-robin instructions."""
    selected_recipe = recipe or ROUND_ROBIN_RENDER_RECIPE_BY_ID[
        UNKNOWN_CONSERVATIVE_RENDER_RECIPE_ID
    ]
    return generate_round_robin_render_instructions(
        recipe=selected_recipe,
        count=SOURCE_ROUND_ROBIN_COUNT,
        seed=seed,
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
    if instruction.recipe_id == PLUCKED_STRING_RECIPE_ID:
        gained_audio = apply_plucked_string_transforms(
            gained_audio,
            sample_rate=sample_rate,
            instruction=instruction,
        )

    return limit_peak(gained_audio)


def render_source_round_robins(
    input_path: str | Path,
    output_dir: str | Path,
    analysis: AnalysisResult,
    category_id: str | None = None,
    source_note: str | None = None,
    seed: int = DEFAULT_RENDER_SEED,
    render_recipe_range_overrides: RenderRecipeRangeOverrides | None = None,
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
    recipe = select_round_robin_render_recipe(
        category_id=category_id,
        profile_id=plan.selected_preset.target_profile,
    )
    if render_recipe_range_overrides is not None:
        recipe = apply_render_recipe_range_overrides(
            recipe,
            render_recipe_range_overrides,
        )

    instructions = build_source_round_robin_instructions(seed=seed, recipe=recipe)
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
        selected_render_recipe_id=recipe.id,
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
        recipe_id=instruction.recipe_id,
        micropitch_cents=instruction.micropitch_cents,
        timing_shift_ms=instruction.timing_shift_ms,
        gain_db=instruction.gain_db,
        attack_amount=instruction.attack_amount,
        brightness_amount=instruction.brightness_amount,
        decay_amount=instruction.decay_amount,
        saturation_amount=instruction.saturation_amount,
        stereo_balance_amount=instruction.stereo_balance_amount,
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
