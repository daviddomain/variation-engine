from dataclasses import dataclass


INSTRUMENT_OR_SOUND_SOURCE = "instrument_or_sound_source"
NON_HORNBOSTEL_SACHS = "non_hornbostel_sachs"
AUTO = "auto"


@dataclass(frozen=True)
class InstrumentCategory:
    id: str
    label: str
    domain: str
    default_profile: str
    hornbostel_sachs_hint: tuple[str, ...]
    allows_pitch_variation: bool
    allows_attack_variation: bool
    allows_timbre_variation: bool
    allows_space_variation: bool


INSTRUMENT_CATEGORIES: tuple[InstrumentCategory, ...] = (
    InstrumentCategory(
        id="piano_keys",
        label="Piano / Keys",
        domain=INSTRUMENT_OR_SOUND_SOURCE,
        default_profile="tonal_percussive",
        hornbostel_sachs_hint=("chordophone", "idiophone", "electrophone"),
        allows_pitch_variation=True,
        allows_attack_variation=True,
        allows_timbre_variation=True,
        allows_space_variation=True,
    ),
    InstrumentCategory(
        id="plucked_string",
        label="Plucked String",
        domain=INSTRUMENT_OR_SOUND_SOURCE,
        default_profile="tonal_percussive",
        hornbostel_sachs_hint=("chordophone",),
        allows_pitch_variation=True,
        allows_attack_variation=True,
        allows_timbre_variation=True,
        allows_space_variation=True,
    ),
    InstrumentCategory(
        id="bowed_string",
        label="Bowed String",
        domain=INSTRUMENT_OR_SOUND_SOURCE,
        default_profile="sustained_tonal",
        hornbostel_sachs_hint=("chordophone",),
        allows_pitch_variation=True,
        allows_attack_variation=True,
        allows_timbre_variation=True,
        allows_space_variation=True,
    ),
    InstrumentCategory(
        id="guitar_bass",
        label="Guitar / Bass",
        domain=INSTRUMENT_OR_SOUND_SOURCE,
        default_profile="tonal_percussive",
        hornbostel_sachs_hint=("chordophone", "electrophone"),
        allows_pitch_variation=True,
        allows_attack_variation=True,
        allows_timbre_variation=True,
        allows_space_variation=True,
    ),
    InstrumentCategory(
        id="drum_percussion",
        label="Drum / Percussion",
        domain=INSTRUMENT_OR_SOUND_SOURCE,
        default_profile="percussive",
        hornbostel_sachs_hint=("membranophone", "idiophone"),
        allows_pitch_variation=True,
        allows_attack_variation=True,
        allows_timbre_variation=True,
        allows_space_variation=True,
    ),
    InstrumentCategory(
        id="synth_lead",
        label="Synth Lead",
        domain=INSTRUMENT_OR_SOUND_SOURCE,
        default_profile="sustained_tonal",
        hornbostel_sachs_hint=("electrophone",),
        allows_pitch_variation=True,
        allows_attack_variation=True,
        allows_timbre_variation=True,
        allows_space_variation=True,
    ),
    InstrumentCategory(
        id="synth_pad",
        label="Synth Pad",
        domain=INSTRUMENT_OR_SOUND_SOURCE,
        default_profile="sustained_tonal",
        hornbostel_sachs_hint=("electrophone",),
        allows_pitch_variation=True,
        allows_attack_variation=True,
        allows_timbre_variation=True,
        allows_space_variation=True,
    ),
    InstrumentCategory(
        id="vocal_voice",
        label="Vocal / Voice",
        domain=INSTRUMENT_OR_SOUND_SOURCE,
        default_profile="sustained_tonal",
        hornbostel_sachs_hint=("aerophone",),
        allows_pitch_variation=True,
        allows_attack_variation=True,
        allows_timbre_variation=True,
        allows_space_variation=True,
    ),
    InstrumentCategory(
        id="fx_foley_texture",
        label="FX / Foley / Texture",
        domain=NON_HORNBOSTEL_SACHS,
        default_profile="sfx_texture",
        hornbostel_sachs_hint=(),
        allows_pitch_variation=True,
        allows_attack_variation=True,
        allows_timbre_variation=True,
        allows_space_variation=True,
    ),
    InstrumentCategory(
        id="unknown_auto",
        label="Unknown / Auto",
        domain=AUTO,
        default_profile="unknown",
        hornbostel_sachs_hint=(),
        allows_pitch_variation=True,
        allows_attack_variation=True,
        allows_timbre_variation=True,
        allows_space_variation=True,
    ),
)


INSTRUMENT_CATEGORY_BY_ID: dict[str, InstrumentCategory] = {
    category.id: category for category in INSTRUMENT_CATEGORIES
}


DEFAULT_PROFILE_BY_CATEGORY_ID: dict[str, str] = {
    category.id: category.default_profile for category in INSTRUMENT_CATEGORIES
}


def get_instrument_category(category_id: str) -> InstrumentCategory:
    """Return a category by stable machine-readable id."""
    try:
        return INSTRUMENT_CATEGORY_BY_ID[category_id]
    except KeyError as exc:
        raise ValueError(f"Unknown instrument category: {category_id}") from exc
