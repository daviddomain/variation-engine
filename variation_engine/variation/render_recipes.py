from dataclasses import dataclass
from random import Random


UNKNOWN_CONSERVATIVE_RENDER_RECIPE_ID = "unknown_conservative"


@dataclass(frozen=True)
class NumericRange:
    min_value: float
    max_value: float

    def __post_init__(self) -> None:
        if self.min_value > self.max_value:
            raise ValueError("NumericRange min_value must be less than or equal to max_value.")


@dataclass(frozen=True)
class RoundRobinRenderRecipe:
    id: str
    target_category_ids: tuple[str, ...]
    target_profile_ids: tuple[str, ...]
    micropitch_cents: NumericRange
    timing_shift_ms: NumericRange
    gain_db: NumericRange
    attack_amount: NumericRange
    brightness_amount: NumericRange
    decay_amount: NumericRange
    saturation_amount: NumericRange
    stereo_balance_amount: NumericRange


@dataclass(frozen=True)
class RoundRobinRenderInstruction:
    index: int
    recipe_id: str
    micropitch_cents: float
    timing_shift_ms: float
    gain_db: float
    attack_amount: float
    brightness_amount: float
    decay_amount: float
    saturation_amount: float
    stereo_balance_amount: float
    output_filename: str


def _range(min_value: float, max_value: float) -> NumericRange:
    return NumericRange(min_value=min_value, max_value=max_value)


ROUND_ROBIN_RENDER_RECIPES: tuple[RoundRobinRenderRecipe, ...] = (
    RoundRobinRenderRecipe(
        id="plucked_string",
        target_category_ids=("plucked_string", "guitar_bass"),
        target_profile_ids=(),
        micropitch_cents=_range(-4.0, 4.0),
        timing_shift_ms=_range(-2.0, 2.0),
        gain_db=_range(-0.8, 0.8),
        attack_amount=_range(-0.15, 0.15),
        brightness_amount=_range(-0.20, 0.20),
        decay_amount=_range(-0.08, 0.08),
        saturation_amount=_range(0.0, 0.05),
        stereo_balance_amount=_range(-0.08, 0.08),
    ),
    RoundRobinRenderRecipe(
        id="piano_keys",
        target_category_ids=("piano_keys",),
        target_profile_ids=(),
        micropitch_cents=_range(-2.5, 2.5),
        timing_shift_ms=_range(-1.5, 1.5),
        gain_db=_range(-0.7, 0.7),
        attack_amount=_range(-0.12, 0.12),
        brightness_amount=_range(-0.16, 0.16),
        decay_amount=_range(-0.06, 0.06),
        saturation_amount=_range(0.0, 0.04),
        stereo_balance_amount=_range(-0.05, 0.05),
    ),
    RoundRobinRenderRecipe(
        id="drum_percussion",
        target_category_ids=("drum_percussion",),
        target_profile_ids=("percussive",),
        micropitch_cents=_range(-6.0, 6.0),
        timing_shift_ms=_range(-2.5, 2.5),
        gain_db=_range(-1.0, 1.0),
        attack_amount=_range(-0.22, 0.22),
        brightness_amount=_range(-0.25, 0.25),
        decay_amount=_range(-0.10, 0.10),
        saturation_amount=_range(0.0, 0.08),
        stereo_balance_amount=_range(-0.08, 0.08),
    ),
    RoundRobinRenderRecipe(
        id="sustained_tonal",
        target_category_ids=("bowed_string", "synth_lead", "synth_pad"),
        target_profile_ids=("sustained_tonal", "tonal_percussive"),
        micropitch_cents=_range(-3.0, 3.0),
        timing_shift_ms=_range(-1.0, 1.0),
        gain_db=_range(-0.6, 0.6),
        attack_amount=_range(-0.10, 0.10),
        brightness_amount=_range(-0.18, 0.18),
        decay_amount=_range(-0.06, 0.06),
        saturation_amount=_range(0.0, 0.04),
        stereo_balance_amount=_range(-0.06, 0.06),
    ),
    RoundRobinRenderRecipe(
        id="sfx_texture",
        target_category_ids=("fx_foley_texture", "sfx_texture"),
        target_profile_ids=("sfx_texture",),
        micropitch_cents=_range(-8.0, 8.0),
        timing_shift_ms=_range(-3.0, 3.0),
        gain_db=_range(-1.2, 1.2),
        attack_amount=_range(-0.20, 0.20),
        brightness_amount=_range(-0.30, 0.30),
        decay_amount=_range(-0.12, 0.12),
        saturation_amount=_range(0.0, 0.10),
        stereo_balance_amount=_range(-0.12, 0.12),
    ),
    RoundRobinRenderRecipe(
        id="vocal_voice",
        target_category_ids=("vocal_voice",),
        target_profile_ids=(),
        micropitch_cents=_range(-2.0, 2.0),
        timing_shift_ms=_range(-1.0, 1.0),
        gain_db=_range(-0.6, 0.6),
        attack_amount=_range(-0.08, 0.08),
        brightness_amount=_range(-0.16, 0.16),
        decay_amount=_range(-0.05, 0.05),
        saturation_amount=_range(0.0, 0.03),
        stereo_balance_amount=_range(-0.05, 0.05),
    ),
    RoundRobinRenderRecipe(
        id=UNKNOWN_CONSERVATIVE_RENDER_RECIPE_ID,
        target_category_ids=("unknown_auto",),
        target_profile_ids=("unknown",),
        micropitch_cents=_range(-1.5, 1.5),
        timing_shift_ms=_range(-0.8, 0.8),
        gain_db=_range(-0.5, 0.5),
        attack_amount=_range(-0.06, 0.06),
        brightness_amount=_range(-0.08, 0.08),
        decay_amount=_range(-0.04, 0.04),
        saturation_amount=_range(0.0, 0.02),
        stereo_balance_amount=_range(-0.04, 0.04),
    ),
)

ROUND_ROBIN_RENDER_RECIPE_BY_ID: dict[str, RoundRobinRenderRecipe] = {
    recipe.id: recipe for recipe in ROUND_ROBIN_RENDER_RECIPES
}


def select_round_robin_render_recipe(
    *,
    category_id: str | None,
    profile_id: str | None,
) -> RoundRobinRenderRecipe:
    """Select a category recipe, then a profile fallback, then the unknown fallback."""
    if category_id is not None:
        for recipe in ROUND_ROBIN_RENDER_RECIPES:
            if category_id in recipe.target_category_ids:
                return recipe

    if profile_id is not None:
        for recipe in ROUND_ROBIN_RENDER_RECIPES:
            if profile_id in recipe.target_profile_ids:
                return recipe

    return ROUND_ROBIN_RENDER_RECIPE_BY_ID[UNKNOWN_CONSERVATIVE_RENDER_RECIPE_ID]


def generate_round_robin_render_instructions(
    *,
    recipe: RoundRobinRenderRecipe,
    count: int,
    seed: int,
) -> tuple[RoundRobinRenderInstruction, ...]:
    if count < 0:
        raise ValueError("count must be greater than or equal to 0.")

    random = Random(seed)
    return tuple(
        _build_instruction(recipe=recipe, index=index, random=random)
        for index in range(1, count + 1)
    )


def _build_instruction(
    *,
    recipe: RoundRobinRenderRecipe,
    index: int,
    random: Random,
) -> RoundRobinRenderInstruction:
    if index == 1:
        return RoundRobinRenderInstruction(
            index=index,
            recipe_id=recipe.id,
            micropitch_cents=0.0,
            timing_shift_ms=0.0,
            gain_db=0.0,
            attack_amount=0.0,
            brightness_amount=0.0,
            decay_amount=0.0,
            saturation_amount=0.0,
            stereo_balance_amount=0.0,
            output_filename=_output_filename(index),
        )

    return RoundRobinRenderInstruction(
        index=index,
        recipe_id=recipe.id,
        micropitch_cents=_range_value(recipe.micropitch_cents, random),
        timing_shift_ms=_range_value(recipe.timing_shift_ms, random),
        gain_db=_range_value(recipe.gain_db, random),
        attack_amount=_range_value(recipe.attack_amount, random),
        brightness_amount=_range_value(recipe.brightness_amount, random),
        decay_amount=_range_value(recipe.decay_amount, random),
        saturation_amount=_range_value(recipe.saturation_amount, random),
        stereo_balance_amount=_range_value(recipe.stereo_balance_amount, random),
        output_filename=_output_filename(index),
    )


def _range_value(value_range: NumericRange, random: Random) -> float:
    return round(random.uniform(value_range.min_value, value_range.max_value), 6)


def _output_filename(index: int) -> str:
    return f"rr_{index:02d}.wav"
