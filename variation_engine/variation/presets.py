from dataclasses import dataclass


SOURCE_ONLY = "source_only"
MAJOR_THIRDS_AROUND_SOURCE = "major_thirds_around_source"
DEFAULT_VARIATION_RULE_PRESET_ID = "unknown"


@dataclass(frozen=True)
class NumericRange:
    min_value: float
    max_value: float
    unit: str


@dataclass(frozen=True)
class PitchMappingPreset:
    enabled: bool
    interval_semitones: int
    octave_radius: int
    include_source_note: bool
    strategy: str


@dataclass(frozen=True)
class VariationTransformRanges:
    micropitch_cents: NumericRange
    timing_shift_ms: NumericRange
    attack_amount: NumericRange
    timbre_brightness: NumericRange
    saturation_amount: NumericRange
    gain_db: NumericRange
    space_amount: NumericRange


@dataclass(frozen=True)
class VariationRulePreset:
    id: str
    label: str
    target_profile: str
    round_robin_count: int
    velocity_layer_count: int
    pitch_mapping: PitchMappingPreset
    transform_ranges: VariationTransformRanges
    notes: tuple[str, ...]


def _source_only_mapping() -> PitchMappingPreset:
    return PitchMappingPreset(
        enabled=False,
        interval_semitones=0,
        octave_radius=0,
        include_source_note=True,
        strategy=SOURCE_ONLY,
    )


def _major_thirds_mapping() -> PitchMappingPreset:
    return PitchMappingPreset(
        enabled=True,
        interval_semitones=4,
        octave_radius=2,
        include_source_note=True,
        strategy=MAJOR_THIRDS_AROUND_SOURCE,
    )


def _ranges(
    micropitch_cents: tuple[float, float],
    timing_shift_ms: tuple[float, float],
    attack_amount: tuple[float, float],
    timbre_brightness: tuple[float, float],
    saturation_amount: tuple[float, float],
    gain_db: tuple[float, float],
    space_amount: tuple[float, float],
) -> VariationTransformRanges:
    return VariationTransformRanges(
        micropitch_cents=NumericRange(*micropitch_cents, "cents"),
        timing_shift_ms=NumericRange(*timing_shift_ms, "ms"),
        attack_amount=NumericRange(*attack_amount, "amount"),
        timbre_brightness=NumericRange(*timbre_brightness, "amount"),
        saturation_amount=NumericRange(*saturation_amount, "amount"),
        gain_db=NumericRange(*gain_db, "dB"),
        space_amount=NumericRange(*space_amount, "amount"),
    )


VARIATION_RULE_PRESETS: tuple[VariationRulePreset, ...] = (
    VariationRulePreset(
        id="percussive",
        label="Percussive",
        target_profile="percussive",
        round_robin_count=8,
        velocity_layer_count=4,
        pitch_mapping=_source_only_mapping(),
        transform_ranges=_ranges(
            micropitch_cents=(-8.0, 8.0),
            timing_shift_ms=(-3.0, 3.0),
            attack_amount=(-0.4, 0.4),
            timbre_brightness=(-0.35, 0.35),
            saturation_amount=(0.0, 0.2),
            gain_db=(-1.5, 1.5),
            space_amount=(0.0, 0.15),
        ),
        notes=("Conservative default for short transient-heavy material.",),
    ),
    VariationRulePreset(
        id="tonal_percussive",
        label="Tonal Percussive",
        target_profile="tonal_percussive",
        round_robin_count=8,
        velocity_layer_count=4,
        pitch_mapping=_major_thirds_mapping(),
        transform_ranges=_ranges(
            micropitch_cents=(-4.0, 4.0),
            timing_shift_ms=(-2.0, 2.0),
            attack_amount=(-0.3, 0.3),
            timbre_brightness=(-0.25, 0.25),
            saturation_amount=(0.0, 0.15),
            gain_db=(-1.25, 1.25),
            space_amount=(0.0, 0.12),
        ),
        notes=("Prepared for future major-third anchor note rendering.",),
    ),
    VariationRulePreset(
        id="sustained_tonal",
        label="Sustained Tonal",
        target_profile="sustained_tonal",
        round_robin_count=8,
        velocity_layer_count=4,
        pitch_mapping=_major_thirds_mapping(),
        transform_ranges=_ranges(
            micropitch_cents=(-3.0, 3.0),
            timing_shift_ms=(-1.0, 1.0),
            attack_amount=(-0.15, 0.15),
            timbre_brightness=(-0.25, 0.25),
            saturation_amount=(0.0, 0.12),
            gain_db=(-1.0, 1.0),
            space_amount=(0.0, 0.2),
        ),
        notes=("Prepared for future major-third anchor note rendering.",),
    ),
    VariationRulePreset(
        id="sfx_texture",
        label="SFX / Texture",
        target_profile="sfx_texture",
        round_robin_count=8,
        velocity_layer_count=4,
        pitch_mapping=_source_only_mapping(),
        transform_ranges=_ranges(
            micropitch_cents=(-10.0, 10.0),
            timing_shift_ms=(-4.0, 4.0),
            attack_amount=(-0.4, 0.4),
            timbre_brightness=(-0.45, 0.45),
            saturation_amount=(0.0, 0.3),
            gain_db=(-2.0, 2.0),
            space_amount=(0.0, 0.3),
        ),
        notes=("First-class texture preset without tonal anchor mapping.",),
    ),
    VariationRulePreset(
        id="unknown",
        label="Unknown",
        target_profile="unknown",
        round_robin_count=8,
        velocity_layer_count=4,
        pitch_mapping=_source_only_mapping(),
        transform_ranges=_ranges(
            micropitch_cents=(-2.0, 2.0),
            timing_shift_ms=(-1.0, 1.0),
            attack_amount=(-0.1, 0.1),
            timbre_brightness=(-0.1, 0.1),
            saturation_amount=(0.0, 0.08),
            gain_db=(-0.75, 0.75),
            space_amount=(0.0, 0.08),
        ),
        notes=("Most conservative fallback for unsupported or ambiguous profiles.",),
    ),
)


VARIATION_RULE_PRESET_BY_ID: dict[str, VariationRulePreset] = {
    preset.id: preset for preset in VARIATION_RULE_PRESETS
}


VARIATION_RULE_PRESET_BY_PROFILE: dict[str, VariationRulePreset] = {
    preset.target_profile: preset for preset in VARIATION_RULE_PRESETS
}


def get_variation_rule_preset(preset_id: str) -> VariationRulePreset:
    """Return a variation rule preset by stable machine-readable id."""
    try:
        return VARIATION_RULE_PRESET_BY_ID[preset_id]
    except KeyError as exc:
        raise ValueError(f"Unknown variation rule preset: {preset_id}") from exc


def get_variation_rule_preset_for_profile(profile: str) -> VariationRulePreset:
    """Return the matching preset for an internal profile, or the unknown fallback."""
    return VARIATION_RULE_PRESET_BY_PROFILE.get(
        profile,
        VARIATION_RULE_PRESET_BY_ID[DEFAULT_VARIATION_RULE_PRESET_ID],
    )
