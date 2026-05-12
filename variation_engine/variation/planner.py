import re
from dataclasses import asdict, dataclass

from variation_engine.analysis.categories import InstrumentCategory, get_instrument_category
from variation_engine.analysis.models import AnalysisResult
from variation_engine.variation.presets import (
    MAJOR_THIRDS_AROUND_SOURCE,
    SOURCE_ONLY,
    VariationRulePreset,
    get_variation_rule_preset_for_profile,
)


SENSIBLE_MIDI_NOTE_MIN = 0
SENSIBLE_MIDI_NOTE_MAX = 127

_NOTE_NAME_PATTERN = re.compile(r"^\s*([A-Ga-g])([#b]?)(-?\d+)\s*$")
_NATURAL_NOTE_OFFSETS = {
    "C": 0,
    "D": 2,
    "E": 4,
    "F": 5,
    "G": 7,
    "A": 9,
    "B": 11,
}
_SHARP_NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


class InvalidNoteNameError(ValueError):
    """Raised when a note name cannot be parsed as a standard MIDI note."""


@dataclass(frozen=True)
class SourceNote:
    note_name: str
    midi_note: int
    source: str


@dataclass(frozen=True)
class TargetNote:
    note_name: str | None
    midi_note: int | None
    semitone_offset: int
    role: str


@dataclass(frozen=True)
class FilePlanSummary:
    path: str
    duration_seconds: float


@dataclass(frozen=True)
class AnalysisProfileSummary:
    suggested_profile: str
    confidence: float


@dataclass(frozen=True)
class AnalysisPitchSummary:
    estimated_note_name: str | None
    estimated_midi_note: int | None
    pitch_confidence: float
    is_probably_pitched: bool


@dataclass(frozen=True)
class SelectedCategorySummary:
    id: str
    default_profile: str


@dataclass(frozen=True)
class SelectedPresetSummary:
    id: str
    target_profile: str
    pitch_mapping_strategy: str


@dataclass(frozen=True)
class VariationPlan:
    source_note: SourceNote | None
    target_notes: tuple[TargetNote, ...]
    round_robin_count: int
    velocity_layer_count: int
    estimated_output_sample_count: int


@dataclass(frozen=True)
class VariationPlanStatus:
    rendering_enabled: bool
    message: str


@dataclass(frozen=True)
class VariationPlanResult:
    file: FilePlanSummary
    analysis_profile: AnalysisProfileSummary
    analysis_pitch: AnalysisPitchSummary
    selected_category: SelectedCategorySummary | None
    selected_preset: SelectedPresetSummary
    plan: VariationPlan
    warnings: tuple[str, ...]
    status: VariationPlanStatus

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def parse_note_name(note_name: str) -> int:
    match = _NOTE_NAME_PATTERN.match(note_name)
    if not match:
        raise InvalidNoteNameError(
            f"Invalid note name: {note_name!r}. Expected a note like C3, C#3, or Db3."
        )

    natural_note, accidental, octave_text = match.groups()
    pitch_class = _NATURAL_NOTE_OFFSETS[natural_note.upper()]
    if accidental == "#":
        pitch_class += 1
    elif accidental == "b":
        pitch_class -= 1

    octave = int(octave_text)
    return (octave + 1) * 12 + pitch_class


def midi_note_to_name(midi_note: int) -> str:
    octave = (midi_note // 12) - 1
    return f"{_SHARP_NOTE_NAMES[midi_note % 12]}{octave}"


def build_target_notes(
    source_midi_note: int | None,
    preset: VariationRulePreset,
) -> tuple[TargetNote, ...]:
    pitch_mapping = preset.pitch_mapping

    if (
        pitch_mapping.enabled
        and pitch_mapping.strategy == MAJOR_THIRDS_AROUND_SOURCE
        and source_midi_note is not None
    ):
        max_offset = pitch_mapping.octave_radius * 12
        offsets = range(-max_offset, max_offset + 1, pitch_mapping.interval_semitones)
        if not pitch_mapping.include_source_note:
            offsets = (offset for offset in offsets if offset != 0)
        return tuple(
            TargetNote(
                note_name=midi_note_to_name(source_midi_note + semitone_offset),
                midi_note=source_midi_note + semitone_offset,
                semitone_offset=semitone_offset,
                role="source" if semitone_offset == 0 else "anchor",
            )
            for semitone_offset in offsets
        )

    if source_midi_note is None:
        return (
            TargetNote(
                note_name=None,
                midi_note=None,
                semitone_offset=0,
                role="source",
            ),
        )

    return (
        TargetNote(
            note_name=midi_note_to_name(source_midi_note),
            midi_note=source_midi_note,
            semitone_offset=0,
            role="source",
        ),
    )


def create_variation_plan(
    analysis: AnalysisResult,
    category_id: str | None = None,
    source_note: str | None = None,
) -> VariationPlanResult:
    warnings: list[str] = []
    category = get_instrument_category(category_id) if category_id is not None else None
    selected_profile = category.default_profile if category is not None else analysis.profile.suggested_profile
    preset = get_variation_rule_preset_for_profile(selected_profile)

    if preset.target_profile != selected_profile:
        warnings.append(
            f"Unsupported profile {selected_profile!r}; using unknown variation preset."
        )

    selected_source_note = _select_source_note(analysis, source_note, warnings)
    source_midi_note = selected_source_note.midi_note if selected_source_note is not None else None

    if _requires_tonal_source_note(preset) and source_midi_note is None:
        warnings.append(
            "Selected pitch mapping strategy requires a source note, but none is available; "
            "falling back to a source-only target note."
        )

    target_notes = build_target_notes(source_midi_note, preset)
    estimated_output_sample_count = (
        len(target_notes) * preset.round_robin_count * preset.velocity_layer_count
    )

    return VariationPlanResult(
        file=FilePlanSummary(
            path=analysis.file.path,
            duration_seconds=analysis.file.duration_seconds,
        ),
        analysis_profile=AnalysisProfileSummary(
            suggested_profile=analysis.profile.suggested_profile,
            confidence=analysis.profile.confidence,
        ),
        analysis_pitch=AnalysisPitchSummary(
            estimated_note_name=analysis.pitch.estimated_note_name,
            estimated_midi_note=analysis.pitch.estimated_midi_note,
            pitch_confidence=analysis.pitch.pitch_confidence,
            is_probably_pitched=analysis.pitch.is_probably_pitched,
        ),
        selected_category=_category_summary(category),
        selected_preset=SelectedPresetSummary(
            id=preset.id,
            target_profile=preset.target_profile,
            pitch_mapping_strategy=preset.pitch_mapping.strategy,
        ),
        plan=VariationPlan(
            source_note=selected_source_note,
            target_notes=target_notes,
            round_robin_count=preset.round_robin_count,
            velocity_layer_count=preset.velocity_layer_count,
            estimated_output_sample_count=estimated_output_sample_count,
        ),
        warnings=tuple(warnings),
        status=VariationPlanStatus(
            rendering_enabled=False,
            message="Dry-run only. No audio files were generated.",
        ),
    )


def _select_source_note(
    analysis: AnalysisResult,
    source_note: str | None,
    warnings: list[str],
) -> SourceNote | None:
    if source_note is not None:
        midi_note = parse_note_name(source_note)
        _warn_if_outside_sensible_range(midi_note, warnings)
        return SourceNote(
            note_name=midi_note_to_name(midi_note),
            midi_note=midi_note,
            source="override",
        )

    if analysis.pitch.is_probably_pitched and analysis.pitch.estimated_midi_note is not None:
        midi_note = analysis.pitch.estimated_midi_note
        _warn_if_outside_sensible_range(midi_note, warnings)
        return SourceNote(
            note_name=midi_note_to_name(midi_note),
            midi_note=midi_note,
            source="detected",
        )

    return None


def _warn_if_outside_sensible_range(midi_note: int, warnings: list[str]) -> None:
    if midi_note < SENSIBLE_MIDI_NOTE_MIN or midi_note > SENSIBLE_MIDI_NOTE_MAX:
        warnings.append(
            f"Source note MIDI value {midi_note} is outside the sensible MIDI range "
            f"{SENSIBLE_MIDI_NOTE_MIN}-{SENSIBLE_MIDI_NOTE_MAX}."
        )


def _requires_tonal_source_note(preset: VariationRulePreset) -> bool:
    return (
        preset.pitch_mapping.enabled
        and preset.pitch_mapping.strategy != SOURCE_ONLY
    )


def _category_summary(category: InstrumentCategory | None) -> SelectedCategorySummary | None:
    if category is None:
        return None
    return SelectedCategorySummary(id=category.id, default_profile=category.default_profile)
